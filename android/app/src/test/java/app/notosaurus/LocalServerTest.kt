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
import io.ktor.http.HttpStatusCode
import io.ktor.http.contentType
import io.ktor.server.testing.ApplicationTestBuilder
import io.ktor.server.testing.testApplication
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import kotlinx.serialization.json.int
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
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
import java.util.concurrent.TimeUnit

/**
 * The page's /api, answered on the phone: called as the page calls them (app.js),
 * with a fake relay (MockWebServer) and a fake AnkiDroid. The page's files are the
 * repository's static/ (the notosaurus.web system property, set by Gradle).
 */
class LocalServerTest {
    @get:Rule val folder = TemporaryFolder()
    private val relay = MockWebServer()
    private val anki = FakeAnki()
    private val prefs = MemoryPreferences()
    private var permissionAsked = 0
    private var grantPermission = true // the user's answer to AnkiDroid's dialog
    private var storeOpened = 0
    private val computer = MockWebServer() // the add-on's Notosaurus, on the computer
    private var scanned: String? = null // what the fake QR scanner reads
    private var scannerMissing = false
    private var modeChanges = 0
    private var micGranted = true // the user's answer to the microphone's dialog
    private val mic = FakeMic()
    private lateinit var local: LocalServer

    private class FakeAnki : AnkiTarget {
        var installed = true
        var permitted = true
        var broken = false // e.g. never opened: no collection yet
        val sent = mutableListOf<Deck>()
        var sounds: Map<String, File> = emptyMap()
        var pictures: Map<String, File> = emptyMap()
        override fun installed() = installed
        override fun permitted() = installed && permitted
        override fun deckNames() = listOf("Default", "Histoire")
        var media = Media()
        var options = Options()
        val notes = mutableMapOf<String, MutableList<Long>>() // a lesson's notes in AnkiDroid
        val deleted = mutableListOf<Long>()
        override fun lessonNotes(lesson: String) = if (broken) null else notes[lesson].orEmpty()
        override fun delete(notes: List<Long>) = notes.size.also { deleted += notes }
        val reviewed = mutableListOf<String>()
        override fun review(deck: String) = (deck in deckNames() || sent.any { it.deck == deck }).also { if (it) reviewed += deck }
        override fun send(deck: Deck, media: Media, options: Options): Sent {
            if (broken) error("no collection")
            sent += deck
            this.media = media
            this.options = options
            sounds = media.audio
            pictures = media.pictures
            return Sent(added = deck.cards.size, duplicates = 0, skipped = 0, deck = deck.deck)
        }
    }

    /** A microphone that "records" what it's told to: ADTS frames, as the phone's would. */
    private class FakeMic : Recorder {
        var said = ByteArray(4000) { 0x55 }
        var busy = false // another app holds the microphone
        var listening = false
        private var file: File? = null
        override fun start(file: File) {
            if (busy) error("start failed")
            this.file = file
            listening = true
        }
        override fun stop() {
            listening = false
            file!!.writeBytes(said)
        }
    }

    @Before
    fun setUp() {
        relay.start()
        val web = File(System.getProperty("notosaurus.web") ?: "../../static")
        val page = File("src/main/assets/page") // the app's own files, first (as forApp)
        prefs[LocalServer.RELAY] = relay.url("/").toString()
        prefs[LocalServer.KEY] = "nts_key"
        local = LocalServer(
            dataDir = folder.root,
            web = { path -> listOf(page, web).map { it.resolve(path) }.firstOrNull { it.isFile }?.readBytes() },
            languages = { web.resolve("i18n").list().orEmpty().filter { it.endsWith(".json") }.map { it.removeSuffix(".json") } },
            anki = anki,
            prefs = prefs,
            version = "0.1.0",
            requestAnkiPermission = {
                permissionAsked++
                anki.permitted = grantPermission
                grantPermission
            },
            installAnki = { storeOpened++ },
            scan = { if (scannerMissing) error("module not downloaded") else scanned },
            modeChanged = { modeChanges++ },
            turnPhoto = { data, degrees -> "turned $degrees:".toByteArray() + data }, // (Photos.turn needs Android)
            recorder = mic,
            requestMicPermission = { micGranted },
        )
        computer.start()
    }

    @After
    fun tearDown() {
        relay.close()
        computer.close()
    }

    private fun app(test: suspend ApplicationTestBuilder.(HttpClient) -> Unit) = testApplication {
        application { with(local) { module() } }
        test(client)
    }

    /** As the app's WebView: its cookie, the page's language. */
    private fun HttpRequestBuilder.page(lang: String = "en") {
        header(HttpHeaders.Cookie, "${LocalServer.COOKIE}=${local.token}")
        header("X-Notosaurus-Lang", lang)
    }

    private suspend fun HttpResponse.json() = json.parseToJsonElement(bodyAsText())

    private fun relayAnswers(body: String, code: Int = 200) =
        relay.enqueue(MockResponse.Builder().code(code).body(body).build())

    private fun RecordedRequest.multipartRequest(): JsonObject {
        val text = body!!.utf8()
        val start = text.indexOf("\r\n\r\n", text.indexOf("name=\"request\"")) + 4
        return json.parseToJsonElement(text.substring(start, text.indexOf("\r\n--", start))).jsonObject
    }

    private suspend fun HttpClient.extract(
        prompt: String = "FR → ES",
        voice: String = "auto",
        path: String = "/api/extract",
        photos: List<String> = listOf("photo 1", "photo 2"),
        quick: Boolean = false,
    ): JsonObject {
        relayAnswers("""{"deck": {"deck": "Espagnol::Leçon 5", "cards": [{"front": "la mère", "back": "la madre"}, {"front": "le père", "back": "el padre"}]}, "turns": [0, 0], "choice": "Vocabulaire", "usage": {"credits": 3, "credits_left": 97}}""")
        return submitFormWithBinaryData(
            path,
            formData {
                photos.forEachIndexed { i, photo ->
                    append("images", photo.toByteArray(), Headers.build {
                        append(HttpHeaders.ContentType, "image/jpeg")
                        append(HttpHeaders.ContentDisposition, "filename=\"page-${i + 1}.jpg\"")
                    })
                }
                append("prompt", prompt)
                append("deck", "")
                append("voice", voice)
                append("fun_facts", "true")
                if (quick) append("quick", "true")
            },
        ) { page() }.json().jsonObject
    }

    @Test
    fun onlyTheAppsWebView() = app { client ->
        val res = client.get("/api/config")
        assertEquals(HttpStatusCode.Unauthorized, res.status)
        assertEquals("device.not_paired", res.json().jsonObject["detail"]!!.jsonObject.string("code"))
        val config = client.get("/api/config") { page() }
        assertEquals(HttpStatusCode.OK, config.status)
        assertEquals("false", config.json().jsonObject["profiles"]!!.jsonPrimitive.content) // no Anki profile badge
    }

    @Test
    fun thePagesFiles() = app { client ->
        val index = client.get("/")
        assertEquals(HttpStatusCode.OK, index.status)
        assertTrue(index.headers[HttpHeaders.ContentType]!!.startsWith("text/html"))
        assertTrue("app.js" in index.bodyAsText())
        assertEquals(HttpStatusCode.OK, client.get("/i18n/fr.json").status)
        assertEquals(HttpStatusCode.NotFound, client.get("/../build.gradle.kts").status)
        assertEquals(HttpStatusCode.NotFound, client.get("/nope.js").status)
        // pdf.js, shipped with the page: a module, so served as JavaScript (or the WebView refuses it)
        val pdfjs = client.get("/vendor/pdfjs/pdf.min.mjs")
        assertEquals(HttpStatusCode.OK, pdfjs.status)
        assertTrue(pdfjs.headers[HttpHeaders.ContentType]!!, "javascript" in pdfjs.headers[HttpHeaders.ContentType]!!)
        // Alpine, KaTeX and the font, shipped too (static/vendor): nothing from elsewhere
        assertEquals(HttpStatusCode.OK, client.get("/vendor/alpinejs/cdn.min.js").status)
        assertEquals(HttpStatusCode.OK, client.get("/vendor/katex/katex.min.css").status)
        assertEquals(HttpStatusCode.OK, client.get("/vendor/nunito/nunito-latin-wght-normal.woff2").status)
    }

    @Test
    fun languagesAndPrompts() = app { client ->
        val lang = client.get("/api/lang") { page() }.json().jsonObject
        val available = lang["available"]!!.jsonArray.map { it.jsonPrimitive.content }
        assertTrue("en" in available && "fr" in available)
        assertEquals("Français", lang["names"]!!.jsonObject.string("fr"))

        // Notosaurus's prompts in the page's language, "Automatic" first
        val prompts = client.get("/api/prompts") { page("fr") }.json().jsonArray.map { it.jsonObject }
        assertEquals(13, prompts.size)
        assertEquals("notosaurus:auto", prompts[0].string("id"))
        assertTrue(prompts.all { it["builtin"]!!.jsonPrimitive.content == "true" })
        val french = json.parseToJsonElement(File(System.getProperty("notosaurus.web") ?: "../../static", "i18n/fr.json").readText())
        assertEquals(french.jsonObject["builtinPrompts"]!!.jsonObject["vocabulary"]!!.jsonObject.string("name"), prompts[1].string("name"))

        // The user's: added, changed, copied, deleted
        val added = client.post("/api/prompts") {
            page(); contentType(ContentType.Application.Json); setBody("""{"name": "Mine", "text": "T", "typing": true}""")
        }.json().jsonObject
        assertEquals(1, added["id"]!!.jsonPrimitive.int)
        client.put("/api/prompts/1") { page(); contentType(ContentType.Application.Json); setBody("""{"name": "Mine 2", "text": "T2"}""") }
        val copy = client.post("/api/prompts/notosaurus:cloze/duplicate") { page("fr") }.json().jsonObject
        assertEquals(2, copy["id"]!!.jsonPrimitive.int)
        client.delete("/api/prompts/1") { page() }
        val mine = client.get("/api/prompts") { page() }.json().jsonArray.drop(13).map { it.jsonObject }
        assertEquals(listOf(2), mine.map { it["id"]!!.jsonPrimitive.int })
        assertFalse(mine[0]["builtin"]!!.jsonPrimitive.content.toBoolean())
    }

    @Test
    fun aLessonMadeQuickThenAgainCarefullyInItsPlace() = app { client ->
        val lesson = client.extract(quick = true)
        assertEquals("true", relay.takeRequest().multipartRequest()["quick"]!!.jsonPrimitive.content)
        val id = lesson.string("id")
        client.put("/api/lessons/$id") {
            page()
            contentType(ContentType.Application.Json)
            setBody("""{"reverse": true}""")
        }

        // "Make again, carefully": the same lesson, new cards and photos, its options kept
        val again = client.extract(path = "/api/lessons/$id/regenerate", photos = listOf("photo 3"))
        assertEquals("false", relay.takeRequest().multipartRequest()["quick"]!!.jsonPrimitive.content)
        assertEquals(id, again.string("id"))
        assertEquals(1, again["photo_count"]!!.jsonPrimitive.int)
        assertTrue(again["reverse"]!!.jsonPrimitive.content.toBoolean())
        assertArrayEquals("photo 3".toByteArray(), client.get("/api/lessons/$id/photos/1") { page() }.bodyAsBytes())
        assertEquals(HttpStatusCode.NotFound, client.get("/api/lessons/$id/photos/2") { page() }.status)
        assertEquals(1, client.get("/api/lessons") { page() }.json().jsonArray.size)
    }

    @Test
    fun cancelledWhileTheRelayWorks() = app { client ->
        coroutineScope { cancelled(client) }
    }

    private suspend fun CoroutineScope.cancelled(client: HttpClient) {
        relay.enqueue(MockResponse.Builder().headersDelay(10, TimeUnit.SECONDS).body("{}").build())
        val made = async {
            client.submitFormWithBinaryData(
                "/api/extract",
                formData {
                    append("prompt", "FR → ES")
                    append("job", "j1")
                },
            ) { page() }
        }
        // The relay at work (waited for elsewhere: this thread runs the app's server)
        assertNotNull(withContext(Dispatchers.IO) { relay.takeRequest(5, TimeUnit.SECONDS) })
        val cancel = client.post("/api/generations/j1/cancel") { page() }.json().jsonObject
        assertTrue(cancel["cancelled"]!!.jsonPrimitive.content.toBoolean())

        val answer = made.await()
        assertEquals(HttpStatusCode.Conflict, answer.status)
        assertEquals("extract.cancelled", answer.json().jsonObject["detail"]!!.jsonObject.string("code"))
        assertEquals(0, client.get("/api/lessons") { page() }.json().jsonArray.size) // nothing saved
        // Gone: nothing to cancel
        assertFalse(client.post("/api/generations/j1/cancel") { page() }.json().jsonObject["cancelled"]!!.jsonPrimitive.content.toBoolean())
    }

    @Test
    fun theCardsAsTheyComeThenTheLesson() = app { client ->
        val lines = listOf(
            """{"card": {"front": "la mère", "back": "la madre"}}""",
            """{"result": {"deck": {"deck": "Espagnol", "cards": [{"front": "la mère", "back": "la madre"}]}, "turns": [], "usage": {"credits": 1, "credits_left": 99}}}""",
        )
        relay.enqueue(MockResponse.Builder().setHeader("Content-Type", Relay.STREAM_TYPE).body(lines.joinToString("\n", postfix = "\n")).build())
        val res = client.submitFormWithBinaryData("/api/extract", formData { append("prompt", "FR → ES") }) {
            page()
            header(HttpHeaders.Accept, Relay.STREAM_TYPE)
        }
        assertTrue(res.headers[HttpHeaders.ContentType]!!.startsWith(Relay.STREAM_TYPE))
        val items = res.bodyAsText().lines().filter { it.isNotBlank() }.map { json.parseToJsonElement(it).jsonObject }
        assertEquals("la madre", items[0]["card"]!!.jsonObject.string("back"))
        val lesson = items[1]["lesson"]!!.jsonObject
        assertEquals("Espagnol", lesson.string("deck"))
        assertEquals(lesson, client.get("/api/lessons/${lesson.string("id")}") { page() }.json()) // saved

        // An error: the last line, as the page translates it
        relay.enqueue(MockResponse.Builder().code(402).body("""{"code": "relay.no_credits", "params": {}}""").build())
        val failed = client.submitFormWithBinaryData("/api/extract", formData { append("prompt", "p") }) {
            page()
            header(HttpHeaders.Accept, Relay.STREAM_TYPE)
        }.bodyAsText().trim()
        assertEquals("relay.no_credits", json.parseToJsonElement(failed).jsonObject["error"]!!.jsonObject.string("code"))
    }

    @Test
    fun aLessonFromPhotos() = app { client ->
        val lesson = client.extract(voice = "auto")
        val sent = relay.takeRequest()
        assertEquals("/v1/extract", sent.url.encodedPath)
        val request = sent.multipartRequest()
        assertEquals("FR → ES", request.string("prompt"))
        assertEquals("true", request["fun_facts"]!!.jsonPrimitive.content)
        assertEquals(2, Regex("""name="images"""").findAll(sent.body!!.utf8()).count())

        // Saved on the phone, as the page then reads it
        val id = lesson.string("id")
        assertEquals("Espagnol::Leçon 5", lesson.string("deck"))
        assertEquals("Vocabulaire", lesson.string("choice"))
        assertEquals("", lesson.string("voice")) // "auto": no voice yet on the phone
        assertEquals(2, lesson["photo_count"]!!.jsonPrimitive.int)
        assertTrue(lesson["cards"]!!.jsonArray.all { it.jsonObject.string("id").isNotEmpty() })
        assertArrayEquals("photo 2".toByteArray(), client.get("/api/lessons/$id/photos/2") { page() }.bodyAsBytes())
        assertEquals(lesson, client.get("/api/lessons/$id") { page() }.json())

        val list = client.get("/api/lessons") { page() }.json().jsonArray
        assertEquals(1, list.size)
        assertEquals(2, list[0].jsonObject["card_count"]!!.jsonPrimitive.int)
        assertFalse("cards" in list[0].jsonObject)

        // The decks offered: the lessons' and AnkiDroid's
        assertEquals(
            listOf("Default", "Espagnol::Leçon 5", "Histoire"),
            client.get("/api/decks") { page() }.json().jsonArray.map { it.jsonPrimitive.content },
        )
    }

    @Test
    fun theRelaysErrorsForThePage() = app { client ->
        relayAnswers("""{"code": "relay.no_credits", "params": {}}""", code = 402)
        val res = client.submitFormWithBinaryData("/api/extract", formData { append("prompt", "p") }) { page() }
        assertEquals(HttpStatusCode.BadGateway, res.status)
        assertEquals("relay.no_credits", res.json().jsonObject["detail"]!!.jsonObject.string("code"))
        assertEquals(JsonArray(emptyList()), client.get("/api/lessons") { page() }.json()) // nothing saved
    }

    @Test
    fun aCorrection() = app { client ->
        val lesson = client.extract()
        relay.takeRequest()
        val id = lesson.string("id")
        val cards = lesson["cards"]!!.jsonArray
        relayAnswers("""{"deck": "Espagnol::Leçon 5", "cards": [${cards[0]}, {"front": "le frère", "back": "el hermano"}], "summary": "Une carte remplacée.", "usage": {"credits": 2, "credits_left": 95}}""")
        val res = client.post("/api/lessons/$id/revise") {
            page("fr"); contentType(ContentType.Application.Json)
            setBody("""{"deck": "Espagnol::Leçon 5", "cards": $cards, "voice": "", "instruction": "remplace le père par le frère"}""")
        }.json().jsonObject

        val sent = relay.takeRequest()
        assertEquals("/v1/revise", sent.url.encodedPath)
        val request = sent.multipartRequest()
        assertEquals("French", request.string("language")) // the page's language, by its English name
        assertEquals("FR → ES", request.string("prompt")) // the lesson's
        assertEquals("remplace le père par le frère", request.string("instruction"))
        assertTrue("photo 1" in sent.body!!.utf8()) // the lesson's photos go with it

        assertEquals("Une carte remplacée.", res.string("summary"))
        val revised = res["lesson"]!!.jsonObject["cards"]!!.jsonArray.map { it.jsonObject }
        assertEquals(cards[0].jsonObject.string("id"), revised[0].string("id")) // kept
        assertTrue(revised[1].string("id").isNotEmpty())
        assertEquals("le frère", client.get("/api/lessons/$id") { page() }.json().jsonObject["cards"]!!.jsonArray[1].jsonObject.string("front"))
    }

    @Test
    fun anExplanation() = app { client ->
        val lesson = client.extract()
        relay.takeRequest()
        relayAnswers("""{"text": "Madre vient du latin mater.", "more": ["example"], "usage": {"credits": 1, "credits_left": 96}}""")
        val res = client.post("/api/lessons/${lesson.string("id")}/explain") {
            page(); contentType(ContentType.Application.Json)
            setBody("""{"card": ${lesson["cards"]!!.jsonArray[0]}, "kind": "mnemonic"}""")
        }.json().jsonObject
        assertEquals("Madre vient du latin mater.", res.string("text"))
        assertFalse("usage" in res) // the relay's own
        val request = json.parseToJsonElement(relay.takeRequest().body!!.utf8()).jsonObject
        assertEquals("mnemonic", request.string("kind"))
        assertEquals("Espagnol::Leçon 5", request.string("deck"))
    }

    @Test
    fun cardsIntoAnkiDroid() = app { client ->
        assertEquals("true", client.get("/api/anki/status") { page() }.json().jsonObject["available"]!!.jsonPrimitive.content)
        val lesson = client.extract()
        val res = client.post("/api/anki/send") {
            page(); contentType(ContentType.Application.Json)
            setBody("""{"deck": "Espagnol::Leçon 5", "cards": ${lesson["cards"]}, "voice": "", "lesson_id": "${lesson.string("id")}"}""")
        }.json().jsonObject
        assertEquals(2, res["added"]!!.jsonPrimitive.int)
        assertEquals(listOf("la mère", "le père"), anki.sent.single().cards.map { it.front })
        // Sending saves the lesson, marked as exported
        assertTrue(client.get("/api/lessons/${lesson.string("id")}") { page() }.json().jsonObject.string("exported_at").isNotEmpty())

        assertEquals(0, permissionAsked) // allowed already: not asked
    }

    private val voices = """[{"voice": "es-US-Chirp3-HD-Aoede", "locale": "es-US", "gender": "Female"},
        {"voice": "es-ES-Chirp3-HD-Charon", "locale": "es-ES", "gender": "Male"},
        {"voice": "es-ES-Chirp3-HD-Aoede", "locale": "es-ES", "gender": "Female"}]"""

    @Test
    fun theRelaysVoicesReadTheBacks() = app { client ->
        relayAnswers(voices)
        val listed = client.get("/api/voices") { page() }.json().jsonArray
        assertEquals("es-US-Chirp3-HD-Aoede", listed[0].jsonObject.string("voice"))
        assertEquals("/v1/voices", relay.takeRequest().url.encodedPath)

        // 🔊: read by the relay, then kept on the phone (not paid for twice)
        relay.enqueue(MockResponse.Builder().setHeader("Content-Type", "audio/mpeg").body("mp3 la madre").build())
        repeat(2) {
            val heard = client.get("/api/tts?text=la%20madre&voice=es-ES-Chirp3-HD-Aoede") { page() }
            assertEquals("mp3 la madre", heard.bodyAsText())
        }
        val spoken = relay.takeRequest()
        assertEquals("/v1/speak", spoken.url.encodedPath)
        val asked = json.parseToJsonElement(spoken.body!!.utf8()).jsonObject
        assertEquals("es-ES-Chirp3-HD-Aoede", asked.string("voice"))
        assertEquals(Relay.SPEECH_RATE, asked["rate"]!!.jsonPrimitive.content.toDouble(), 0.0)
        assertEquals(2, relay.requestCount) // voices, one speak

        // Sent to AnkiDroid: each back's sound (la madre: kept already; el padre: fails)
        relay.enqueue(MockResponse.Builder().code(503).body("""{"code": "relay.unavailable", "params": {}}""").build())
        val cards = """[{"front": "la mère", "back": "la madre"}, {"front": "le père", "back": "el padre"}]"""
        val res = client.post("/api/anki/send") {
            page(); contentType(ContentType.Application.Json)
            setBody("""{"deck": "Espagnol", "cards": $cards, "voice": "es-ES-Chirp3-HD-Aoede", "lesson_id": ""}""")
        }.json().jsonObject
        assertEquals(2, res["added"]!!.jsonPrimitive.int)
        assertEquals(1, res["audio_failures"]!!.jsonPrimitive.int)
        assertEquals(setOf("la madre"), anki.sounds.keys)
        assertEquals("mp3 la madre", anki.sounds["la madre"]!!.readText())
    }

    @Test
    fun picturesDrawnByTheRelayThenIntoAnkiDroid() = app { client ->
        relayAnswers("""{"deck": {"deck": "Anglais", "cards": [
            {"front": "Comment dit-on ?", "back": "an apple", "picture_prompt": "an apple"},
            {"front": "Ce triangle ?", "back": "rectangle", "figure": "a right triangle", "picture_on_back": true},
            {"front": "le père", "back": "the father"}]}, "turns": [], "usage": {"credits": 1, "credits_left": 99}}""")
        val lesson = client.submitFormWithBinaryData("/api/extract", formData { append("prompt", "p") }) { page() }.json().jsonObject
        val id = lesson.string("id")
        val (apple, triangle) = lesson["cards"]!!.jsonArray.map { it.jsonObject.string("id") }

        // The missing ones drawn: a picture (/v1/picture) and a figure (/v1/figure)
        relay.dispatcher = object : mockwebserver3.Dispatcher() {
            override fun dispatch(request: RecordedRequest) = when (request.url.encodedPath) {
                "/v1/picture" -> MockResponse.Builder().setHeader("Content-Type", "image/jpeg").body("jpeg " + request.body!!.utf8()).build()
                // Another subject written for a picture: the relay's AI plans it (a picture, as written)
                "/v1/plan-picture" -> MockResponse.Builder().body(buildJsonObject {
                    put("kind", "picture")
                    put("description", json.parseToJsonElement(request.body!!.utf8()).jsonObject.string("asked"))
                    put("usage", buildJsonObject { put("credits", 1); put("credits_left", 96) })
                }.toString()).build()
                else -> MockResponse.Builder().body("""{"svg": "<svg/>", "usage": {"credits": 1, "credits_left": 97}}""").build()
            }
        }
        val drawn = client.post("/api/lessons/$id/pictures") { page() }.json().jsonObject
        assertEquals(0, drawn["failures"]!!.jsonPrimitive.int)
        val cards = drawn["lesson"]!!.jsonObject["cards"]!!.jsonArray.map { it.jsonObject }
        val (picture, figure) = cards.take(2).map { it.string("picture") }
        assertTrue(picture.matches(Regex("picture-$apple-[0-9a-f]{8}\\.jpg")))
        assertTrue(figure.matches(Regex("picture-$triangle-[0-9a-f]{8}\\.svg")))
        assertEquals("", cards[2].string("picture"))
        assertTrue(client.get("/api/lessons/$id/pictures/$picture") { page() }.bodyAsText().contains("\"fresh\":false"))
        val svg = client.get("/api/lessons/$id/pictures/$figure") { page() }
        assertEquals("<svg/>", svg.bodyAsText())
        assertTrue(svg.headers["Content-Security-Policy"]!!.startsWith("default-src 'none'"))

        // Drawn again with another subject: fresh, the old file gone
        val again = client.post("/api/lessons/$id/cards/$apple/picture/draw") {
            page(); contentType(ContentType.Application.Json); setBody("""{"subject": "a red apple"}""")
        }.json().jsonObject["card"]!!.jsonObject
        assertEquals("a red apple", again.string("picture_prompt"))
        assertTrue(client.get("/api/lessons/$id/pictures/${again.string("picture")}") { page() }.bodyAsText().contains("\"fresh\":true"))
        assertEquals(HttpStatusCode.NotFound, client.get("/api/lessons/$id/pictures/$picture") { page() }.status)

        // Sent to AnkiDroid with their pictures
        val sending = client.get("/api/lessons/$id") { page() }.json().jsonObject
        client.post("/api/anki/send") {
            page(); contentType(ContentType.Application.Json)
            setBody("""{"deck": "Anglais", "cards": ${sending["cards"]}, "voice": "", "lesson_id": "$id"}""")
        }
        assertEquals(setOf(again.string("picture"), figure), anki.pictures.keys)
        assertTrue(anki.sent.single().cards[1].pictureOnBack)

        // The user's own photo, then no picture at all
        val own = client.submitFormWithBinaryData("/api/lessons/$id/cards/$apple/picture", formData {
            append("photo", "my photo".toByteArray(), Headers.build {
                append(HttpHeaders.ContentType, "image/jpeg")
                append(HttpHeaders.ContentDisposition, "filename=\"photo.jpg\"")
            })
        }) { page() }.json().jsonObject["card"]!!.jsonObject
        assertEquals("my photo", client.get("/api/lessons/$id/pictures/${own.string("picture")}") { page() }.bodyAsText())
        val none = client.delete("/api/lessons/$id/cards/$apple/picture") { page() }.json().jsonObject["card"]!!.jsonObject
        assertEquals(listOf("", "", ""), listOf("picture", "picture_prompt", "figure").map { none.string(it) })
        assertEquals(HttpStatusCode.NotFound, client.get("/api/lessons/$id/pictures/${own.string("picture")}") { page() }.status)
    }

    @Test
    fun diagramsAndGapsIntoAnkiDroid() = app { client ->
        val lesson = client.extract() // two photos
        val id = lesson.string("id")
        val cards = """[
            {"front": "Qu'est-ce que (1) ?", "back": "la bouche", "mask": {"page": 2, "n": 1, "box": [0.1, 0.1, 0.2, 0.15]}},
            {"front": "Qu'est-ce que (2) ?", "back": "l'estomac", "mask": {"page": 2, "n": 2, "box": [0.5, 0.5, 0.6, 0.55]}},
            {"front": "La Révolution commence en {{c1::1789}}.", "back": ""}]"""
        client.post("/api/anki/send") {
            page(); contentType(ContentType.Application.Json)
            setBody("""{"deck": "SVT", "cards": $cards, "voice": "", "lesson_id": "$id"}""")
        }
        // Every card sent, with the photo the labels are on
        assertEquals(3, anki.sent.single().cards.size)
        assertEquals(setOf(2), anki.media.photos.keys)
        assertArrayEquals("photo 2".toByteArray(), anki.media.photos[2]!!.readBytes())
        assertEquals(id, anki.media.lesson)
        assertEquals(emptyMap<Int, List<Double>>(), anki.media.frames) // none in this lesson
    }

    @Test
    fun theDiagramFramesKeptAndSent() = app { client ->
        relayAnswers("""{"deck": {"deck": "SVT", "cards": [{"front": "(1) ?", "back": "la bouche", "mask": {"page": 1, "n": 1, "box": [0.1, 0.1, 0.2, 0.15]}}]},
            "turns": [0], "frames": [{"page": 1, "box": [0.05, 0.05, 0.6, 0.7]}], "usage": {"credits": 1, "credits_left": 99}}""")
        val lesson = client.submitFormWithBinaryData("/api/extract", formData {
            append("prompt", "p")
            append("images", "photo 1".toByteArray(), Headers.build {
                append(HttpHeaders.ContentType, "image/jpeg")
                append(HttpHeaders.ContentDisposition, "filename=\"page-1.jpg\"")
            })
        }) { page() }.json().jsonObject
        assertEquals("""[{"page":1,"box":[0.05,0.05,0.6,0.7]}]""", lesson["frames"].toString())
        client.post("/api/anki/send") {
            page(); contentType(ContentType.Application.Json)
            setBody("""{"deck": "SVT", "cards": ${lesson["cards"]}, "voice": "", "lesson_id": "${lesson.string("id")}"}""")
        }
        assertEquals(mapOf(1 to listOf(0.05, 0.05, 0.6, 0.7)), anki.media.frames)
    }

    @Test
    fun boxesTurnedAsOnTheComputer() {
        // diagrams.rotate_box([0.1, 0.2, 0.3, 0.5], degrees) on the computer
        assertEquals(listOf(0.5, 0.1, 0.8, 0.3), Diagrams.rotateBox(listOf(0.1, 0.2, 0.3, 0.5), 90))
        assertEquals(listOf(0.7, 0.5, 0.9, 0.8), Diagrams.rotateBox(listOf(0.1, 0.2, 0.3, 0.5), 180))
        assertEquals(listOf(0.2, 0.7, 0.5, 0.9), Diagrams.rotateBox(listOf(0.1, 0.2, 0.3, 0.5), 270))
    }

    @Test
    fun sidewaysPhotosSavedUprightThenTurnedByHand() = app { client ->
        relayAnswers("""{"deck": {"deck": "SVT", "cards": [{"front": "(1) ?", "back": "la bouche", "mask": {"page": 1, "n": 1, "box": [0.1, 0.2, 0.3, 0.5]}}]},
            "turns": [90], "frames": [{"page": 1, "box": [0.1, 0.2, 0.3, 0.5]}], "usage": {"credits": 1, "credits_left": 99}}""")
        val lesson = client.submitFormWithBinaryData("/api/extract", formData {
            append("prompt", "p")
            append("images", "photo 1".toByteArray(), Headers.build {
                append(HttpHeaders.ContentType, "image/jpeg")
                append(HttpHeaders.ContentDisposition, "filename=\"page-1.jpg\"")
            })
        }) { page() }.json().jsonObject
        val id = lesson.string("id")
        // The AI found it turned a quarter: saved upright, its mask and frame with it
        assertEquals("turned 90:photo 1", client.get("/api/lessons/$id/photos/1") { page() }.bodyAsText())
        fun box(of: JsonObject?) = of!!["box"]!!.jsonArray.map { it.jsonPrimitive.content.toDouble() }
        assertEquals(listOf(0.5, 0.1, 0.8, 0.3), box(lesson["cards"]!!.jsonArray[0].jsonObject["mask"]?.jsonObject))
        assertEquals(listOf(0.5, 0.1, 0.8, 0.3), box(lesson["frames"]!!.jsonArray[0].jsonObject))

        // ↻ in the review: a quarter more, by hand
        val turned = client.post("/api/lessons/$id/photos/1/rotate") { page() }.json().jsonObject
        assertEquals("turned 90:turned 90:photo 1", client.get("/api/lessons/$id/photos/1") { page() }.bodyAsText())
        assertEquals(Diagrams.rotateBox(listOf(0.5, 0.1, 0.8, 0.3), 90), box(turned["cards"]!!.jsonArray[0].jsonObject["mask"]?.jsonObject))
        assertEquals(HttpStatusCode.NotFound, client.post("/api/lessons/$id/photos/9/rotate") { page() }.status)
    }

    @Test
    fun theVoicesSpeedAndNoApkg() = app { client ->
        assertEquals("false", client.get("/api/config") { page() }.json().jsonObject["apkg"]!!.jsonPrimitive.content)
        assertEquals("-10%", client.get("/api/admin/settings") { page() }.json().jsonObject.string("tts_rate"))
        client.put("/api/admin/settings") { page(); contentType(ContentType.Application.Json); setBody("""{"tts_rate": "-25%"}""") }
        client.put("/api/admin/settings") { page(); contentType(ContentType.Application.Json); setBody("""{"tts_rate": "+90%"}""") } // not one: ignored
        assertEquals("-25%", client.get("/api/admin/settings") { page() }.json().jsonObject.string("tts_rate"))
        relay.enqueue(MockResponse.Builder().setHeader("Content-Type", "audio/mpeg").body("mp3").build())
        client.get("/api/tts?text=hola&voice=es-ES-Chirp3-HD-Aoede") { page() }
        assertEquals("0.75", json.parseToJsonElement(relay.takeRequest().body!!.utf8()).jsonObject["rate"]!!.jsonPrimitive.content)
    }

    @Test
    fun theLessonsOptionsSentAndItsNotesDeletedWithIt() = app { client ->
        val lesson = client.extract()
        val id = lesson.string("id")
        client.post("/api/anki/send") {
            page(); contentType(ContentType.Application.Json)
            setBody("""{"deck": "D", "cards": ${lesson["cards"]}, "voice": "", "reverse": true, "typing": false, "dictation": true, "lesson_id": "$id"}""")
        }
        assertEquals(Options(reverse = true, dictation = true), anki.options)

        // Its notes counted before deleting it; kept, then deleted with it
        anki.notes[id] = mutableListOf(11L, 12L)
        val found = client.get("/api/lessons/$id/anki-notes") { page() }.json().jsonObject
        assertEquals(listOf("true", "2"), listOf("available", "count").map { found[it]!!.jsonPrimitive.content })
        val gone = client.delete("/api/lessons/$id?anki=true") { page() }.json().jsonObject
        assertEquals(2, gone["anki_deleted"]!!.jsonPrimitive.int)
        assertEquals(listOf(11L, 12L), anki.deleted)
        assertEquals(JsonArray(emptyList()), client.get("/api/lessons") { page() }.json())

        // Without ?anki=true: the lesson alone
        val other = client.extract().string("id")
        anki.notes[other] = mutableListOf(13L)
        assertEquals(0, client.delete("/api/lessons/$other") { page() }.json().jsonObject["anki_deleted"]!!.jsonPrimitive.int)
        assertEquals(listOf(11L, 12L), anki.deleted)
    }

    @Test
    fun aSentLessonReviewedInAnkiDroid() = app { client ->
        assertEquals("true", client.get("/api/config") { page() }.json().jsonObject["review_in_anki"]!!.jsonPrimitive.content)
        val lesson = client.extract()
        client.send(lesson)
        val res = client.post("/api/anki/review") { page(); contentType(ContentType.Application.Json); setBody("""{"deck": "Espagnol::Leçon 5"}""") }
        assertEquals(HttpStatusCode.OK, res.status)
        assertEquals(listOf("Espagnol::Leçon 5"), anki.reviewed)
        val missing = client.post("/api/anki/review") { page(); contentType(ContentType.Application.Json); setBody("""{"deck": "Nope"}""") }
        assertEquals("anki.android_no_deck", missing.json().jsonObject["detail"]!!.jsonObject.string("code"))
    }

    @Test
    fun anAutoVoiceInTheLanguageLearned() = app { client ->
        relayAnswers("""{"deck": {"deck": "Espagnol", "cards": [{"front": "la mère", "back": "la madre"}]}, "turns": [], "back_language": "es-ES", "usage": {"credits": 1, "credits_left": 99}}""")
        relayAnswers(voices)
        val lesson = client.submitFormWithBinaryData("/api/extract", formData {
            append("prompt", "FR → ES")
            append("voice", "auto")
        }) { page("fr") }.json().jsonObject
        assertEquals("es-ES-Chirp3-HD-Aoede", lesson.string("voice")) // the variety asked for, the default voice

        // The pupil's own language: no voice (unless the cards are for writing what is heard)
        relayAnswers("""{"deck": {"deck": "Français", "cards": [{"front": "q", "back": "r"}]}, "turns": [], "back_language": "fr-FR", "usage": {"credits": 1, "credits_left": 98}}""")
        val french = client.submitFormWithBinaryData("/api/extract", formData {
            append("prompt", "p")
            append("voice", "auto")
        }) { page("fr") }.json().jsonObject
        assertEquals("", french.string("voice"))
    }

    private suspend fun HttpClient.send(lesson: JsonObject) = post("/api/anki/send") {
        page(); contentType(ContentType.Application.Json)
        setBody("""{"deck": "Espagnol::Leçon 5", "cards": ${lesson["cards"]}, "voice": "", "lesson_id": "${lesson.string("id")}"}""")
    }

    @Test
    fun ankiDroidAskedForAtTheFirstSend() = app { client ->
        val lesson = client.extract()
        // Not allowed yet: AnkiDroid's dialog, then the cards go in
        anki.permitted = false
        assertEquals(2, client.send(lesson).json().jsonObject["added"]!!.jsonPrimitive.int)
        assertEquals(1, permissionAsked)

        // Refused: said, nothing sent
        anki.permitted = false
        grantPermission = false
        val refused = client.send(lesson)
        assertEquals("anki.android_refused", refused.json().jsonObject["detail"]!!.jsonObject.string("code"))
        assertEquals(1, anki.sent.size)
    }

    @Test
    fun ankiDroidMissingOrNotReady() = app { client ->
        // "Add to Anki" stays offered without AnkiDroid: it's asked for when used
        anki.installed = false
        assertEquals("true", client.get("/api/anki/status") { page() }.json().jsonObject["available"]!!.jsonPrimitive.content)
        val lesson = client.extract()
        val missing = client.send(lesson)
        assertEquals("anki.android_missing", missing.json().jsonObject["detail"]!!.jsonObject.string("code"))
        assertEquals(0, storeOpened) // said, not opened by surprise
        client.post("/api/anki/install") { page() } // the message's button
        assertEquals(1, storeOpened) // its Play Store page
        assertEquals(0, permissionAsked)

        // Installed, never opened: AnkiDroid's error, said
        anki.installed = true
        anki.broken = true
        val failed = client.send(lesson).json().jsonObject["detail"]!!.jsonObject
        assertEquals("anki.android_failed", failed.string("code"))
        assertEquals("no collection", failed["params"]!!.jsonObject.string("detail"))
    }

    @Test
    fun deletedAndUnknownLessons() = app { client ->
        val id = client.extract().string("id")
        client.delete("/api/lessons/$id") { page() }
        val res = client.get("/api/lessons/$id") { page() }
        assertEquals(HttpStatusCode.NotFound, res.status)
        assertEquals("lesson.not_found", res.json().jsonObject["detail"]!!.jsonObject.string("code"))
        assertEquals(HttpStatusCode.NotFound, client.get("/api/lessons/$id/photos/1") { page() }.status)
    }

    // --- The settings page (assets/page/admin.html)

    @Test
    fun theAppsOwnSettingsPage() = app { client ->
        val page = client.get("/admin.html").bodyAsText()
        assertTrue("settings.js" in page) // the app's, not the computer's admin.js
        assertTrue("android.licence.title" in page)
        assertEquals("true", client.get("/api/admin") { page() }.json().jsonObject["allowed"]!!.jsonPrimitive.content)
        // The texts the app's pages use are in every language of the web page
        var own = ""
        for (file in listOf("admin.html", "unreachable.html", "settings.js")) own += client.get("/$file").bodyAsText()
        val names = Regex("""t\(["'](android\.[a-zA-Z.]+)["']""").findAll(own).map { it.groupValues[1] }.toSet()
        assertTrue(names.size > 30)
        val web = File(System.getProperty("notosaurus.web") ?: "../../static")
        for (lang in web.resolve("i18n").listFiles()!!) {
            val messages = json.parseToJsonElement(lang.readText()).jsonObject
            for (name in names) {
                val found = name.split(".").fold<String, kotlinx.serialization.json.JsonElement?>(messages) { at, part -> (at as? JsonObject)?.get(part) }
                assertTrue("${lang.name}: $name", found != null)
            }
        }
    }

    @Test
    fun settingsSavedAndTheKeyNeverGivenBack() = app { client ->
        val shown = client.get("/api/admin/settings") { page() }.json().jsonObject
        assertEquals("•••••••", shown.string("key")) // a short key: all hidden
        assertEquals("0.1.0", shown.string("version"))

        val saved = client.put("/api/admin/settings") {
            page(); contentType(ContentType.Application.Json)
            setBody("""{"key": " nts_new_licence_key ", "instructions": "Léa est en 5e", "card_helps": true, "relay": "http://192.168.1.10:8080/"}""")
        }.json().jsonObject
        assertEquals("nts_…_key", saved.string("key"))
        assertEquals("nts_new_licence_key", prefs[LocalServer.keyOf("http://192.168.1.10:8080")]) // the new relay's
        assertEquals("http://192.168.1.10:8080", prefs[LocalServer.RELAY])
        val config = client.get("/api/config") { page() }.json().jsonObject
        assertEquals("true", config["card_helps"]!!.jsonPrimitive.content)
        assertEquals("false", config["donations"]!!.jsonPrimitive.content) // paid for: no Ko-fi link

        // Only what's given changes
        client.put("/api/admin/settings") { page(); contentType(ContentType.Application.Json); setBody("""{"card_helps": false}""") }
        assertEquals("Léa est en 5e", prefs[LocalServer.INSTRUCTIONS])
        assertEquals("nts_new_licence_key", prefs[LocalServer.keyOf("http://192.168.1.10:8080")])
    }

    @Test
    fun eachRelayKeepsItsLicence() = app { client ->
        // The key saved before keys were per relay: the relay in use then got it
        assertEquals("nts_key", prefs[LocalServer.keyOf(relay.url("/").toString())])
        val settings = client.get("/api/admin/settings") { page() }.json().jsonObject
        val relays = settings["relays"]!!.jsonObject
        assertEquals(LocalServer.REAL_RELAY, relays.string("real"))
        assertEquals(LocalServer.TEST_RELAY, relays.string("test")) // a debug build: the test relay offered

        suspend fun use(url: String, key: String? = null) = client.put("/api/admin/settings") {
            page(); contentType(ContentType.Application.Json)
            setBody(buildString {
                append("""{"relay": "$url"""")
                if (key != null) append(""", "key": "$key"""")
                append("}")
            })
        }.json().jsonObject
        val test = use(LocalServer.TEST_RELAY)
        assertEquals(false, test["has_key"]!!.jsonPrimitive.content.toBoolean()) // its own licence: none yet
        use(LocalServer.TEST_RELAY, "nts_test_licence")
        val real = use(LocalServer.REAL_RELAY, "nts_real_licence")
        assertEquals("nts_…ence", real.string("key"))
        assertEquals("nts_…ence", use(LocalServer.TEST_RELAY).string("key"))
        assertEquals("nts_test_licence", prefs[LocalServer.keyOf(LocalServer.TEST_RELAY)])
        assertEquals("nts_real_licence", prefs[LocalServer.keyOf(LocalServer.REAL_RELAY)])

        // The relay called with its own key
        use(relay.url("/").toString())
        relayAnswers("""{"plan": "test", "credits_left": 10, "daily_left": 5}""")
        client.get("/api/admin/account") { page() }
        assertEquals("Bearer nts_key", relay.takeRequest(5, TimeUnit.SECONDS)!!.headers["Authorization"])
    }

    @Test
    fun standingInstructionsGoToTheAi() = app { client ->
        prefs[LocalServer.INSTRUCTIONS] = "Léa est en 5e"
        client.extract()
        val instructions = relay.takeRequest().multipartRequest().string("instructions")
        assertTrue(instructions.startsWith("Standing instructions, for every lesson:\nLéa est en 5e"))

        prefs[LocalServer.INSTRUCTIONS] = ""
        client.extract()
        assertEquals("", relay.takeRequest().multipartRequest().string("instructions"))
    }

    @Test
    fun theLicencesAccount() = app { client ->
        relayAnswers("""{"plan": "monthly", "credits_left": 1200, "daily_left": 300, "renews_at": "2026-11-06T10:00:00+00:00"}""")
        val account = client.get("/api/admin/account") { page() }.json().jsonObject
        assertEquals(1200, account["credits_left"]!!.jsonPrimitive.int)
        assertEquals("Bearer nts_key", relay.takeRequest().headers["Authorization"])

        relayAnswers("""{"code": "relay.invalid_key", "params": {}}""", code = 401)
        val res = client.get("/api/admin/account") { page() }
        assertEquals("relay.invalid_key", res.json().jsonObject["detail"]!!.jsonObject.string("code"))
    }

    @Test
    fun ankiDroidAndItsPermission() = app { client ->
        assertEquals("true", client.get("/api/admin/anki") { page() }.json().jsonObject["permitted"]!!.jsonPrimitive.content)
        anki.permitted = false
        val asked = client.post("/api/admin/anki/permission") { page() }.json().jsonObject
        assertEquals("true", asked["permitted"]!!.jsonPrimitive.content)
        assertEquals(1, permissionAsked)
        anki.installed = false
        val status = client.get("/api/admin/anki") { page() }.json().jsonObject
        assertEquals("false", status["installed"]!!.jsonPrimitive.content)
    }

    @Test
    fun theLessonsOnThePhone() = app { client ->
        client.extract()
        client.extract()
        fun bytes() = runBlocking { client.get("/api/admin/data") { page() }.json().jsonObject["bytes"]!!.jsonPrimitive.content.toLong() }
        val data = client.get("/api/admin/data") { page() }.json().jsonObject
        assertEquals(2, data["lessons"]!!.jsonPrimitive.int)
        val lessonsOnly = bytes()
        assertTrue(lessonsOnly > 0)

        // A back read aloud (🔊): its sound counted with the lessons
        relay.enqueue(MockResponse.Builder().setHeader("Content-Type", "audio/mpeg").body("x".repeat(1000)).build())
        client.get("/api/tts?text=la%20madre&voice=es-ES-Chirp3-HD-Aoede") { page() }
        assertEquals(lessonsOnly + 1000, bytes())

        // Deleted with them
        assertEquals(2, client.delete("/api/admin/lessons") { page() }.json().jsonObject["deleted"]!!.jsonPrimitive.int)
        assertEquals(JsonArray(emptyList()), client.get("/api/lessons") { page() }.json())
        assertEquals(0L, bytes())
    }

    // --- With my computer

    /** A Notosaurus answering: its /api/lang, then its /api/config (its name, when it gives it). */
    private fun computerAnswers(name: String? = "salon-pc") {
        computer.enqueue(MockResponse.Builder().body("""{"lang": null, "available": ["en", "fr"]}""").build())
        val named = if (name == null) "" else ""","computer_name": "$name""""
        computer.enqueue(MockResponse.Builder().body("""{"version": "1.1.0"$named}""").build())
    }

    private suspend fun HttpClient.connect(address: String) = put("/api/admin/computer") {
        page(); contentType(ContentType.Application.Json); setBody("""{"address": "$address"}""")
    }

    @Test
    fun aComputerFromItsQrCode() = app { client ->
        val qr = "http://127.0.0.1:${computer.port}/?k=token123"
        scanned = qr
        computerAnswers()
        val answer = client.post("/api/admin/computer/scan") { page() }.json().jsonObject
        assertEquals(qr, answer.string("url")) // where the page goes: the computer's page, paired by its token
        assertEquals("/api/lang", computer.takeRequest().url.encodedPath) // checked: a Notosaurus answers
        val config = computer.takeRequest() // its name, asked as a paired phone (the QR code's token)
        assertEquals("/api/config", config.url.encodedPath)
        assertEquals("token123", config.url.queryParameter("k"))
        assertEquals(LocalServer.COMPUTER_MODE, prefs[LocalServer.MODE])
        assertEquals(qr, prefs[LocalServer.COMPUTER])
        assertEquals(1, modeChanges) // the app's shortcuts follow

        val settings = client.get("/api/admin/settings") { page() }.json().jsonObject
        assertEquals("computer", settings.string("mode"))
        assertEquals("http://127.0.0.1:${computer.port}", settings.string("computer_address")) // without its token
        assertEquals("salon-pc", settings.string("computer_name"))

        scanned = null // cancelled: nothing changes
        assertEquals("true", client.post("/api/admin/computer/scan") { page() }.json().jsonObject["cancelled"]!!.jsonPrimitive.content)

        scannerMissing = true // not downloaded yet: said, so the address can be typed instead
        val missing = client.post("/api/admin/computer/scan") { page() }
        assertEquals("computer.scan_unavailable", missing.json().jsonObject["detail"]!!.jsonObject.string("code"))
    }

    @Test
    fun aComputerByItsAddress() = app { client ->
        computerAnswers()
        val answer = client.connect("127.0.0.1:${computer.port}").json().jsonObject
        assertEquals("http://127.0.0.1:${computer.port}/", answer.string("url"))
    }

    @Test
    fun notAComputer() = app { client ->
        val notAUrl = client.connect("Bonjour !")
        assertEquals(HttpStatusCode.BadRequest, notAUrl.status)
        assertEquals("computer.not_a_qr", notAUrl.json().jsonObject["detail"]!!.jsonObject.string("code"))

        computer.enqueue(MockResponse.Builder().code(404).body("<html>a router</html>").build())
        val notNotosaurus = client.connect("http://127.0.0.1:${computer.port}/")
        assertEquals("computer.not_found", notNotosaurus.json().jsonObject["detail"]!!.jsonObject.string("code"))
        assertEquals(null, prefs[LocalServer.COMPUTER]) // nothing kept
        assertEquals(null, prefs[LocalServer.MODE])
    }

    @Test
    fun backToThePhone() = app { client ->
        val noComputer = client.post("/api/admin/mode") { page(); contentType(ContentType.Application.Json); setBody("""{"mode": "computer"}""") }
        assertEquals(HttpStatusCode.BadRequest, noComputer.status)

        computerAnswers()
        client.connect("127.0.0.1:${computer.port}")
        val phone = client.post("/api/admin/mode") { page(); contentType(ContentType.Application.Json); setBody("""{"mode": "phone"}""") }.json().jsonObject
        assertEquals("/", phone.string("url"))
        assertEquals(LocalServer.PHONE_MODE, prefs[LocalServer.MODE])
        assertTrue(prefs[LocalServer.COMPUTER] != null) // kept, to come back to
        val again = client.post("/api/admin/mode") { page(); contentType(ContentType.Application.Json); setBody("""{"mode": "computer"}""") }.json().jsonObject
        assertEquals("http://127.0.0.1:${computer.port}/", again.string("url"))
    }

    @Test
    fun computerAddresses() {
        assertEquals("http://192.168.1.10:8000/?k=abc", LocalServer.computerUrl("192.168.1.10:8000/?k=abc").toString())
        assertEquals("http://192.168.1.10:8000/", LocalServer.computerUrl(" http://192.168.1.10:8000 ").toString())
        assertEquals("https://pc.tailnet.ts.net/", LocalServer.computerUrl("https://pc.tailnet.ts.net").toString())
        assertEquals(null, LocalServer.computerUrl("ftp://pc/"))
        assertEquals(null, LocalServer.computerUrl("bonjour !"))
        assertEquals("http://192.168.1.10:8000", LocalServer.origin(LocalServer.computerUrl("192.168.1.10:8000/?k=abc")!!))
    }

    @Test
    fun aComputerThatDoesntSayItsName() = app { client ->
        computerAnswers(name = null) // an add-on older than computer_name
        client.connect("127.0.0.1:${computer.port}/?k=t")
        assertEquals("", client.get("/api/admin/settings") { page() }.json().jsonObject.string("computer_name"))
    }

    // --- Dictation (🎤)

    private suspend fun HttpClient.dictate(kind: String = "prompt"): HttpResponse {
        val started = post("/api/dictation/start") { page("fr") }
        if (started.status != HttpStatusCode.OK) return started
        return post("/api/dictation/stop") {
            page("fr")
            contentType(ContentType.Application.Json)
            setBody("""{"kind": "$kind"}""")
        }
    }

    @Test
    fun dictationWrittenByTheRelay() = app { client ->
        assertEquals("true", client.get("/api/config") { page() }.json().jsonObject["dictation"]!!.jsonPrimitive.content)
        relayAnswers("""{"text": "Enlève la carte sur el tío.", "usage": {"credits": 1, "credits_left": 99}}""")
        val res = client.dictate("correction")
        assertEquals(HttpStatusCode.OK, res.status)
        assertEquals("Enlève la carte sur el tío.", res.json().jsonObject.string("text"))
        assertFalse(mic.listening)
        val sent = relay.takeRequest(5, TimeUnit.SECONDS)!!
        assertEquals("/v1/transcribe", sent.url.encodedPath)
        assertEquals("correction", sent.multipartRequest().string("kind"))
        assertEquals("French", sent.multipartRequest().string("language"))
        val body = sent.body!!.utf8()
        assertTrue("name=\"audio\"; filename=\"dictation.aac\"" in body && "Content-Type: audio/aac" in body)
        assertTrue(folder.root.resolve("dictation").list().orEmpty().isEmpty()) // the recording isn't kept
    }

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

    @Test
    fun picturesFoundThroughTheRelay() = app { client ->
        relayAnswers("""{"results": [{"source": "pixabay", "id": "42", "title": "fortress", "preview": "data:,", "licence": "Pixabay"}]}""")
        val found = client.post("/api/pictures/search") {
            page(); contentType(ContentType.Application.Json); setBody("""{"subject": "a castle"}""")
        }.json().jsonObject
        assertEquals("42", found["results"]!!.jsonArray[0].jsonObject.string("id"))
        assertEquals("/v1/pictures/search", relay.takeRequest(5, TimeUnit.SECONDS)!!.url.encodedPath)

        val lesson = client.extract()
        relay.takeRequest(5, TimeUnit.SECONDS) // the extraction
        val card = lesson["cards"]!!.jsonArray[0].jsonObject.string("id")
        relay.enqueue(
            MockResponse.Builder().setHeader("Content-Type", "image/jpeg")
                .setHeader(Relay.PICTURE_SOURCE_HEADER, """{"source": "pixabay", "licence": "Pixabay", "page": "https://pixabay.com/photos/42/"}""")
                .body("jpeg of 42").build(),
        )
        val res = client.post("/api/lessons/${lesson.string("id")}/cards/$card/picture/found") {
            page(); contentType(ContentType.Application.Json); setBody("""{"source": "pixabay", "id": "42"}""")
        }.json().jsonObject
        val picture = res["card"]!!.jsonObject.string("picture")
        assertTrue(picture.isNotEmpty())
        assertEquals("https://pixabay.com/photos/42/", res["card"]!!.jsonObject["picture_source"]!!.jsonObject.string("page"))
        val asked = relay.takeRequest(5, TimeUnit.SECONDS)!!
        assertEquals("/v1/pictures/found", asked.url.encodedPath)
        assertEquals("""{"source":"pixabay","id":"42"}""", asked.body!!.utf8())
        assertArrayEquals("jpeg of 42".toByteArray(), client.get("/api/lessons/${lesson.string("id")}/pictures/$picture") { page() }.bodyAsBytes())
    }

    @Test
    fun aFreePictureLookedForFirst() = app { client ->
        relayAnswers("""{"deck": {"deck": "Espagnol", "cards": [
            {"front": "Comment dit-on ?", "back": "el perro", "picture_prompt": "a dog sitting", "picture_search": "dog"}]},
            "turns": [], "usage": {"credits": 1, "credits_left": 99}}""")
        val lesson = client.submitFormWithBinaryData("/api/extract", formData { append("prompt", "p") }) { page() }.json().jsonObject
        relay.takeRequest(5, TimeUnit.SECONDS) // the extraction
        val asked = mutableListOf<JsonObject>()
        relay.dispatcher = object : mockwebserver3.Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                asked += json.parseToJsonElement(request.body!!.utf8()).jsonObject
                return MockResponse.Builder().setHeader("Content-Type", "image/jpeg")
                    .setHeader(Relay.PICTURE_SOURCE_HEADER, """{"source": "commons", "licence": "CC0", "page": "https://commons.wikimedia.org/wiki/File:Dog.jpg"}""")
                    .body("jpeg").build()
            }
        }
        val id = lesson.string("id")
        val drawn = client.post("/api/lessons/$id/pictures") { page() }.json().jsonObject
        val source = drawn["lesson"]!!.jsonObject["cards"]!!.jsonArray[0].jsonObject["picture_source"]!!.jsonObject
        assertEquals("https://commons.wikimedia.org/wiki/File:Dog.jpg", source.string("page")) // kept with the card
        assertEquals("dog", asked[0].string("search"))
        assertEquals("Comment dit-on ? → el perro", asked[0].string("context"))

        // Always drawn: in the settings
        client.put("/api/admin/settings") { page(); contentType(ContentType.Application.Json); setBody("""{"picture_find": false}""") }
        assertEquals("false", client.get("/api/admin/settings") { page() }.json().jsonObject["picture_find"]!!.jsonPrimitive.content)
        val card = lesson["cards"]!!.jsonArray[0].jsonObject.string("id")
        client.delete("/api/lessons/$id/cards/$card/picture") { page() }
        val again = client.put("/api/lessons/$id") {
            page(); contentType(ContentType.Application.Json)
            setBody(buildJsonObject { put("cards", JsonArray(listOf(lesson["cards"]!!.jsonArray[0]))) }.toString())
        }
        assertEquals(HttpStatusCode.OK, again.status)
        client.post("/api/lessons/$id/pictures") { page() }
        assertFalse("search" in asked.last())
    }

    @Test
    fun drawDecidesAFigureOrAPicture() = app { client ->
        relayAnswers("""{"deck": {"deck": "Maths", "cards": [{"front": "La réunion de A et B ?", "back": "\\\\(A \\\\cup B\\\\)"}]},
            "turns": [], "usage": {"credits": 1, "credits_left": 99}}""")
        val lesson = client.submitFormWithBinaryData("/api/extract", formData { append("prompt", "p") }) { page() }.json().jsonObject
        relay.takeRequest(5, TimeUnit.SECONDS) // the extraction
        val asked = mutableListOf<Pair<String, String>>()
        relay.dispatcher = object : mockwebserver3.Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                asked += request.url.encodedPath to request.body!!.utf8()
                return when (request.url.encodedPath) {
                    "/v1/plan-picture" -> MockResponse.Builder().body(
                        """{"kind": "figure", "description": "Deux ensembles, leur réunion hachurée", "search": "", "usage": {"credits": 1, "credits_left": 98}}""",
                    ).build()
                    "/v1/figure" -> MockResponse.Builder().body("""{"svg": "<svg/>", "usage": {"credits": 1, "credits_left": 97}}""").build()
                    else -> MockResponse.Builder().body("""{"results": [], "words": "union Venn diagram"}""").build()
                }
            }
        }
        val id = lesson.string("id")
        val card = lesson["cards"]!!.jsonArray[0].jsonObject.string("id")
        val drawn = client.post("/api/lessons/$id/cards/$card/picture/draw") {
            page("fr"); contentType(ContentType.Application.Json); setBody("""{"subject": ""}""")
        }.json().jsonObject["card"]!!.jsonObject
        assertEquals("Deux ensembles, leur réunion hachurée", drawn.string("figure"))
        assertTrue(drawn.string("picture").endsWith(".svg"))
        val plan = json.parseToJsonElement(asked[0].second).jsonObject
        assertEquals("/v1/plan-picture", asked[0].first)
        assertEquals("French", plan.string("language"))
        assertEquals("/v1/figure", asked[1].first)

        client.post("/api/pictures/search") {
            page(); contentType(ContentType.Application.Json); setBody("""{"subject": "la réunion", "context": "La réunion ? → A ∪ B"}""")
        }
        val search = json.parseToJsonElement(asked.last().second).jsonObject
        assertEquals("true", search["translate"]!!.jsonPrimitive.content) // written in any language
        assertEquals("La réunion ? → A ∪ B", search.string("context"))
    }
}
