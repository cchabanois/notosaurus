package app.notosaurus

import app.notosaurus.LocalServer.Companion.MAX_PHOTOS
import io.ktor.server.routing.Route
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.intOrNull
import kotlinx.serialization.json.jsonPrimitive
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
            switches.check("lesson.regenerate")
            val old = lesson()
            val made = generation.make(form, onCard)
            lessons.regenerated(old.string("id"), made.content, made.photos) ?: notFound()
        }
        // Its next pages, days later: only they are read, the AI knowing the cards made already;
        // their cards come after the lesson's, which stay (so do their notes in AnkiDroid)
        making("/api/lessons/{id}/complete") { form, onCard ->
            switches.check("lesson.complete")
            val old = lesson()
            if (form.images.isEmpty()) throw BadRequest("extract.no_input")
            val count = old["photo_count"]?.jsonPrimitive?.intOrNull ?: 0
            if (count + form.images.size > MAX_PHOTOS) throw BadRequest("extract.too_many", buildJsonObject { put("max", MAX_PHOTOS) })
            val existing = old.cards().map { c ->
                c.string("front").trim() + c.string("subdeck").trim().let { if (it.isEmpty()) "" else " [$it]" }
            }
            // Its deck and voice are the lesson's: only the cards, photos and frames are taken
            val asked = GenerationForm(form.fields + mapOf("deck" to old.string("deck"), "voice" to ""), form.images, form.lang)
            val made = generation.make(asked, onCard, existing)
            lessons.completed(old.string("id"), made.content, made.photos) ?: notFound()
        }
        api("POST", "/api/lessons/{id}/revise") {
            val lesson = lesson()
            val req = body()
            val every = children.list()
            // The deck without the children's levels: no child's name to the AI (put back after)
            val (private, deck) = Children.splitDeck(req.string("deck"), every)
            val request = buildJsonObject {
                put("prompt", lesson.string("prompt"))
                put("deck", buildJsonObject { put("deck", deck); put("cards", req["cards"]!!) })
                put("instruction", req["instruction"]!!)
                put("language", languageName())
                put("instructions", generation.instructions(children.get(lesson.string("child"))))
            }
            val revised = relay().withPhotos("revise", request, lessons.photos(lesson.string("id")))
            val revisedDeck = listOf(private, revised.string("deck")).filter { it.isNotEmpty() }.joinToString("::")
            val changes = JsonObject(req + mapOf("deck" to JsonPrimitive(revisedDeck), "cards" to revised["cards"]!!))
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
                put("deck", Children.splitDeck(lesson.string("deck"), children.list()).second) // no child's name to the AI
                put("language", languageName())
                put("page_texts", lesson["page_texts"] ?: JsonArray(emptyList()))
                put("instructions", generation.instructions(children.get(lesson.string("child"))))
            }
            JsonObject(relay().post("explain", request) - "usage")
        }
        // Content the AI made, reported (Google Play's policy on generated content): what the
        // page showed the user and they sent, the lesson's instructions; no photo, no child's name
        api("POST", "/api/lessons/{id}/report") {
            val lesson = lesson()
            val req = body()
            val request = buildJsonObject {
                for (field in listOf("kind", "reason", "comment", "content", "picture")) req[field]?.let { put(field, it) }
                put("prompt", lesson.string("prompt"))
                put("language", languageName())
            }
            relay().post("report", request)
        }
    }
}
