package app.notosaurus

import kotlinx.serialization.json.jsonObject
import okhttp3.OkHttpClient
import okhttp3.Request
import java.net.URI
import java.util.concurrent.TimeUnit

/**
 * Where the relays are: read from a small file the project publishes (docs/public/relay.json,
 * on GitHub Pages), not only the address built into the app. Moved (another Google Cloud
 * project, another host), the file says so and every installed app follows, with no update.
 *
 * Read when the app starts, and again when the relay can't be reached (the app started offline,
 * then online; a relay gone): the next try goes to where it is now. Unreachable or wrong: the
 * address known last, else the built-in one. A relay that moved keeps the user's choice of it
 * and their licence key (saved per relay, LocalServer.keyOf). Only https Cloud Run addresses
 * are taken: a relay on another host needs an app update adding it ([accepted]).
 */
class RelayDirectory(
    private val prefs: Preferences,
    private val url: String?, // the file's address; null: none (the tests)
    private val builtInReal: String = BuildConfig.REAL_RELAY,
    private val builtInTest: String = BuildConfig.TEST_RELAY, // "" in a release: no test relay
) {
    /** The real relay's address, as known last. */
    fun real(): String = prefs[KNOWN_REAL] ?: builtInReal

    /** The test relay's (a debug build's); "" in a release. */
    fun test(): String = if (builtInTest.isEmpty()) "" else prefs[KNOWN_TEST] ?: builtInTest

    @Volatile private var lastRead: Long? = null // when the file was last read (System.nanoTime)
    @Volatile private var reading = false

    /** The file read again (on the network: off the main thread); the relays that moved followed. */
    fun refresh() {
        val listed = runCatching { read() }.getOrNull() ?: return
        lastRead = System.nanoTime()
        listed["real"]?.let { move(KNOWN_REAL, real(), it) }
        if (builtInTest.isNotEmpty()) listed["test"]?.let { move(KNOWN_TEST, test(), it) }
    }

    /** The relay couldn't be reached: the file read again in the background, unless it was
     * read less than [AGAIN_AFTER_S] ago (not read, offline: tried again each time). */
    @Synchronized fun refreshSoon() {
        val last = lastRead
        if (url == null || reading || (last != null && System.nanoTime() - last < AGAIN_AFTER_S * 1_000_000_000L)) return
        reading = true
        Thread {
            try {
                refresh()
            } finally {
                reading = false
            }
        }.start()
    }

    private fun read(): Map<String, String>? {
        val request = Request.Builder().url(url ?: return null).build()
        client.newCall(request).execute().use { response ->
            if (!response.isSuccessful) return null
            val listed = json.parseToJsonElement(response.body.string()).jsonObject
            return listOf("real", "test").mapNotNull { role ->
                listed.string(role).trimEnd('/').takeIf(::accepted)?.let { role to it }
            }.toMap()
        }
    }

    private fun move(known: String, from: String, to: String) {
        if (to == from) return
        prefs[known] = to
        val key = prefs[LocalServer.keyOf(from)].orEmpty()
        if (key.isNotEmpty() && prefs[LocalServer.keyOf(to)].isNullOrEmpty()) prefs[LocalServer.keyOf(to)] = key
        if (prefs[LocalServer.RELAY] == from) prefs[LocalServer.RELAY] = to // the one chosen in the settings
    }

    companion object {
        const val URL = "https://cchabanois.github.io/notosaurus/relay.json"
        private const val AGAIN_AFTER_S = 30L
        private const val KNOWN_REAL = "relay_real"
        private const val KNOWN_TEST = "relay_test"
        private val CLOUD_RUN = Regex("""^[a-z0-9-]+\.[a-z0-9-]+\.run\.app$""")

        /** An address the file may give: https, on Cloud Run. */
        fun accepted(address: String): Boolean {
            val uri = runCatching { URI(address) }.getOrNull() ?: return false
            return uri.scheme == "https" && uri.host?.matches(CLOUD_RUN) == true && uri.port == -1 &&
                uri.path.orEmpty().isEmpty() && uri.query == null && uri.userInfo == null
        }

        private val client = OkHttpClient.Builder()
            .callTimeout(5, TimeUnit.SECONDS) // the app starts meanwhile, on the address known last
            .build()
    }
}
