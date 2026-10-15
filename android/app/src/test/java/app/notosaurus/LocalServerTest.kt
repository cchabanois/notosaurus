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
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
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

/**
 * The page's /api, answered on the phone: called as the page calls them (app.js),
 * with a fake relay (MockWebServer) and a fake AnkiDroid. The page's files are the
 * repository's static/ (the notosaurus.web system property, set by Gradle).
 */
class LocalServerTest {
    @get:Rule val folder = TemporaryFolder()
    private val relay = MockWebServer()
    private val anki = FakeAnki()
    private val play = FakePlay()

    /** Google Play: the offer, a purchase's token (null: given up), the subscriptions owned. */
    private class FakePlay : SubscriptionStore {
        var offer: Offer? = Offer("4,99 €", 7)
        var buying: String? = "token-1"
        var owned = listOf<String>()
        var managed = 0
        override suspend fun offer() = offer
        override suspend fun subscribe() = buying
        override suspend fun owned() = owned
        override fun manage() { managed++ }
    }
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
            return Sent(added = deck.cards.size, duplicates = 0, skipped = 0, deck = deck.deck, notes = sentNotes)
        }
        var sentNotes: Map<String, Long> = emptyMap() // the notes the cards updated
        override fun leftovers(lesson: String, keep: Set<Long>) =
            notes[lesson].orEmpty().filter { it !in keep }.map { Leftover(it, "note $it", "D") }
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
            subscriptions = play,
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

    /** The relay's /v1/card-picture, as the core: the card's picture decided (`decide`, from the
     * request), then a figure (an SVG) or a picture (a "JPEG" holding the request). */
    private fun cardPicture(request: RecordedRequest, decide: (JsonObject) -> Map<String, String> = { emptyMap() }): MockResponse {
        val asked = json.parseToJsonElement(request.body!!.utf8()).jsonObject
        val card = JsonObject(asked["card"]!!.jsonObject + decide(asked).mapValues { JsonPrimitive(it.value) })
        val figure = card.string("figure").isNotBlank()
        if (!figure && asked["draw"]?.jsonPrimitive?.content == "false") { // as the core: no free one fits, not drawn
            val params = buildJsonObject { put("description", card.string("picture_prompt")); put("search", card.string("picture_search")) }
            return MockResponse.Builder().code(409).body(buildJsonObject { put("code", "picture.needs_drawing"); put("params", params) }.toString()).build()
        }
        val data = if (figure) "<svg/>" else "jpeg $asked"
        return MockResponse.Builder().body(buildJsonObject {
            put("card", card)
            put("data", Base64.getEncoder().encodeToString(data.toByteArray()))
            put("media_type", if (figure) "image/svg+xml" else "image/jpeg")
            put("usage", buildJsonObject { put("credits", 1); put("credits_left", 97) })
        }.toString()).build()
    }

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
        // Alpine and KaTeX, shipped too (static/vendor): nothing from elsewhere
        assertEquals(HttpStatusCode.OK, client.get("/vendor/alpinejs/cdn.min.js").status)
        assertEquals(HttpStatusCode.OK, client.get("/vendor/katex/katex.min.css").status)
    }

    @Test
    fun languagesAndPrompts() = app { client ->
        val lang = client.get("/api/lang") { page() }.json().jsonObject
        val available = lang["available"]!!.jsonArray.map { it.jsonPrimitive.content }
        assertTrue("en" in available && "fr" in available)
        assertEquals("Français", lang["names"]!!.jsonObject.string("fr"))

        // Notosaurus's prompts in the page's language, "Automatic" first
        val prompts = client.get("/api/prompts") { page("fr") }.json().jsonArray.map { it.jsonObject }
        assertEquals(20, prompts.size) // app/prompts.py BUILTIN
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
        val all = client.get("/api/prompts") { page() }.json().jsonArray.map { it.jsonObject }
        val mine = all.filter { it["builtin"]!!.jsonPrimitive.content != "true" } // after Notosaurus's, however many
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
    fun aLessonsNextPageAddsItsCards() = app { client ->
        val lesson = client.extract()
        relay.takeRequest()
        val id = lesson.string("id")
        val before = lesson["cards"]!!.jsonArray.map { it.jsonObject }

        // Days later, page 3: only it goes to the relay, with the cards made already
        relayAnswers("""{"deck": {"deck": "Autre", "cards": [{"front": "le grand-père", "back": "el abuelo",
            "mask": {"page": 1, "n": 1, "box": [0.1, 0.1, 0.2, 0.2]}}]}, "turns": [0],
            "frames": [{"page": 1, "box": [0, 0, 1, 1]}], "usage": {"credits": 2, "credits_left": 95}}""")
        val done = client.submitFormWithBinaryData("/api/lessons/$id/complete", formData {
            append("images", "photo 3".toByteArray(), Headers.build {
                append(HttpHeaders.ContentType, "image/jpeg")
                append(HttpHeaders.ContentDisposition, "filename=\"page-3.jpg\"")
            })
            append("prompt", "FR → ES")
        }) { page() }.json().jsonObject
        val asked = relay.takeRequest()
        assertEquals(listOf("la mère", "le père"), asked.multipartRequest()["existing"]!!.jsonArray.map { it.jsonPrimitive.content })
        assertEquals(1, asked.body!!.utf8().split("filename=").size - 1) // the new page only

        val cards = done["cards"]!!.jsonArray.map { it.jsonObject }
        assertEquals(before, cards.take(2)) // untouched, ids included
        assertEquals("le grand-père", cards[2].string("front"))
        assertTrue(cards[2].string("id").isNotEmpty())
        assertEquals("3", cards[2]["mask"]!!.jsonObject["page"]!!.jsonPrimitive.content) // its page among the lesson's
        assertEquals("3", done["frames"]!!.jsonArray.last().jsonObject["page"]!!.jsonPrimitive.content)
        assertEquals(lesson.string("deck"), done.string("deck")) // the lesson's, not the AI's
        assertEquals(3, done["photo_count"]!!.jsonPrimitive.int)
        assertArrayEquals("photo 3".toByteArray(), client.get("/api/lessons/$id/photos/3") { page() }.bodyAsBytes())

        // Nothing to read, or one page too many
        val none = client.submitFormWithBinaryData("/api/lessons/$id/complete", formData { append("prompt", "p") }) { page() }
        assertEquals(HttpStatusCode.BadRequest, none.status)
    }

    @Test
    fun aLessonsNextPagesKeepTheirDiagramAndTexts() = app { client ->
        val lesson = client.extract() // 2 photos, no text kept
        relay.takeRequest()
        val id = lesson.string("id")
        suspend fun next(texts: String): JsonObject {
            // A label on the new pages' 2nd photo, its diagram's frame on their 1st
            relayAnswers("""{"deck": {"deck": "Autre", "cards": [{"front": "Label 1", "back": "le cœur",
                "mask": {"page": 2, "n": 1, "box": [0.1, 0.2, 0.3, 0.25]}}]}, "turns": [0, 0],
                "frames": [{"page": 1, "box": [0, 0, 1, 0.8]}], "usage": {"credits": 2, "credits_left": 95}}""")
            val done = client.submitFormWithBinaryData("/api/lessons/$id/complete", formData {
                listOf("photo a", "photo b").forEachIndexed { i, photo ->
                    append("images", photo.toByteArray(), Headers.build {
                        append(HttpHeaders.ContentType, "image/jpeg")
                        append(HttpHeaders.ContentDisposition, "filename=\"new-${i + 1}.jpg\"")
                    })
                }
                append("prompt", "FR → ES")
                append("page_texts", texts)
            }) { page() }.json().jsonObject
            relay.takeRequest()
            return done
        }
        fun JsonObject.pages(key: String, field: String? = null) = this[key]!!.jsonArray.mapNotNull { item ->
            (if (field == null) item.jsonObject else item.jsonObject[field] as? JsonObject)?.get("page")?.jsonPrimitive?.int
        }
        fun JsonObject.texts() = this["page_texts"]!!.jsonArray.map { it.jsonPrimitive.content }

        // Pages 3 and 4, a PDF page with text then a photo: "" for the lesson's photos before it
        var done = next("""["page 3", ""]""")
        assertEquals(listOf(4), done.pages("cards", "mask")) // the new pages' 2nd: the lesson's 4th
        assertEquals(listOf(3), done.pages("frames"))
        assertEquals(listOf("", "", "page 3", ""), done.texts())
        assertEquals(4, done["photo_count"]!!.jsonPrimitive.int)

        // Pages 5 and 6 without text: the texts stay, the earlier diagram where it was
        done = next("""["", ""]""")
        assertEquals(listOf(4, 6), done.pages("cards", "mask"))
        assertEquals(listOf(3, 5), done.pages("frames"))
        assertEquals(listOf("", "", "page 3", ""), done.texts())
        assertEquals(done, client.get("/api/lessons/$id") { page() }.json().jsonObject) // as saved
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
        assertEquals("true", request["fun_facts"]!!.jsonPrimitive.content) // the settings', on at first
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
        relayAnswers("""{"deck": "Espagnol::Leçon 5", "cards": [${cards[0]}, {"front": "le frère", "back": "el hermano"}], "summary": "Une carte remplacée.", "reverse": "off", "typing": "on", "usage": {"credits": 2, "credits_left": 95}}""")
        val res = client.post("/api/lessons/$id/revise") {
            page("fr"); contentType(ContentType.Application.Json)
            setBody("""{"deck": "Espagnol::Leçon 5", "cards": $cards, "voice": "", "reverse": true, "dictation": true, "instruction": "remplace le père par le frère"}""")
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
        // How the cards are asked: as the correction said ("off", "on"), the others as they were
        val saved = res["lesson"]!!.jsonObject
        assertEquals(listOf("false", "true", "true"), listOf("reverse", "typing", "dictation").map { saved[it]!!.jsonPrimitive.content })
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
    fun aCardReportedToTheRelay() = app { client ->
        val lesson = client.extract()
        relay.takeRequest()
        relayAnswers("""{"received": true}""")
        val res = client.post("/api/lessons/${lesson.string("id")}/report") {
            page(); contentType(ContentType.Application.Json)
            setBody("""{"kind": "card", "reason": "wrong", "comment": "", "content": "Front: la mère\nBack: la madre", "picture": "", "deck": "not sent"}""")
        }.json().jsonObject
        assertEquals("true", res["received"]!!.jsonPrimitive.content)
        val sent = relay.takeRequest()
        assertEquals("/v1/report", sent.url.encodedPath)
        val request = json.parseToJsonElement(sent.body!!.utf8()).jsonObject
        assertEquals("wrong", request.string("reason"))
        assertEquals("Front: la mère\nBack: la madre", request.string("content"))
        assertEquals(lesson.string("prompt"), request.string("prompt")) // the lesson's instructions, from the phone
        assertFalse("deck" in request) // only the report's fields
    }

    @Test
    fun whatTheRelayTellsForNow() = app { client ->
        relayAnswers(
            """{"plan": "monthly", "credits_left": 10, "daily_left": 5, "latest": "0.2.0", "disabled": ["anki.send", "anki.move", "lesson.complete"],
            "notice": {"id": "n1", "level": "warning", "texts": {"fr": "On répare", "en": "Fixing it"}}}""",
        )
        val switches = client.get("/api/switches") { page("fr") }.json().jsonObject
        assertEquals("On répare", switches["notice"]!!.jsonObject.string("text"))
        assertEquals("warning", switches["notice"]!!.jsonObject.string("level"))
        assertEquals(listOf("anki.send", "anki.move", "lesson.complete"), switches["disabled"]!!.jsonArray.map { it.jsonPrimitive.content })
        assertEquals("true", switches["update"]!!.jsonPrimitive.content) // 0.2.0 after this 0.1.0
        assertTrue(switches.string("store").endsWith("id=app.notosaurus"))

        // Turned off: refused, said so
        val lesson = client.extract()
        relay.takeRequest(5, TimeUnit.SECONDS) // /v1/account
        relay.takeRequest(5, TimeUnit.SECONDS) // the extraction
        val send = client.post("/api/anki/send") {
            page(); contentType(ContentType.Application.Json)
            setBody("""{"deck": "D", "cards": ${lesson["cards"]}, "voice": "", "lesson_id": "${lesson.string("id")}"}""")
        }
        assertEquals(HttpStatusCode.BadRequest, send.status)
        assertEquals("app.feature_off", send.json().jsonObject["detail"]!!.jsonObject.string("code"))
        assertTrue(anki.sent.isEmpty())

        // The relay unreachable: the last ones told stay (offline, still off); another language: English
        relayAnswers("", 503)
        val offline = client.get("/api/switches") { page("de") }.json().jsonObject
        assertEquals("Fixing it", offline["notice"]!!.jsonObject.string("text"))
        assertEquals(3, offline["disabled"]!!.jsonArray.size)

        // Turned on again: sent, its cards not moved while anki.move is off
        relayAnswers("""{"plan": "monthly", "credits_left": 10, "daily_left": 5, "disabled": ["anki.move"]}""")
        val again = client.get("/api/switches") { page() }.json().jsonObject
        assertEquals(JsonNull, again["notice"])
        assertEquals("false", again["update"]!!.jsonPrimitive.content)
        client.post("/api/anki/send") {
            page(); contentType(ContentType.Application.Json)
            setBody("""{"deck": "D", "cards": ${lesson["cards"]}, "voice": "", "lesson_id": "${lesson.string("id")}"}""")
        }
        assertEquals(false, anki.options?.move)
    }

    @Test
    fun aLessonCopiedForAnotherChild() = app { client ->
        val kids = """[{"id": "jules", "name": "Jules", "grade": "5e", "decks": "Jules::5e"}, {"id": "mathilde", "name": "Mathilde", "grade": "3e", "decks": "Mathilde::3e"}]"""
        client.put("/api/children") { page(); contentType(ContentType.Application.Json); setBody(kids) }
        relayAnswers("""{"deck": {"deck": "Anglais::Food", "cards": [{"front": "le pain", "back": "bread"}]}, "turns": [], "usage": {"credits": 1, "credits_left": 99}}""")
        val lesson = client.submitFormWithBinaryData("/api/extract", formData {
            append("prompt", "FR → EN")
            append("child", "jules")
        }) { page() }.json().jsonObject
        relay.takeRequest(5, TimeUnit.SECONDS)
        val copy = client.post("/api/lessons/${lesson.string("id")}/copy") {
            page(); contentType(ContentType.Application.Json); setBody("""{"child": "mathilde"}""")
        }.json().jsonObject
        assertEquals("Mathilde::3e::Anglais::Food", copy.string("deck"))
        assertEquals("mathilde", copy.string("child"))
        assertTrue(copy.string("id") != lesson.string("id"))
        val ids = { l: JsonObject -> l["cards"]!!.jsonArray.map { it.jsonObject.string("id") }.toSet() }
        assertTrue((ids(copy) intersect ids(lesson)).isEmpty()) // other notes in AnkiDroid
        assertEquals(2, client.get("/api/lessons") { page() }.json().jsonArray.size)
        val gone = client.post("/api/lessons/${lesson.string("id")}/copy") {
            page(); contentType(ContentType.Application.Json); setBody("""{"child": "nobody"}""")
        }
        assertEquals("children.not_found", gone.json().jsonObject["detail"]!!.jsonObject.string("code"))
    }

    @Test
    fun aLessonForAChild() = app { client ->
        val jules = """{"id": "jules", "name": "Jules", "grade": "5e", "decks": "Jules::{classe}", "instructions": "Peu de cartes."}"""
        val saved = client.put("/api/children") { page(); contentType(ContentType.Application.Json); setBody("[$jules]") }.json().jsonArray
        assertEquals("Jules", saved.single().jsonObject.string("name"))
        val twice = client.put("/api/children") { page(); contentType(ContentType.Application.Json); setBody("[$jules, $jules]") }
        assertEquals("children.same_id", twice.json().jsonObject["detail"]!!.jsonObject.string("code"))

        relayAnswers("""{"deck": {"deck": "Anglais::5ème::Food", "cards": [{"front": "le pain", "back": "bread"}]}, "turns": [], "usage": {"credits": 1, "credits_left": 99}}""")
        val lesson = client.submitFormWithBinaryData("/api/extract", formData {
            append("prompt", "FR → EN")
            append("child", "jules")
        }) { page() }.json().jsonObject
        assertEquals("Jules::5e::Anglais::Food", lesson.string("deck")) // in its decks, the class not twice
        assertEquals("jules", lesson.string("child"))
        val asked = relay.takeRequest(5, TimeUnit.SECONDS)!!.multipartRequest()
        assertTrue("5e" in asked.string("instructions") && "Peu de cartes." in asked.string("instructions"))
        assertFalse("Jules" in asked.toString()) // its name never to the AI

        // Another lesson: the decks the AI may reuse, without the child's levels
        relayAnswers("""{"deck": {"deck": "Anglais::Food", "cards": [{"front": "le lait", "back": "milk"}]}, "turns": [], "usage": {"credits": 1, "credits_left": 98}}""")
        client.submitFormWithBinaryData("/api/extract", formData { append("prompt", "FR → EN"); append("child", "jules") }) { page() }
        val second = relay.takeRequest(5, TimeUnit.SECONDS)!!.multipartRequest()
        assertEquals(listOf("Anglais::Food"), second["decks"]!!.jsonArray.map { it.jsonPrimitive.content })

        // Corrected: the AI sees the deck without the child's levels, which are put back
        relayAnswers("""{"deck": "Anglais::Food", "cards": [{"front": "le pain", "back": "bread"}], "summary": "ok", "usage": {"credits": 1, "credits_left": 97}}""")
        val revised = client.post("/api/lessons/${lesson.string("id")}/revise") {
            page(); contentType(ContentType.Application.Json)
            setBody("""{"deck": "Jules::5e::Anglais::Food", "cards": ${lesson["cards"]}, "instruction": "ok"}""")
        }.json().jsonObject
        assertEquals("Jules::5e::Anglais::Food", revised["lesson"]!!.jsonObject.string("deck"))
        val sent = relay.takeRequest(5, TimeUnit.SECONDS)!!.multipartRequest()
        assertEquals("Anglais::Food", sent["deck"]!!.jsonObject.string("deck"))
    }

    @Test
    fun aChildsDecks() {
        val jules = Child("jules", "Jules", "5e", "Jules::{classe}")
        assertEquals("Jules::5e::Maths", Children.deckFor(jules, "Maths"))
        assertEquals("Jules::5e::Maths", Children.deckFor(jules, "jules::5ème::Maths"))
        assertEquals("Maths", Children.deckFor(Child("m", "M"), "Maths"))
        assertEquals("Jules::5e" to "Maths::Fractions", Children.splitDeck("Jules::5e::Maths::Fractions", listOf(jules)))
        assertEquals("" to "Maths", Children.splitDeck("Maths", listOf(jules)))
        assertFalse("Jules" in Children.forAi(Child("jules", "Jules", "5e", instructions = "Lent.")))
        // The decks the AI may reuse: the child's own and no one's, never another child's
        val mathilde = Child("mathilde", "Mathilde", "3e", "Mathilde")
        val decks = listOf("Jules::5e::Anglais::Food", "Mathilde::SVT::La cellule", "Maths::Fractions")
        assertEquals(listOf("Anglais::Food", "Maths::Fractions"), Children.decksForAi(decks, listOf(jules, mathilde), jules))
        assertEquals(listOf("Maths::Fractions"), Children.decksForAi(decks, listOf(jules, mathilde), null))
    }

    @Test
    fun versionsCompared() {
        assertTrue(Switches.newer("1.10.0", "1.9.2"))
        assertTrue(Switches.newer("1.2", "1.1.9"))
        assertFalse(Switches.newer("1.2.0", "1.2.0"))
        assertFalse(Switches.newer("1.2.0", "1.3.0-debug"))
        assertFalse(Switches.newer("", "1.0.0"))
        assertFalse(Switches.newer("soon", "1.0.0"))
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

        // A dictation: its sentence, then the word
        // Each line read on its own (a natural voice makes words up from a lone word then a sentence), joined
        for (part in listOf("<sentence>", "<lait>")) {
            relay.enqueue(MockResponse.Builder().setHeader("Content-Type", "audio/mpeg").body(part).build())
        }
        val dictated = """[{"front": "Le chat boit du … (une boisson)", "back": "lait"}]"""
        client.post("/api/anki/send") {
            page(); contentType(ContentType.Application.Json)
            setBody("""{"deck": "Dictée", "cards": $dictated, "voice": "es-ES-Chirp3-HD-Aoede", "lesson_id": "", "dictation": true}""")
        }
        assertEquals(setOf("Le chat boit du lait.\nlait"), anki.sounds.keys) // what's in brackets not read
        assertEquals("<sentence><lait>", anki.sounds.values.single().readText())
        val read = (1..3).map { json.parseToJsonElement(relay.takeRequest(5, TimeUnit.SECONDS)!!.body!!.utf8()).jsonObject.string("text") }
        assertEquals(listOf("Le chat boit du lait.", "lait"), read.takeLast(2)) // after el padre's
        assertFalse(anki.options.dictationOnly)

        // The dictation alone (the built-in Dictation): its sound the same, no front → back card
        client.post("/api/anki/send") {
            page(); contentType(ContentType.Application.Json)
            setBody("""{"deck": "Dictée", "cards": $dictated, "voice": "es-ES-Chirp3-HD-Aoede", "lesson_id": "", "dictation_only": true}""")
        }
        assertTrue(anki.options.dictation && anki.options.dictationOnly)
        assertEquals(setOf("Le chat boit du lait.\nlait"), anki.sounds.keys)
    }

    @Test
    fun whatTheSoundSays() {
        fun card(front: String, back: String) = Card(front = front, back = back)
        assertEquals("Le chat boit du lait.\nlait", Speech.spoken(card("Le chat boit du ….", "lait"), dictation = true))
        assertEquals("Le pré est vert.\nvert", Speech.spoken(card("Le pré est ___", "vert"), dictation = true)) // its full stop added
        assertEquals("lait", Speech.spoken(card("Le chat boit du ….", "lait"), dictation = false)) // not a dictation
        assertEquals("la madre", Speech.spoken(card("la mère", "la madre"), dictation = true)) // no blank
        assertEquals("Ça coûte $1.\n$1", Speech.spoken(card("Ça coûte ...", "$1"), dictation = true)) // as written
    }

    @Test
    fun theBacksSpeed() { // as the computer's (test_prompts.test_the_backs_speed)
        assertEquals("-25%", Speech.rate("-25%", "", foreign = true, dictation = false))
        assertEquals("-25%", Speech.rate("-25%", "", foreign = false, dictation = true)) // time to write
        assertEquals("+0%", Speech.rate("-25%", "", foreign = false, dictation = false)) // a history lesson
        assertEquals("+0%", Speech.rate("-25%", "normal", foreign = true, dictation = false))
        assertEquals("-10%", Speech.rate("+0%", "slow", foreign = false, dictation = false)) // asked: slowed all the same
        assertEquals("+0%", Speech.rate("+0%", "", foreign = true, dictation = true)) // the settings don't slow
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

        // The missing ones drawn by the relay (/v1/card-picture): a picture and a figure. Another
        // subject written for a picture: the relay's AI plans it (a picture, as written)
        relay.dispatcher = object : mockwebserver3.Dispatcher() {
            override fun dispatch(request: RecordedRequest) = when (request.url.encodedPath) {
                "/v1/card-picture" -> cardPicture(request) { asked ->
                    asked.string("asked").let { if (it.isEmpty()) emptyMap() else mapOf("picture_prompt" to it) }
                }
                else -> MockResponse.Builder().code(404).build()
            }
        }
        // Not drawn without a yes: the picture listed, the figure (cheap) drawn
        val asked = client.post("/api/lessons/$id/pictures") {
            page(); contentType(ContentType.Application.Json); setBody("""{"draw": false}""")
        }.json().jsonObject
        assertEquals(listOf(apple), asked["to_draw"]!!.jsonArray.map { it.jsonPrimitive.content })
        val drawn = client.post("/api/lessons/$id/pictures") {
            page(); contentType(ContentType.Application.Json); setBody("""{"draw": true}""")
        }.json().jsonObject
        assertEquals(0, drawn["failures"]!!.jsonPrimitive.int)
        assertEquals(0, drawn["to_draw"]!!.jsonArray.size)
        val cards = drawn["lesson"]!!.jsonObject["cards"]!!.jsonArray.map { it.jsonObject }
        val (picture, figure) = cards.take(2).map { it.string("picture") }
        assertTrue(picture.matches(Regex("picture-$apple-[0-9a-f]{8}\\.jpg")))
        assertTrue(figure.matches(Regex("picture-$triangle-[0-9a-f]{8}\\.svg")))
        assertEquals("", cards[2].string("picture"))
        assertTrue(client.get("/api/lessons/$id/pictures/$picture") { page() }.bodyAsText().contains("\"fresh\":false"))
        val svg = client.get("/api/lessons/$id/pictures/$figure") { page() }
        assertEquals("<svg/>", svg.bodyAsText())
        assertTrue(svg.headers["Content-Security-Policy"]!!.startsWith("default-src 'none'"))

        // "✨ Image" with another subject: decided (a picture: its words, nothing drawn), then drawn
        // when the user says yes: fresh, the old file gone
        val made = client.post("/api/lessons/$id/cards/$apple/picture/make") {
            page(); contentType(ContentType.Application.Json); setBody("""{"subject": "a red apple"}""")
        }.json().jsonObject
        assertEquals("a red apple", made["card"]!!.jsonObject.string("picture_prompt"))
        assertEquals("a red apple", made.string("search"))
        val again = client.post("/api/lessons/$id/cards/$apple/picture/draw") { page() }.json().jsonObject["card"]!!.jsonObject
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
        // A voice chosen per language variety (an empty one not kept)
        val voices = """{"voices": {"es-ES": "es-ES-Chirp3-HD-Puck", "en-GB": ""}}"""
        client.put("/api/admin/settings") { page(); contentType(ContentType.Application.Json); setBody(voices) }
        val chosen = client.get("/api/admin/settings") { page() }.json().jsonObject["voices"]!!.jsonObject
        assertEquals(mapOf("es-ES" to "es-ES-Chirp3-HD-Puck"), chosen.mapValues { it.value.jsonPrimitive.content })
        relay.enqueue(MockResponse.Builder().setHeader("Content-Type", "audio/mpeg").body("mp3").build())
        client.get("/api/tts?text=hola&voice=es-ES-Chirp3-HD-Aoede") { page() }
        assertEquals("0.75", json.parseToJsonElement(relay.takeRequest().body!!.utf8()).jsonObject["rate"]!!.jsonPrimitive.content)
    }

    @Test
    fun aSubscriptionBoughtThenRestored() = app { client ->
        val offered = client.get("/api/admin/subscription") { page() }.json().jsonObject
        assertEquals("4,99 €", offered["offer"]!!.jsonObject.string("price"))
        assertEquals(7, offered["offer"]!!.jsonObject["trial_days"]!!.jsonPrimitive.int)

        // Bought: the relay checks the purchase and answers its key, kept for this relay
        relayAnswers("""{"key": "nts_from_play", "account": {"plan": "trial", "credits_left": 1000, "daily_left": 300,
            "renews_at": "2026-10-18T10:00:00+00:00", "ends_at": "2026-10-18T10:00:00+00:00"}}""")
        val bought = client.post("/api/admin/subscription/subscribe") { page() }.json().jsonObject
        assertEquals("trial", bought.string("plan"))
        val asked = relay.takeRequest(5, TimeUnit.SECONDS)!!
        assertEquals("/v1/subscribe", asked.url.encodedPath)
        val sent = json.parseToJsonElement(asked.body!!.utf8()).jsonObject
        assertEquals(listOf("token-1", PlayStore.PRODUCT), listOf(sent.string("purchase_token"), sent.string("product_id")))
        assertEquals("nts_from_play", prefs[LocalServer.keyOf(local.relayUrl())])

        // Given up on Google Play's screen: nothing changes
        play.buying = null
        assertEquals("true", client.post("/api/admin/subscription/subscribe") { page() }.json().jsonObject["cancelled"]!!.jsonPrimitive.content)

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
        play.offer = null
        assertEquals(JsonNull, client.get("/api/admin/subscription") { page() }.json().jsonObject["offer"])
    }

    @Test
    fun pageTextsOnePerPhotoOrNone() {
        assertEquals(listOf("", "page 2"), Generation.pageTexts("""["", "page 2"]""", 2).map { it.jsonPrimitive.content })
        // Not one per photo, not strings, not JSON, none: no texts (never a page's text on another photo)
        for (raw in listOf("""["page 1"]""", """["a", "b", "c"]""", """[1, 2]""", "{}", "not json", "", null)) {
            assertEquals(raw, 0, Generation.pageTexts(raw, 2).size)
        }
    }

    @Test
    fun theWelcomeAcceptedOnce() = app { client ->
        val before = client.get("/api/config") { page() }.json().jsonObject
        assertEquals(LocalServer.WELCOME_VERSION, before["welcome"]!!.jsonPrimitive.int)
        assertFalse(before["welcome_accepted"]!!.jsonPrimitive.content.toBoolean())
        client.post("/api/welcome") { page() }
        assertTrue(client.get("/api/config") { page() }.json().jsonObject["welcome_accepted"]!!.jsonPrimitive.content.toBoolean())
    }

    @Test
    fun notesNoCardHasAnyMoreOfferedThenDeleted() = app { client ->
        val lesson = client.extract()
        val id = lesson.string("id")
        anki.notes[id] = mutableListOf(21L, 22L, 23L) // its notes in AnkiDroid
        anki.sentNotes = mapOf("card" to 21L) // the one its cards still have
        val sent = client.post("/api/anki/send") {
            page(); contentType(ContentType.Application.Json)
            setBody("""{"deck": "D", "cards": ${lesson["cards"]}, "voice": "", "lesson_id": "$id"}""")
        }.json().jsonObject
        val left = sent["leftovers"]!!.jsonArray.map { it.jsonObject }
        assertEquals(listOf(22L, 23L), left.map { it["id"]!!.jsonPrimitive.long })
        assertEquals("note 22", left[0].string("text"))

        // Deleted when asked: those only, never the card's own note nor an unknown one
        val done = client.post("/api/lessons/$id/anki-notes/delete") {
            page(); contentType(ContentType.Application.Json); setBody("""{"ids": [22, 23, 21, 99]}""")
        }.json().jsonObject
        assertEquals(2, done["deleted"]!!.jsonPrimitive.int)
        assertEquals(listOf(22L, 23L), anki.deleted)
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
        // The relay's voices, read once
        relayAnswers(voices.dropLast(1) + """, {"voice": "fr-CA-Chirp3-HD-Aoede", "locale": "fr-CA", "gender": "Female"}, {"voice": "fr-FR-Chirp3-HD-Aoede", "locale": "fr-FR", "gender": "Female"}, {"voice": "en-AU-Chirp3-HD-Aoede", "locale": "en-AU", "gender": "Female"}, {"voice": "en-GB-Chirp3-HD-Aoede", "locale": "en-GB", "gender": "Female"}, {"voice": "en-US-Chirp3-HD-Aoede", "locale": "en-US", "gender": "Female"}]""")
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

        // A dictation in their own language, the AI giving none: theirs (the page's)
        relayAnswers("""{"deck": {"deck": "Français::Dictée", "cards": [{"front": "Le … boit", "back": "chat"}]}, "turns": [], "back_language": "", "usage": {"credits": 1, "credits_left": 97}}""")
        val dictation = client.submitFormWithBinaryData("/api/extract", formData {
            append("prompt", "Dictée")
            append("voice", "auto")
            append("typing", "true")
            append("dictation", "true")
        }) { page("fr") }.json().jsonObject
        assertEquals("fr-FR-Chirp3-HD-Aoede", dictation.string("voice"))

        // "en" alone: its usual variety, not the first by name (en-AU)
        relayAnswers("""{"deck": {"deck": "Anglais", "cards": [{"front": "le chat", "back": "the cat"}]}, "turns": [], "back_language": "en", "usage": {"credits": 1, "credits_left": 96}}""")
        val english = client.submitFormWithBinaryData("/api/extract", formData {
            append("prompt", "FR → EN")
            append("voice", "auto")
        }) { page("fr") }.json().jsonObject
        assertEquals("en-GB-Chirp3-HD-Aoede", english.string("voice"))

        // Automatic, the AI recognising a dictation to prepare: dictation cards alone, the pupil's voice
        relayAnswers("""{"deck": {"deck": "Français::Dictée", "cards": [{"front": "Le … boit", "back": "chat"}]}, "turns": [], "back_language": "", "choice": "Une dictée.", "dictation": true, "usage": {"credits": 1, "credits_left": 95}}""")
        val recognised = client.submitFormWithBinaryData("/api/extract", formData {
            append("prompt", "Automatique")
            append("voice", "auto")
        }) { page("fr") }.json().jsonObject
        assertEquals("fr-FR-Chirp3-HD-Aoede", recognised.string("voice"))
        assertEquals("true", recognised["dictation_only"].toString())
        assertEquals("true", recognised["dictation"].toString())
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
        // About: free software, its libraries' licences (the computer's page, served with the app's)
        assertTrue("admin.about.free" in page && "licences.html" in page)
        assertTrue("licences.js" in client.get("/licences.html").bodyAsText())
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
            setBody("""{"key": " nts_new_licence_key ", "instructions": "Léa est en 5e", "helps": false, "relay": "http://192.168.1.10:8080/"}""")
        }.json().jsonObject
        assertEquals("nts_…_key", saved.string("key"))
        assertEquals("nts_new_licence_key", prefs[LocalServer.keyOf("http://192.168.1.10:8080")]) // the new relay's
        assertEquals("http://192.168.1.10:8080", prefs[LocalServer.RELAY])
        assertEquals(listOf("true", "false", "true"), listOf("fun_facts", "helps", "pictures").map { saved[it]!!.jsonPrimitive.content }) // on at first
        val config = client.get("/api/config") { page() }.json().jsonObject
        assertEquals("false", config["donations"]!!.jsonPrimitive.content) // paid for: no Ko-fi link

        // Only what's given changes
        client.put("/api/admin/settings") { page(); contentType(ContentType.Application.Json); setBody("""{"helps": true}""") }
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
    fun picturesFoundShownAsEachSourceAnswers() = app { client ->
        val lines = listOf(
            """{"found": [{"source": "pixabay", "id": "1", "title": "a", "preview": "data:,", "licence": "Pixabay"}]}""",
            """{"found": [{"source": "commons", "id": "File:B.jpg", "title": "b", "preview": "data:,", "licence": "CC0"}]}""",
            """{"done": {"results": [], "words": "castle", "usage": {"credits": 1, "credits_left": 99}}}""",
        )
        relay.enqueue(MockResponse.Builder().setHeader("Content-Type", Relay.STREAM_TYPE).body(lines.joinToString("\n", postfix = "\n")).build())
        val res = client.post("/api/pictures/search") {
            page(); contentType(ContentType.Application.Json); header(HttpHeaders.Accept, Relay.STREAM_TYPE)
            setBody("""{"subject": "un château"}""")
        }
        assertTrue(res.headers[HttpHeaders.ContentType]!!.startsWith(Relay.STREAM_TYPE))
        val items = res.bodyAsText().lines().filter { it.isNotBlank() }.map { json.parseToJsonElement(it).jsonObject }
        assertEquals(listOf("1", "File:B.jpg"), items.take(2).map { it["found"]!!.jsonArray[0].jsonObject.string("id") })
        assertEquals("castle", items[2]["done"]!!.jsonObject.string("words"))
        assertEquals(Relay.STREAM_TYPE, relay.takeRequest(5, TimeUnit.SECONDS)!!.headers["Accept"])

        // Every source down: the error as the last line
        relayAnswers("""{"code": "picture.search_failed", "params": {}}""", 502)
        val failed = client.post("/api/pictures/search") {
            page(); contentType(ContentType.Application.Json); header(HttpHeaders.Accept, Relay.STREAM_TYPE)
            setBody("""{"subject": "un château"}""")
        }.bodyAsText().trim()
        assertEquals("picture.search_failed", json.parseToJsonElement(failed).jsonObject["error"]!!.jsonObject.string("code"))
    }

    @Test
    fun picturesFoundThroughTheRelay() = app { client ->
        relayAnswers("""{"results": [{"source": "pixabay", "id": "42", "title": "fortress", "preview": "data:,", "licence": "Pixabay"}]}""")
        val found = client.post("/api/pictures/search") {
            page(); contentType(ContentType.Application.Json); setBody("""{"subject": "a castle"}""")
        }.json().jsonObject
        assertEquals("42", found["results"]!!.jsonArray[0].jsonObject.string("id"))
        val searched = relay.takeRequest(5, TimeUnit.SECONDS)!!
        assertEquals("/v1/pictures/search", searched.url.encodedPath)
        val sent = json.parseToJsonElement(searched.body!!.utf8()).jsonObject
        assertEquals("a castle", sent.string("subject"))
        assertEquals("true", sent["translate"].toString()) // written by the user
        assertEquals("true", sent["sort"].toString()) // sorted by the AI

        // The card's own search words: as they are
        relayAnswers("""{"results": []}""")
        client.post("/api/pictures/search") {
            page(); contentType(ContentType.Application.Json); setBody("""{"subject": "un château fort", "words": "castle"}""")
        }
        val withWords = json.parseToJsonElement(relay.takeRequest(5, TimeUnit.SECONDS)!!.body!!.utf8()).jsonObject
        assertEquals("castle", withWords.string("subject"))
        assertEquals("false", withWords["translate"].toString())

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
        val found = json.parseToJsonElement(
            """{"source": "commons", "licence": "CC0", "page": "https://commons.wikimedia.org/wiki/File:Dog.jpg"}""",
        )
        relay.dispatcher = object : mockwebserver3.Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                val body = json.parseToJsonElement(request.body!!.utf8()).jsonObject
                asked += body
                val card = JsonObject(body["card"]!!.jsonObject + ("picture_source" to found))
                return MockResponse.Builder().body(buildJsonObject {
                    put("card", card)
                    put("data", Base64.getEncoder().encodeToString("jpeg".toByteArray()))
                    put("media_type", "image/jpeg")
                    put("usage", buildJsonObject { put("credits", 1); put("credits_left", 98) })
                }.toString()).build()
            }
        }
        val id = lesson.string("id")
        val drawn = client.post("/api/lessons/$id/pictures") { page() }.json().jsonObject
        val source = drawn["lesson"]!!.jsonObject["cards"]!!.jsonArray[0].jsonObject["picture_source"]!!.jsonObject
        assertEquals("https://commons.wikimedia.org/wiki/File:Dog.jpg", source.string("page")) // kept with the card
        assertEquals("dog", asked[0]["card"]!!.jsonObject.string("picture_search")) // the relay looks for it
        assertEquals("true", asked[0]["find"]!!.jsonPrimitive.content)
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
                    // The relay's AI decides: a figure
                    "/v1/card-picture" -> cardPicture(request) { mapOf("figure" to "Deux ensembles, leur réunion hachurée") }
                    else -> MockResponse.Builder().body("""{"results": [], "words": "union Venn diagram"}""").build()
                }
            }
        }
        val id = lesson.string("id")
        val card = lesson["cards"]!!.jsonArray[0].jsonObject.string("id")
        val drawn = client.post("/api/lessons/$id/cards/$card/picture/make") {
            page("fr"); contentType(ContentType.Application.Json); setBody("""{"subject": ""}""")
        }.json().jsonObject["card"]!!.jsonObject
        assertEquals("Deux ensembles, leur réunion hachurée", drawn.string("figure"))
        assertTrue(drawn.string("picture").endsWith(".svg"))
        val made = json.parseToJsonElement(asked.single().second).jsonObject
        assertEquals("/v1/card-picture", asked.single().first) // one call: decided and drawn
        assertEquals("French", made.string("language"))
        assertEquals("", made.string("asked"))
        assertEquals("true", made["fresh"]!!.jsonPrimitive.content)
        assertEquals("false", made["draw"]!!.jsonPrimitive.content) // never the image model without a yes

        client.post("/api/pictures/search") {
            page(); contentType(ContentType.Application.Json); setBody("""{"subject": "la réunion", "context": "La réunion ? → A ∪ B"}""")
        }
        val search = json.parseToJsonElement(asked.last().second).jsonObject
        assertEquals("true", search["translate"]!!.jsonPrimitive.content) // written in any language
        assertEquals("La réunion ? → A ∪ B", search.string("context"))
    }
}
