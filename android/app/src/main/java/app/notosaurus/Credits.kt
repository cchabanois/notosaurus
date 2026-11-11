package app.notosaurus

import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.withTimeoutOrNull
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.jsonArray

/**
 * What the figures are drawn with (Typst, its packages, the maps' data), each with its licence
 * and its page: the licences page lists them, a figure's credit links to them. The relay's
 * (/v1/credits), as it draws them: a package added there is credited without a new app.
 * The relay unreachable, or too old to say: the last it said, else the list shipped with the
 * page (web/figure-credits.json, core's at the app's build).
 */
class Credits(
    private val prefs: Preferences,
    private val relay: () -> Relay,
    private val shipped: () -> ByteArray?,
) {
    suspend fun list(): JsonArray {
        val told = try {
            withTimeoutOrNull(WAIT_MS) { relay().credits() }?.takeIf { it.isNotEmpty() }
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) { // the relay unreachable, or one without the route
            null
        }
        if (told != null) {
            prefs[KEPT] = told.toString()
            return told
        }
        fun parsed(text: String?) = text?.let { runCatching { json.parseToJsonElement(it).jsonArray }.getOrNull() }
        return parsed(prefs[KEPT]) ?: parsed(shipped()?.decodeToString()) ?: JsonArray(emptyList())
    }

    companion object {
        const val KEPT = "credits" // the relay's last list
        const val WAIT_MS = 4_000L // the licences page waits no longer for the relay
    }
}
