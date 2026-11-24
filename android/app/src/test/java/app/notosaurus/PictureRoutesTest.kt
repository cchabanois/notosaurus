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
import io.ktor.utils.io.ByteReadChannel
import io.ktor.utils.io.readRemaining
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import kotlinx.io.readByteArray
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
    fun aCardsOwnPhotoTooHeavyRefused() = app { client ->
        relayAnswers("""{"deck": {"deck": "Anglais", "cards": [{"front": "the cat", "back": "le chat"}]}, "turns": [], "usage": {"credits": 1, "credits_left": 99}}""")
        val lesson = client.submitFormWithBinaryData("/api/extract", formData { append("prompt", "p") }) { page() }.json().jsonObject
        val (id, card) = lesson.string("id") to lesson["cards"]!!.jsonArray.single().jsonObject.string("id")
        suspend fun own(photo: ByteArray) = client.submitFormWithBinaryData("/api/lessons/$id/cards/$card/picture", formData {
            append("photo", photo, Headers.build {
                append(HttpHeaders.ContentType, "image/jpeg")
                append(HttpHeaders.ContentDisposition, "filename=\"photo.jpg\"")
            })
        }) { page() }
        // Heavier than the relay takes (as the computer, read_photo): refused, the card as it was
        val heavy = own(ByteArray(LocalServer.MAX_IMAGE_BYTES + 1))
        assertEquals(HttpStatusCode.BadRequest, heavy.status)
        val error = heavy.json().jsonObject["detail"]!!.jsonObject
        assertEquals("extract.too_large" to 4, error.string("code") to error["params"]!!.jsonObject["max"]!!.jsonPrimitive.int)
        assertEquals("", client.get("/api/lessons/$id") { page() }.json().jsonObject.cards().single().string("picture"))
        // At the cap: taken
        assertEquals(HttpStatusCode.Created, own(jpeg("").copyOf(LocalServer.MAX_IMAGE_BYTES)).status)
    }

    @Test
    fun aCardsOwnPhotoOfAnotherKindRefused() = app { client ->
        relayAnswers("""{"deck": {"deck": "Anglais", "cards": [{"front": "the cat", "back": "le chat"}]}, "turns": [], "usage": {"credits": 1, "credits_left": 99}}""")
        val lesson = client.submitFormWithBinaryData("/api/extract", formData { append("prompt", "p") }) { page() }.json().jsonObject
        val (id, card) = lesson.string("id") to lesson["cards"]!!.jsonArray.single().jsonObject.string("id")
        suspend fun own(photo: ByteArray, type: String) = client.submitFormWithBinaryData("/api/lessons/$id/cards/$card/picture", formData {
            append("photo", photo, Headers.build {
                append(HttpHeaders.ContentType, type)
                append(HttpHeaders.ContentDisposition, "filename=\"photo\"")
            })
        }) { page() }
        // Not a kind a card shows, or not an image of its kind: refused as the computer's
        // (extract.bad_format, its format), the card as it was
        for ((photo, type) in listOf(jpeg("") to "application/pdf", "not an image".toByteArray() to "image/jpeg", jpeg("") to "image/svg+xml")) {
            val refused = own(photo, type)
            assertEquals(type, HttpStatusCode.BadRequest, refused.status)
            val error = refused.json().jsonObject["detail"]!!.jsonObject
            assertEquals("extract.bad_format" to type, error.string("code") to error["params"]!!.jsonObject.string("format"))
        }
        assertEquals("", client.get("/api/lessons/$id") { page() }.json().jsonObject.cards().single().string("picture"))
        // Each kind the computer takes, by its first bytes
        val png = byteArrayOf(0x89.toByte(), 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A)
        val webp = "RIFF".toByteArray() + ByteArray(4) + "WEBPVP8 ".toByteArray()
        for ((photo, type) in listOf(jpeg("") to "image/jpeg", png to "image/png", webp to "image/webp", "GIF89a".toByteArray() to "image/gif")) {
            assertEquals(type, HttpStatusCode.Created, own(photo, type).status)
        }
    }

    @Test
    fun picturesOfALongCardLookedForItCut() = app { client ->
        // A card has no length limit: its context cut to MAX_CARD ("…" last), the search never refused
        relay.enqueue(MockResponse.Builder().setHeader("Content-Type", "application/json")
            .body("""{"results": [], "words": "castle", "usage": {"credits": 1, "credits_left": 99}}""").build())
        val context = "q → " + "b".repeat(6000)
        val res = client.post("/api/pictures/search") {
            page(); contentType(ContentType.Application.Json)
            setBody(buildJsonObject { put("subject", "un château"); put("context", context) }.toString())
        }
        assertEquals(HttpStatusCode.OK, res.status)
        val sent = json.parseToJsonElement(relay.takeRequest(5, TimeUnit.SECONDS)!!.body!!.utf8()).jsonObject.string("context")
        assertEquals(Pictures.MAX_CARD, sent.length)
        assertEquals(context.take(Pictures.MAX_CARD - 1) + "…", sent)
    }

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
    fun aPictureDrawnFromWhatItsCardNoLongerSaysSetAside() = app { client ->
        relayAnswers("""{"deck": {"deck": "Maths", "cards": [{"front": "Ce triangle ?", "back": "rectangle", "figure": "a right triangle"},
            {"front": "Ce carré ?", "back": "un carré", "figure": "a square"}]}, "turns": [], "usage": {"credits": 1, "credits_left": 99}}""")
        val lesson = client.submitFormWithBinaryData("/api/extract", formData { append("prompt", "p") }) { page() }.json().jsonObject
        relay.takeRequest(5, TimeUnit.SECONDS) // the extraction
        val id = lesson.string("id")
        val held = java.util.concurrent.CountDownLatch(1)
        val asked = java.util.Collections.synchronizedList(mutableListOf<String>())
        relay.dispatcher = object : mockwebserver3.Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                val figure = json.parseToJsonElement(request.body!!.utf8()).jsonObject["card"]!!.jsonObject.string("figure")
                asked += figure
                if (figure == "a square") held.await(10, TimeUnit.SECONDS) // drawn slowly
                return cardPicture(request)
            }
        }
        suspend fun drawn() = client.post("/api/lessons/$id/pictures") { page(); contentType(ContentType.Application.Json); setBody("{}") }
            .json().jsonObject["lesson"]!!.jsonObject["cards"]!!.jsonArray.map { it.jsonObject }
        coroutineScope {
            val drawing = async(Dispatchers.IO) { drawn() }
            assertTrue(waitFor { "a square" in asked })
            // The page saves the square's correction meanwhile: what its figure shows changed
            val saved = client.get("/api/lessons/$id") { page() }.json().jsonObject["cards"]!!.jsonArray.map { it.jsonObject }
            val corrected = JsonArray(listOf(saved[0], saved[1].with("figure" to JsonPrimitive("a red square"))))
            client.put("/api/lessons/$id") { page(); contentType(ContentType.Application.Json); setBody("""{"deck": "Maths", "cards": $corrected}""") }
            held.countDown()
            val cards = drawing.await()
            assertTrue(cards[0].string("picture").endsWith(".svg")) // the triangle's: as it says
            assertEquals("a red square", cards[1].string("figure"))
            assertEquals("", cards[1].string("picture")) // not the square drawn before
            assertEquals(cards, client.get("/api/lessons/$id") { page() }.json().jsonObject["cards"]!!.jsonArray.map { it.jsonObject })
        }
        val cards = drawn() // drawn as it says now
        assertEquals("a red square", asked.last())
        assertTrue(cards[1].string("picture").endsWith(".svg"))
    }

    @Test
    fun aPictureChosenWhileTheLessonIsDrawnKept() = app { client ->
        relayAnswers("""{"deck": {"deck": "Maths", "cards": [{"front": "Ce triangle ?", "back": "rectangle", "figure": "a right triangle"},
            {"front": "Ce carré ?", "back": "un carré", "figure": "a square"}]}, "turns": [], "usage": {"credits": 1, "credits_left": 99}}""")
        val lesson = client.submitFormWithBinaryData("/api/extract", formData { append("prompt", "p") }) { page() }.json().jsonObject
        relay.takeRequest(5, TimeUnit.SECONDS) // the extraction
        val id = lesson.string("id")
        val square = lesson["cards"]!!.jsonArray[1].jsonObject.string("id")
        val held = java.util.concurrent.CountDownLatch(1)
        val asked = java.util.Collections.synchronizedList(mutableListOf<String>())
        relay.dispatcher = object : mockwebserver3.Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                val figure = json.parseToJsonElement(request.body!!.utf8()).jsonObject["card"]!!.jsonObject.string("figure")
                asked += figure
                if (figure == "a square") held.await(10, TimeUnit.SECONDS) // drawn slowly
                return cardPicture(request)
            }
        }
        coroutineScope {
            val drawing = async(Dispatchers.IO) {
                client.post("/api/lessons/$id/pictures") { page(); contentType(ContentType.Application.Json); setBody("{}") }
                    .json().jsonObject["lesson"]!!.jsonObject["cards"]!!.jsonArray.map { it.jsonObject }
            }
            assertTrue(waitFor { "a square" in asked })
            // The user's own photo for the square meanwhile (its controls still there)
            val own = client.submitFormWithBinaryData("/api/lessons/$id/cards/$square/picture", formData {
                append("photo", jpeg("mine"), Headers.build {
                    append(HttpHeaders.ContentType, "image/jpeg")
                    append(HttpHeaders.ContentDisposition, "filename=\"photo.jpg\"")
                })
            }) { page() }.json().jsonObject["card"]!!.jsonObject.string("picture")
            held.countDown()
            val cards = drawing.await()
            assertTrue(cards[0].string("picture").endsWith(".svg")) // the triangle's: drawn
            assertEquals(own, cards[1].string("picture")) // not the square drawn meanwhile
            assertEquals("photo", cards[1]["picture_source"]!!.jsonObject.string("source"))
            assertEquals(cards, client.get("/api/lessons/$id") { page() }.json().jsonObject["cards"]!!.jsonArray.map { it.jsonObject })
            // The square drawn pruned, the photo kept
            assertEquals(1, client.post("/api/lessons/$id/pictures/prune") { page() }.json().jsonObject["removed"]!!.jsonPrimitive.int)
            assertTrue(folder.root.resolve("lessons/$id/images/$own").isFile)
        }
    }

    /** A lesson whose one card is a figure, its sources answered by the relay (`sources`); the
     * requests to card-picture kept in `asked`. */
    private suspend fun io.ktor.client.HttpClient.figureLesson(asked: MutableList<JsonObject>, sources: List<String>): JsonObject {
        relayAnswers("""{"deck": {"deck": "Maths", "cards": [{"front": "Ce triangle ?", "back": "rectangle", "figure": "a right triangle",
            "figure_kind": "geometry"}]}, "turns": [], "usage": {"credits": 1, "credits_left": 99}}""")
        val lesson = submitFormWithBinaryData("/api/extract", formData { append("prompt", "p") }) { page() }.json().jsonObject
        relay.takeRequest(5, TimeUnit.SECONDS) // the extraction
        relay.dispatcher = object : mockwebserver3.Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                asked += json.parseToJsonElement(request.body!!.utf8()).jsonObject
                return cardPicture(request, sources)
            }
        }
        val id = lesson.string("id")
        post("/api/lessons/$id/pictures") { page(); contentType(ContentType.Application.Json); setBody("{}") }
        return get("/api/lessons/$id") { page() }.json().jsonObject
    }

    private fun JsonObject.sourceFiles() = this["picture_source"]!!.jsonObject["sources"]!!.jsonArray.map { it.jsonObject.string("file") }

    @Test
    fun aFigureKeepsWhatItWasDrawnFromAndIsDrawnAgainFromIt() = app { client ->
        val asked = mutableListOf<JsonObject>()
        val lesson = client.figureLesson(asked, listOf("#rect(width: 2cm)", "#circle()"))
        val id = lesson.string("id")
        val card = lesson["cards"]!!.jsonArray[0].jsonObject
        val stem = card.string("picture").removeSuffix(".svg")
        // Kept beside it, named by its card, as the computer's (core's keep_sources)
        assertEquals(listOf("$stem.typ", "$stem-2.typ"), card.sourceFiles())
        val images = folder.root.resolve("lessons/$id/images")
        assertEquals("#rect(width: 2cm)", images.resolve("$stem.typ").readText())
        assertEquals("#circle()", images.resolve("$stem-2.typ").readText())
        assertEquals("typst", card["picture_source"]!!.jsonObject.string("engine"))
        assertEquals(emptyList<String>(), asked.single()["previous"]!!.jsonArray.map { it.jsonPrimitive.content }) // a first one: anew
        // Not served to the page, nor to AnkiDroid (Pictures.file: the pictures only)
        assertEquals(HttpStatusCode.NotFound, client.get("/api/lessons/$id/pictures/$stem.typ") { page() }.status)

        // Drawn again (its check found something): from what it was drawn from, in order
        val cardId = card.string("id")
        client.post("/api/lessons/$id/cards/$cardId/picture/draw") {
            page(); contentType(ContentType.Application.Json); setBody("""{"problem": "the right angle is not marked"}""")
        }
        val again = asked.last()
        assertEquals(listOf("#rect(width: 2cm)", "#circle()"), again["previous"]!!.jsonArray.map { it.jsonPrimitive.content })
        assertEquals("geometry", again.string("previous_kind"))
        assertEquals("typst", again.string("previous_engine"))

        // One of them missing: none sent, drawn anew
        images.resolve("$stem-2.typ").delete()
        client.post("/api/lessons/$id/cards/$cardId/picture/draw") { page(); contentType(ContentType.Application.Json); setBody("{}") }
        assertEquals(0, asked.last()["previous"]!!.jsonArray.size)
        assertEquals("", asked.last().string("previous_engine")) // nothing told of it (Pictures.redrawFrom)
    }

    private fun JsonObject.previous() = this["previous"]!!.jsonArray.map { it.jsonPrimitive.content }

    @Test
    fun aFigureMadeAgainFromItsTypstWhenItsDescriptionChanged() = app { client ->
        val asked = mutableListOf<JsonObject>()
        val lesson = client.figureLesson(asked, listOf("#rect(width: 2cm)", "#circle()"))
        val id = lesson.string("id")
        val make = "/api/lessons/$id/cards/${lesson["cards"]!!.jsonArray[0].jsonObject.string("id")}/picture/make"
        // "📐 Redraw the figure", its description the same, or none: another drawing wanted, anew
        for (body in listOf("""{"subject": "a right triangle"}""", "{}")) {
            client.post(make) { page(); contentType(ContentType.Application.Json); setBody(body) }
            assertEquals(emptyList<String>(), asked.last().previous())
        }
        // Its description changed: from what it was drawn from, what is asked changed (as the computer's)
        client.post(make) { page(); contentType(ContentType.Application.Json); setBody("""{"subject": "a right triangle, in red"}""") }
        assertEquals(listOf("#rect(width: 2cm)", "#circle()"), asked.last().previous())
        assertEquals("geometry", asked.last().string("previous_kind"))
        assertEquals("typst", asked.last().string("previous_engine"))
    }

    @Test
    fun aFigureACorrectionReplacedDrawnAgainFromIt() = app { client ->
        val asked = mutableListOf<JsonObject>()
        val lesson = client.figureLesson(asked, listOf("#rect(width: 2cm)", "#circle()"))
        val id = lesson.string("id")
        val card = lesson["cards"]!!.jsonArray[0].jsonObject
        // As a correction left it: its figure changed, its picture and where it came from cleared
        val corrected = JsonObject(
            card + mapOf("figure" to JsonPrimitive("a right triangle, in red"), "picture" to JsonPrimitive(""), "picture_source" to JsonNull),
        )
        suspend fun drawn(body: String): JsonObject {
            client.put("/api/lessons/$id") { page(); contentType(ContentType.Application.Json); setBody("""{"deck": "Maths", "cards": [$corrected]}""") }
            client.post("/api/lessons/$id/pictures") { page(); contentType(ContentType.Application.Json); setBody(body) }
            return asked.last()
        }
        // The page's "previous": the figure it had (its sources, its family), drawn again from it
        val previous = """{"${card.string("id")}": {"source": ${card["picture_source"]}, "kind": "geometry"}}"""
        val again = drawn("""{"previous": $previous}""")
        assertEquals(listOf("#rect(width: 2cm)", "#circle()"), again.previous())
        assertEquals("geometry", again.string("previous_kind"))
        assertEquals("typst", again.string("previous_engine"))
        // None: drawn anew
        assertEquals(emptyList<String>(), drawn("{}").previous())
    }

    @Test
    fun aFigureACorrectionReplacedMadeAgainFromIt() = app { client ->
        val asked = mutableListOf<JsonObject>()
        val lesson = client.figureLesson(asked, listOf("#rect(width: 2cm)", "#circle()"))
        val id = lesson.string("id")
        val card = lesson["cards"]!!.jsonArray[0].jsonObject
        // As a correction left it: its figure changed, its picture and where it came from cleared
        val corrected = JsonObject(
            card + mapOf("figure" to JsonPrimitive("a right triangle, in red"), "picture" to JsonPrimitive(""), "picture_source" to JsonNull),
        )
        client.put("/api/lessons/$id") { page(); contentType(ContentType.Application.Json); setBody("""{"deck": "Maths", "cards": [$corrected]}""") }
        val make = "/api/lessons/$id/cards/${card.string("id")}/picture/make"
        suspend fun made(body: String): JsonObject {
            client.post(make) { page(); contentType(ContentType.Application.Json); setBody(body) }
            return asked.last()
        }
        // "📐 Draw the figure", its description as corrected, with the page's "previous" (the figure
        // it had: its sources, its family): drawn again from it
        val previous = """{"source": ${card["picture_source"]}, "kind": "geometry"}"""
        val again = made("""{"subject": "a right triangle, in red", "previous": $previous}""")
        assertEquals(listOf("#rect(width: 2cm)", "#circle()"), again.previous())
        assertEquals("geometry", again.string("previous_kind"))
        assertEquals("typst", again.string("previous_engine"))
        // None (a figure drawn since): anew
        assertEquals(emptyList<String>(), made("""{"subject": "a right triangle, in red"}""").previous())
    }

    @Test
    fun aGoneFiguresSourcesPrunedAUsedOnesKept() = app { client ->
        val lesson = client.extract()
        relay.takeRequest(5, TimeUnit.SECONDS)
        val id = lesson.string("id")
        val cards = lesson["cards"]!!.jsonArray.map { it.jsonObject }
        val (a, b) = cards.map { it.string("id") }
        // Its hash all digits: its sources still its own (core's SOURCE_NAME, #763)
        val used = listOf("picture-$a-12345678.svg", "picture-$b-abcdef01.svg")
        val saved = JsonArray(cards.zip(used) { c, p -> JsonObject(c + ("picture" to JsonPrimitive(p))) })
        client.put("/api/lessons/$id") { page(); contentType(ContentType.Application.Json); setBody("""{"deck": "Espagnol", "cards": $saved}""") }
        val images = folder.root.resolve("lessons/$id/images").apply { mkdirs() }
        val kept = used + listOf("picture-$a-12345678.typ", "picture-$a-12345678-2.typ", "picture-$b-abcdef01.typ", "notes.typ")
        val gone = listOf("picture-$a-87654321.svg", "picture-$a-87654321.typ", "picture-$a-87654321-2.typ", "picture-$b-00000000.typ")
        (kept + gone).forEach { images.resolve(it).writeText("x") }
        assertEquals(1, client.post("/api/lessons/$id/pictures/prune") { page() }.json().jsonObject["removed"]!!.jsonPrimitive.int)
        assertEquals(kept.sorted(), images.list()!!.sorted())
    }

    @Test
    fun aFiguresSourcesFollowItInACopyAndATransfer() = app { client ->
        client.put("/api/children") {
            page(); contentType(ContentType.Application.Json); setBody("""[{"id": "mathilde", "name": "Mathilde", "grade": "3e", "decks": "Mathilde::3e"}]""")
        }
        val lesson = client.figureLesson(mutableListOf(), listOf("#rect()", "#circle()"))
        val id = lesson.string("id")
        val copy = client.post("/api/lessons/$id/copy") {
            page(); contentType(ContentType.Application.Json); setBody("""{"child": "mathilde"}""")
        }.json().jsonObject
        val card = copy["cards"]!!.jsonArray[0].jsonObject
        val stem = card.string("picture").removeSuffix(".svg")
        assertTrue(stem.startsWith("picture-${card.string("id")}-"))
        // Named after its picture, as its picture is (core's lessons.copy): none under the old name
        assertEquals(listOf("$stem.typ", "$stem-2.typ"), card.sourceFiles())
        val images = folder.root.resolve("lessons/${copy.string("id")}/images")
        assertEquals(listOf("#rect()", "#circle()"), card.sourceFiles().map { images.resolve(it).readText() })
        assertEquals(listOf("$stem-2.typ", "$stem.svg", "$stem.typ"), images.list()!!.sorted())

        // Exported then taken in again (to the computer, another phone): with them
        val sources = lesson["cards"]!!.jsonArray[0].jsonObject.sourceFiles()
        client.post("/api/admin/transfer/export") { page() }
        val zip = document!!.toByteArray()
        assertTrue(sources.all { "lessons/$id/images/$it" in entries(zip) })
        local.lessons.delete(id)
        client.importFile(zip)
        assertEquals(listOf("#rect()", "#circle()"), sources.map { folder.root.resolve("lessons/$id/images/$it").readText() })
    }

    @Test
    fun aFigureTurnedIntoAPictureStaysTheFigureUntilAPictureIsChosen() = app { client ->
        val asked = mutableListOf<Pair<String, JsonObject>>()
        val lesson = client.figureLesson(mutableListOf(), emptyList())
        val id = lesson.string("id")
        val figure = lesson["cards"]!!.jsonArray[0].jsonObject
        val cardId = figure.string("id")
        assertTrue(figure.string("picture").endsWith(".svg"))
        relay.dispatcher = object : mockwebserver3.Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                asked += request.url.encodedPath to json.parseToJsonElement(request.body!!.utf8()).jsonObject
                return when (request.url.encodedPath) {
                    // The relay's AI decides a picture, nothing written: no free one asked, 409
                    "/v1/card-picture" -> cardPicture(request) { sent ->
                        if (sent.string("asked").isEmpty() && sent["card"]!!.jsonObject.string("figure").isNotEmpty()) {
                            mapOf("figure" to "", "figure_kind" to "", "picture_prompt" to "a photo of a set square", "picture_search" to "set square")
                        } else emptyMap()
                    }
                    else -> MockResponse.Builder().code(404).build()
                }
            }
        }
        suspend fun saved() = client.get("/api/lessons/$id") { page() }.json().jsonObject["cards"]!!.jsonArray[0].jsonObject
        val made = client.post("/api/lessons/$id/cards/$cardId/picture/make") {
            page(); contentType(ContentType.Application.Json); setBody("""{"subject": ""}""")
        }.json().jsonObject
        assertEquals("set square", made.string("search"))
        val decided = made["decided"]!!.jsonObject
        assertEquals("a photo of a set square" to "set square", decided.string("picture_prompt") to decided.string("picture_search"))
        // The search given up: still the figure, its drawing and its description (never one without the other)
        for (card in listOf(made["card"]!!.jsonObject, saved())) {
            assertEquals("a right triangle" to figure.string("picture"), card.string("figure") to card.string("picture"))
            assertEquals("geometry" to "", card.string("figure_kind") to card.string("picture_prompt"))
        }

        // The user said yes: drawn by the image model as the picture decided, the figure replaced
        val drawn = client.post("/api/lessons/$id/cards/$cardId/picture/draw") {
            page(); contentType(ContentType.Application.Json); setBody("""{"decided": $decided}""")
        }.json().jsonObject["card"]!!.jsonObject
        val sent = asked.last().second["card"]!!.jsonObject
        assertEquals("" to "a photo of a set square", sent.string("figure") to sent.string("picture_prompt"))
        assertEquals("true", asked.last().second["draw"]!!.jsonPrimitive.content)
        for (card in listOf(drawn, saved())) {
            assertEquals("" to "", card.string("figure") to card.string("figure_kind"))
            assertEquals("a photo of a set square" to "set square", card.string("picture_prompt") to card.string("picture_search"))
            assertTrue(card.string("picture").endsWith(".jpg"))
        }
    }

    @Test
    fun aFigureTurnedIntoAPictureReplacedByTheUsersPhoto() = app { client ->
        val lesson = client.figureLesson(mutableListOf(), emptyList())
        val id = lesson.string("id")
        val cardId = lesson["cards"]!!.jsonArray[0].jsonObject.string("id")
        val decided = """{"picture_prompt": "a photo of a set square", "picture_search": "set square", "picture_on_back": false}"""
        val photo = client.submitFormWithBinaryData("/api/lessons/$id/cards/$cardId/picture", formData {
            append("decided", decided)
            append("photo", jpeg("a set square"), Headers.build {
                append(HttpHeaders.ContentType, "image/jpeg")
                append(HttpHeaders.ContentDisposition, "filename=\"photo.jpg\"")
            })
        }) { page() }.json().jsonObject["card"]!!.jsonObject
        assertEquals("" to "a photo of a set square", photo.string("figure") to photo.string("picture_prompt"))
        assertTrue(photo.string("picture").endsWith(".jpg"))
        assertEquals("photo", photo["picture_source"]!!.jsonObject.string("source"))
        // Not a decision: refused, the card as it was
        val refused = client.submitFormWithBinaryData("/api/lessons/$id/cards/$cardId/picture", formData {
            append("decided", "nope")
            append("photo", jpeg("x"), Headers.build {
                append(HttpHeaders.ContentType, "image/jpeg")
                append(HttpHeaders.ContentDisposition, "filename=\"photo.jpg\"")
            })
        }) { page() }
        assertEquals(HttpStatusCode.BadRequest, refused.status)
    }

    @Test
    fun anSvgWithoutItsFigureCheckedAsAFigure() = app { client ->
        // A figure an older version turned into a picture without replacing its drawing: still
        // checked (/v1/check-figure), against what the card's picture should show, else the card
        val lesson = client.figureLesson(mutableListOf(), emptyList())
        val id = lesson.string("id")
        val card = lesson["cards"]!!.jsonArray[0].jsonObject
        val asked = mutableListOf<Pair<String, JsonObject>>()
        relay.dispatcher = object : mockwebserver3.Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                asked += request.url.encodedPath to json.parseToJsonElement(request.body!!.utf8()).jsonObject
                return MockResponse.Builder().addHeader("Content-Type", "application/json")
                    .body("""{"ok": false, "problem": "A triangle, not a set square.", "usage": {"credits": 1, "credits_left": 90}}""").build()
            }
        }
        for ((prompt, meant) in listOf("a photo of a set square" to "a photo of a set square", "" to "Ce triangle ? → rectangle")) {
            val legacy = JsonObject(card + mapOf("figure" to JsonPrimitive(""), "figure_kind" to JsonPrimitive(""), "picture_prompt" to JsonPrimitive(prompt)))
            client.put("/api/lessons/$id") { page(); contentType(ContentType.Application.Json); setBody("""{"deck": "Maths", "cards": [$legacy]}""") }
            val checked = client.post("/api/lessons/$id/cards/${card.string("id")}/picture/check") { page() }
            assertEquals(HttpStatusCode.OK, checked.status)
            assertEquals("A triangle, not a set square.", checked.json().jsonObject.string("problem"))
            val (path, sent) = asked.last()
            assertEquals("/v1/check-figure" to meant, path to sent.string("description"))
            assertEquals("<svg/>", sent.string("svg"))
        }
    }

    @Test
    fun aLongCardsPictureCheckedCutToWhatTheRelayTakes() = app { client ->
        // A card has no length limit, the relay's check one (MAX_CARD): cut to it, not refused
        relayAnswers("""{"deck": {"deck": "D", "cards": [{"front": "q", "back": "${"b".repeat(5000)}"},
            {"front": "q", "back": "${"b".repeat(1500)}"}]}, "turns": [], "usage": {"credits": 1, "credits_left": 99}}""")
        val lesson = client.submitFormWithBinaryData("/api/extract", formData { append("prompt", "p") }) { page() }.json().jsonObject
        relay.takeRequest(5, TimeUnit.SECONDS) // the extraction
        val id = lesson.string("id")
        val asked = mutableListOf<JsonObject>()
        relay.dispatcher = object : mockwebserver3.Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                asked += json.parseToJsonElement(request.body!!.utf8()).jsonObject
                return MockResponse.Builder().addHeader("Content-Type", "application/json")
                    .body("""{"ok": true, "problem": "", "usage": {"credits": 1, "credits_left": 90}}""").build()
            }
        }
        for (card in lesson["cards"]!!.jsonArray.map { it.jsonObject }) {
            client.submitFormWithBinaryData("/api/lessons/$id/cards/${card.string("id")}/picture", formData {
                append("photo", jpeg("a photo"), Headers.build {
                    append(HttpHeaders.ContentType, "image/jpeg")
                    append(HttpHeaders.ContentDisposition, "filename=\"photo.jpg\"")
                })
            }) { page() }
            assertEquals(HttpStatusCode.OK, client.post("/api/lessons/$id/cards/${card.string("id")}/picture/check") { page() }.status)
        }
        val (long, short) = asked.map { it.string("card") }
        assertEquals(Pictures.MAX_CARD, long.length)
        assertEquals("q → " + "b".repeat(Pictures.MAX_CARD - 5) + "…", long)
        assertEquals("q → " + "b".repeat(1500), short) // under the limit: sent whole
    }

    @Test
    fun aCutTextNeverEndsInHalfACharacter() {
        assertEquals("abc", Pictures.cut("abc", 3))
        assertEquals("ab…", Pictures.cut("abcd", 3))
        assertEquals("a…", Pictures.cut("a\uD83D\uDE00b", 3)) // the emoji not split: dropped whole
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
