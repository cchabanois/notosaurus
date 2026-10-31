package app.notosaurus

import io.ktor.server.routing.Route
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put

/** The page's 🎤. */
internal fun Route.dictationRoutes(server: LocalServer) {
    with(server) {
        // --- Dictation (🎤): recorded here, written by the relay's AI as the user meant to type it
        api("POST", "/api/dictation/start") {
            val dictation = dictation ?: notFound()
            switches.check("speech.transcribe")
            if (!requestMicPermission()) throw BadRequest("dictation.refused")
            dictation.start()
            buildJsonObject { put("listening", true) }
        }
        api("POST", "/api/dictation/stop") {
            val dictation = dictation ?: notFound()
            val kind = body().string("kind").takeIf { it in Dictation.KINDS } ?: "prompt"
            buildJsonObject { put("text", dictation.stop(kind, languageName())) }
        }
    }
}
