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

/** The local server: GenerationRoutes.kt's routes. */
class GenerationRoutesTest : LocalServerTestBase() {
    @Test
    fun cancelledWhileTheRelayWorks() = app { client ->
        coroutineScope { cancelled(client) }
    }

    @Test
    fun cancelledWhileTheRelaysAnswerComes() = app { client ->
        // The relay answering as it goes, then slow to write the rest (the AI at work): "Cancel"
        // stops it then too, not only before its first line (the stream read, not waited for)
        val first = """{"step": {"step": "slow"}}""" + "\n"
        relay.enqueue(
            MockResponse.Builder().addHeader("Content-Type", Relay.STREAM_TYPE)
                // (the throttle also reads the request: a request under 4096 bytes isn't held)
                .body(first + "x".repeat(8192) + "\n").throttleBody(4096, 20, TimeUnit.SECONDS).build(),
        )
        coroutineScope {
            val made = async {
                client.submitFormWithBinaryData("/api/extract", formData { append("prompt", "FR → ES"); append("job", "j2") }) { page() }
            }
            assertNotNull(withContext(Dispatchers.IO) { relay.takeRequest(5, TimeUnit.SECONDS) })
            withContext(Dispatchers.IO) { Thread.sleep(500) } // its first line read
            assertTrue(client.post("/api/generations/j2/cancel") { page() }.json().jsonObject["cancelled"]!!.jsonPrimitive.content.toBoolean())
            val answer = withTimeout(5_000) { made.await() } // at once, not when the relay is done
            assertEquals("extract.cancelled", answer.json().jsonObject["detail"]!!.jsonObject.string("code"))
        }
    }

    @Test
    fun aCorrectionCancelledWhileTheRelayWorks() = app { client ->
        // "Cancel" while the AI corrects the lesson, or a card: the relay call stops, the lesson
        // as it was; told in the stream ({"cancelled"}), or 409 asked at once (a card's)
        val lesson = client.extract()
        relay.takeRequest()
        val id = lesson.string("id")
        val body = """{"deck": "Espagnol::Leçon 5", "cards": ${lesson["cards"]}, "instruction": "x"}"""
        val fixBody = """{"card": ${lesson["cards"]!!.jsonArray[0]}, "instruction": "x", "others": []}"""
        for ((path, job, streamed) in listOf(Triple("revise", "r1", true), Triple("revise", "r2", false), Triple("fix-card", "f1", false))) {
            relay.enqueue(MockResponse.Builder().headersDelay(10, TimeUnit.SECONDS).body("{}").build())
            coroutineScope {
                val asked = async {
                    client.post("/api/lessons/$id/$path?job=$job") {
                        page(); contentType(ContentType.Application.Json)
                        if (streamed) header(HttpHeaders.Accept, Relay.STREAM_TYPE)
                        setBody(if (path == "revise") body else fixBody)
                    }
                }
                assertNotNull(withContext(Dispatchers.IO) { relay.takeRequest(5, TimeUnit.SECONDS) }) // the relay at work
                val cancel = client.post("/api/generations/$job/cancel") { page() }.json().jsonObject
                assertTrue(cancel["cancelled"]!!.jsonPrimitive.content.toBoolean())
                val answer = withTimeout(5_000) { asked.await() } // at once, not when the relay is done
                if (streamed) {
                    assertEquals("""{"cancelled":true}""", answer.bodyAsText().trim())
                } else {
                    assertEquals(HttpStatusCode.Conflict, answer.status)
                    assertEquals("extract.cancelled", answer.json().jsonObject["detail"]!!.jsonObject.string("code"))
                }
            }
        }
        assertEquals(lesson["cards"], client.get("/api/lessons/$id") { page() }.json().jsonObject["cards"]) // as it was
    }

    @Test
    fun theCardsAsTheyComeThenTheLesson() = app { client ->
        val lines = listOf(
            """{"step": {"step": "slow"}}""", // what the AI is at: passed on to the page
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
        assertEquals("slow", items[0]["step"]!!.jsonObject.string("step"))
        assertEquals("la madre", items[1]["card"]!!.jsonObject.string("back"))
        val lesson = items[2]["lesson"]!!.jsonObject
        assertEquals("Espagnol", lesson.string("deck"))
        assertEquals(lesson, client.get("/api/lessons/${lesson.string("id")}") { page() }.json()) // saved

        // Corrected, asked as it goes: what the AI is at, then the answer
        val revision = listOf(
            """{"step": {"step": "fallback"}}""",
            """{"result": {"deck": "Espagnol", "cards": [{"front": "la mère", "back": "la madre", "info": "f."}], "summary": "ok", "usage": {"credits": 1, "credits_left": 98}}}""",
        )
        relay.enqueue(MockResponse.Builder().setHeader("Content-Type", Relay.STREAM_TYPE).body(revision.joinToString("\n", postfix = "\n")).build())
        val revised = client.post("/api/lessons/${lesson.string("id")}/revise") {
            page(); header(HttpHeaders.Accept, Relay.STREAM_TYPE); contentType(ContentType.Application.Json)
            setBody("""{"deck": "Espagnol", "cards": ${lesson["cards"]}, "instruction": "ajoute le genre"}""")
        }.bodyAsText().lines().filter { it.isNotBlank() }.map { json.parseToJsonElement(it).jsonObject }
        assertEquals("fallback", revised[0]["step"]!!.jsonObject.string("step"))
        assertEquals("ok", revised[1]["result"]!!.jsonObject.string("summary"))

        // An error: the last line, as the page translates it
        relay.enqueue(MockResponse.Builder().code(402).body("""{"code": "relay.no_credits", "params": {}}""").build())
        val failed = client.submitFormWithBinaryData("/api/extract", formData { append("prompt", "p") }) {
            page()
            header(HttpHeaders.Accept, Relay.STREAM_TYPE)
        }.bodyAsText().trim()
        assertEquals("relay.no_credits", json.parseToJsonElement(failed).jsonObject["error"]!!.jsonObject.string("code"))
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
    fun eachCardsPictureStepsToldAsTheRelayTellsThem() = app { client ->
        relayAnswers("""{"deck": {"deck": "Maths", "cards": [
            {"front": "Ce triangle ?", "back": "rectangle", "figure": "a right triangle"}]}, "turns": [], "usage": {"credits": 1, "credits_left": 99}}""")
        val lesson = client.submitFormWithBinaryData("/api/extract", formData { append("prompt", "p") }) { page() }.json().jsonObject
        val (id, triangle) = lesson.string("id") to lesson["cards"]!!.jsonArray.single().jsonObject.string("id")
        // The relay's steps as the core tells them (relay_api.CardPictureLine), then its answer
        relay.dispatcher = object : mockwebserver3.Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                val card = json.parseToJsonElement(request.body!!.utf8()).jsonObject["card"]!!
                val svg = Base64.getEncoder().encodeToString("<svg/>".toByteArray())
                val answer = """{"card": $card, "data": "$svg", "media_type": "image/svg+xml", "usage": {"credits": 3, "credits_left": 90}}"""
                val lines = listOf(
                    """{"step": {"step": "drawing", "problem": "", "first": ""}}""",
                    """{"step": {"step": "checking", "problem": "", "first": ""}}""",
                    """{"step": {"step": "redrawing", "problem": "Off its segment.", "first": "<svg>1</svg>"}}""",
                    """{"result": $answer}""",
                )
                return MockResponse.Builder().addHeader("Content-Type", Relay.STREAM_TYPE).body(lines.joinToString("\n") + "\n").build()
            }
        }
        val response = client.post("/api/lessons/$id/pictures") {
            page(); header(HttpHeaders.Accept, Relay.STREAM_TYPE)
            contentType(ContentType.Application.Json); setBody("""{"draw": true}""")
        }
        val lines = response.bodyAsText().lines().filter { it.isNotBlank() }.map { json.parseToJsonElement(it).jsonObject }
        val steps = lines.filter { "step" in it }
        assertEquals(listOf("drawing", "checking", "redrawing", "ready"), steps.map { it.string("step") })
        assertTrue(steps.all { it.string("card") == triangle })
        val redrawing = steps[2]
        assertEquals("Off its segment." to "<svg>1</svg>", redrawing.string("problem") to redrawing.string("first"))
        val drawn = lines.last()["result"]!!.jsonObject["lesson"]!!.jsonObject["cards"]!!.jsonArray.single().jsonObject
        assertTrue(drawn.string("picture").endsWith(".svg"))
        // Its picture told the moment it has it, not when the others are done
        assertEquals(drawn.string("picture"), steps.last().string("picture"))

        // "✨ Image" on that card, asked as it goes: its steps nested ({"step": {…}}), then the answer
        val made = client.post("/api/lessons/$id/cards/$triangle/picture/make") {
            page(); header(HttpHeaders.Accept, Relay.STREAM_TYPE)
            contentType(ContentType.Application.Json); setBody("""{"subject": null}""")
        }.bodyAsText().lines().filter { it.isNotBlank() }.map { json.parseToJsonElement(it).jsonObject }
        assertEquals(listOf("drawing", "checking", "redrawing"), made.dropLast(1).map { it["step"]!!.jsonObject.string("step") })
        assertTrue(made.last()["result"]!!.jsonObject["card"]!!.jsonObject.string("picture").endsWith(".svg"))
    }

    @Test
    fun theLessonsOwnDrawingsTakenFirst() = app { client ->
        relayAnswers("""{"deck": {"deck": "Anglais", "cards": [
            {"front": "le chat", "back": "the cat", "picture_prompt": "a cat"},
            {"front": "le chien", "back": "the dog", "picture_prompt": "a dog"},
            {"front": "Ce triangle ?", "back": "rectangle", "figure": "a right triangle"}]}, "turns": [0], "usage": {"credits": 1, "credits_left": 99}}""")
        val lesson = client.submitFormWithBinaryData("/api/extract", formData {
            append("images", "the page".toByteArray(), Headers.build {
                append(HttpHeaders.ContentType, "image/jpeg")
                append(HttpHeaders.ContentDisposition, "filename=\"page-1.jpg\"")
            })
            append("prompt", "p")
        }) { page() }.json().jsonObject
        val id = lesson.string("id")
        // Written from the fake relay's threads: the other cards' pictures are asked at once (Pictures.AT_ONCE)
        val asked: MutableList<String> = java.util.Collections.synchronizedList(mutableListOf())
        relay.dispatcher = object : mockwebserver3.Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse = when (request.url.encodedPath) {
                "/v1/lesson-drawings" -> {
                    val body = request.body!!.utf8()
                    asked += "lesson-drawings " + request.multipartRequest()["cards"]!!.jsonArray.size + " " + body.contains("the page")
                    val cat = Base64.getEncoder().encodeToString("the cat, cut out".toByteArray())
                    MockResponse.Builder().body("""{"drawings": [{"card": 0, "data": "$cat"}], "usage": {"credits": 1, "credits_left": 98}}""").build()
                }
                "/v1/card-picture" -> {
                    asked += "card-picture " + json.parseToJsonElement(request.body!!.utf8()).jsonObject["card"]!!.jsonObject.string("front")
                    cardPicture(request)
                }
                else -> MockResponse.Builder().code(404).build()
            }
        }
        val drawn = client.post("/api/lessons/$id/pictures") {
            page(); contentType(ContentType.Application.Json); setBody("""{"draw": true}""")
        }.json().jsonObject
        // One call for the lesson's drawings (the pictures' cards, the photo), then the others one by one
        assertEquals("lesson-drawings 2 true", asked.first())
        assertEquals(setOf("card-picture le chien", "card-picture Ce triangle ?"), asked.drop(1).toSet())
        val cat = drawn["lesson"]!!.jsonObject["cards"]!!.jsonArray.first().jsonObject
        assertEquals("lesson", cat["picture_source"]!!.jsonObject.string("source"))
        assertEquals("the cat, cut out", client.get("/api/lessons/$id/pictures/${cat.string("picture")}") { page() }.bodyAsText())
    }

    /** Pages `numbers` as the page sends them, each "page #n;" (found again in what the relay gets). */
    private fun pageForm(numbers: IntRange) = formData {
        for (n in numbers) {
            append("images", "page #$n;".toByteArray(), Headers.build {
                append(HttpHeaders.ContentType, "image/jpeg")
                append(HttpHeaders.ContentDisposition, "filename=\"page-$n.jpg\"")
            })
        }
        append("prompt", "p")
    }

    @Test
    fun aCardsPageCountedAmongTheLessonsPhotos() = app { client ->
        // The AI numbers the photos of its call: a page past them is unknown (0); a lesson
        // completed numbers its next pages' cards after its own, its older cards untouched
        relayAnswers("""{"deck": {"deck": "Anglais", "cards": [
            {"front": "le chat", "back": "the cat", "page": 3},
            {"front": "le chien", "back": "the dog"},
            {"front": "l'oiseau", "back": "the bird", "page": 11}]}, "turns": [], "usage": {"credits": 1, "credits_left": 99}}""")
        val id = client.submitFormWithBinaryData("/api/extract", pageForm(1..10)) { page() }.json().jsonObject.string("id")
        relayAnswers("""{"deck": {"deck": "Anglais", "cards": [
            {"front": "le ciel", "back": "the sky", "page": 2},
            {"front": "la mer", "back": "the sea", "page": 3},
            {"front": "la terre", "back": "the earth", "page": 0}]}, "turns": [], "usage": {"credits": 1, "credits_left": 98}}""")
        val lesson = client.submitFormWithBinaryData("/api/lessons/$id/complete", pageForm(11..12)) { page() }.json().jsonObject
        assertEquals(listOf(3, 0, 0, 12, 0, 0), lesson.cards().map { it["page"]!!.jsonPrimitive.int })
        assertEquals("page #3;", folder.root.resolve("lessons/$id/page-3.jpg").readText()) // the older card's page still its photo
        // Made again: from 1
        relayAnswers("""{"deck": {"deck": "Anglais", "cards": [{"front": "le chat", "back": "the cat", "page": 2}]},
            "turns": [], "usage": {"credits": 1, "credits_left": 97}}""")
        val again = client.submitFormWithBinaryData("/api/lessons/$id/regenerate", pageForm(1..2)) { page() }.json().jsonObject
        assertEquals(listOf(2), again.cards().map { it["page"]!!.jsonPrimitive.int })
    }

    @Test
    fun aCardCorrectedWithItsOwnPageAlone() = app { client ->
        // A lesson of 12 pages (more than the relay takes at once): a card corrected sends the
        // page it comes from alone; an older card's (no page) sends none, rather than all 12
        // (relay.too_large); a short lesson's older card, all of them, as before
        relayAnswers("""{"deck": {"deck": "Anglais", "cards": [{"front": "le chat", "back": "the cat"}]}, "turns": [],
            "usage": {"credits": 1, "credits_left": 99}}""")
        val id = client.submitFormWithBinaryData("/api/extract", pageForm(1..10)) { page() }.json().jsonObject.string("id")
        relayAnswers("""{"deck": {"deck": "Anglais", "cards": [{"front": "le ciel", "back": "the sky", "page": 2}]},
            "turns": [], "usage": {"credits": 1, "credits_left": 98}}""")
        val long = client.submitFormWithBinaryData("/api/lessons/$id/complete", pageForm(11..12)) { page() }.json().jsonObject
        relayAnswers("""{"deck": {"deck": "Anglais", "cards": [{"front": "le chat", "back": "the cat"}]}, "turns": [],
            "usage": {"credits": 1, "credits_left": 97}}""")
        val short = client.submitFormWithBinaryData("/api/extract", pageForm(1..3)) { page() }.json().jsonObject

        val sent = mutableListOf<Pair<List<Int>, String>>()
        relay.dispatcher = object : mockwebserver3.Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                if (request.url.encodedPath != "/v1/fix-card") return MockResponse.Builder().code(404).build()
                val body = request.body!!.utf8()
                val asked = request.multipartRequest()
                sent += (1..12).filter { body.contains("page #$it;") } to asked.string("photos_sent")
                if (sent.last().first.size > 10) return MockResponse.Builder().code(413).body("""{"code": "relay.too_large"}""").build()
                val card = JsonObject(asked["card"]!!.jsonObject + ("back" to JsonPrimitive("fixed")))
                return MockResponse.Builder().body("""{"card": $card, "summary": "ok", "usage": {"credits": 1, "credits_left": 90}}""").build()
            }
        }
        suspend fun fix(lesson: JsonObject, card: JsonObject): JsonObject {
            val res = client.post("/api/lessons/${lesson.string("id")}/fix-card") {
                page(); contentType(ContentType.Application.Json)
                setBody("""{"card": $card, "instruction": "x", "others": []}""")
            }
            assertEquals(HttpStatusCode.OK, res.status)
            return res.json().jsonObject["card"]!!.jsonObject
        }
        val (older, known) = long.cards()
        assertEquals(12, known["page"]!!.jsonPrimitive.int)
        assertEquals(12, fix(long, known)["page"]!!.jsonPrimitive.int) // its page kept
        assertEquals(listOf(12) to "card", sent.last())
        assertEquals("fixed", fix(long, older).string("back")) // corrected all the same
        assertEquals(emptyList<Int>() to "none", sent.last())
        fix(short, short.cards()[0])
        assertEquals((1..3).toList() to "all", sent.last())
    }

    @Test
    fun aLongLessonCorrectedFromItsCards() = app { client ->
        // A lesson of 12 pages (more than the relay takes at once): corrected as a whole, it sends
        // none of them, "photos_sent" "none" (the AI told its pages aren't shown), rather than all
        // 12 (relay.too_large); a lesson of 10, all of them
        relayAnswers("""{"deck": {"deck": "Anglais", "cards": [{"front": "le chat", "back": "the cat", "page": 1}]},
            "turns": [], "usage": {"credits": 1, "credits_left": 99}}""")
        val ten = client.submitFormWithBinaryData("/api/extract", pageForm(1..10)) { page() }.json().jsonObject
        relayAnswers("""{"deck": {"deck": "Anglais", "cards": [{"front": "le chat", "back": "the cat", "page": 1}]},
            "turns": [], "usage": {"credits": 1, "credits_left": 98}}""")
        val id = client.submitFormWithBinaryData("/api/extract", pageForm(1..10)) { page() }.json().jsonObject.string("id")
        relayAnswers("""{"deck": {"deck": "Anglais", "cards": [{"front": "le ciel", "back": "the sky", "page": 2}]},
            "turns": [], "usage": {"credits": 1, "credits_left": 97}}""")
        val long = client.submitFormWithBinaryData("/api/lessons/$id/complete", pageForm(11..12)) { page() }.json().jsonObject

        val sent = mutableListOf<Pair<List<Int>, String>>()
        relay.dispatcher = object : mockwebserver3.Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                if (request.url.encodedPath != "/v1/revise") return MockResponse.Builder().code(404).build()
                val body = request.body!!.utf8()
                val asked = request.multipartRequest()
                sent += (1..12).filter { body.contains("page #$it;") } to asked.string("photos_sent")
                if (sent.last().first.size > 10) return MockResponse.Builder().code(413).body("""{"code": "relay.too_large"}""").build()
                val cards = asked["deck"]!!.jsonObject["cards"]!!
                return MockResponse.Builder().body(
                    """{"deck": "Anglais", "cards": $cards, "summary": "ok", "usage": {"credits": 1, "credits_left": 90}}"""
                ).build()
            }
        }
        suspend fun revise(lesson: JsonObject): JsonObject {
            val res = client.post("/api/lessons/${lesson.string("id")}/revise") {
                page(); contentType(ContentType.Application.Json)
                setBody("""{"deck": "Anglais", "cards": ${lesson["cards"]}, "instruction": "x"}""")
            }
            assertEquals(HttpStatusCode.OK, res.status)
            return res.json().jsonObject
        }
        assertEquals(12, long["photo_count"]!!.jsonPrimitive.int)
        val revised = revise(long)
        assertEquals("ok", revised.string("summary")) // corrected all the same
        assertEquals(emptyList<Int>() to "none", sent.last())
        assertEquals(listOf(1, 12), revised["lesson"]!!.jsonObject.cards().map { it["page"]!!.jsonPrimitive.int })
        revise(ten)
        assertEquals((1..10).toList() to "all", sent.last())
    }

    @Test
    fun theLessonsOwnDrawingsLookedForTenPagesAtATime() = app { client ->
        // A lesson of 12 pages: 10 read at once, then its 2 next ones
        fun pages(numbers: IntRange) = formData {
            for (n in numbers) {
                append("images", "page #$n;".toByteArray(), Headers.build {
                    append(HttpHeaders.ContentType, "image/jpeg")
                    append(HttpHeaders.ContentDisposition, "filename=\"page-$n.jpg\"")
                })
            }
            append("prompt", "p")
        }
        relayAnswers("""{"deck": {"deck": "Anglais", "cards": [
            {"front": "le chat", "back": "the cat", "picture_prompt": "a cat"},
            {"front": "le chien", "back": "the dog", "picture_prompt": "a dog"},
            {"front": "l'oiseau", "back": "the bird", "picture_prompt": "a bird"}]}, "turns": [0], "usage": {"credits": 1, "credits_left": 99}}""")
        val id = client.submitFormWithBinaryData("/api/extract", pages(1..10)) { page() }.json().jsonObject.string("id")
        relayAnswers("""{"deck": {"deck": "Anglais", "cards": [{"front": "le ciel", "back": "the sky"}]}, "turns": [0],
            "usage": {"credits": 1, "credits_left": 98}}""")
        assertEquals(12, client.submitFormWithBinaryData("/api/lessons/$id/complete", pages(11..12)) { page() }
            .json().jsonObject["photo_count"]!!.jsonPrimitive.int)
        // Written from the fake relay's threads: the other cards' pictures are asked at once (Pictures.AT_ONCE)
        val asked: MutableList<String> = java.util.Collections.synchronizedList(mutableListOf())
        relay.dispatcher = object : mockwebserver3.Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse = when (request.url.encodedPath) {
                "/v1/lesson-drawings" -> {
                    val body = request.body!!.utf8()
                    val sent = (1..12).filter { body.contains("page #$it;") }
                    val fronts = request.multipartRequest()["cards"]!!.jsonArray.map { it.jsonObject.string("front") }
                    asked += "lesson-drawings ${sent.first()}-${sent.last()} (${sent.size}) $fronts"
                    // The relay's cap (relay_api.MAX_IMAGES): more refused
                    if (sent.size > 10) MockResponse.Builder().code(413).body("""{"code": "relay.too_large"}""").build()
                    else {
                        // The cat on the first pages, the bird on the last: each an index into the cards sent
                        val found = if (1 in sent) "le chat" to "the cat, cut out" else "l'oiseau" to "the bird, cut out"
                        val data = Base64.getEncoder().encodeToString(found.second.toByteArray())
                        MockResponse.Builder().body("""{"drawings": [{"card": ${fronts.indexOf(found.first)}, "data": "$data"}],
                            "usage": {"credits": 1, "credits_left": 97}}""").build()
                    }
                }
                "/v1/card-picture" -> {
                    asked += "card-picture " + json.parseToJsonElement(request.body!!.utf8()).jsonObject["card"]!!.jsonObject.string("front")
                    cardPicture(request)
                }
                else -> MockResponse.Builder().code(404).build()
            }
        }
        val drawn = client.post("/api/lessons/$id/pictures") {
            page(); contentType(ContentType.Application.Json); setBody("""{"draw": true}""")
        }.json().jsonObject
        // Two calls of at most 10 pages, one after the other: the cat found in the first not asked again
        assertEquals(
            listOf("lesson-drawings 1-10 (10) [le chat, le chien, l'oiseau]", "lesson-drawings 11-12 (2) [le chien, l'oiseau]"),
            asked.take(2),
        )
        assertEquals(listOf("card-picture le chien"), asked.drop(2))
        val cards = drawn["lesson"]!!.jsonObject["cards"]!!.jsonArray.map { it.jsonObject }
        for ((card, cutOut) in listOf(cards[0] to "the cat, cut out", cards[2] to "the bird, cut out")) {
            assertEquals("lesson", card["picture_source"]!!.jsonObject.string("source"))
            assertEquals(cutOut, client.get("/api/lessons/$id/pictures/${card.string("picture")}") { page() }.bodyAsText())
        }
    }

    @Test
    fun aPictureACorrectionReplacedNotCutOutOfTheLessonAgain() = app { client ->
        relayAnswers("""{"deck": {"deck": "Anglais", "cards": [
            {"front": "le chat", "back": "the cat", "picture_prompt": "a cat"},
            {"front": "le chien", "back": "the dog", "picture_prompt": "a dog"},
            {"front": "Ce triangle ?", "back": "rectangle", "figure": "a right triangle"}]}, "turns": [0], "usage": {"credits": 1, "credits_left": 99}}""")
        val lesson = client.submitFormWithBinaryData("/api/extract", formData {
            append("images", "the page".toByteArray(), Headers.build {
                append(HttpHeaders.ContentType, "image/jpeg")
                append(HttpHeaders.ContentDisposition, "filename=\"page-1.jpg\"")
            })
            append("prompt", "p")
        }) { page() }.json().jsonObject
        val id = lesson.string("id")
        // The cat's picture replaced by a correction: the lesson's drawing would only come back
        val cat = lesson["cards"]!!.jsonArray.first().jsonObject.string("id")
        // Written from the fake relay's threads: the other cards' pictures are asked at once (Pictures.AT_ONCE)
        val asked: MutableList<String> = java.util.Collections.synchronizedList(mutableListOf())
        relay.dispatcher = object : mockwebserver3.Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse = when (request.url.encodedPath) {
                "/v1/lesson-drawings" -> {
                    val body = request.body!!.utf8()
                    asked += "lesson-drawings " + request.multipartRequest()["cards"]!!.jsonArray.size + " " + body.contains("the page")
                    val cat = Base64.getEncoder().encodeToString("the cat, cut out".toByteArray())
                    MockResponse.Builder().body("""{"drawings": [{"card": 0, "data": "$cat"}], "usage": {"credits": 1, "credits_left": 98}}""").build()
                }
                "/v1/card-picture" -> {
                    asked += "card-picture " + json.parseToJsonElement(request.body!!.utf8()).jsonObject["card"]!!.jsonObject.string("front")
                    cardPicture(request)
                }
                else -> MockResponse.Builder().code(404).build()
            }
        }
        val drawn = client.post("/api/lessons/$id/pictures") {
            page(); contentType(ContentType.Application.Json); setBody("""{"draw": true, "not_from_lesson": ["$cat"]}""")
        }.json().jsonObject
        // The lesson looked at for the dog only; the cat's picture looked for as any other
        assertEquals("lesson-drawings 1 true", asked.first())
        assertEquals(setOf("card-picture le chat", "card-picture Ce triangle ?"), asked.drop(1).toSet())
        val drawnCat = drawn["lesson"]!!.jsonObject["cards"]!!.jsonArray.first().jsonObject
        assertTrue(drawnCat.string("picture").isNotBlank())
        assertTrue((drawnCat["picture_source"] as? JsonObject)?.string("source") != "lesson")
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
    fun moreThanALessonsPagesRefusedAtOnce() = app { client ->
        // Eleven photos: refused before anything is sent to the relay, with the limit said
        val refused = client.submitFormWithBinaryData(
            "/api/extract",
            formData {
                repeat(11) { i ->
                    append("images", "photo $i".toByteArray(), Headers.build {
                        append(HttpHeaders.ContentType, "image/jpeg")
                        append(HttpHeaders.ContentDisposition, "filename=\"p$i.jpg\"")
                    })
                }
                append("prompt", "FR → ES")
            },
        ) { page() }
        assertEquals(HttpStatusCode.BadRequest, refused.status)
        val detail = refused.json().jsonObject["detail"]!!.jsonObject
        assertEquals("extract.too_many", detail.string("code"))
        assertEquals(10, detail["params"]!!.jsonObject["max"]!!.jsonPrimitive.int)
        assertEquals(null, relay.takeRequest(200, TimeUnit.MILLISECONDS))
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
}
