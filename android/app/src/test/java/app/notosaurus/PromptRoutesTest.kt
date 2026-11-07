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

/** The local server: PromptRoutes.kt's routes. */
class PromptRoutesTest : LocalServerTestBase() {
    @Test
    fun languagesAndPrompts() = app { client ->
        val lang = client.get("/api/lang") { page() }.json().jsonObject
        val available = lang["available"]!!.jsonArray.map { it.jsonPrimitive.content }
        assertTrue("en" in available && "fr" in available)
        assertEquals("Français", lang["names"]!!.jsonObject.string("fr"))

        // Notosaurus's prompts in the page's language, "Automatic" first
        val prompts = client.get("/api/prompts") { page("fr") }.json().jsonArray.map { it.jsonObject }
        assertEquals(21, prompts.size) // app/prompts.py BUILTIN
        assertEquals("notosaurus:auto", prompts[0].string("id"))
        assertTrue(prompts.all { it["builtin"]!!.jsonPrimitive.content == "true" })
        val french = json.parseToJsonElement(File(System.getProperty("notosaurus.web") ?: "../../static", "i18n/fr.json").readText())
        assertEquals(french.jsonObject["builtinPrompts"]!!.jsonObject["vocabulary"]!!.jsonObject.string("name"), prompts[1].string("name"))
        // Its text from its own file (static/prompts/<lang>/<key>.md)
        val vocabulary = File(System.getProperty("notosaurus.web") ?: "../../static", "prompts/fr/vocabulary.md").readText()
        assertEquals(vocabulary, prompts[1].string("text"))
        assertTrue(prompts.all { it.string("text").isNotBlank() })

        // The user's: added, changed, copied, deleted
        val added = client.post("/api/prompts") {
            page(); contentType(ContentType.Application.Json); setBody("""{"name": "Mine", "text": "T", "typing": true}""")
        }.json().jsonObject
        assertEquals(1, added["id"]!!.jsonPrimitive.int)
        client.put("/api/prompts/1") { page(); contentType(ContentType.Application.Json); setBody("""{"name": "Mine 2", "text": "T2"}""") }
        val copy = client.post("/api/prompts/notosaurus:cloze/duplicate") { page("fr") }.json().jsonObject
        assertEquals(2, copy["id"]!!.jsonPrimitive.int)
        client.delete("/api/prompts/1") { page() }
        val all = client.get("/api/prompts") { page() }.json().jsonArray.map { it.jsonObject }
        val mine = all.filter { it["builtin"]!!.jsonPrimitive.content != "true" } // after Notosaurus's, however many
        assertEquals(listOf(2), mine.map { it["id"]!!.jsonPrimitive.int })
        assertFalse(mine[0]["builtin"]!!.jsonPrimitive.content.toBoolean())
    }

    @Test
    fun aFreeTrialRefusedSaysSo() = app { client ->
        prefs[LocalServer.keyOf(local.relayUrl())] = "" // a new user: no key yet
        // Play Integrity giving no token: the AI call refused with why, the relay never asked
        play.integrity = null
        val refused = client.post("/api/prompt/rephrase") { page(); contentType(ContentType.Application.Json); setBody("""{"text": "t"}""") }
        assertEquals(HttpStatusCode.BadRequest, refused.status)
        assertEquals("relay.trial_refused", refused.json().jsonObject["detail"]!!.jsonObject.string("code"))
        assertEquals(null, relay.takeRequest(200, TimeUnit.MILLISECONDS))
        // The settings no longer say the first lesson starts it
        assertEquals("false", client.get("/api/admin/subscription") { page() }.json().jsonObject["trial"]!!.jsonPrimitive.content)
    }

    @Test
    fun instructionsTidiedUpByTheRelay() = app { client ->
        relayAnswers("""{"text": "Douze cartes : la famille en espagnol.", "usage": {"credits": 1, "credits_left": 99}}""")
        val res = client.post("/api/prompt/rephrase") {
            page("fr")
            contentType(ContentType.Application.Json)
            setBody("""{"text": "euh la famille en espagnol, dix cartes non douze"}""")
        }
        assertEquals("""{"text":"Douze cartes : la famille en espagnol."}""", res.bodyAsText())
        val sent = json.parseToJsonElement(relay.takeRequest(5, TimeUnit.SECONDS)!!.body!!.utf8()).jsonObject
        assertEquals("euh la famille en espagnol, dix cartes non douze", sent.string("text"))
        assertEquals("French", sent.string("language"))
    }
}
