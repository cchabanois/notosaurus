package app.notosaurus

import io.ktor.http.ContentType
import io.ktor.http.HttpHeaders
import io.ktor.server.response.header
import io.ktor.server.response.respondText
import io.ktor.server.routing.Route
import io.ktor.server.routing.get
import kotlinx.serialization.builtins.MapSerializer
import kotlinx.serialization.builtins.serializer
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.jsonPrimitive

/**
 * What the page keeps on this phone (static/i18n.js's kept/keep): the child chosen, the
 * language, the last prompt, quick or careful, the notice closed, the subjects opened. In
 * the app's preferences, not the WebView's localStorage: that one goes with the page's
 * address (its port, another at each launch) and with the WebView's data.
 */
class Saved(private val prefs: Preferences) {
    private val map = MapSerializer(String.serializer(), String.serializer())

    fun all(): Map<String, String> = runCatching { json.decodeFromString(map, prefs[KEY].orEmpty()) }.getOrDefault(emptyMap())

    /** Each key its value, or removed (null). Only the page's own keys ("notosaurus.…"), sizes bounded. */
    @Synchronized
    fun change(changes: Map<String, String?>) {
        val all = all().toMutableMap()
        for ((key, value) in changes) {
            if (!key.startsWith(PREFIX) || key.length > MAX_KEY) continue
            if (value == null) all.remove(key)
            else if (value.length <= MAX_VALUE && (key in all || all.size < MAX_KEYS)) all[key] = value
        }
        prefs[KEY] = json.encodeToString(map, all)
    }

    companion object {
        const val KEY = "page_saved"
        const val PREFIX = "notosaurus."
        const val MAX_KEY = 100
        const val MAX_VALUE = 20_000 // the subjects opened: a few hundred characters
        const val MAX_KEYS = 50
    }
}

internal fun Route.savedRoutes(server: LocalServer) {
    with(server) {
        // Read before the page's scripts, as its localStorage was (the computer's static/saved.js: null, its localStorage)
        get("/saved.js") {
            if (!allowed()) return@get
            call.response.header(HttpHeaders.CacheControl, "no-store")
            val kept = JsonObject(saved.all().mapValues { JsonPrimitive(it.value) })
            call.respondText("window.SAVED = $kept;\n", ContentType.Text.JavaScript)
        }
        api("PUT", "/api/saved") {
            saved.change(body().mapValues { (_, value) -> value.takeUnless { it is JsonNull }?.jsonPrimitive?.content })
            JsonObject(emptyMap())
        }
    }
}
