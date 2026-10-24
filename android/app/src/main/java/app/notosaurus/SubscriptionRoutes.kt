package app.notosaurus

import app.notosaurus.LocalServer.Companion.keyOf
import io.ktor.server.routing.Route
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.put

/** The subscription (Google Play), in the app's settings: what is offered, subscribing,
 * restoring it on a new phone, Google Play's page to manage it. Every purchase is checked
 * by the relay (/v1/subscribe), which answers its licence key, kept as a typed key is. */
internal fun Route.subscriptionRoutes(server: LocalServer) {
    with(server) {
        // What is offered; without a key, a subscription this Google account has is restored
        api("GET", "/api/admin/subscription") {
            val store = subscriptions
            val offers = store?.let { withContext(Dispatchers.IO) { runCatching { it.offers() }.getOrNull() } }.orEmpty()
            var restored = false
            // No key yet, or a purchase paid later (pending when bought): the one this Google account has
            if (store != null && (licence().isEmpty() || prefs[PURCHASE_PENDING] == "1")) {
                val owned = withContext(Dispatchers.IO) { runCatching { store.owned() }.getOrDefault(emptyList()) }
                restored = owned.firstNotNullOfOrNull { token -> runCatching { licensed(token) }.getOrNull() } != null
                if (restored) prefs[PURCHASE_PENDING] = ""
            }
            buildJsonObject {
                put("offers", JsonArray(offers.map { buildJsonObject { put("plan", it.plan); put("price", it.price); put("trial_days", it.trialDays) } }))
                put("restored", restored)
                put("trial", store != null) // the free trial (no card), offered without a key
            }
        }
        // Google Play's purchase screen for a base plan, then the relay's licence for the purchase
        api("POST", "/api/admin/subscription/subscribe") {
            val store = subscriptions ?: throw BadRequest("subscription.unavailable")
            val plan = body().string("plan").takeIf { it in PlayStore.PLANS } ?: throw BadRequest("subscription.none")
            when (val bought = store.subscribe(plan)) {
                is Bought.Paid -> licensed(bought.token)
                // Paid later (some ways to pay): restored as the settings open once Google Play has it
                Bought.Pending -> buildJsonObject { put("pending", true) }.also { prefs[PURCHASE_PENDING] = "1" }
                Bought.GivenUp -> buildJsonObject { put("cancelled", true) }
            }
        }
        // A new phone, the app reinstalled: the subscription this Google account has
        api("POST", "/api/admin/subscription/restore") {
            val store = subscriptions ?: throw BadRequest("subscription.unavailable")
            val owned = withContext(Dispatchers.IO) { store.owned() }
            licensed(owned.firstOrNull() ?: throw BadRequest("subscription.none"))
        }
        api("POST", "/api/admin/subscription/manage") {
            subscriptions?.manage()
            buildJsonObject { put("opened", subscriptions != null) }
        }
    }
}

/** The purchase's licence key from the relay (it checks the purchase with Google Play),
 * kept for the relay in use; its account (the settings show it). */
internal suspend fun LocalServer.licensed(token: String): JsonObject {
    val answer = withContext(Dispatchers.IO) {
        Relay(relayUrl(), "").post("subscribe", buildJsonObject {
            put("purchase_token", token)
            put("product_id", PlayStore.PRODUCT)
        })
    }
    return keep(answer)
}

/** The free trial, no card, started at the first AI call without a key (LocalServer.trialKey):
 * once per phone (Play Integrity says it is the app from Google Play on a real one); the
 * relay answers its key, kept as a purchase's is; its account. */
internal suspend fun LocalServer.startTrial(store: SubscriptionStore): JsonObject {
    val device = store.device()
    val token = withContext(Dispatchers.IO) { store.integrity(device) } ?: throw BadRequest("relay.trial_refused")
    val request = buildJsonObject { put("integrity_token", token); put("device", device) }
    return keep(withContext(Dispatchers.IO) { Relay(relayUrl(), "").post("trial", request) })
}

/** The relay's licence key kept for the relay in use; its account. */
private fun LocalServer.keep(answer: JsonObject): JsonObject {
    prefs[keyOf(relayUrl())] = answer.string("key")
    return answer["account"]!!.jsonObject
}

/** A purchase Google Play said pending (paid later): the settings look for it until found. */
private const val PURCHASE_PENDING = "purchase_pending"
