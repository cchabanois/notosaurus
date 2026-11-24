package app.notosaurus

import io.ktor.http.ContentType
import io.ktor.http.HttpHeaders
import io.ktor.http.HttpStatusCode
import io.ktor.http.content.PartData
import io.ktor.server.response.respondBytes
import io.ktor.server.response.respondText
import io.ktor.server.response.respondTextWriter
import io.ktor.server.routing.Route
import io.ktor.server.routing.get
import io.ktor.server.routing.post
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.SerializationException
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.contentOrNull
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
            // The cards whose picture a correction replaced: not the lesson's drawing again; a
            // figure drawn again from the one it had ("previous": by card id, {"source", "kind"})
            val notFromLesson = (req["not_from_lesson"] as? JsonArray).orEmpty().mapNotNull { (it as? JsonPrimitive)?.contentOrNull }.toSet()
            val previous = (req["previous"] as? JsonObject).orEmpty().mapNotNull { (card, was) -> (was as? JsonObject)?.let { card to it } }.toMap()
            pictures.drawMissing(lesson(), draw, step, notFromLesson, previous)
        }
        // "✨ Image", its first step: a figure drawn, or a picture decided (the page then looks
        // for free ones, and asks before one is drawn); "previous": the figure a correction replaced
        // ({"source", "kind"}), drawn again from it
        // Asked as Relay.STREAM_TYPE (both): its steps ({"step": {…}}) as they begin, then the answer
        stepping("/api/lessons/{id}/cards/{card}/picture/make") { req, step ->
            val lesson = lesson()
            val subject = req["subject"]?.takeIf { it !is JsonNull }?.jsonPrimitive?.content
            val replaced = req["previous"] as? JsonObject
            pictures.make(lesson, cardIndex(lesson), subject, languageName(), replaced) { step(buildJsonObject { put("step", it) }) }
        }
        // The user said yes: drawn by the image model (it costs); a figure drawn again, told what
        // its check found ("problem"), with the model's thinking when "careful", from what it was
        // drawn from (its kept sources); "decided": a picture "make" decided for a figure, drawn now
        stepping("/api/lessons/{id}/cards/{card}/picture/draw") { req, step ->
            val lesson = lesson()
            val i = cardIndex(lesson)
            val decided = decidedPicture(req["decided"])
            if (decided != null || lesson.cards()[i].string("figure").isBlank()) switches.check("pictures.draw")
            val problem = req["problem"]?.takeIf { it !is JsonNull }?.jsonPrimitive?.content.orEmpty()
            val careful = req["careful"]?.jsonPrimitive?.booleanOrNull == true && !switches.off("ai.careful")
            pictures.draw(lesson, i, problem, careful, decided) { step(buildJsonObject { put("step", it) }) }
        }
        // "🔍 Check": the card's figure looked at by the AI, nothing changed ({"ok", "problem"})
        stepping("/api/lessons/{id}/cards/{card}/picture/check") { _, _ ->
            switches.check("figures.check")
            val lesson = lesson()
            pictures.check(lesson, cardIndex(lesson))
        }
        // The user's own photo as the card's picture (the page made it card size); "decided" (JSON):
        // a picture "make" decided for its figure, the card's now
        post("/api/lessons/{id}/cards/{card}/picture") {
            if (!allowed()) return@post
            val (status, answer) = try {
                val lesson = lesson()
                val i = cardIndex(lesson)
                var photo: ByteArray? = null
                var decided: String? = null
                eachPart { part ->
                    if (part is PartData.FileItem && part.name == "photo") {
                        // Of a kind a card shows, as the computer's (IMAGE_TYPES): checked before it is read, then its bytes
                        val type = part.contentType?.withoutParameters()?.toString()
                        val refused = BadRequest("extract.bad_format", buildJsonObject { put("format", type) })
                        if (type !in LocalServer.IMAGE_TYPES) throw refused
                        photo = LocalServer.readPhoto(part.provider()).also { if (!LocalServer.isImage(it)) throw refused }
                    }
                    if (part is PartData.FormItem && part.name == "decided") decided = part.value
                }
                val chosen = decided?.let(::decidedField) // once the whole request is read
                HttpStatusCode.Created to pictures.own(lesson, i, photo ?: throw BadRequest("extract.no_input"), decided = chosen)
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
                // A card has no length limit: a longer one cut to what a card is sent as (Pictures.cut), never refused
                return relay().searchPictures(subject, Pictures.cut(req.string("context")), req.string("words"), onFound)
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
            val decided = decidedPicture(req["decided"]) // before the relay is asked for it
            val found = relay().foundPicture(req.string("source"), req.string("id"))
            pictures.own(lesson, i, found.jpeg, found.source, decided)
        }
        // The pictures no card uses any more removed (drawn again, replaced, removed: kept until
        // then, so that the page can undo a card's correction while it is edited): asked by the
        // page once no card is edited, and when the lesson opens ({"removed": n})
        api("POST", "/api/lessons/{id}/pictures/prune") {
            buildJsonObject { put("removed", pictures.prune(lesson())) }
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
                    call.response.headers.append("Content-Security-Policy", PICTURE_POLICY)
                    call.response.headers.append("X-Content-Type-Options", "nosniff")
                    call.respondBytes(file.readBytes(), ContentType.Image.SVG)
                }
                else -> call.respondBytes(file.readBytes(), ContentType.Image.JPEG)
            }
        }
    }
}

/** A form's "decided" field (a picture "make" decided for a card's figure, as JSON): as
 * [decidedPicture]; not JSON, a request that isn't valid. */
internal fun decidedField(value: String): JsonObject =
    try {
        Json.parseToJsonElement(value) as? JsonObject
    } catch (e: SerializationException) {
        null
    }?.let(::decidedPicture) ?: throw BadRequest("invalid") // errors.invalid

/** A picture "make" decided for a card's figure ("decided", sent back with the picture chosen),
 * checked as the computer's DecidedPicture (app/models.py): a picture_prompt not empty, a
 * picture_search ("" when not said), each at most MAX_SUBJECT characters, picture_on_back (false
 * when not said), those three only. Null when not sent; anything else, a request that isn't
 * valid (400 errors.invalid), never a figure cleared for an empty picture. */
internal fun decidedPicture(value: JsonElement?): JsonObject? {
    if (value == null || value is JsonNull) return null
    val decided = value as? JsonObject ?: throw BadRequest("invalid")
    fun text(field: String, least: Int): String {
        val given = decided[field]
        val text = if (given == null) "" else (given as? JsonPrimitive)?.takeIf { it.isString }?.content ?: throw BadRequest("invalid")
        if (text.codePointCount(0, text.length) !in least..MAX_SUBJECT) throw BadRequest("invalid")
        return text
    }
    val onBack = decided["picture_on_back"]?.let { given ->
        (given as? JsonPrimitive)?.takeIf { !it.isString }?.booleanOrNull ?: throw BadRequest("invalid")
    } ?: false
    return buildJsonObject {
        put("picture_prompt", text("picture_prompt", 1))
        put("picture_search", text("picture_search", 0))
        put("picture_on_back", onBack)
    }
}

// A card's figure, served: nothing in it may run or load (the computer's app/origins.py, PICTURE_POLICY)
internal const val PICTURE_POLICY = "default-src 'none'; style-src 'unsafe-inline'"

// A picture's subject, a figure's description, at most (core's relay_api.MAX_SUBJECT)
internal const val MAX_SUBJECT = 1000
