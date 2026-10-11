package app.notosaurus

import io.ktor.http.ContentType
import io.ktor.http.HttpStatusCode
import io.ktor.server.response.respondBytes
import io.ktor.server.response.respondText
import io.ktor.server.routing.Route
import io.ktor.server.routing.get
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.longOrNull
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.put

/** The lessons on the phone: listed, changed, deleted (in AnkiDroid too when asked), their photos, the decks. */
internal fun Route.lessonRoutes(server: LocalServer) {
    with(server) {
        // --- Lessons
        api("GET", "/api/lessons") { JsonArray(lessons.list().map(lessons::summary)) }
        api("GET", "/api/lessons/{id}") { lesson() }
        api("PUT", "/api/lessons/{id}") { lessons.update(param("id"), body()) ?: notFound() }
        // Deleting a lesson: its notes in AnkiDroid counted first; deleted too when asked (?anki=true)
        api("GET", "/api/lessons/{id}/anki-notes") {
            val found = withContext(Dispatchers.IO) { runCatching { anki.lessonNotes(lesson().string("id")) }.getOrNull() }
            buildJsonObject {
                put("available", found != null)
                put("count", found?.size ?: 0)
            }
        }
        // After a send: the lesson's notes no card has any more, deleted when asked; only those
        // (never a card's own note, nor another lesson's)
        api("POST", "/api/lessons/{id}/anki-notes/delete") {
            val lesson = lesson()
            val asked = body()["ids"]?.jsonArray?.mapNotNull { it.jsonPrimitive.longOrNull }.orEmpty().toSet()
            val kept = (lesson["anki_notes"] as? JsonObject)?.values?.mapNotNull { it.jsonPrimitive.longOrNull }.orEmpty().toSet()
            val deleted = withContext(Dispatchers.IO) {
                val allowed = anki.leftovers(lesson.string("id"), kept).map { it.id }.toSet()
                anki.delete((asked intersect allowed).toList())
            }
            buildJsonObject {
                put("deleted", deleted)
                put("synced", false)
            }
        }
        api("DELETE", "/api/lessons/{id}") {
            val id = lesson().string("id")
            var inAnki = 0
            if (call.request.queryParameters["anki"] == "true") {
                inAnki = withContext(Dispatchers.IO) {
                    val notes = runCatching { anki.lessonNotes(id) }.getOrNull() ?: throw BadRequest("anki.android_failed")
                    anki.delete(notes)
                }
            }
            lessons.delete(id)
            buildJsonObject {
                put("deleted", true)
                put("anki_deleted", inAnki)
                put("synced", false)
            }
        }
        // A photo turned a quarter turn clockwise (it came out sideways), its masks and frame with it
        api("POST", "/api/lessons/{id}/photos/{n}/rotate") {
            val lesson = lesson()
            val id = lesson.string("id")
            val n = param("n").toIntOrNull() ?: notFound()
            val photo = lessons.photo(id, n) ?: notFound()
            photo.writeBytes(turnPhoto(photo.readBytes(), 90))
            val cards = lesson.cards().map { Diagrams.turnedMask(it, n, 90) }
            val frames = (lesson["frames"] as? JsonArray)?.map { Diagrams.turnedFrame(it.jsonObject, n, 90) }.orEmpty()
            lessons.update(id, buildJsonObject { put("cards", JsonArray(cards)); put("frames", JsonArray(frames)) }) ?: notFound()
        }
        get("/api/lessons/{id}/photos/{n}") {
            if (!allowed()) return@get
            val photo = lessons.photo(param("id"), param("n").toInt())
            if (photo == null) call.respondText("", status = HttpStatusCode.NotFound)
            else call.respondBytes(photo.readBytes(), ContentType.Image.JPEG)
        }
        api("GET", "/api/decks") {
            val known = (lessons.list().map { it.string("deck") } + anki.deckNames()).filter { it.isNotBlank() }
            JsonArray(known.distinct().sorted().map(::JsonPrimitive))
        }
    }
}
