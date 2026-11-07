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

/** The local server: ExamRoutes.kt's routes. */
class ExamRoutesTest : LocalServerTestBase() {
    @Test
    fun aTestToPrepareTagsItsLessonsNotesInAnkiDroid() = app { client ->
        relayAnswers("""{"deck": {"deck": "SVT::Chapitre 1", "cards": [{"front": "Q1", "back": "R1"}, {"front": "Q2", "back": "R2"}]}, "turns": [], "usage": {"credits": 1, "credits_left": 99}}""")
        val lesson = client.submitFormWithBinaryData("/api/extract", formData { append("prompt", "Questions") }) { page() }.json().jsonObject
        relay.takeRequest(5, TimeUnit.SECONDS)
        val id = lesson.string("id")
        val ids = lesson["cards"]!!.jsonArray.map { it.jsonObject.string("id") }
        assertEquals("[]", client.get("/api/exams") { page() }.bodyAsText())

        // Made before the lesson is in AnkiDroid: nothing to tag yet; sent, the notes carry the tag
        val made = client.put("/api/exams/interro-svt") {
            page(); contentType(ContentType.Application.Json)
            setBody("""{"name": "Interro SVT de lundi", "date": "2026-10-20", "lessons": [{"lesson": "$id"}]}""")
        }.json().jsonObject
        assertEquals("Exam::Interro_SVT_de_lundi", made.string("tag"))
        assertEquals("tag:Exam::Interro_SVT_de_lundi", made.string("search"))
        assertEquals("SVT::Chapitre 1", made.string("deck"))
        assertEquals(0, made["lessons"]!!.jsonArray.single().jsonObject["in_anki"]!!.jsonPrimitive.int)
        assertTrue(made["anki"]!!.jsonPrimitive.content == "true" && anki.retagged.isEmpty())
        anki.sentNotes = mapOf(ids[0] to 11L, ids[1] to 12L)
        client.post("/api/anki/send") {
            page(); contentType(ContentType.Application.Json)
            setBody("""{"deck": "SVT::Chapitre 1", "cards": ${lesson["cards"]}, "voice": "", "lesson_id": "$id"}""")
        }
        assertEquals(setOf("Exam::Interro_SVT_de_lundi"), anki.media.extraTags[ids[0]])
        assertEquals(2, client.get("/api/exams") { page() }.json().jsonArray.single().jsonObject["lessons"]!!.jsonArray.single().jsonObject["in_anki"]!!.jsonPrimitive.int)

        // Some of its cards only: the other note loses the tag; renamed: the tag follows
        client.put("/api/exams/interro-svt") {
            page(); contentType(ContentType.Application.Json)
            setBody("""{"name": "Interro SVT de lundi", "date": "2026-10-20", "lessons": [{"lesson": "$id", "cards": ["${ids[0]}"]}]}""")
        }
        assertEquals(emptyMap<String, Set<Long>>() to mapOf("Exam::Interro_SVT_de_lundi" to setOf(12L)), anki.retagged.last())
        // The page shown those cards, not the whole lesson
        val part = client.get("/api/exams") { page() }.json().jsonArray.single().jsonObject["lessons"]!!.jsonArray.single().jsonObject
        assertEquals(listOf(ids[0]), part["cards"]!!.jsonArray.map { it.jsonPrimitive.content })
        assertEquals(1, part["total"]!!.jsonPrimitive.int)
        client.put("/api/exams/interro-svt") {
            page(); contentType(ContentType.Application.Json)
            setBody("""{"name": "Brevet blanc", "lessons": [{"lesson": "$id"}]}""")
        }
        assertEquals(mapOf("Exam::Brevet_blanc" to setOf(11L, 12L)) to mapOf("Exam::Interro_SVT_de_lundi" to setOf(11L)), anki.retagged.last())

        // Renamed while AnkiDroid couldn't follow: the old tag taken off once it can (the tests listed)
        anki.broken = true
        val renamed = client.put("/api/exams/interro-svt") {
            page(); contentType(ContentType.Application.Json)
            setBody("""{"name": "Brevet blanc 2", "lessons": [{"lesson": "$id"}]}""")
        }.json().jsonObject
        assertEquals("false", renamed["anki"]!!.jsonPrimitive.content)
        anki.broken = false
        client.get("/api/exams") { page() }
        assertEquals(mapOf("Exam::Brevet_blanc_2" to setOf(11L, 12L)) to mapOf("Exam::Brevet_blanc" to setOf(11L, 12L)), anki.retagged.last())
        val followed = anki.retagged.size
        client.get("/api/exams") { page() }
        assertEquals(followed, anki.retagged.size) // done: not again

        // Made while AnkiDroid couldn't follow, its notes tagged by a send since, then renamed
        // while it couldn't again: the old tag still taken off once it can
        anki.broken = true
        client.put("/api/exams/later") { page(); contentType(ContentType.Application.Json); setBody("""{"name": "Plus tard", "lessons": [{"lesson": "$id"}]}""") }
        anki.broken = false
        client.post("/api/anki/send") {
            page(); contentType(ContentType.Application.Json)
            setBody("""{"deck": "SVT::Chapitre 1", "cards": ${lesson["cards"]}, "voice": "", "lesson_id": "$id"}""")
        }
        anki.broken = true
        client.put("/api/exams/later") { page(); contentType(ContentType.Application.Json); setBody("""{"name": "Plus tard 2", "lessons": [{"lesson": "$id"}]}""") }
        anki.broken = false
        client.get("/api/exams") { page() }
        assertEquals(mapOf("Exam::Plus_tard_2" to setOf(11L, 12L)) to mapOf("Exam::Plus_tard" to setOf(11L, 12L)), anki.retagged.last())
        client.delete("/api/exams/later") { page() }

        // Another test whose name differs by its case only: one tag for AnkiDroid, refused
        val same = client.put("/api/exams/other") { page(); contentType(ContentType.Application.Json); setBody("""{"name": "brevet BLANC 2"}""") }
        assertEquals("exams.same_name", same.json().jsonObject["detail"]!!.jsonObject.string("code"))

        // Deleted: the tag taken off; a lesson deleted leaves the tests
        assertEquals("""{"deleted":true,"anki":true}""", client.delete("/api/exams/interro-svt") { page() }.bodyAsText())
        assertEquals(mapOf("Exam::Brevet_blanc_2" to setOf(11L, 12L)), anki.retagged.last().second)
        client.put("/api/exams/brevet") { page(); contentType(ContentType.Application.Json); setBody("""{"name": "Brevet", "lessons": [{"lesson": "$id"}, {"lesson": "2026-01-01-gone"}]}""") }
        client.delete("/api/lessons/$id") { page() }
        assertEquals(0, client.get("/api/exams") { page() }.json().jsonArray.single().jsonObject["lessons"]!!.jsonArray.size)
        val refused = client.put("/api/exams/Bad id") { page(); contentType(ContentType.Application.Json); setBody("""{"name": "x"}""") }
        assertEquals(400, refused.status.value)
        assertEquals("exams.invalid", refused.json().jsonObject["detail"]!!.jsonObject.string("code")) // the test's, not the relay's
        val tooLong = client.put("/api/exams/long") { page(); contentType(ContentType.Application.Json); setBody("""{"name": "${"x".repeat(61)}"}""") }
        assertEquals("exams.invalid", tooLong.json().jsonObject["detail"]!!.jsonObject.string("code"))
    }
}
