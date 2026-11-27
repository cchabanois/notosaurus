package app.notosaurus

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonObject
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
import com.sun.net.httpserver.HttpServer
import java.net.InetSocketAddress
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicInteger

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

    /** The app kept running (Busy) around the relay's calls whose work a lesson waits for: the
     * AI's, the lesson's own drawings, its sounds, the free pictures; not the voices nor the
     * account. Only the AI's start the free trial (a call without a key). */
    @Test
    fun theAppKeptRunningAroundALessonsWork() = runBlocking {
        val told = mutableListOf<String>()
        val busy = object : Relay.Busy {
            override fun begin() { told += "begin" }
            override fun end() { told += "end" }
        }
        var trials = 0
        val relay = Relay(server.url("/").toString(), "", noKey = { trials++; "nts_trial" }, busy = busy)
        fun kept(what: String, answer: String = "{}", call: suspend () -> Unit) {
            told.clear()
            server.enqueue(MockResponse.Builder().body(answer).build())
            runBlocking { call() }
            assertEquals(what, listOf("begin", "end"), told)
        }
        kept("the lesson's drawings") { relay.withPhotos("lesson-drawings", buildJsonObject {}, listOf("photo".toByteArray())) }
        kept("a sound") { relay.speak("la madre", "es-ES-Chirp3-HD-Puck") }
        kept("free pictures", """{"done": true, "results": []}""") { relay.searchPictures("une trousse") }
        kept("a free picture") { relay.foundPicture("openverse", "1") }
        assertEquals("not the AI's: no trial", 0, trials)
        told.clear()
        server.enqueue(MockResponse.Builder().body("[]").build())
        relay.voices()
        assertEquals("the voices", emptyList<String>(), told)
        kept("the AI's", """{"text": "bonjour"}""") { relay.post("rephrase", buildJsonObject {}) }
        assertEquals("the AI's: the trial", 1, trials)
    }

    @Test
    fun aSubscriptionPastItsEndTold() = runBlocking {
        var lapsed = 0
        val relay = Relay(server.url("/").toString(), "nts_key", lapsed = { lapsed++ })
        for (code in listOf("relay.subscription_ended", "relay.payment_pending", "relay.no_credits")) {
            server.enqueue(MockResponse.Builder().code(402).body("""{"code": "$code"}""").build())
            try {
                relay.post("explain", buildJsonObject {})
                fail("refused")
            } catch (e: RelayException) {
                assertEquals(code, e.code)
            }
        }
        assertEquals(2, lapsed) // not for credits used up
    }

    @Test
    fun noKeyTheFreeTrialsForAnAiCallOnly() = runBlocking {
        var asked = 0
        val relay = Relay(server.url("/").toString(), "", noKey = { asked++; "nts_trial" })
        server.enqueue(MockResponse.Builder().body("""{"plan": "free_trial", "credits_left": 300, "daily_left": 150}""").build())
        relay.account() // not an AI call: no trial
        assertEquals("Bearer", server.takeRequest().headers["Authorization"]?.trim())
        server.enqueue(MockResponse.Builder().body("""{"text": "t"}""").build())
        relay.post("rephrase", buildJsonObject {})
        assertEquals("Bearer nts_trial", server.takeRequest().headers["Authorization"])
        assertEquals(1, asked)
        // A key already: never asked
        server.enqueue(MockResponse.Builder().body("""{"text": "t"}""").build())
        Relay(server.url("/").toString(), "nts_key", noKey = { asked++; "x" }).post("rephrase", buildJsonObject {})
        assertEquals(1, asked)
    }

    @Test
    fun theCardsAsTheAiWritesThem() = runBlocking {
        val lines = listOf(
            """{"card": {"front": "a", "back": "x"}}""",
            """{"restart": true}""",
            """{"card": {"front": "b", "back": "y"}}""",
            """{"result": {"deck": {"deck": "D", "cards": []}, "turns": [], "usage": {"credits": 2, "credits_left": 98}}}""",
        )
        server.enqueue(MockResponse.Builder().setHeader("Content-Type", Relay.STREAM_TYPE).body(lines.joinToString("\n", postfix = "\n")).build())
        val told = mutableListOf<String?>()
        val answer = relay().extract(buildJsonObject { put("prompt", "p") }, emptyList()) { told += it?.string("front") }
        assertEquals(listOf("a", null, "b"), told)
        assertEquals("D", answer["deck"]!!.jsonObject.string("deck"))
        assertEquals(Relay.STREAM_TYPE, server.takeRequest().headers["Accept"])

        // An error once the cards came: the last line
        server.enqueue(MockResponse.Builder().setHeader("Content-Type", Relay.STREAM_TYPE).body("""{"card": {"front": "a"}}""" + "\n" + """{"error": {"code": "llm.refused", "params": {}}}""" + "\n").build())
        try {
            relay().extract(buildJsonObject { }, emptyList()) {}
            fail()
        } catch (e: RelayException) {
            assertEquals("llm.refused", e.code)
        }

        // A relay that answers all at once (an older one): its answer
        server.enqueue(MockResponse.Builder().body("""{"deck": {"deck": "E", "cards": []}, "turns": []}""").build())
        assertEquals("E", relay().extract(buildJsonObject { }, emptyList()) { fail() }["deck"]!!.jsonObject.string("deck"))
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

    /** A lesson's pictures and its sounds asked together (4 and 4 at a time, a lesson being read):
     * never more at once than the relay takes from a licence (6), which refused the others
     * (relay.busy), their sounds lost (2026-11-26). Counted where the relay counts them, while it
     * answers: a call's answer comes as it is made (a picture's steps), its headers first, its end
     * seconds later; OkHttp's own limit (5 a host) lets a call go once its headers are in. */
    @Test
    fun neverMoreCallsAtOnceThanTheRelayTakes() = runBlocking {
        val running = AtomicInteger()
        val most = AtomicInteger()
        val slow = HttpServer.create(InetSocketAddress("127.0.0.1", 0), 0).apply {
            executor = Executors.newCachedThreadPool()
            createContext("/") { exchange ->
                most.accumulateAndGet(running.incrementAndGet(), ::maxOf)
                exchange.sendResponseHeaders(200, 0) // its headers at once, then its answer as it comes
                exchange.responseBody.use { body ->
                    body.flush()
                    Thread.sleep(300)
                    body.write("mp3".toByteArray())
                }
                running.decrementAndGet()
            }
            start()
        }
        try {
            val relay = Relay("http://127.0.0.1:${slow.address.port}/", "nts_key")
            val sounds = (1..10).map { async(Dispatchers.IO) { relay.speak("mot $it", "fr-FR-Chirp3-HD-Aoede") } }.awaitAll()
            assertEquals(List(10) { "mp3" }, sounds.map { String(it) })
            assertTrue("${most.get()} at once", most.get() <= Relay.CALLS_AT_ONCE)
            assertTrue(Relay.CALLS_AT_ONCE < 6) // the relay's own limit, one kept
        } finally {
            slow.stop(0)
        }
    }

    /** Refused all the same, too many of the licence's calls running (relay.busy, before the AI is
     * asked: nothing charged): asked again a moment after; any other refusal said at once. */
    @Test
    fun aBusyRefusalAskedAgainAnyOtherSaid() = runBlocking {
        val busy = """{"code": "relay.busy", "params": {}}"""
        server.enqueue(MockResponse.Builder().code(429).body(busy).build())
        server.enqueue(MockResponse.Builder().code(429).body(busy).build())
        server.enqueue(MockResponse.Builder().body("mp3").build())
        assertEquals("mp3", String(relay().speak("le père", "fr-FR-Chirp3-HD-Aoede")))
        assertEquals(3, server.requestCount)

        server.enqueue(MockResponse.Builder().code(429).body("""{"code": "relay.daily_limit", "params": {}}""").build())
        try {
            relay().speak("la mère", "fr-FR-Chirp3-HD-Aoede")
            fail("refused")
        } catch (e: RelayException) {
            assertEquals("relay.daily_limit", e.code)
        }
        assertEquals(4, server.requestCount) // once
    }
}
