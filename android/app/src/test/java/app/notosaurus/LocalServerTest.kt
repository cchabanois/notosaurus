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

/** The local server: the page's files, the draft, versions: what no routes file serves. */
class LocalServerTest : LocalServerTestBase() {
    @Test
    fun theFiguresCreditsAsTheRelayDrawsThem() = app { client ->
        // The relay's list (a package it added, credited without a new app), kept
        relayAnswers("""[{"name": "newpkg", "version": "1.0.0", "licence": "MIT", "url": "https://example.org/newpkg"}]""")
        val told = client.get("/api/credits") { page() }.json().jsonArray
        assertEquals("/v1/credits", relay.takeRequest().url.encodedPath)
        assertEquals("newpkg", told.single().jsonObject["name"]!!.jsonPrimitive.content)
        // A relay too old to say: the last it said
        relayAnswers("""{"detail": "Not Found"}""", 404)
        assertEquals(told, client.get("/api/credits") { page() }.json().jsonArray)
        // Never told (a fresh install), a relay too old: the list shipped with the page, core's
        prefs[Credits.KEPT] = ""
        relayAnswers("""{"detail": "Not Found"}""", 404)
        val shipped = client.get("/api/credits") { page() }.json().jsonArray.map { it.jsonObject["name"]!!.jsonPrimitive.content }
        assertTrue("cetz" in shipped && "Natural Earth" in shipped)
    }

    @Test
    fun theLessonInProgressKeptByTheApp() = app { client ->
        // As the page keeps it (app-draft.js): found again after the settings or Android closing the app
        assertEquals("{}", client.get("/api/draft") { page() }.bodyAsText())
        val draft = """{"lesson":null,"prompt":{"selected":null,"chosen":true,"form":{"text":"Une carte par capitale"}}}"""
        suspend fun send(text: String, photos: List<String>?) = client.submitFormWithBinaryData(
            "/api/draft",
            formData {
                append("draft", text)
                if (photos != null) append("photos_sent", "true")
                photos?.forEachIndexed { i, photo ->
                    append("photos", photo.toByteArray(), Headers.build {
                        append(HttpHeaders.ContentType, "image/jpeg")
                        append(HttpHeaders.ContentDisposition, "filename=\"photo-${i + 1}.jpg\"")
                    })
                }
            },
        ) { method = HttpMethod.Put; page() }
        assertEquals(HttpStatusCode.OK, send(draft, listOf("one", "two")).status)
        val kept = client.get("/api/draft") { page() }.json().jsonObject
        assertEquals(2, kept["photos"]!!.jsonPrimitive.int)
        assertEquals("Une carte par capitale", kept["prompt"]!!.jsonObject["form"]!!.jsonObject.string("text"))
        assertEquals("two", client.get("/api/draft/photos/2") { page() }.bodyAsText())
        send(draft.replace("capitale", "fleuve"), null) // the prompt alone: its photos kept
        assertEquals(2, client.get("/api/draft") { page() }.json().jsonObject["photos"]!!.jsonPrimitive.int)
        send("""{"lesson":"abc"}""", emptyList()) // made: the lesson open, no photo
        assertEquals("""{"lesson":"abc","photos":0}""", client.get("/api/draft") { page() }.bodyAsText())
        assertEquals(HttpStatusCode.BadRequest, send("[1]", null).status)
        client.delete("/api/draft") { page() }
        assertEquals("{}", client.get("/api/draft") { page() }.bodyAsText())
        assertEquals(HttpStatusCode.Unauthorized, client.get("/api/draft").status) // never without the WebView's cookie
    }

    @Test
    fun whatWasSharedKeptUntilThePageTakesIt() = app { client ->
        // Nothing shared: nothing to take
        val none = client.get("/api/shared") { page() }.json().jsonObject
        assertEquals(0, none["files"]!!.jsonArray.size)
        assertEquals("", none.string("text"))
        // "Share" in another app (MainActivity): a photo, a PDF, a text file, a ZIP, the text shared
        val pdf = "%PDF-1.4 a school's PDF".toByteArray()
        local.shared.take(
            listOf(
                Shared.Item("cahier.jpg", "image/jpeg") { "photo".byteInputStream() },
                Shared.Item("Leçon 5.pdf", null) { pdf.inputStream() }, // its type unknown: its name says
                Shared.Item("notes.txt", "text/plain") { "La Révolution française".byteInputStream() },
                Shared.Item("archive.zip", "application/zip") { "zip".byteInputStream() },
                Shared.Item("huge.jpg", "image/jpeg") { java.io.ByteArrayInputStream(ByteArray((Shared.MAX_BYTES + 1).toInt())) },
            ),
            "En 1789, le peuple de Paris prend la Bastille.",
        )
        val shared = client.get("/api/shared") { page() }.json().jsonObject
        val files = shared["files"]!!.jsonArray.map { it.jsonObject }
        assertEquals(listOf("cahier.jpg", "Leçon 5.pdf"), files.map { it.string("name") })
        assertEquals(listOf("image/jpeg", Shared.PDF), files.map { it.string("type") })
        assertEquals("En 1789, le peuple de Paris prend la Bastille.\n\nLa Révolution française", shared.string("text"))
        assertEquals(listOf("archive.zip", "huge.jpg"), shared["skipped"]!!.jsonArray.map { it.jsonPrimitive.content })
        assertArrayEquals(pdf, client.get("/api/shared/2") { page() }.bodyAsBytes())
        assertEquals(HttpStatusCode.NotFound, client.get("/api/shared/3") { page() }.status)
        assertEquals(HttpStatusCode.Unauthorized, client.get("/api/shared").status) // never without the WebView's cookie
        assertEquals(HttpStatusCode.Unauthorized, client.get("/api/shared/1").status)
        // Taken by the page: gone
        client.delete("/api/shared") { page() }
        assertEquals(0, client.get("/api/shared") { page() }.json().jsonObject["files"]!!.jsonArray.size)
        // A new share replaces what the page hadn't taken
        local.shared.take(listOf(Shared.Item("a.jpg", "image/jpeg") { "a".byteInputStream() }), null)
        local.shared.take(listOf(Shared.Item("b.png", "image/png") { "b".byteInputStream() }), null)
        assertEquals(listOf("b.png"), client.get("/api/shared") { page() }.json().jsonObject["files"]!!.jsonArray.map { it.jsonObject.string("name") })
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
        // Alpine and MathJax, shipped too (static/vendor): nothing from elsewhere
        assertEquals(HttpStatusCode.OK, client.get("/vendor/alpinejs/cdn.min.js").status)
        assertEquals(HttpStatusCode.OK, client.get("/vendor/mathjax/tex-chtml-full.js").status)
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
    fun whatTheSoundSays() {
        fun card(front: String, back: String) = Card(front = front, back = back)
        assertEquals("Le chat boit du lait.\nlait", Speech.spoken(card("Le chat boit du ….", "lait"), dictation = true))
        assertEquals("Le pré est vert.\nvert", Speech.spoken(card("Le pré est ___", "vert"), dictation = true)) // its full stop added
        assertEquals("lait", Speech.spoken(card("Le chat boit du ….", "lait"), dictation = false)) // not a dictation
        assertEquals("la madre", Speech.spoken(card("la mère", "la madre"), dictation = true)) // no blank
        assertEquals("Ça coûte $1.\n$1", Speech.spoken(card("Ça coûte ...", "$1"), dictation = true)) // as written
        // A transcription isn't read (a voice would say "slash"): the front's quoted examples are
        assertEquals("bird", Speech.spoken(card("Quel son de voyelle entend-on dans le mot anglais \"bird\" ?", "/ɜː/"), dictation = false))
        assertEquals("bird\ngirl", Speech.spoken(card("Le son de « bird » et de “girl” ?", "/ɜː/"), dictation = true))
        assertEquals("", Speech.spoken(card("Comment prononce-t-on thought ?", "[θɔːt]"), dictation = false)) // no example
        assertEquals("a tiger", Speech.spoken(card("x", "a t[i]ger"), dictation = false)) // a part singled out
        assertEquals("12/10/2026, 90 km/h", Speech.spoken(card("x", "12/10/2026, 90 km/h"), dictation = false))
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
    fun boxesTurnedAsOnTheComputer() {
        // diagrams.rotate_box([0.1, 0.2, 0.3, 0.5], degrees) on the computer
        assertEquals(listOf(0.5, 0.1, 0.8, 0.3), Diagrams.rotateBox(listOf(0.1, 0.2, 0.3, 0.5), 90))
        assertEquals(listOf(0.7, 0.5, 0.9, 0.8), Diagrams.rotateBox(listOf(0.1, 0.2, 0.3, 0.5), 180))
        assertEquals(listOf(0.2, 0.7, 0.5, 0.9), Diagrams.rotateBox(listOf(0.1, 0.2, 0.3, 0.5), 270))
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
    fun whatThePageKeepsKeptByTheApp() = app { client ->
        // In the preferences, whatever the page's address: the child chosen, the language…
        assertEquals("window.SAVED = {};\n", client.get("/saved.js") { page() }.bodyAsText())
        client.put("/api/saved") {
            page(); contentType(ContentType.Application.Json)
            setBody("""{"notosaurus.child": "lea", "notosaurus.lang": "fr", "other": "x"}""")
        }
        client.put("/api/saved") { page(); contentType(ContentType.Application.Json); setBody("""{"notosaurus.lang": null}""") }
        val script = client.get("/saved.js") { page() }
        assertEquals("no-store", script.headers[HttpHeaders.CacheControl])
        assertEquals("""window.SAVED = {"notosaurus.child":"lea"};""" + "\n", script.bodyAsText()) // not another key; removed
        assertEquals(mapOf("notosaurus.child" to "lea"), Saved(prefs).all()) // the next launch's too
        assertEquals(HttpStatusCode.Unauthorized, client.get("/saved.js").status) // never without the WebView's cookie
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
    fun anOlderVersionsSoundsMovedIntoTheirLessons() {
        // As an older version kept them: in audio/, named after (voice, speed, text)
        val id = "espagnol-lecon-5-abc123"
        folder.root.resolve("lessons/$id").mkdirs()
        folder.root.resolve("lessons/$id/lesson.json").writeText(
            """{"id": "$id", "deck": "Espagnol", "voice": "es-ES-Chirp3-HD-Aoede", "rate": "", "cards": [{"front": "la mère", "back": "la madre"}]}""",
        )
        val sha = java.security.MessageDigest.getInstance("SHA-1").digest("es-ES-Chirp3-HD-Aoede|${Relay.SPEECH_RATE}|la madre".toByteArray())
        val legacy = folder.root.resolve("audio/" + sha.joinToString("") { "%02x".format(it) }.take(16) + ".mp3")
        legacy.writeText("older la madre")
        val prefs = MemoryPreferences()
        val speech = Speech(folder.root.resolve("audio"), prefs, { error("no relay") }) { folder.root.resolve("lessons/$it/audio") }
        speech.moveIntoLessons(Lessons(folder.root.resolve("lessons")).list())
        val moved = audioOf(id).resolve(Speech.fileName("la madre", "es-ES-Chirp3-HD-Aoede", "-10%"))
        assertEquals("older la madre", moved.readText())
        assertFalse(legacy.exists()) // audio/ keeps only previews now
        legacy.writeText("again")
        speech.moveIntoLessons(emptyList()) // once
        assertTrue(legacy.exists())
    }
}
