package app.notosaurus

import io.ktor.server.routing.Route
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import java.util.Locale

/** The page's 🎤. */
internal fun Route.dictationRoutes(server: LocalServer) {
    with(server) {
        // --- Dictation (🎤): heard by the phone's speech recognition, the text shown as it comes
        // (Dictation.live); without one, recorded here and written by the relay's AI
        api("POST", "/api/dictation/start") {
            val dictation = dictation ?: notFound()
            val live = dictation.live
            if (!live) switches.check("speech.transcribe") // the relay's AI: turned off for now
            if (!requestMicPermission()) throw BadRequest("dictation.refused")
            if (live) dictation.listen(spokenLanguage(lang())) else dictation.start()
            buildJsonObject {
                put("listening", true)
                put("live", live)
            }
        }
        // Heard so far (live): the page shows it in the field as it comes
        api("GET", "/api/dictation/heard") {
            val (text, failure) = (dictation ?: notFound()).heard()
            buildJsonObject {
                put("text", text)
                failure?.let { put("error", it) }
            }
        }
        api("POST", "/api/dictation/stop") {
            val dictation = dictation ?: notFound()
            if (dictation.live && dictation.listeningLive) return@api buildJsonObject { put("text", dictation.stopListening()) }
            val kind = body().string("kind").takeIf { it in Dictation.KINDS } ?: "prompt"
            buildJsonObject { put("text", dictation.stop(kind, languageName())) }
        }
    }
}

/** The language the user speaks to the 🎤: the page's, as the phone says it when it is the
 * phone's own ("fr-CA" for French in Quebec), else the page's alone ("fr"). */
internal fun spokenLanguage(page: String, phone: Locale = Locale.getDefault()): String =
    if (phone.language == page) phone.toLanguageTag() else page
