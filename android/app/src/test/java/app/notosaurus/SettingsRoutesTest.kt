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

/** The local server: SettingsRoutes.kt's routes. */
class SettingsRoutesTest : LocalServerTestBase() {
    @Test
    fun onlyTheAppsWebView() = app { client ->
        val res = client.get("/api/config")
        assertEquals(HttpStatusCode.Unauthorized, res.status)
        assertEquals("device.not_paired", res.json().jsonObject["detail"]!!.jsonObject.string("code"))
        val config = client.get("/api/config") { page() }
        assertEquals(HttpStatusCode.OK, config.status)
        assertEquals("false", config.json().jsonObject["profiles"]!!.jsonPrimitive.content) // no Anki profile badge
        // 30 pages a lesson, 10 read in one call: the page sends more in several
        assertEquals("30", config.json().jsonObject["max_photos"]!!.jsonPrimitive.content)
        assertEquals("10", config.json().jsonObject["max_per_call"]!!.jsonPrimitive.content)
    }

    @Test
    fun theLessonsExportedThenImportedBackOnThisPhone() = app { client ->
        val lesson = client.extract()
        relay.takeRequest()
        val id = lesson.string("id")
        folder.root.resolve("lessons/$id/audio").mkdirs()
        folder.root.resolve("lessons/$id/audio/la-madre-55895502.mp3").writeText("mp3")
        local.lessons.setAnkiNotes(id, mapOf(lesson["cards"]!!.jsonArray[0].jsonObject.string("id") to 42L))
        local.children.save(listOf(Child("jules", "Jules", grade = "5e")))
        val exported = client.post("/api/admin/transfer/export") { page() }.json().jsonObject
        assertEquals(1, exported["lessons"]!!.jsonPrimitive.int)
        assertTrue(exported.string("name").startsWith("notosaurus-") && exported.string("name").endsWith(" (1).zip")) // the name as created
        val zip = document!!.toByteArray()
        val files = entries(zip)
        assertTrue("lessons/$id/lesson.json" in files && "lessons/$id/page-1.jpg" in files && "lessons/$id/audio/la-madre-55895502.mp3" in files)
        assertTrue(listOf("children.json", "exams.json", "prompts.json", "manifest.json").all { it in files })
        val manifest = json.parseToJsonElement(files.getValue("manifest.json").decodeToString()).jsonObject
        assertEquals(listOf("notosaurus", "android"), listOf(manifest.string("app"), manifest.string("device")))
        assertEquals("Jules", json.parseToJsonElement(files.getValue("children.json").decodeToString()).jsonObject["children"]!!.jsonArray[0].jsonObject.string("name"))
        assertFalse(files.keys.any { "key" in it || "settings" in it }) // no licence key, no setting

        // The picker cancelled: nothing written, said so
        document = null
        assertEquals("true", client.post("/api/admin/transfer/export") { page() }.json().jsonObject["cancelled"]!!.jsonPrimitive.content)

        // Deleted, then taken in again: the same lesson, its notes in AnkiDroid still known (this phone's)
        local.lessons.delete(id)
        val done = client.importFile(zip)
        assertEquals(listOf(1, 0, 0, 0), listOf("added", "replaced", "kept", "children").map { done[it]!!.jsonPrimitive.int })
        val back = local.lessons.get(id)!!
        assertEquals(42L, back["anki_notes"]!!.jsonObject.values.single().jsonPrimitive.content.toLong())
        assertEquals("mp3", folder.root.resolve("lessons/$id/audio/la-madre-55895502.mp3").readText())
        assertEquals(0, client.importFile(zip)["added"]!!.jsonPrimitive.int) // again: kept, nothing twice
    }

    @Test
    fun aLessonFromTheComputerTakenIn() = app { client ->
        relayAnswers(voices) // the relay's voices: the lesson's voice chosen among them
        val lesson = """{"format": 1, "deck": "Espagnol::Leçon 5", "prompt": "FR → ES", "voice": "es-ES-ElviraNeural", "rate": "-10%",
            "cards": [{"front": "la mère", "back": "la madre", "id": "c1"}], "owner": "Léa", "anki_notes": {"Léa": {"c1": 1234}},
            "created_at": "2026-10-30T10:00:00", "updated_at": "2026-10-30T10:00:00"}"""
        val zip = zipOf(
            mapOf(
                "manifest.json" to """{"format": 1, "app": "notosaurus", "device": "computer", "install": "the-computer"}""".toByteArray(),
                "lessons/2026-10-30-espagnol-lecon-5/lesson.json" to lesson.toByteArray(),
                "lessons/2026-10-30-espagnol-lecon-5/page-1.jpg" to "photo".toByteArray(),
                "lessons/2026-10-30-espagnol-lecon-5/audio/la-madre-55895502.mp3" to "computer's la madre".toByteArray(),
                "lessons/2026-10-30-espagnol-lecon-5/../../evil.txt" to "x".toByteArray(),
                "lessons/../evil/lesson.json" to lesson.toByteArray(),
                "children.json" to """{"children": [{"id": "jules", "name": "Jules", "grade": "5e", "anki_profile": "Léa"}]}""".toByteArray(),
                "exams.json" to """{"exams": [{"id": "brevet", "name": "Brevet blanc", "lessons": [{"lesson": "2026-10-30-espagnol-lecon-5"}]}]}""".toByteArray(),
                "prompts.json" to """{"user": [{"id": 7, "name": "Vocabulaire", "text": "Une carte par mot"}]}""".toByteArray(),
            ),
        )
        val done = client.importFile(zip)
        assertEquals(listOf(1, 1, 1, 1), listOf("added", "children", "exams", "prompts").map { done[it]!!.jsonPrimitive.int })
        val there = local.lessons.get("2026-10-30-espagnol-lecon-5")!!
        assertEquals(1, there["photo_count"]!!.jsonPrimitive.int) // the computer's lesson.json has none
        assertEquals("2026-10-30-espagnol-lecon-5", there.string("id"))
        assertEquals(JsonObject(emptyMap()), there["anki_notes"]) // the computer's Anki's
        assertTrue(Speech.reads(there.string("voice")) && there.string("voice").contains("Chirp3-HD")) // the relay's
        assertEquals("es-ES-ElviraNeural", there["cards"]!!.jsonArray[0].jsonObject.string("voice")) // its sound's
        assertFalse(folder.root.resolve("evil.txt").exists() || folder.root.resolve("evil").exists())
        assertEquals(listOf("Jules"), local.children.list().map { it.name })
        assertEquals(listOf("Brevet blanc"), local.exams.list().map { it.name })

        // Not an export: said
        val refused = client.post("/api/admin/transfer") {
            page()
            setBody(io.ktor.client.request.forms.MultiPartFormDataContent(io.ktor.client.request.forms.formData {
                append("file", "nope".toByteArray(), io.ktor.http.Headers.build { append(HttpHeaders.ContentDisposition, "filename=\"x.zip\"") })
            }))
        }
        assertEquals(HttpStatusCode.BadRequest, refused.status)
        assertTrue("transfer.not_an_export" in refused.bodyAsText())
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
    fun aLessonForAChild() = app { client ->
        val jules = """{"id": "jules", "name": "Jules", "grade": "5e", "decks": "Jules::{classe}", "instructions": "Peu de cartes."}"""
        val saved = client.put("/api/children") { page(); contentType(ContentType.Application.Json); setBody("[$jules]") }.json().jsonArray
        assertEquals("Jules", saved.single().jsonObject.string("name"))
        val twice = client.put("/api/children") { page(); contentType(ContentType.Application.Json); setBody("[$jules, $jules]") }
        assertEquals("children.same_id", twice.json().jsonObject["detail"]!!.jsonObject.string("code"))
        // A sheet that isn't valid: its own code, not one about the relay
        val invalid = client.put("/api/children") {
            page(); contentType(ContentType.Application.Json); setBody("""[{"id": "c1", "name": "", "grade": ""}]""")
        }
        assertEquals("children.invalid", invalid.json().jsonObject["detail"]!!.jsonObject.string("code"))

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
    fun theVoicesSpeedAndApkg() = app { client ->
        // The cards shared as an .apkg (ExportRoutes): the page shows "📤 Partager"
        assertEquals("true", client.get("/api/config") { page() }.json().jsonObject["apkg"]!!.jsonPrimitive.content)
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
    fun aRenewalTheRelayMissedFoundFromGooglePlay() = app { client ->
        prefs[LocalServer.keyOf(local.relayUrl())] = "nts_from_play"
        play.owned = listOf("token-1")
        // Past its end for the relay (a renewal's notification lost): the purchase checked again, the new period
        relayAnswers("""{"plan": "monthly", "credits_left": 12, "daily_left": 12, "ends_at": "2026-01-01T00:00:00+00:00"}""")
        relayAnswers("""{"key": "nts_from_play", "account": {"plan": "monthly", "credits_left": 3000, "daily_left": 500,
            "ends_at": "2999-01-01T00:00:00+00:00"}}""")
        relayAnswers("""{"plan": "monthly", "credits_left": 3000, "daily_left": 500, "ends_at": "2999-01-01T00:00:00+00:00"}""")
        val account = client.get("/api/admin/account") { page() }.json().jsonObject
        assertEquals(3000, account["credits_left"]!!.jsonPrimitive.int)
        val asked = (1..3).map { relay.takeRequest(5, TimeUnit.SECONDS)!!.url.encodedPath }
        assertEquals(listOf("/v1/account", "/v1/subscribe", "/v1/account"), asked)

        // Nothing owned (it really ended): the account as the relay says, nothing else asked
        play.owned = emptyList()
        relayAnswers("""{"plan": "monthly", "credits_left": 12, "daily_left": 12, "ends_at": "2026-01-01T00:00:00+00:00"}""")
        assertEquals(12, client.get("/api/admin/account") { page() }.json().jsonObject["credits_left"]!!.jsonPrimitive.int)
        assertEquals("/v1/account", relay.takeRequest(5, TimeUnit.SECONDS)!!.url.encodedPath)
        assertEquals(null, relay.takeRequest(200, TimeUnit.MILLISECONDS))
    }

    @Test
    fun aFreeTrialStartedByTheFirstAiCall() = app { client ->
        prefs[LocalServer.keyOf(local.relayUrl())] = "" // a new user: no key yet
        assertEquals("true", client.get("/api/admin/subscription") { page() }.json().jsonObject["trial"]!!.jsonPrimitive.content)
        // No key: the first AI call starts the free trial, then is made with its key
        relayAnswers("""{"key": "nts_trial", "account": {"plan": "free_trial", "credits_left": 300, "daily_left": 150,
            "renews_at": "2026-11-04T10:00:00+00:00", "ends_at": "2026-11-04T10:00:00+00:00"}}""")
        relayAnswers("""{"text": "Tidied"}""")
        val tidied = client.post("/api/prompt/rephrase") { page(); contentType(ContentType.Application.Json); setBody("""{"text": "t"}""") }
        assertEquals("Tidied", tidied.json().jsonObject.string("text"))
        val trial = relay.takeRequest(5, TimeUnit.SECONDS)!!
        assertEquals("/v1/trial", trial.url.encodedPath)
        val sent = json.parseToJsonElement(trial.body!!.utf8()).jsonObject
        assertEquals(listOf("integrity-1", "ab".repeat(32)), listOf(sent.string("integrity_token"), sent.string("device")))
        val call = relay.takeRequest(5, TimeUnit.SECONDS)!!
        assertEquals("/v1/rephrase" to "Bearer nts_trial", call.url.encodedPath to call.headers["Authorization"])
        assertEquals("nts_trial", prefs[LocalServer.keyOf(local.relayUrl())])

        // Told once to the page (its notice): its end, and its credits as they are now (the call's spent)
        relayAnswers("""{"plan": "free_trial", "credits_left": 290, "daily_left": 140}""")
        val told = client.get("/api/switches") { page() }.json().jsonObject["trial"]!!.jsonObject
        assertEquals(290, told["credits_left"]!!.jsonPrimitive.int)
        assertEquals("2026-11-04T10:00:00+00:00", told.string("ends_at"))
        relayAnswers("""{"plan": "free_trial", "credits_left": 290, "daily_left": 140}""")
        assertEquals(JsonNull, client.get("/api/switches") { page() }.json().jsonObject["trial"])
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
    fun theAppsOwnSettingsPage() = app { client ->
        val page = client.get("/admin.html").bodyAsText()
        assertTrue("settings.js" in page) // the app's, not the computer's admin.js
        assertTrue("android.licence.title" in page)
        // About: free software, its libraries' licences (the computer's page, served with the app's)
        assertTrue("admin.about.free" in page && "licences.html" in page)
        assertTrue("licences.js" in client.get("/licences.html").bodyAsText())
        assertEquals("true", client.get("/api/admin") { page() }.json().jsonObject["allowed"]!!.jsonPrimitive.content)
        // Every setting the page shows or saves (form.…) is one the server gives: a name the
        // server doesn't know would be neither shown as it is nor saved
        val script = page + client.get("/settings.js").bodyAsText()
        val fields = Regex("""form\.([a-z_]+)""").findAll(script).map { it.groupValues[1] }.toSet()
        val given = client.get("/api/admin/settings") { page() }.json().jsonObject.keys + "computer" // given once one is connected
        assertTrue(fields.size > 5)
        assertEquals(emptySet<String>(), fields - given)
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
    fun aReleaseTalksToTheRealRelayOnly() {
        // Saved before (an older version, the settings' "Advanced"): ignored, and none taken
        val release = LocalServer(folder.newFolder(), { null }, { listOf("en") }, anki, prefs, relayChoosable = false)
        assertEquals(LocalServer.REAL_RELAY, release.relayUrl())
        testApplication {
            application { with(release) { module() } }
            client.put("/api/admin/settings") {
                header(HttpHeaders.Cookie, "${LocalServer.COOKIE}=${release.token}")
                contentType(ContentType.Application.Json); setBody("""{"relay": "https://elsewhere.example"}""")
            }
        }
        assertEquals(relay.url("/").toString(), prefs[LocalServer.RELAY]) // untouched
        assertEquals(LocalServer.REAL_RELAY, release.relayUrl())
        release.stop()
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
    fun aKeyTheRelayRefusesIsNotKept() = app { client ->
        // Mistyped: refused, then no longer kept (subscribing offered again, the trial possible)
        client.put("/api/admin/settings") { page(); contentType(ContentType.Application.Json); setBody("""{"key": "nts_typo"}""") }
        relayAnswers("""{"code": "relay.invalid_key", "params": {}}""", code = 401)
        client.get("/api/admin/account") { page() }
        assertEquals("Bearer nts_typo", relay.takeRequest(5, TimeUnit.SECONDS)!!.headers["Authorization"])
        val settings = client.get("/api/admin/settings") { page() }.json().jsonObject
        assertEquals(false, settings["has_key"]!!.jsonPrimitive.content.toBoolean())

        // Another key typed meanwhile: the refusal of the old one leaves it
        local.licensing.setKey("nts_good")
        local.licensing.forget("nts_typo")
        assertEquals("nts_good", local.licence())

        // Not a refusal of the key (credits used up): kept
        relayAnswers("""{"code": "relay.no_credits", "params": {}}""", code = 402)
        client.get("/api/admin/account") { page() }
        assertEquals("nts_good", local.licence())
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
    fun aComputerThatDoesntSayItsName() = app { client ->
        computerAnswers(name = null) // an add-on older than computer_name
        client.connect("127.0.0.1:${computer.port}/?k=t")
        assertEquals("", client.get("/api/admin/settings") { page() }.json().jsonObject.string("computer_name"))
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
}
