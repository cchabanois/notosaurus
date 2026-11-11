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

/** The local server: LessonRoutes.kt's routes. */
class LessonRoutesTest : LocalServerTestBase() {
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
        // The same cards made again: their ids, so their notes and history in AnkiDroid (Lessons.keptIds)
        val ids = { l: JsonObject -> l["cards"]!!.jsonArray.map { it.jsonObject.string("id") } }
        assertEquals(ids(lesson), ids(again))
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
    fun aLessonHoldsThirtyPagesReadTenAtATime() = app { client ->
        val lesson = client.extract() // 2 pages
        relay.takeRequest()
        val id = lesson.string("id")
        suspend fun next(pages: Int) = client.submitFormWithBinaryData("/api/lessons/$id/complete", formData {
            repeat(pages) { i ->
                append("images", "page $i".toByteArray(), Headers.build {
                    append(HttpHeaders.ContentType, "image/jpeg")
                    append(HttpHeaders.ContentDisposition, "filename=\"p$i.jpg\"")
                })
            }
            append("prompt", "FR → ES")
        }) { page() }
        for ((pages, count) in listOf(10 to 12, 10 to 22, 8 to 30)) {
            relayAnswers("""{"deck": {"deck": "Autre", "cards": [{"front": "f$count", "back": "b"}]}, "turns": [],
                "usage": {"credits": 2, "credits_left": 95}}""")
            assertEquals(count, next(pages).json().jsonObject["photo_count"]!!.jsonPrimitive.int)
            relay.takeRequest()
        }
        // Past its 30 pages: refused before the relay (more than one call reads: GenerationRoutesTest)
        val refused = next(1)
        assertEquals(HttpStatusCode.BadRequest, refused.status)
        assertEquals(30, refused.json().jsonObject["detail"]!!.jsonObject["params"]!!.jsonObject["max"]!!.jsonPrimitive.int)
        assertEquals(null, relay.takeRequest(200, TimeUnit.MILLISECONDS))
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
    fun aPathsNumberThatIsntOneIsNotFound() = app { client ->
        // A photo's number, a prompt's: not a number is no such thing (a 404), not a server error
        assertEquals(HttpStatusCode.NotFound, client.get("/api/lessons/x/photos/abc") { page() }.status)
        val prompt = client.put("/api/prompts/abc") { page(); contentType(ContentType.Application.Json); setBody("""{"name": "n", "text": "t"}""") }
        assertEquals(HttpStatusCode.NotFound, prompt.status)
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
    fun aCardCorrectedOnItsOwn() = app { client ->
        val lesson = client.extract()
        relay.takeRequest()
        val card = lesson["cards"]!!.jsonArray[0].jsonObject
        relayAnswers("""{"card": ${JsonObject(card + ("back" to JsonPrimitive("la mamá")))}, "summary": "Réponse corrigée.", "usage": {"credits": 2, "credits_left": 95}}""")
        val res = client.post("/api/lessons/${lesson.string("id")}/fix-card") {
            page("fr"); contentType(ContentType.Application.Json)
            setBody("""{"card": $card, "instruction": "plutôt la mamá", "others": ["le père"]}""")
        }.json().jsonObject
        assertEquals("la mamá", res["card"]!!.jsonObject.string("back"))
        assertEquals("Réponse corrigée.", res.string("summary"))
        assertFalse("usage" in res) // the relay's own

        val sent = relay.takeRequest()
        assertEquals("/v1/fix-card", sent.url.encodedPath)
        val request = sent.multipartRequest()
        assertEquals("plutôt la mamá", request.string("instruction"))
        assertEquals("French", request.string("language"))
        assertEquals("Espagnol::Leçon 5", request.string("deck"))
        assertEquals(listOf("le père"), request["others"]!!.jsonArray.map { it.jsonPrimitive.content })
        // Not saved here: the page puts it in place
        assertEquals(card.string("back"), client.get("/api/lessons/${lesson.string("id")}") { page() }.json().jsonObject["cards"]!!.jsonArray[0].jsonObject.string("back"))
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
    fun aFigureCheckedWhenAskedThenDrawnAgainWithItsProblem() = app { client ->
        relayAnswers("""{"deck": {"deck": "Maths", "cards": [
            {"front": "Ce triangle ?", "back": "rectangle", "figure": "a right triangle"}]}, "turns": [], "usage": {"credits": 1, "credits_left": 99}}""")
        val lesson = client.submitFormWithBinaryData("/api/extract", formData { append("prompt", "p") }) { page() }.json().jsonObject
        val (id, triangle) = lesson.string("id") to lesson["cards"]!!.jsonArray.single().jsonObject.string("id")
        val asked = mutableListOf<Pair<String, JsonObject>>()
        relay.dispatcher = object : mockwebserver3.Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                val body = json.parseToJsonElement(request.body!!.utf8()).jsonObject
                asked += request.url.encodedPath to body
                val answer = when (request.url.encodedPath) {
                    "/v1/check-figure" -> """{"ok": false, "problem": "The angle is at B.", "usage": {"credits": 1, "credits_left": 90}}"""
                    else -> {
                        val svg = Base64.getEncoder().encodeToString("<svg>${asked.size}</svg>".toByteArray())
                        """{"card": ${body["card"]}, "data": "$svg", "media_type": "image/svg+xml", "usage": {"credits": 3, "credits_left": 90}}"""
                    }
                }
                return MockResponse.Builder().addHeader("Content-Type", "application/json").body(answer).build()
            }
        }
        client.post("/api/lessons/$id/pictures") { page(); contentType(ContentType.Application.Json); setBody("""{"draw": true}""") }
        // Checked: the figure as drawn sent with its description, nothing changed
        val checked = client.post("/api/lessons/$id/cards/$triangle/picture/check") { page() }.json().jsonObject
        assertEquals(false to "The angle is at B.", checked["ok"]!!.jsonPrimitive.boolean to checked.string("problem"))
        val (path, sent) = asked.last()
        assertEquals("/v1/check-figure" to "a right triangle", path to sent.string("description"))
        assertEquals("<svg>1</svg>", sent.string("svg"))
        // Drawn again, told the problem: quickly first
        val drawn = client.post("/api/lessons/$id/cards/$triangle/picture/draw") {
            page(); contentType(ContentType.Application.Json); setBody("""{"problem": "The angle is at B."}""")
        }.json().jsonObject
        assertEquals("The angle is at B." to "false", asked.last().second.string("problem") to asked.last().second["careful"].toString())
        assertTrue(drawn["card"]!!.jsonObject.string("picture").endsWith(".svg"))
        // Still wrong: drawn again with the model's thinking
        client.post("/api/lessons/$id/cards/$triangle/picture/draw") {
            page(); contentType(ContentType.Application.Json); setBody("""{"problem": "Still at B.", "careful": true}""")
        }
        assertEquals("Still at B." to "true", asked.last().second.string("problem") to asked.last().second["careful"].toString())
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
    fun photosSavedAsTakenThenTurnedByHand() = app { client ->
        // No turn guessed (SCH-04: the AI named a line's direction wrongly, a photo upside down):
        // the photo as taken, its mask and frame as the AI put them, whatever turn an older relay says
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
        assertEquals("photo 1", client.get("/api/lessons/$id/photos/1") { page() }.bodyAsText())
        fun box(of: JsonObject?) = of!!["box"]!!.jsonArray.map { it.jsonPrimitive.content.toDouble() }
        assertEquals(listOf(0.1, 0.2, 0.3, 0.5), box(lesson["cards"]!!.jsonArray[0].jsonObject["mask"]?.jsonObject))
        assertEquals(listOf(0.1, 0.2, 0.3, 0.5), box(lesson["frames"]!!.jsonArray[0].jsonObject))

        // ↻ in the review: a quarter, by hand, its mask with it
        val turned = client.post("/api/lessons/$id/photos/1/rotate") { page() }.json().jsonObject
        assertEquals("turned 90:photo 1", client.get("/api/lessons/$id/photos/1") { page() }.bodyAsText())
        assertEquals(Diagrams.rotateBox(listOf(0.1, 0.2, 0.3, 0.5), 90), box(turned["cards"]!!.jsonArray[0].jsonObject["mask"]?.jsonObject))
        assertEquals(HttpStatusCode.NotFound, client.post("/api/lessons/$id/photos/9/rotate") { page() }.status)
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
    fun deletedAndUnknownLessons() = app { client ->
        val id = client.extract().string("id")
        client.delete("/api/lessons/$id") { page() }
        val res = client.get("/api/lessons/$id") { page() }
        assertEquals(HttpStatusCode.NotFound, res.status)
        assertEquals("lesson.not_found", res.json().jsonObject["detail"]!!.jsonObject.string("code"))
        assertEquals(HttpStatusCode.NotFound, client.get("/api/lessons/$id/photos/1") { page() }.status)
    }

    @Test
    fun aLessonsSoundsInItsOwnFolder() = app { client ->
        val id = client.extract(voice = "").string("id")
        relay.takeRequest(5, TimeUnit.SECONDS) // the extraction
        val speaker = Speaker(voices = listOf("es-ES-Chirp3-HD-Aoede", "es-ES-Chirp3-HD-Puck"))
        relay.dispatcher = speaker
        client.saveLesson(id, listOf("la madre"))
        // 🔊 on its card (the page says its lesson): kept in the lesson, then sent without paying again
        val rate = client.get("/api/lessons/$id") { page() }.json().jsonObject.string("rate") // as the page sends it
        client.get("/api/tts?text=la%20madre&voice=es-ES-Chirp3-HD-Aoede&lesson=$id&rate=${rate.encodeURLParameter()}") { page() }
        client.sendLesson(id)
        assertEquals(listOf("la madre"), speaker.read)
        val r = rate.ifEmpty { "-10%" }
        val name = Speech.fileName("la madre", "es-ES-Chirp3-HD-Aoede", r)
        assertTrue(name.startsWith("la-madre-"))
        assertEquals(listOf(name), audioOf(id).list()!!.filter { it.endsWith(".mp3") })
        assertFalse(folder.root.resolve("audio").list()!!.any { it.endsWith(".mp3") }) // not among the previews

        // Its back corrected: sent, the old sound gone
        client.saveLesson(id, listOf("la mamá"))
        client.sendLesson(id)
        assertEquals(listOf(Speech.fileName("la mamá", "es-ES-Chirp3-HD-Aoede", r)), audioOf(id).list()!!.filter { it.endsWith(".mp3") })

        // Its voice changed for another of the relay's: read again with it
        client.saveLesson(id, listOf("la mamá"), voice = "es-ES-Chirp3-HD-Puck")
        client.sendLesson(id, voice = "es-ES-Chirp3-HD-Puck")
        assertEquals(listOf("la madre", "la mamá", "la mamá"), speaker.read)

        // Deleted: its sounds with it
        client.delete("/api/lessons/$id") { page() }
        assertFalse(audioOf(id).exists())
    }

    @Test
    fun aCardsOwnVoiceKeepsItsSoundMadeOnTheComputer() = app { client ->
        val id = client.extract(voice = "").string("id")
        relay.takeRequest(5, TimeUnit.SECONDS)
        val speaker = Speaker(voices = listOf("es-ES-Chirp3-HD-Aoede"))
        relay.dispatcher = speaker
        // As a lesson moved from the computer: each card's voice, edge-tts's; the lesson's, the relay's
        val cards = """[{"front": "la mère", "back": "la madre", "voice": "es-ES-ElviraNeural"},
            {"front": "le père", "back": "el padre", "voice": "es-ES-ElviraNeural"}, {"front": "le fils", "back": "el hijo"}]"""
        client.put("/api/lessons/$id") {
            page(); contentType(ContentType.Application.Json)
            setBody("""{"deck": "Espagnol", "cards": $cards, "voice": "es-ES-Chirp3-HD-Aoede", "rate": "-10%"}""")
        }
        audioOf(id).mkdirs()
        val madre = audioOf(id).resolve(Speech.fileName("la madre", "es-ES-ElviraNeural", "-10%")) // the same name there
        madre.writeText("computer's la madre")
        client.sendLesson(id)
        // la madre: the computer's, no credit; el padre (its sound not come) and el hijo: the lesson's voice
        assertEquals(setOf("el padre", "el hijo"), speaker.read.toSet())
        assertEquals("computer's la madre", anki.sounds["la madre"]!!.readText())
        assertTrue(madre.isFile) // still used: kept
        assertTrue(audioOf(id).resolve(Speech.fileName("el padre", "es-ES-Chirp3-HD-Aoede", "-10%")).isFile)
        // 🔊 on its card, its voice said by the page: the computer's sound
        val heard = client.get("/api/tts?text=la%20madre&voice=es-ES-ElviraNeural&lesson=$id&rate=-10%25") { page() }
        assertEquals("computer's la madre", heard.bodyAsText())
    }

    @Test
    fun soundsReadAheadOnceALessonIsSaved() = app { client ->
        val lesson = client.extract(voice = "")
        val id = lesson.string("id")
        relay.takeRequest(5, TimeUnit.SECONDS) // the extraction
        val speaker = Speaker()
        relay.dispatcher = speaker
        local.soundsAhead.delayMs = 50
        client.saveLesson(id, listOf("la madre", "el padre"))
        assertTrue(waitFor { speaker.read.toSet() == setOf("la madre", "el padre") && local.soundsAhead.pending().isEmpty() })

        // Sent as the page sends it (the lesson's rate): its sounds read already, the relay not asked again
        val saved = client.get("/api/lessons/$id") { page() }.json().jsonObject
        val lines = client.sendSteps("""{"deck": "Espagnol", "cards": ${saved["cards"]}, "voice": "es-ES-Chirp3-HD-Aoede", "rate": "${saved.string("rate")}", "lesson_id": "$id"}""")
        assertEquals(2, speaker.read.size)
        assertEquals(setOf("la madre", "el padre"), anki.sounds.keys)
        assertEquals("mp3 la madre", anki.sounds["la madre"]!!.readText())
        assertEquals(2, lines.last()["result"]!!.jsonObject["added"]!!.jsonPrimitive.int)

        // Saved as the user types: only the backs as last saved are read
        local.soundsAhead.delayMs = 300
        client.saveLesson(id, listOf("la mad"))
        client.saveLesson(id, listOf("la mamá"))
        assertTrue(waitFor { "la mamá" in speaker.read && local.soundsAhead.pending().isEmpty() })
        assertFalse("la mad" in speaker.read)

        // Nothing for a voice AnkiDroid reads, nor without a licence
        local.soundsAhead.delayMs = 10
        client.saveLesson(id, listOf("el hijo"), voice = "es_ES")
        assertTrue(local.soundsAhead.pending().isEmpty())
        prefs[LocalServer.keyOf(local.relayUrl())] = ""
        client.saveLesson(id, listOf("el hijo"))
        assertTrue(local.soundsAhead.pending().isEmpty())
        kotlinx.coroutines.delay(100)
        assertFalse("el hijo" in speaker.read)
    }
}
