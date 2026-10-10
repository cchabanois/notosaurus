package app.notosaurus

import io.ktor.server.routing.Route
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put

/** The AI, through the relay: a lesson made (again), revised, a card explained. */
internal fun Route.generationRoutes(server: LocalServer) {
    with(server) {
        // --- The AI, through the relay
        making("/api/extract") { form, onCard ->
            val made = generation.make(form, onCard)
            lessons.create(made.content, made.photos)
        }
        // "Cancel" while waiting: the relay call stops, no lesson is saved
        api("POST", "/api/generations/{job}/cancel") {
            buildJsonObject { put("cancelled", generation.cancel(param("job"))) }
        }
        // Generated again in its place (another prompt, photos, or carefully this time)
        making("/api/lessons/{id}/regenerate") { form, onCard ->
            val old = lesson()
            val made = generation.make(form, onCard)
            lessons.regenerated(old.string("id"), made.content, made.photos) ?: notFound()
        }
        api("POST", "/api/lessons/{id}/revise") {
            val lesson = lesson()
            val req = body()
            val request = buildJsonObject {
                put("prompt", lesson.string("prompt"))
                put("deck", buildJsonObject { put("deck", req["deck"]!!); put("cards", req["cards"]!!) })
                put("instruction", req["instruction"]!!)
                put("language", languageName())
                put("instructions", generation.instructions())
            }
            val revised = relay().withPhotos("revise", request, lessons.photos(lesson.string("id")))
            val changes = JsonObject(req + mapOf("deck" to revised["deck"]!!, "cards" to revised["cards"]!!))
            buildJsonObject {
                put("lesson", lessons.update(lesson.string("id"), changes)!!)
                put("summary", revised["summary"]!!)
            }
        }
        api("POST", "/api/lessons/{id}/explain") {
            val lesson = lesson()
            val req = body()
            val request = buildJsonObject {
                put("card", req["card"]!!)
                put("kind", req["kind"] ?: JsonPrimitive("explain"))
                put("prompt", lesson.string("prompt"))
                put("deck", lesson.string("deck"))
                put("language", languageName())
                put("page_texts", lesson["page_texts"] ?: JsonArray(emptyList()))
                put("instructions", generation.instructions())
            }
            JsonObject(relay().post("explain", request) - "usage")
        }
    }
}
