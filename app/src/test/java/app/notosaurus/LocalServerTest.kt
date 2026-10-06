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
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
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
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.File

/**
 * The page's /api, answered on the phone: called as the page calls them (app.js),
 * with a fake relay (MockWebServer) and a fake AnkiDroid. The page's files are the
 * public repository's static/ (the notosaurus.web system property, set by Gradle).
 */
class LocalServerTest {
    @get:Rule val folder = TemporaryFolder()
    private val relay = MockWebServer()
    private val anki = FakeAnki()
    private val prefs = MemoryPreferences()
    private var permissionAsked = false
    private lateinit var local: LocalServer

    private class FakeAnki : AnkiTarget {
        var available = true
        val sent = mutableListOf<Deck>()
        override fun installed() = available
        override fun permitted() = available
        override fun deckNames() = listOf("Default", "Histoire")
        override fun send(deck: Deck): Sent {
            sent += deck
            return Sent(added = deck.cards.size, duplicates = 0, skipped = 0, deck = deck.deck)
        }
    }

    @Before
    fun setUp() {
        relay.start()
        val web = File(System.getProperty("notosaurus.web") ?: "../../notosaurus/static")
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
            requestAnkiPermission = { permissionAsked = true },
        )
    }

    @After fun tearDown() = relay.close()

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

    private suspend fun HttpClient.extract(prompt: String = "FR → ES", voice: String = "auto"): JsonObject {
        relayAnswers("""{"deck": {"deck": "Espagnol::Leçon 5", "cards": [{"front": "la mère", "back": "la madre"}, {"front": "le père", "back": "el padre"}]}, "turns": [0, 0], "choice": "Vocabulaire", "usage": {"credits": 3, "credits_left": 97}}""")
        return submitFormWithBinaryData(
            "/api/extract",
            formData {
                listOf("photo 1", "photo 2").forEachIndexed { i, photo ->
                    append("images", photo.toByteArray(), Headers.build {
                        append(HttpHeaders.ContentType, "image/jpeg")
                        append(HttpHeaders.ContentDisposition, "filename=\"page-${i + 1}.jpg\"")
                    })
                }
                append("prompt", prompt)
                append("deck", "")
                append("voice", voice)
                append("fun_facts", "true")
            },
        ) { page() }.json().jsonObject
    }

    @Test
    fun onlyTheAppsWebView() = app { client ->
        val res = client.get("/api/config")
        assertEquals(HttpStatusCode.Unauthorized, res.status)
        assertEquals("device.not_paired", res.json().jsonObject["detail"]!!.jsonObject.string("code"))
        assertEquals(HttpStatusCode.OK, client.get("/api/config") { page() }.status)
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
        val french = json.parseToJsonElement(File(System.getProperty("notosaurus.web") ?: "../../notosaurus/static", "i18n/fr.json").readText())
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

        anki.available = false
        assertEquals("false", client.get("/api/anki/status") { page() }.json().jsonObject["available"]!!.jsonPrimitive.content)
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
        // The texts it uses are in every language of the web page
        val names = Regex("""\${'$'}t\('(android\.[a-zA-Z.]+)'""").findAll(page).map { it.groupValues[1] }.toSet()
        val web = File(System.getProperty("notosaurus.web") ?: "../../notosaurus/static")
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
        assertEquals("nts_new_licence_key", prefs[LocalServer.KEY])
        assertEquals("http://192.168.1.10:8080", prefs[LocalServer.RELAY])
        assertEquals("true", client.get("/api/config") { page() }.json().jsonObject["card_helps"]!!.jsonPrimitive.content)

        // Only what's given changes
        client.put("/api/admin/settings") { page(); contentType(ContentType.Application.Json); setBody("""{"card_helps": false}""") }
        assertEquals("Léa est en 5e", prefs[LocalServer.INSTRUCTIONS])
        assertEquals("nts_new_licence_key", prefs[LocalServer.KEY])
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
        client.post("/api/admin/anki/permission") { page() }
        assertTrue(permissionAsked)
        anki.available = false
        val status = client.get("/api/admin/anki") { page() }.json().jsonObject
        assertEquals("false", status["installed"]!!.jsonPrimitive.content)
    }

    @Test
    fun theLessonsOnThePhone() = app { client ->
        client.extract()
        client.extract()
        val data = client.get("/api/admin/data") { page() }.json().jsonObject
        assertEquals(2, data["lessons"]!!.jsonPrimitive.int)
        assertTrue(data["bytes"]!!.jsonPrimitive.content.toLong() > 0)
        assertEquals(2, client.delete("/api/admin/lessons") { page() }.json().jsonObject["deleted"]!!.jsonPrimitive.int)
        assertEquals(JsonArray(emptyList()), client.get("/api/lessons") { page() }.json())
    }
}
