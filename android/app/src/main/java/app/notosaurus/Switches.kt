package app.notosaurus

import kotlinx.serialization.builtins.ListSerializer
import kotlinx.serialization.builtins.serializer
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put

/**
 * What the relay tells the app for now (/v1/account, set on the relay: no app update): a
 * notice for every user, the features turned off while their fix waits for the store
 * (relay_api.FEATURES), the latest version. The last ones told are kept: offline, a
 * feature turned off stays off.
 */
class Switches(private val prefs: Preferences, private val version: String) {
    /** What the relay's account says now. */
    fun keep(account: Account) {
        prefs[DISABLED] = json.encodeToString(ListSerializer(String.serializer()), account.disabled)
        prefs[NOTICE] = account.notice?.let { json.encodeToString(Notice.serializer(), it) }.orEmpty()
        prefs[LATEST] = account.latest
    }

    fun disabled(): List<String> =
        runCatching { json.decodeFromString(ListSerializer(String.serializer()), prefs[DISABLED].orEmpty()) }.getOrDefault(emptyList())

    fun off(feature: String) = feature in disabled()

    /** Refused while turned off: the page says it is unavailable for now. */
    fun check(feature: String) {
        if (off(feature)) throw BadRequest("app.feature_off", buildJsonObject { put("feature", feature) })
    }

    /** The notice in the page's language (else English, else any); null: none. */
    fun notice(lang: String): JsonObject? {
        val notice = runCatching { json.decodeFromString(Notice.serializer(), prefs[NOTICE].orEmpty()) }.getOrNull() ?: return null
        val text = notice.texts[lang] ?: notice.texts["en"] ?: notice.texts.values.firstOrNull() ?: return null
        return buildJsonObject {
            put("id", notice.id)
            put("level", notice.level)
            put("text", text)
        }
    }

    /** A newer version is out (its store page then offered). */
    fun updateAvailable(): Boolean = newer(prefs[LATEST].orEmpty(), version)

    companion object {
        private const val DISABLED = "switches_disabled"
        private const val NOTICE = "switches_notice"
        private const val LATEST = "switches_latest"

        /** Whether `latest` ("1.10.0") is a newer version than `current` ("1.9.2"); never when either isn't one. */
        fun newer(latest: String, current: String): Boolean {
            fun parts(v: String): List<Int>? = v.trim().split(".").map { it.toIntOrNull() }.takeIf { null !in it }?.filterNotNull()
            val a = parts(latest) ?: return false
            val b = parts(current.substringBefore("-")) ?: return false
            for (i in 0 until maxOf(a.size, b.size)) {
                val (x, y) = a.getOrElse(i) { 0 } to b.getOrElse(i) { 0 }
                if (x != y) return x > y
            }
            return false
        }
    }
}
