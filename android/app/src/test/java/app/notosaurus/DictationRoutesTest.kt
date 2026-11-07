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

/** The local server: DictationRoutes.kt's routes. */
class DictationRoutesTest : LocalServerTestBase() {
    @Test
    fun dictationNothingSaid() = app { client ->
        mic.said = ByteArray(10) // a tap on start then stop: nothing for the relay
        val res = client.dictate()
        assertEquals("", res.json().jsonObject.string("text"))
        assertEquals(0, relay.requestCount)
    }

    @Test
    fun dictationWithoutTheMicrophone() = app { client ->
        micGranted = false
        val refused = client.dictate()
        assertEquals(HttpStatusCode.BadRequest, refused.status)
        assertEquals("dictation.refused", refused.json().jsonObject["detail"]!!.jsonObject.string("code"))
        micGranted = true
        mic.busy = true
        val failed = client.dictate()
        assertEquals("dictation.failed", failed.json().jsonObject["detail"]!!.jsonObject.string("code"))
        mic.busy = false
        val notStarted = client.post("/api/dictation/stop") {
            page()
            setBody("""{"kind": "prompt"}""")
        }
        assertEquals("dictation.failed", notStarted.json().jsonObject["detail"]!!.jsonObject.string("code"))
    }
}
