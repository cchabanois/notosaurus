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

/** The local server: AnkiRoutes.kt's routes. */
class AnkiRoutesTest : LocalServerTestBase() {
    @Test
    fun aLessonFromTheComputerTakenInWhileTheRelayCouldntSay() = app { client ->
        // The relay unreachable when it's taken in: the lesson's voice the computer's still
        relayAnswers("""{"code": "relay.unavailable", "params": {}}""", 503)
        val id = "2026-10-30-espagnol"
        val lesson = """{"format": 1, "deck": "Espagnol", "prompt": "FR → ES", "voice": "es-ES-ElviraNeural", "rate": "-10%",
            "cards": [{"front": "la mère", "back": "la madre", "id": "c1"}, {"front": "le père", "back": "el padre", "id": "c2"}],
            "created_at": "2026-10-30T10:00:00", "updated_at": "2026-10-30T10:00:00"}"""
        val zip = zipOf(
            mapOf(
                "manifest.json" to """{"format": 1, "app": "notosaurus", "device": "computer", "install": "the-computer"}""".toByteArray(),
                "lessons/$id/lesson.json" to lesson.toByteArray(),
                "lessons/$id/audio/${Speech.fileName("la madre", "es-ES-ElviraNeural", "-10%")}" to "computer's la madre".toByteArray(),
            ),
        )
        assertEquals(1, client.importFile(zip)["added"]!!.jsonPrimitive.int)
        assertEquals("es-ES-ElviraNeural", local.lessons.get(id)!!.string("voice"))

        // Sent once the relay answers: el padre in the relay's voice, la madre the computer's sound
        val speaker = Speaker(voices = listOf("es-ES-Chirp3-HD-Aoede"))
        relay.dispatcher = speaker
        client.sendLesson(id, voice = "es-ES-ElviraNeural")
        assertEquals(listOf("el padre"), speaker.read)
        assertEquals("computer's la madre", anki.sounds["la madre"]!!.readText())
        assertTrue(folder.root.resolve("lessons/$id/audio/${Speech.fileName("el padre", "es-ES-Chirp3-HD-Aoede", "-10%")}").isFile)
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
    fun aTestsCardsInAnkiDroidsBrowser() = app { client ->
        val res = client.post("/api/anki/browse") { page(); contentType(ContentType.Application.Json); setBody("""{"search": "tag:notosaurus::controle::svt"}""") }
        assertEquals(HttpStatusCode.OK, res.status)
        assertEquals(listOf("tag:notosaurus::controle::svt"), anki.browsed)
        anki.installed = false
        val missing = client.post("/api/anki/browse") { page(); contentType(ContentType.Application.Json); setBody("""{"search": "tag:x"}""") }
        assertEquals("anki.android_missing", missing.json().jsonObject["detail"]!!.jsonObject.string("code"))
    }

    @Test
    fun ankiDroidOpenedFromThePage() = app { client ->
        assertEquals(HttpStatusCode.OK, client.post("/api/anki/open") { page() }.status)
        assertEquals(1, anki.opened)
        // Its own icon, as installed, for the button; the page's cookie needed as for the rest
        val icon = client.get("/api/anki/icon") { page() }
        assertEquals(HttpStatusCode.OK, icon.status)
        assertEquals("image/png", icon.headers[HttpHeaders.ContentType])
        assertEquals(4, icon.bodyAsBytes().size)
        assertEquals(HttpStatusCode.Unauthorized, client.get("/api/anki/icon").status)
        anki.installed = false // missing: said, the page offers to install it; no icon (the page shows 🎓)
        val missing = client.post("/api/anki/open") { page() }
        assertEquals("anki.android_missing", missing.json().jsonObject["detail"]!!.jsonObject.string("code"))
        assertEquals(1, anki.opened)
        assertEquals(HttpStatusCode.NotFound, client.get("/api/anki/icon") { page() }.status)
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
    fun theSendReadsItsSoundsFourAtATimeAndSaysHowFarItIs() = app { client ->
        val speaker = Speaker(slowMs = 150)
        relay.dispatcher = speaker
        val cards = JsonArray((1..6).map { buildJsonObject { put("front", "carte $it"); put("back", "réponse $it") } })
        val lines = client.sendSteps("""{"deck": "Espagnol", "cards": $cards, "voice": "es-ES-Chirp3-HD-Aoede", "lesson_id": ""}""")
        val sounds = lines.filter { it.string("step") == "sounds" }
        assertEquals((0..6).toList(), sounds.map { it["done"]!!.jsonPrimitive.int })
        assertTrue(sounds.all { it["total"]!!.jsonPrimitive.int == 6 })
        assertEquals("cards", lines[lines.size - 2].string("step"))
        val result = lines.last()["result"]!!.jsonObject
        assertEquals(6, result["added"]!!.jsonPrimitive.int)
        assertFalse("audio_failures" in result)
        assertEquals(6, anki.sounds.size)
        assertTrue("${speaker.most}", speaker.most.get() in 2..Speech.PARALLEL) // at once, never more than 4

        // AnkiDroid missing: the error as the page knows it
        anki.installed = false
        val refused = client.sendSteps("""{"deck": "Espagnol", "cards": $cards, "voice": "", "lesson_id": ""}""")
        assertEquals("anki.android_missing", refused.single()["error"]!!.jsonObject.string("code"))
    }
}
