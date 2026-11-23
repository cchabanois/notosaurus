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

/** The local server: PictureRoutes.kt's routes. */
class PictureRoutesTest : LocalServerTestBase() {
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

    @Test
    fun noPruneWhileDrawnAndNoCardAddedMeanwhileDropped() = app { client ->
        relayAnswers("""{"deck": {"deck": "Maths", "cards": [{"front": "Ce triangle ?", "back": "rectangle", "figure": "a right triangle"},
            {"front": "Ce carré ?", "back": "un carré", "figure": "a square"}]}, "turns": [], "usage": {"credits": 1, "credits_left": 99}}""")
        val lesson = client.submitFormWithBinaryData("/api/extract", formData { append("prompt", "p") }) { page() }.json().jsonObject
        relay.takeRequest(5, TimeUnit.SECONDS) // the extraction
        val id = lesson.string("id")
        val held = java.util.concurrent.CountDownLatch(1)
        relay.dispatcher = object : mockwebserver3.Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                val asked = json.parseToJsonElement(request.body!!.utf8()).jsonObject
                if (asked["card"]!!.jsonObject.string("figure") == "a square") held.await(10, TimeUnit.SECONDS) // drawn slowly
                return cardPicture(request)
            }
        }
        val images = folder.root.resolve("lessons/$id/images")
        coroutineScope {
            val drawing = async(Dispatchers.IO) {
                client.post("/api/lessons/$id/pictures") { page(); contentType(ContentType.Application.Json); setBody("{}") }.json().jsonObject
            }
            assertTrue(waitFor { images.listFiles().orEmpty().isNotEmpty() }) // the triangle's: in no saved card yet
            val first = images.listFiles()!!.single()
            // A prune asked meanwhile (a reload, the lesson opened again): none
            assertEquals(0, client.post("/api/lessons/$id/pictures/prune") { page() }.json().jsonObject["removed"]!!.jsonPrimitive.int)
            assertTrue(first.isFile)
            // The page saves a card added meanwhile (the next pages' cards, completed)
            val saved = client.get("/api/lessons/$id") { page() }.json().jsonObject["cards"]!!.jsonArray
            val added = JsonArray(saved + buildJsonObject { put("front", "Ce cercle ?"); put("back", "un cercle") })
            client.put("/api/lessons/$id") { page(); contentType(ContentType.Application.Json); setBody("""{"deck": "Maths", "cards": $added}""") }
            held.countDown()
            val cards = drawing.await()["lesson"]!!.jsonObject["cards"]!!.jsonArray.map { it.jsonObject }
            assertEquals(listOf("Ce triangle ?", "Ce carré ?", "Ce cercle ?"), cards.map { it.string("front") }) // kept
            assertEquals(first.name, cards[0].string("picture"))
            assertTrue(cards[1].string("picture").endsWith(".svg"))
        }
        assertEquals(0, client.post("/api/lessons/$id/pictures/prune") { page() }.json().jsonObject["removed"]!!.jsonPrimitive.int)
        assertTrue(images.resolve(client.get("/api/lessons/$id") { page() }.json().jsonObject["cards"]!!.jsonArray[0].jsonObject.string("picture")).isFile)
    }

    @Test
    fun anEditsCardsMergedIntoTheLessonsAsSavedNow() {
        fun card(id: String, vararg fields: Pair<String, String>) =
            JsonObject(mapOf("id" to JsonPrimitive(id), "front" to JsonPrimitive(id)) + fields.map { it.first to JsonPrimitive(it.second) })
        val before = listOf(card("a"), card("b"), card("c"))
        val after = listOf(card("a", "picture" to "pa.jpg"), card("d"), card("c")) // b removed, d added
        val now = listOf(card("a", "back" to "A"), card("b"), card("c", "front" to "C"), card("e"))
        assertEquals(
            listOf(card("a", "back" to "A", "picture" to "pa.jpg"), card("c", "front" to "C"), card("e"), card("d")),
            Pictures.mergedCards(before, after, now),
        )
        val noIds = listOf(JsonObject(mapOf("front" to JsonPrimitive("x"))))
        assertEquals(listOf(card("a")), Pictures.mergedCards(noIds, listOf(card("a")), listOf(card("b")))) // the edit's
    }
}
