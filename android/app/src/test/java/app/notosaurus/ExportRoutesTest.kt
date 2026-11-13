package app.notosaurus

import io.ktor.client.request.forms.formData
import io.ktor.client.request.forms.submitFormWithBinaryData
import io.ktor.client.request.get
import io.ktor.client.request.post
import io.ktor.client.request.put
import io.ktor.client.request.setBody
import io.ktor.client.statement.bodyAsBytes
import io.ktor.http.ContentType
import io.ktor.http.HttpHeaders
import io.ktor.http.HttpStatusCode
import io.ktor.http.contentType
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.util.concurrent.TimeUnit

/** The local server: ExportRoutes.kt's routes, the cards as an .apkg made on the phone. */
class ExportRoutesTest : LocalServerTestBase() {
    private suspend fun io.ktor.client.HttpClient.lesson(deck: String, child: String = ""): JsonObject {
        val cards = """[{"front": "Q1", "back": "R1"}, {"front": "Q2", "back": "R2"}]"""
        relayAnswers("""{"deck": {"deck": "$deck", "cards": $cards}, "turns": [], "usage": {"credits": 1, "credits_left": 99}}""")
        val res = submitFormWithBinaryData("/api/extract", formData { append("prompt", "Questions"); if (child.isNotEmpty()) append("child", child) }) { page() }
        val made = res.json().jsonObject
        relay.takeRequest(5, TimeUnit.SECONDS)
        return made
    }

    private suspend fun io.ktor.client.HttpClient.shared(body: String) = post("/api/export/shared") {
        page(); contentType(ContentType.Application.Json); setBody(body)
    }

    @Test
    fun aTestsChosenCardsSharedWithoutTheChild() = app { client ->
        client.put("/api/children") {
            page(); contentType(ContentType.Application.Json)
            setBody("""[{"id": "jules", "name": "Jules", "grade": "5e", "decks": "Jules::{classe}"}]""")
        }
        val revolution = client.lesson("Histoire::Révolution", "jules")
        val napoleon = client.lesson("Histoire::Napoléon", "jules")
        assertTrue(revolution.string("deck").startsWith("Jules::5e::")) // the child's decks
        assertTrue("jules" in revolution.string("id")) // its id made from them
        val chosen = napoleon["cards"]!!.jsonArray.first().jsonObject.string("id")
        client.put("/api/exams/interro") {
            page(); contentType(ContentType.Application.Json)
            setBody("""{"name": "Interro d'histoire", "date": "", "lessons": [{"lesson": "${revolution.string("id")}"}, {"lesson": "${napoleon.string("id")}", "cards": ["$chosen"]}]}""")
        }

        val answer = client.shared("""{"exam": "interro"}""")
        assertEquals(HttpStatusCode.OK, answer.status)
        assertEquals("application/apkg", answer.headers[HttpHeaders.ContentType])
        assertTrue("Interro d'histoire.apkg" in answer.headers[HttpHeaders.ContentDisposition].orEmpty())
        val apkg = OpenedApkg(answer.bodyAsBytes(), folder.newFolder())
        assertEquals(setOf("Default", "Interro d'histoire::Révolution", "Interro d'histoire::Napoléon"), apkg.deckNames)
        assertEquals(3, apkg.query("SELECT count(*) FROM notes") { it.getInt(1) }.single()) // two, then the one chosen
        assertEquals(0, apkg.query("SELECT count(*) FROM revlog") { it.getInt(1) }.single())
        val everything = apkg.query("SELECT tags || flds FROM notes") { it.getString(1) }.joinToString("\n")
        assertFalse("notosaurus::" in everything || "Exam::" in everything) // this home's tags
        assertFalse("jules" in everything.lowercase()) // nor the child, by its lessons' ids
        assertTrue(anki.sent.isEmpty()) // AnkiDroid untouched

        // Lessons ticked: under the deck they share
        val ticked = OpenedApkg(client.shared("""{"lessons": ["${revolution.string("id")}", "${napoleon.string("id")}"]}""").bodyAsBytes(), folder.newFolder())
        assertEquals(setOf("Default", "Histoire::Révolution", "Histoire::Napoléon"), ticked.deckNames)
        // Nothing to share
        assertEquals("export.no_cards", client.shared("""{"lessons": []}""").json().jsonObject["detail"]!!.jsonObject.string("code"))
    }

    @Test
    fun turnedOffFromTheRelayRefused() = app { client ->
        val lesson = client.lesson("Histoire::Révolution")
        relayAnswers("""{"plan": "monthly", "credits_left": 10, "daily_left": 5, "disabled": ["anki.share"]}""")
        assertEquals(listOf("anki.share"), client.get("/api/switches") { page() }.json().jsonObject["disabled"]!!.jsonArray.map { it.jsonPrimitive.content })
        val refused = client.shared("""{"lessons": ["${lesson.string("id")}"]}""")
        assertEquals(HttpStatusCode.BadRequest, refused.status)
        assertEquals("app.feature_off", refused.json().jsonObject["detail"]!!.jsonObject.string("code"))
        val alone = client.post("/api/export") {
            page(); contentType(ContentType.Application.Json)
            setBody("""{"deck": "D", "cards": ${lesson["cards"]}, "voice": "", "lesson_id": "${lesson.string("id")}"}""")
        }
        assertEquals("app.feature_off", alone.json().jsonObject["detail"]!!.jsonObject.string("code"))
    }

    @Test
    fun theOpenLessonsCardsAsBefore() = app { client ->
        val lesson = client.lesson("Histoire::Révolution")
        val answer = client.post("/api/export") {
            page(); contentType(ContentType.Application.Json)
            setBody("""{"deck": "Histoire::Révolution", "cards": ${lesson["cards"]}, "voice": "", "lesson_id": "${lesson.string("id")}", "reverse": true}""")
        }
        assertEquals(HttpStatusCode.OK, answer.status)
        val apkg = OpenedApkg(answer.bodyAsBytes(), folder.newFolder())
        assertEquals(2, apkg.query("SELECT count(*) FROM notes") { it.getInt(1) }.single())
        assertEquals(4, apkg.query("SELECT count(*) FROM cards") { it.getInt(1) }.single()) // reversed: two each
        assertEquals(setOf("Default", "Histoire::Révolution"), apkg.deckNames)
    }
}
