package app.notosaurus

import io.ktor.http.ContentType
import io.ktor.http.HttpStatusCode
import io.ktor.server.response.respondBytes
import io.ktor.server.response.respondText
import io.ktor.server.routing.Route
import io.ktor.server.routing.get
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put

/** The page's languages, and the relay's voices (🔊). */
internal fun Route.languageRoutes(server: LocalServer) {
    with(server) {
        api("GET", "/api/lang") {
            val codes = texts.codes()
            buildJsonObject {
                put("lang", JsonNull) // the page uses the phone's language
                put("available", JsonArray(codes.map(::JsonPrimitive)))
                put("names", JsonObject(codes.associateWith { JsonPrimitive(texts.get(it, "meta", "name") ?: it) }))
            }
        }
        api("GET", "/api/voices") {
            try {
                speech.voices()
            } catch (e: RelayException) {
                throw BadRequest("tts.voices_unavailable", buildJsonObject { put("detail", e.code) })
            }
        }
        // Listen to a text (🔊), read by the relay's voice
        get("/api/tts") {
            if (!allowed()) return@get
            val text = call.request.queryParameters["text"].orEmpty()
            val voice = call.request.queryParameters["voice"].orEmpty()
            val mp3 = runCatching { speech.read(text, voice) }.getOrNull()
            if (mp3 == null) call.respondText("", status = HttpStatusCode.BadGateway)
            else call.respondBytes(mp3.readBytes(), ContentType.Audio.MPEG)
        }
    }
}
