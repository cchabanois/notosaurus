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
            if (store != null && licence().isEmpty()) {
                val owned = withContext(Dispatchers.IO) { runCatching { store.owned() }.getOrDefault(emptyList()) }
                restored = owned.firstNotNullOfOrNull { token -> runCatching { licensed(token) }.getOrNull() } != null
            }
            buildJsonObject {
                put("offers", JsonArray(offers.map { buildJsonObject { put("plan", it.plan); put("price", it.price); put("trial_days", it.trialDays) } }))
                put("restored", restored)
            }
        }
        // Google Play's purchase screen for a base plan, then the relay's licence for the purchase
        api("POST", "/api/admin/subscription/subscribe") {
            val store = subscriptions ?: throw BadRequest("subscription.unavailable")
            val plan = body().string("plan").takeIf { it in PlayStore.PLANS } ?: throw BadRequest("subscription.none")
            val token = store.subscribe(plan) ?: return@api buildJsonObject { put("cancelled", true) }
            licensed(token)
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
private suspend fun LocalServer.licensed(token: String): JsonObject {
    val answer = withContext(Dispatchers.IO) {
        Relay(relayUrl(), "").post("subscribe", buildJsonObject {
            put("purchase_token", token)
            put("product_id", PlayStore.PRODUCT)
        })
    }
    prefs[keyOf(relayUrl())] = answer.string("key")
    return answer["account"]!!.jsonObject
}
