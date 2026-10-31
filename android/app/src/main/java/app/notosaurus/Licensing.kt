package app.notosaurus

import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.put

/**
 * The licence of the relay in use, and how the app gets one: its key (each relay keeps its
 * own: the test one has its own licences), the free trial started by the first AI call, a
 * Google Play purchase checked by the relay (bought, restored, paid later), and checked
 * again when the relay says the subscription lapsed. `relayUrl`: the relay in use; `store`:
 * Google Play (none: a key typed in the settings only); `now`: nanoseconds, a clock.
 */
class Licensing(
    private val prefs: Preferences,
    private val relayUrl: () -> String,
    val store: SubscriptionStore?,
    private val now: () -> Long = System::nanoTime, // the tests move time on
) {
    /** The key for the relay in use; "" when there is none yet. */
    fun key(): String = prefs[LocalServer.keyOf(relayUrl())].orEmpty()

    fun setKey(key: String) {
        prefs[LocalServer.keyOf(relayUrl())] = key.trim()
    }

    /** The relay said this key is unknown or ended (one mistyped): no longer kept, unless
     * another took its place meanwhile. Without one, the settings offer subscribing again
     * and the next lesson starts the free trial. */
    @Synchronized fun forget(key: String) {
        if (key() == key.trim()) setKey("")
    }

    // --- The free trial

    private val trialStarting = Mutex()

    /** The free trial's account, just started: told once to the page (/api/switches). */
    @Volatile private var trialStarted: JsonObject? = null

    fun takeTrialStarted(): JsonObject? = trialStarted.also { trialStarted = null }

    /**
     * No key yet, an AI call (the first lesson): the free trial started without a word
     * (Google Play missing: none, the relay then says a key is needed). Once, however many
     * calls come at the same time (a lesson's pictures).
     */
    suspend fun trialKey(): String = trialStarting.withLock {
        key().ifEmpty {
            val store = store ?: return@withLock ""
            trialStarted = startTrial(store)
            key()
        }
    }

    /** Once per phone (Play Integrity says it is the app from Google Play on a real one): the
     * relay answers its key, kept as a purchase's is; its account. */
    private suspend fun startTrial(store: SubscriptionStore): JsonObject {
        val device = store.device()
        val token = withContext(Dispatchers.IO) { store.integrity(device) } ?: throw BadRequest("relay.trial_refused")
        val request = buildJsonObject { put("integrity_token", token); put("device", device) }
        return keep(withContext(Dispatchers.IO) { Relay(relayUrl(), "").post("trial", request) })
    }

    // --- Google Play's purchases

    /** The purchase's licence key from the relay (it checks the purchase with Google Play),
     * kept for the relay in use; its account (the settings show it). */
    suspend fun licensed(token: String): JsonObject {
        val answer = withContext(Dispatchers.IO) {
            Relay(relayUrl(), "").post("subscribe", buildJsonObject {
                put("purchase_token", token)
                put("product_id", PlayStore.PRODUCT)
            })
        }
        return keep(answer)
    }

    /** A purchase Google Play said pending (paid later): the settings look for it until found,
     * for PENDING_DAYS at most (Google Play cancels one not paid by then: not asked forever). */
    var purchasePending: Boolean
        get() {
            val since = prefs[PURCHASE_PENDING]?.toLongOrNull() ?: return false
            return System.currentTimeMillis() - since < PENDING_DAYS * 86_400_000L
        }
        set(value) {
            prefs[PURCHASE_PENDING] = if (value) System.currentTimeMillis().toString() else ""
        }

    /** Google Play's purchases of this Google account checked by the relay: the first it
     * gives access to, its key kept; false if none does (or no Google Play). */
    suspend fun recheck(): Boolean = withContext(Dispatchers.IO) {
        val owned = store?.let { runCatching { it.owned() }.getOrNull() }.orEmpty()
        owned.any { token -> runCatching { licensed(token) }.isSuccess }
    }

    private var recheckedAt: Long? = null

    // Work in the background (a subscription checked again): stopped with the server
    private val background = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    /**
     * The relay said the subscription ended or is on hold: Google Play's purchases checked
     * again in the background, at most every RECHECK_S (a renewal, or a payment fixed,
     * whose notification never reached the relay: the next call has the new period).
     */
    @Synchronized fun recheckSoon() {
        if (store == null) return
        val last = recheckedAt
        if (last != null && now() - last < RECHECK_S * 1_000_000_000L) return
        recheckedAt = now()
        background.launch { recheck() }
    }

    fun stop() = background.cancel()

    /** The relay's licence key kept for the relay in use; its account. */
    private fun keep(answer: JsonObject): JsonObject {
        setKey(answer.string("key"))
        return answer["account"]!!.jsonObject
    }

    companion object {
        // The subscription's purchases checked again at most this often when the relay says it lapsed
        private const val RECHECK_S = 600L
        private const val PURCHASE_PENDING = "purchase_pending" // since when (ms)
        private const val PENDING_DAYS = 7L
    }
}
