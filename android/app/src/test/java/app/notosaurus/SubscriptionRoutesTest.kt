package app.notosaurus

import io.ktor.client.HttpClient
import io.ktor.client.request.HttpRequestBuilder
import io.ktor.client.request.delete
import io.ktor.client.request.forms.formData
import io.ktor.client.request.forms.submitFormWithBinaryData
import io.ktor.client.request.get
import io.ktor.client.request.header
import io.ktor.client.request.post
import io.ktor.client.request.put
import io.ktor.client.request.setBody
import io.ktor.client.statement.HttpResponse
import io.ktor.client.statement.bodyAsBytes
import io.ktor.client.statement.bodyAsText
import io.ktor.http.ContentType
import io.ktor.http.Headers
import io.ktor.http.HttpHeaders
import io.ktor.http.HttpMethod
import io.ktor.http.HttpStatusCode
import io.ktor.http.contentType
import io.ktor.http.encodeURLParameter
import io.ktor.server.testing.ApplicationTestBuilder
import io.ktor.server.testing.testApplication
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import kotlinx.serialization.json.boolean
import kotlinx.serialization.json.int
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.long
import mockwebserver3.MockResponse
import mockwebserver3.MockWebServer
import mockwebserver3.RecordedRequest
import org.junit.After
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.File
import java.util.Base64
import java.util.concurrent.TimeUnit

/** The local server: SubscriptionRoutes.kt's routes. */
class SubscriptionRoutesTest : LocalServerTestBase() {
    @Test
    fun aSubscriptionBoughtThenRestored() = app { client ->
        val offered = client.get("/api/admin/subscription") { page() }.json().jsonObject
        val offers = offered["offers"]!!.jsonArray.map { it.jsonObject }
        assertEquals(listOf("monthly" to "3,99 €", "yearly" to "29,99 €"), offers.map { it.string("plan") to it.string("price") })
        assertEquals(7, offers[1]["trial_days"]!!.jsonPrimitive.int)

        // Bought: the relay checks the purchase and answers its key, kept for this relay
        relayAnswers("""{"key": "nts_from_play", "account": {"plan": "trial", "credits_left": 1000, "daily_left": 300,
            "renews_at": "2026-10-18T10:00:00+00:00", "ends_at": "2026-10-18T10:00:00+00:00"}}""")
        val bought = client.post("/api/admin/subscription/subscribe") { page(); contentType(ContentType.Application.Json); setBody("""{"plan": "yearly"}""") }.json().jsonObject
        assertEquals("trial", bought.string("plan"))
        assertEquals(listOf("yearly"), play.plans)
        val asked = relay.takeRequest(5, TimeUnit.SECONDS)!!
        assertEquals("/v1/subscribe", asked.url.encodedPath)
        val sent = json.parseToJsonElement(asked.body!!.utf8()).jsonObject
        assertEquals(listOf("token-1", PlayStore.PRODUCT), listOf(sent.string("purchase_token"), sent.string("product_id")))
        assertEquals("nts_from_play", prefs[LocalServer.keyOf(local.relayUrl())])

        // Given up on Google Play's screen: nothing changes
        play.buying = Bought.GivenUp
        assertEquals("true", client.post("/api/admin/subscription/subscribe") { page(); contentType(ContentType.Application.Json); setBody("""{"plan": "monthly"}""") }.json().jsonObject["cancelled"]!!.jsonPrimitive.content)
        // Paid later (some ways to pay): said pending, then restored as the settings open once paid
        play.buying = Bought.Pending
        assertEquals("true", client.post("/api/admin/subscription/subscribe") { page(); contentType(ContentType.Application.Json); setBody("""{"plan": "monthly"}""") }.json().jsonObject["pending"]!!.jsonPrimitive.content)
        play.owned = listOf("token-2")
        relayAnswers("""{"key": "nts_paid_later", "account": {"plan": "monthly", "credits_left": 3000, "daily_left": 500}}""")
        assertEquals("true", client.get("/api/admin/subscription") { page() }.json().jsonObject["restored"]!!.jsonPrimitive.content)
        assertEquals("nts_paid_later", prefs[LocalServer.keyOf(local.relayUrl())])
        assertEquals("/v1/subscribe", relay.takeRequest(5, TimeUnit.SECONDS)!!.url.encodedPath)
        assertFalse(local.licensing.purchasePending) // found: no more looked for
        play.owned = emptyList()
        // A base plan that isn't one: not asked of Google Play
        assertEquals(HttpStatusCode.BadRequest, client.post("/api/admin/subscription/subscribe") { page(); contentType(ContentType.Application.Json); setBody("""{"plan": "weekly"}""") }.status)
        assertEquals(listOf("yearly", "monthly", "monthly"), play.plans)

        // A new phone (no key): the subscription this Google account has, restored as the settings open
        prefs[LocalServer.keyOf(local.relayUrl())] = ""
        play.owned = listOf("token-1")
        relayAnswers("""{"key": "nts_from_play", "account": {"plan": "monthly", "credits_left": 20000, "daily_left": 2000}}""")
        assertEquals("true", client.get("/api/admin/subscription") { page() }.json().jsonObject["restored"]!!.jsonPrimitive.content)
        assertEquals("nts_from_play", prefs[LocalServer.keyOf(local.relayUrl())])

        // Nothing to restore; Google Play's page to manage it
        play.owned = emptyList()
        val none = client.post("/api/admin/subscription/restore") { page() }
        assertEquals(HttpStatusCode.BadRequest, none.status)
        assertEquals("subscription.none", none.json().jsonObject["detail"]!!.jsonObject.string("code"))
        client.post("/api/admin/subscription/manage") { page() }
        assertEquals(1, play.managed)

        // Not on sale yet: no offer (the settings show the key only)
        play.offers = emptyList()
        assertEquals(0, client.get("/api/admin/subscription") { page() }.json().jsonObject["offers"]!!.jsonArray.size)
    }
}
