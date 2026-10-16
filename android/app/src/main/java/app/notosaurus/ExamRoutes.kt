package app.notosaurus

import io.ktor.server.routing.Route
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put

/** The tests to prepare (Exams.kt): listed as the page shows them, saved, deleted; the
 * notes in AnkiDroid tagged to follow. */
internal fun Route.examRoutes(server: LocalServer) {
    with(server) {
        api("GET", "/api/exams") { JsonArray(exams.list().map(exams::view)) }
        api("PUT", "/api/exams/{id}") {
            val id = param("id")
            val asked = body()
            val parts = (asked["lessons"] as? JsonArray).orEmpty().map { json.decodeFromJsonElement(ExamLesson.serializer(), it) }
            val before = exams.get(id)
            val after = exams.save(id, asked.string("name"), asked.string("date"), parts)
            JsonObject(exams.view(after) + ("anki" to JsonPrimitive(retag(before, after))))
        }
        api("DELETE", "/api/exams/{id}") {
            val before = exams.get(param("id")) ?: throw BadRequest("exams.not_found")
            val ok = retag(before, null)
            exams.delete(before.id)
            buildJsonObject {
                put("deleted", true)
                put("anki", ok)
            }
        }
    }
}

/** AnkiDroid's notes made to follow the change; false when AnkiDroid couldn't (the tags of
 * the notes sent later come with them anyway: Media.extraTags). */
private suspend fun LocalServer.retag(before: Exam?, after: Exam?): Boolean {
    val (add, remove) = exams.retagging(before, after)
    if (add.isEmpty() && remove.isEmpty()) return true
    return withContext(Dispatchers.IO) { runCatching { anki.retag(add, remove) }.getOrDefault(false) }
}
