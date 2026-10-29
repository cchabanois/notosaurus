package app.notosaurus

import io.ktor.server.routing.Route
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put

/** The prompts, and "✨ Tidy up" for the instructions being written. */
internal fun Route.promptRoutes(server: LocalServer) {
    with(server) {
        // --- Prompts: Notosaurus's (from the page's languages), then the user's
        api("GET", "/api/prompts") { JsonArray(prompts.all(lang())) }
        api("POST", "/api/prompts") { prompts.save(null, body()) }
        api("PUT", "/api/prompts/{id}") { prompts.save(param("id").toIntOrNull() ?: notFound(), body()) }
        api("DELETE", "/api/prompts/{id}") {
            prompts.delete(param("id"))
            JsonNull
        }
        api("POST", "/api/prompts/{id}/duplicate") { prompts.duplicate(lang(), param("id")) }
        // "✨ Tidy up" the instructions being written, by the relay's AI
        api("POST", "/api/prompt/rephrase") {
            val text = body().string("text").trim().takeIf { it.isNotEmpty() } ?: throw BadRequest("extract.no_input")
            val request = buildJsonObject {
                put("text", text)
                put("language", languageName())
            }
            buildJsonObject { put("text", relay().post("rephrase", request).string("text")) }
        }
    }
}
