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
        api("GET", "/api/exams") {
            // Changes made while AnkiDroid couldn't follow: followed now, if it can
            for (id in exams.pending().keys) retag(id, null, exams.get(id))
            JsonArray(exams.list().map(exams::view))
        }
        api("PUT", "/api/exams/{id}") {
            val id = param("id")
            val asked = body()
            val parts = (asked["lessons"] as? JsonArray).orEmpty().map { json.decodeFromJsonElement(ExamLesson.serializer(), it) }
            val before = exams.get(id)
            val after = exams.save(id, asked.string("name"), asked.string("date"), parts)
            JsonObject(exams.view(after) + ("anki" to JsonPrimitive(retag(id, before, after))))
        }
        api("DELETE", "/api/exams/{id}") {
            val before = exams.get(param("id")) ?: throw BadRequest("exams.not_found")
            val ok = retag(before.id, before, null)
            exams.delete(before.id)
            buildJsonObject {
                put("deleted", true)
                put("anki", ok)
            }
        }
    }
}

/** AnkiDroid's notes made to follow the test's change; false when AnkiDroid couldn't: the
 * change then waits (Exams.pending), from the state AnkiDroid's notes still have (a test
 * renamed or deleted meanwhile: its old tag taken off then). */
private suspend fun LocalServer.retag(id: String, before: Exam?, after: Exam?): Boolean {
    val waiting = exams.pending()
    val from = if (waiting.containsKey(id)) waiting[id] else before
    val (add, remove) = exams.retagging(from, after)
    val done = add.isEmpty() && remove.isEmpty() ||
        withContext(Dispatchers.IO) { runCatching { anki.retag(add, remove) }.getOrDefault(false) }
    exams.setPending(id, from, done)
    return done
}
