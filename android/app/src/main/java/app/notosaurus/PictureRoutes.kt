package app.notosaurus

import io.ktor.http.ContentType
import io.ktor.http.HttpHeaders
import io.ktor.http.HttpStatusCode
import io.ktor.http.content.PartData
import io.ktor.http.content.forEachPart
import io.ktor.server.request.receiveMultipart
import io.ktor.server.response.respondBytes
import io.ktor.server.response.respondText
import io.ktor.server.response.respondTextWriter
import io.ktor.server.routing.Route
import io.ktor.server.routing.get
import io.ktor.server.routing.post
import io.ktor.utils.io.toByteArray
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put

/** The cards' pictures: drawn, found, the user's own, none; and served to the page. */
internal fun Route.pictureRoutes(server: LocalServer) {
    with(server) {
        // --- Pictures, through the relay (as app/main.py): drawn, the user's own, none
        // The pictures the cards ask for: figures, free pictures; drawn by the image model only
        // when asked ("draw": the user said yes), else listed in "to_draw"
        // Asked as Relay.STREAM_TYPE: each card's steps as they begin, then the answer
        stepping("/api/lessons/{id}/pictures") { req, step ->
            val draw = req["draw"]?.jsonPrimitive?.booleanOrNull == true
            if (draw) switches.check("pictures.draw")
            pictures.drawMissing(lesson(), draw, step)
        }
        // "✨ Image", its first step: a figure drawn, or a picture decided (the page then looks
        // for free ones, and asks before one is drawn)
        // Asked as Relay.STREAM_TYPE (both): its steps ({"step": {…}}) as they begin, then the answer
        stepping("/api/lessons/{id}/cards/{card}/picture/make") { req, step ->
            val lesson = lesson()
            val subject = req["subject"]?.takeIf { it !is JsonNull }?.jsonPrimitive?.content
            pictures.make(lesson, cardIndex(lesson), subject, languageName()) { step(buildJsonObject { put("step", it) }) }
        }
        // The user said yes: drawn by the image model (it costs); a figure drawn again, told what
        // its check found ("problem"), with the model's thinking when "careful"
        stepping("/api/lessons/{id}/cards/{card}/picture/draw") { req, step ->
            val lesson = lesson()
            val i = cardIndex(lesson)
            if (lesson.cards()[i].string("figure").isBlank()) switches.check("pictures.draw")
            val problem = req["problem"]?.takeIf { it !is JsonNull }?.jsonPrimitive?.content.orEmpty()
            val careful = req["careful"]?.jsonPrimitive?.booleanOrNull == true && !switches.off("ai.careful")
            pictures.draw(lesson, i, problem, careful) { step(buildJsonObject { put("step", it) }) }
        }
        // "🔍 Check": the card's figure looked at by the AI, nothing changed ({"ok", "problem"})
        stepping("/api/lessons/{id}/cards/{card}/picture/check") { _, _ ->
            switches.check("figures.check")
            val lesson = lesson()
            pictures.check(lesson, cardIndex(lesson))
        }
        // The user's own photo as the card's picture (the page made it card size)
        post("/api/lessons/{id}/cards/{card}/picture") {
            if (!allowed()) return@post
            val (status, answer) = try {
                val lesson = lesson()
                val i = cardIndex(lesson)
                var photo: ByteArray? = null
                call.receiveMultipart(formFieldLimit = 20L * 1024 * 1024).forEachPart { part ->
                    if (part is PartData.FileItem && part.name == "photo") photo = part.provider().toByteArray()
                    part.dispose()
                }
                HttpStatusCode.Created to pictures.own(lesson, i, photo ?: throw BadRequest("extract.no_input"))
            } catch (e: Exception) {
                failure(e) ?: throw e
            }
            call.respondText(answer.toString(), ContentType.Application.Json, status)
        }
        // Free pictures of a subject to choose from (the relay: Commons, Openverse, Pixabay), the AI
        // keeping those that show it; asked as Relay.STREAM_TYPE, each source's as it answers (as
        // app/routes/pictures.py): {"found"} lines, then {"done"} or {"error"}. Then the one chosen.
        post("/api/pictures/search") {
            if (!allowed()) return@post
            val req = body()
            val subject = req.string("subject").trim()
            suspend fun search(onFound: suspend (JsonArray) -> Unit): JsonObject {
                switches.check("pictures.search")
                if (subject.isEmpty()) throw BadRequest("picture.no_subject")
                return relay().searchPictures(subject, req.string("context"), req.string("words"), onFound)
            }
            if (call.request.headers[HttpHeaders.Accept]?.contains(Relay.STREAM_TYPE) != true) {
                val (status, answer) = try {
                    val found = mutableListOf<JsonElement>()
                    val words = search { found.addAll(it) }.string("words")
                    HttpStatusCode.OK to buildJsonObject {
                        put("results", JsonArray(found))
                        put("words", words)
                    }
                } catch (e: Exception) {
                    failure(e) ?: throw e
                }
                call.respondText(answer.toString(), ContentType.Application.Json, status)
                return@post
            }
            call.respondTextWriter(ContentType.parse(Relay.STREAM_TYPE)) {
                val writer = this
                suspend fun line(item: JsonObject) = withContext(Dispatchers.IO) {
                    writer.write("$item\n")
                    writer.flush()
                }
                val last = try {
                    val words = search { line(buildJsonObject { put("found", it) }) }.string("words")
                    buildJsonObject { put("done", buildJsonObject { put("words", words) }) }
                } catch (e: Exception) {
                    val (_, answer) = failure(e) ?: throw e
                    buildJsonObject { put("error", answer["detail"]!!) }
                }
                line(last)
            }
        }
        api("POST", "/api/lessons/{id}/cards/{card}/picture/found") {
            val lesson = lesson()
            val i = cardIndex(lesson)
            val req = body()
            val found = relay().foundPicture(req.string("source"), req.string("id"))
            pictures.own(lesson, i, found.jpeg, found.source)
        }
        // No picture on the card any more: a text card
        api("DELETE", "/api/lessons/{id}/cards/{card}/picture") {
            val lesson = lesson()
            pictures.remove(lesson, cardIndex(lesson))
        }
        get("/api/lessons/{id}/pictures/{name}") {
            if (!allowed()) return@get
            val name = param("name")
            val file = pictures.file(param("id"), name)
            when {
                file == null -> call.respondText("", status = HttpStatusCode.NotFound)
                name.endsWith(".svg") -> {
                    // Cleaned by the relay; and even opened on its own, nothing in it may run or load
                    call.response.headers.append("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'")
                    call.response.headers.append("X-Content-Type-Options", "nosniff")
                    call.respondBytes(file.readBytes(), ContentType.Image.SVG)
                }
                else -> call.respondBytes(file.readBytes(), ContentType.Image.JPEG)
            }
        }
    }
}
