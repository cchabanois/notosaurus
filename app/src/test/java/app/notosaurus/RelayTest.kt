package app.notosaurus

import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put
import mockwebserver3.MockResponse
import mockwebserver3.MockWebServer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Before
import org.junit.Test

/** The relay's client, against a fake relay. */
class RelayTest {
    private val server = MockWebServer()

    @Before fun start() = server.start()

    @After fun stop() = server.close()

    private fun relay() = Relay(server.url("/").toString(), "nts_key")

    @Test
    fun photosInAMultipartWithTheJsonRequest() = runBlocking {
        server.enqueue(MockResponse.Builder().body("""{"deck": {"deck": "D", "cards": []}, "turns": [0]}""").build())
        val answer = relay().withPhotos("extract", buildJsonObject { put("prompt", "FR → ES") }, listOf("photo 1".toByteArray(), "photo 2".toByteArray()))
        assertEquals("[0]", answer["turns"].toString())

        val request = server.takeRequest()
        assertEquals("/v1/extract", request.url.encodedPath)
        assertEquals("Bearer nts_key", request.headers["Authorization"])
        assertEquals(Relay.CLIENT_VERSION, request.headers[Relay.CLIENT_HEADER])
        val body = request.body!!.utf8()
        // The JSON request in its own part, typed; then each photo, in order
        assertTrue(body, Regex("""name="request"\r\nContent-Type: application/json[^\r]*\r\n(Content-Length: \d+\r\n)?\r\n\{"prompt":"FR → ES"\}""").containsMatchIn(body))
        assertTrue(body.indexOf("""name="images"; filename="page-1.jpg"""") in 0 until body.indexOf("photo 1"))
        assertTrue(body.indexOf("photo 1") < body.indexOf("photo 2"))
        assertTrue("Content-Type: image/jpeg" in body)
    }

    @Test
    fun theRelaysErrorsAsTheyAre() = runBlocking {
        server.enqueue(MockResponse.Builder().code(402).body("""{"code": "relay.no_credits", "params": {"renews_at": "2026-11-01"}}""").build())
        try {
            relay().post("explain", buildJsonObject { })
            fail()
        } catch (e: RelayException) {
            assertEquals("relay.no_credits", e.code)
            assertEquals("2026-11-01", e.params["renews_at"]!!.jsonPrimitive.content)
        }
    }

    @Test
    fun anAnswerThatIsntTheRelays() = runBlocking {
        server.enqueue(MockResponse.Builder().code(500).body("<html>proxy error</html>").build())
        try {
            relay().post("explain", buildJsonObject { })
            fail()
        } catch (e: RelayException) {
            assertEquals("relay.http_500", e.code)
        }
    }

    @Test
    fun noRelay() = runBlocking {
        val gone = server.url("/").toString()
        server.close()
        try {
            Relay(gone, "k").account()
            fail()
        } catch (e: RelayException) {
            assertEquals("relay.unreachable", e.code)
        }
    }
}
