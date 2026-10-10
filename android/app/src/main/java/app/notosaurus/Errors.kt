package app.notosaurus

import io.ktor.http.HttpStatusCode
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put

/** The local server's errors, answered as the page expects them ({"detail": {code, params}}). */
internal class NotFound : Exception()

/** "Cancel" stopped the lesson being made. */
internal class Cancelled : Exception()

internal class BadRequest(val code: String, val params: JsonObject = JsonObject(emptyMap())) : Exception(code)

internal fun notFound(): Nothing = throw NotFound()

/** The answer to an error the page translates; null: not one of ours. */
internal fun failure(e: Exception): Pair<HttpStatusCode, JsonObject>? = when (e) {
    is NotFound -> HttpStatusCode.NotFound to error("lesson.not_found", JsonObject(emptyMap()))
    is RelayException -> HttpStatusCode.BadGateway to error(e.code, e.params)
    is BadRequest -> HttpStatusCode.BadRequest to error(e.code, e.params)
    is Cancelled -> HttpStatusCode.Conflict to error("extract.cancelled", JsonObject(emptyMap()))
    else -> null
}

internal fun error(code: String, params: JsonObject) = buildJsonObject {
    put("detail", buildJsonObject { put("code", code); put("params", params) })
}
