package app.notosaurus

import io.ktor.http.ContentType
import io.ktor.http.HttpStatusCode
import io.ktor.http.content.PartData
import io.ktor.http.content.forEachPart
import io.ktor.server.request.receiveMultipart
import io.ktor.server.response.respondBytes
import io.ktor.server.response.respondText
import io.ktor.server.routing.Route
import io.ktor.server.routing.get
import io.ktor.server.routing.post
import io.ktor.utils.io.toByteArray
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.jsonPrimitive

/** The cards' pictures: drawn, found, the user's own, none; and served to the page. */
internal fun Route.pictureRoutes(server: LocalServer) {
    with(server) {
        // --- Pictures, through the relay (as app/main.py): drawn, the user's own, none
        api("POST", "/api/lessons/{id}/pictures") { pictures.drawMissing(lesson()) }
        // A card's picture drawn again: its subject (or figure), or the one the user wrote
        api("POST", "/api/lessons/{id}/cards/{card}/picture/draw") {
            val lesson = lesson()
            val subject = body()["subject"]?.takeIf { it !is JsonNull }?.jsonPrimitive?.content
            pictures.redraw(lesson, cardIndex(lesson), subject, languageName())
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
        // Free pictures of a subject to choose from (the relay: Commons, Openverse, Pixabay), then the one chosen
        api("POST", "/api/pictures/search") {
            val req = body()
            val subject = req.string("subject").trim().takeIf { it.isNotEmpty() } ?: throw BadRequest("picture.no_subject")
            relay().searchPictures(subject, req.string("context"), req.string("words"))
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
