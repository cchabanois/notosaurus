package app.notosaurus

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.put
import okhttp3.OkHttpClient
import okhttp3.Request
import java.net.URI
import java.util.concurrent.TimeUnit

/** "With my computer": the Anki add-on's Notosaurus, connected to by its QR code (or its
 * address), checked, kept in the settings, the app switched to it. */
class Computer(private val prefs: Preferences, private val modeChanged: () -> Unit) {
    /** Connected to `raw` (the QR code's address, or one typed): where to go. */
    suspend fun connect(raw: String): JsonObject {
        val url = url(raw) ?: throw BadRequest("computer.not_a_qr")
        if (!isNotosaurus(url)) throw BadRequest("computer.not_found")
        prefs[LocalServer.COMPUTER] = url.toString()
        prefs[LocalServer.COMPUTER_NAME] = name(url).orEmpty()
        prefs[LocalServer.MODE] = LocalServer.COMPUTER_MODE
        modeChanged()
        return buildJsonObject { put("url", url.toString()) }
    }

    /** The computer's name, which its /api/config gives a paired phone (the QR code's
     * token pairs it); null from an add-on older than that, or without a token. */
    private suspend fun name(url: URI): String? = withContext(Dispatchers.IO) {
        val request = Request.Builder().url("${origin(url)}/api/config?${url.rawQuery.orEmpty()}").build()
        runCatching {
            client.newCall(request).execute().use {
                if (it.isSuccessful) json.parseToJsonElement(it.body.string()).jsonObject.string("computer_name") else null
            }
        }.getOrNull()?.takeIf { it.isNotBlank() }
    }

    /** Notosaurus answers there: its /api/lang, which a phone not paired yet may read. */
    private suspend fun isNotosaurus(url: URI): Boolean = withContext(Dispatchers.IO) {
        val request = Request.Builder().url("${origin(url)}/api/lang").build()
        runCatching { client.newCall(request).execute().use { it.isSuccessful && "\"available\"" in it.body.string() } }
            .getOrDefault(false)
    }

    companion object {
        private val client = OkHttpClient.Builder()
            .connectTimeout(3, TimeUnit.SECONDS)
            .readTimeout(5, TimeUnit.SECONDS)
            .build()

        /** The computer's Notosaurus address, from its QR code or as typed ("192.168.1.10:8000"):
         * http(s), a host; null when it isn't one. */
        fun url(raw: String): URI? {
            val text = raw.trim().let { if ("://" in it) it else "http://$it" }
            val url = runCatching { URI(text) }.getOrNull() ?: return null
            if (url.scheme !in setOf("http", "https") || url.host.isNullOrEmpty()) return null
            return if (url.path.isNullOrEmpty()) URI(url.scheme, url.userInfo, url.host, url.port, "/", url.query, null) else url
        }

        fun origin(url: URI) = "${url.scheme}://${url.host}${if (url.port > 0) ":${url.port}" else ""}"
    }
}
