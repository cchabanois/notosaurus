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

/**
 * The page's /api, answered on the phone: called as the page calls them (app.js),
 * with a fake relay (MockWebServer) and a fake AnkiDroid. The page's files are the
 * repository's static/ (the notosaurus.web system property, set by Gradle).
 *
 * What every test of it shares, LocalServerTest and one class per routes file
 * (*RoutesTest): the fakes (relay, AnkiDroid, Google Play, the computer, the microphone),
 * the server started on them, the helpers.
 */
abstract class LocalServerTestBase {
    @get:Rule val folder = TemporaryFolder()
    protected val relay = MockWebServer()
    protected val anki = FakeAnki()
    protected val play = FakePlay()

    /** Google Play: the offer, a purchase's token (null: given up), the subscriptions owned. */
    protected class FakePlay : SubscriptionStore {
        var offers = listOf(Offer("monthly", "3,99 €", 7), Offer("yearly", "29,99 €", 7))
        var buying: Bought = Bought.Paid("token-1")
        var plans = mutableListOf<String>() // the base plans bought
        var owned = listOf<String>()
        var managed = 0
        override suspend fun offers() = offers
        override suspend fun subscribe(plan: String) = buying.also { plans += plan }
        override suspend fun owned() = owned
        override fun manage() { managed++ }
        var integrity: String? = "integrity-1" // Play Integrity's token (null: not the app from Google Play)
        override fun device() = "ab".repeat(32)
        override suspend fun integrity(device: String) = integrity
    }
    protected val prefs = MemoryPreferences()
    protected var permissionAsked = 0
    protected var grantPermission = true // the user's answer to AnkiDroid's dialog
    protected var storeOpened = 0
    protected val computer = MockWebServer() // the add-on's Notosaurus, on the computer
    protected var scanned: String? = null // what the fake QR scanner reads
    protected var document: java.io.ByteArrayOutputStream? = java.io.ByteArrayOutputStream() // where the fake document picker writes (null: cancelled)
    protected var scannerMissing = false
    protected var modeChanges = 0
    protected var micGranted = true // the user's answer to the microphone's dialog
    protected val mic = FakeMic()
    protected lateinit var local: LocalServer

    protected class FakeAnki : AnkiTarget {
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
        val retagged = mutableListOf<Pair<Map<String, Set<Long>>, Map<String, Set<Long>>>>() // (added, removed)
        override fun retag(add: Map<String, Set<Long>>, remove: Map<String, Set<Long>>) = !broken.also { if (!broken) retagged += add to remove }
        var opened = 0
        override fun open() = installed.also { if (it) opened++ }
        val browsed = mutableListOf<String>()
        override fun browse(search: String) = installed.also { if (it) browsed += search }
        override fun icon() = if (installed) byteArrayOf(0x89.toByte(), 0x50, 0x4E, 0x47) else null // "PNG"
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
    protected class FakeMic : Recorder {
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
            createDocument = { name, _ -> document?.let { Document(name.replace(".zip", " (1).zip"), it) } }, // one of that name there
            modeChanged = { modeChanges++ },
            turnPhoto = { data, degrees -> "turned $degrees:".toByteArray() + data }, // (Photos.turn needs Android)
            recorder = mic,
            requestMicPermission = { micGranted },
            subscriptions = play,
        )
        computer.start()
        // No sound read ahead while a test runs, unless it says so (soundsReadAhead…): the
        // relay's answers go to what the test asks
        local.soundsAhead.delayMs = 3_600_000
    }

    @After
    fun tearDown() {
        local.stop()
        relay.close()
        computer.close()
    }

    protected fun app(test: suspend ApplicationTestBuilder.(HttpClient) -> Unit) = testApplication {
        application { with(local) { module() } }
        test(client)
    }

    /** As the app's WebView: its cookie, the page's language. */
    protected fun HttpRequestBuilder.page(lang: String = "en") {
        header(HttpHeaders.Cookie, "${LocalServer.COOKIE}=${local.token}")
        header("X-Notosaurus-Lang", lang)
    }

    protected suspend fun HttpResponse.json() = json.parseToJsonElement(bodyAsText())

    protected fun relayAnswers(body: String, code: Int = 200) =
        relay.enqueue(MockResponse.Builder().code(code).body(body).build())

    /** The relay's /v1/card-picture, as the core: the card's picture decided (`decide`, from the
     * request), then a figure (an SVG) or a picture (a "JPEG" holding the request). */
    protected fun cardPicture(request: RecordedRequest, decide: (JsonObject) -> Map<String, String> = { emptyMap() }): MockResponse {
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

    protected fun RecordedRequest.multipartRequest(): JsonObject {
        val text = body!!.utf8()
        val start = text.indexOf("\r\n\r\n", text.indexOf("name=\"request\"")) + 4
        return json.parseToJsonElement(text.substring(start, text.indexOf("\r\n--", start))).jsonObject
    }

    protected suspend fun HttpClient.extract(
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

    protected suspend fun CoroutineScope.cancelled(client: HttpClient) {
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

    protected fun zipOf(files: Map<String, ByteArray>): ByteArray {
        val out = java.io.ByteArrayOutputStream()
        java.util.zip.ZipOutputStream(out).use { z ->
            files.forEach { (name, data) -> z.putNextEntry(java.util.zip.ZipEntry(name)); z.write(data); z.closeEntry() }
        }
        return out.toByteArray()
    }

    protected fun entries(zip: ByteArray): Map<String, ByteArray> = buildMap {
        java.util.zip.ZipInputStream(zip.inputStream()).use { z -> generateSequence { z.nextEntry }.forEach { put(it.name, z.readBytes()) } }
    }

    protected suspend fun HttpClient.importFile(zip: ByteArray): JsonObject = post("/api/admin/transfer") {
        page()
        setBody(io.ktor.client.request.forms.MultiPartFormDataContent(io.ktor.client.request.forms.formData {
            append("file", zip, io.ktor.http.Headers.build {
                append(HttpHeaders.ContentType, "application/zip"); append(HttpHeaders.ContentDisposition, "filename=\"export.zip\"")
            })
        }))
    }.json().jsonObject

    protected suspend fun HttpClient.send(lesson: JsonObject) = post("/api/anki/send") {
        page(); contentType(ContentType.Application.Json)
        setBody("""{"deck": "Espagnol::Leçon 5", "cards": ${lesson["cards"]}, "voice": "", "lesson_id": "${lesson.string("id")}"}""")
    }

    // --- The settings page (assets/page/admin.html)

    // --- With my computer

    /** A Notosaurus answering: its /api/lang, then its /api/config (its name, when it gives it). */
    protected fun computerAnswers(name: String? = "salon-pc") {
        computer.enqueue(MockResponse.Builder().body("""{"lang": null, "available": ["en", "fr"]}""").build())
        val named = if (name == null) "" else ""","computer_name": "$name""""
        computer.enqueue(MockResponse.Builder().body("""{"version": "1.1.0"$named}""").build())
    }

    protected suspend fun HttpClient.connect(address: String) = put("/api/admin/computer") {
        page(); contentType(ContentType.Application.Json); setBody("""{"address": "$address"}""")
    }

    // --- Dictation (🎤)

    protected suspend fun HttpClient.dictate(kind: String = "prompt"): HttpResponse {
        val started = post("/api/dictation/start") { page("fr") }
        if (started.status != HttpStatusCode.OK) return started
        return post("/api/dictation/stop") {
            page("fr")
            contentType(ContentType.Application.Json)
            setBody("""{"kind": "$kind"}""")
        }
    }

    /** The relay reading aloud (/v1/speak): "mp3 <text>", `slowMs` each; what it read, and the
     * most it read at once. */
    protected class Speaker(private val slowMs: Long = 0, private val voices: List<String> = emptyList()) : mockwebserver3.Dispatcher() {
        val read: MutableList<String> = java.util.Collections.synchronizedList(mutableListOf())
        private val now = java.util.concurrent.atomic.AtomicInteger()
        val most = java.util.concurrent.atomic.AtomicInteger()
        override fun dispatch(request: RecordedRequest): MockResponse {
            if (request.url.encodedPath == "/v1/voices" && voices.isNotEmpty()) {
                val listed = voices.joinToString(",") { """{"voice": "$it", "locale": "${it.take(5)}", "gender": "Female"}""" }
                return MockResponse.Builder().setHeader("Content-Type", "application/json").body("[$listed]").build()
            }
            if (request.url.encodedPath != "/v1/speak") return MockResponse.Builder().code(404).build()
            val text = json.parseToJsonElement(request.body!!.utf8()).jsonObject.string("text")
            most.accumulateAndGet(now.incrementAndGet(), ::maxOf)
            Thread.sleep(slowMs)
            now.decrementAndGet()
            read += text
            return MockResponse.Builder().setHeader("Content-Type", "audio/mpeg").body("mp3 $text").build()
        }
    }

    protected suspend fun waitFor(condition: () -> Boolean): Boolean {
        repeat(250) {
            if (condition()) return true
            kotlinx.coroutines.delay(20)
        }
        return condition()
    }

    protected suspend fun HttpClient.saveLesson(id: String, backs: List<String>, voice: String = "es-ES-Chirp3-HD-Aoede") {
        val cards = JsonArray(backs.mapIndexed { i, back -> buildJsonObject { put("front", "carte $i"); put("back", back) } })
        val res = put("/api/lessons/$id") {
            page(); contentType(ContentType.Application.Json)
            setBody("""{"deck": "Espagnol", "cards": $cards, "voice": "$voice"}""")
        }
        assertEquals(HttpStatusCode.OK, res.status)
    }

    protected suspend fun HttpClient.sendSteps(body: String): List<JsonObject> {
        val res = post("/api/anki/send") {
            page(); contentType(ContentType.Application.Json); header(HttpHeaders.Accept, Relay.STREAM_TYPE)
            setBody(body)
        }
        assertTrue(res.headers[HttpHeaders.ContentType]!!.startsWith(Relay.STREAM_TYPE))
        return res.bodyAsText().lines().filter { it.isNotBlank() }.map { json.parseToJsonElement(it).jsonObject }
    }

    protected fun audioOf(id: String) = folder.root.resolve("lessons/$id/audio")

    protected suspend fun HttpClient.sendLesson(id: String, voice: String = "es-ES-Chirp3-HD-Aoede") {
        val saved = get("/api/lessons/$id") { page() }.json().jsonObject
        sendSteps("""{"deck": "Espagnol", "cards": ${saved["cards"]}, "voice": "$voice", "rate": "${saved.string("rate")}", "lesson_id": "$id"}""")
    }

    protected val voices = """[{"voice": "es-US-Chirp3-HD-Aoede", "locale": "es-US", "gender": "Female"},
        {"voice": "es-ES-Chirp3-HD-Charon", "locale": "es-ES", "gender": "Male"},
        {"voice": "es-ES-Chirp3-HD-Aoede", "locale": "es-ES", "gender": "Female"}]"""
}
