package app.notosaurus

import android.content.Context
import io.ktor.http.ContentType
import io.ktor.http.HttpHeaders
import io.ktor.http.HttpStatusCode
import io.ktor.http.content.PartData
import io.ktor.http.content.forEachPart
import io.ktor.http.defaultForFilePath
import io.ktor.server.application.Application
import io.ktor.server.cio.CIO
import io.ktor.server.engine.EmbeddedServer
import io.ktor.server.engine.embeddedServer
import io.ktor.server.request.receiveMultipart
import io.ktor.server.request.receiveText
import io.ktor.server.response.respondBytes
import io.ktor.server.response.respondText
import io.ktor.server.response.respondTextWriter
import io.ktor.server.routing.Route
import io.ktor.server.routing.RoutingContext
import io.ktor.server.routing.delete
import io.ktor.server.routing.get
import io.ktor.server.routing.post
import io.ktor.server.routing.put
import io.ktor.server.routing.routing
import io.ktor.utils.io.toByteArray
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put
import java.io.File
import java.net.URI
import java.util.UUID

/**
 * The computer's server, as the page sees it: the same /api routes (app/main.py),
 * answered on the phone. The page itself (assets/web/, the repository's
 * static/) is served from here too, so it runs unchanged.
 *
 * The routes only; the work in: Generation (a lesson made by the relay), Pictures,
 * Speech (the voices), Prompts, Computer ("With my computer"), Lessons (on the phone),
 * Anki (AnkiDroid), PageTexts (the page's languages).
 *
 * Listens on 127.0.0.1 only, and answers /api only with the cookie the app's WebView
 * has: another app on the phone can't use it.
 */
class LocalServer(
    dataDir: File,
    private val web: (String) -> ByteArray?, // a file of the page, by its path ("index.html", "i18n/fr.json")
    private val languages: () -> List<String>, // the page's languages ("en", "fr"…)
    private val anki: AnkiTarget,
    private val prefs: Preferences,
    private val version: String = "",
    private val requestAnkiPermission: suspend () -> Boolean = { false }, // AnkiDroid's permission dialog: granted?
    private val installAnki: () -> Unit = {}, // AnkiDroid's Play Store page
    private val scan: suspend () -> String? = { null }, // a QR code read by the camera (null: cancelled)
    private val modeChanged: () -> Unit = {}, // the app's shortcuts follow
    private val turnPhoto: (ByteArray, Int) -> ByteArray = { data, _ -> data }, // a JPEG turned clockwise (Photos.turn)
    val token: String = UUID.randomUUID().toString(),
) {
    private val lessons = Lessons(File(dataDir, "lessons").apply { mkdirs() })
    private val texts = PageTexts(web, languages)
    private val prompts = Prompts(File(dataDir, "prompts.json"), texts)
    private val speech = Speech(File(dataDir, "audio").apply { mkdirs() }, prefs, ::relay) // the backs read aloud, kept
    private val pictures = Pictures(lessons, ::relay)
    private val generation = Generation(lessons, prefs, ::relay, speech, turnPhoto)
    private val computer = Computer(prefs, modeChanged)
    private lateinit var server: EmbeddedServer<*, *>

    /** Starts it; returns its port. */
    fun start(): Int {
        server = embeddedServer(CIO, port = 0, host = "127.0.0.1") { module() }
        server.start(wait = false)
        return runBlocking { server.engine.resolvedConnectors().first().port }
    }

    /** The relay, with the licence key of the settings. */
    private fun relay() = Relay(prefs[RELAY] ?: DEFAULT_RELAY, prefs[KEY].orEmpty())

    /** A text of the page's languages (the app's shortcuts), English when missing. */
    fun text(lang: String, vararg keys: String): String? = texts.get(lang, *keys) ?: texts.get("en", *keys)

    fun Application.module() = routing {
        api("GET", "/api/config") {
            buildJsonObject {
                put("version", version)
                put("diagram_warning", false)
                put("max_photos", 10)
                put("profiles", false) // AnkiDroid doesn't say its profile: no Anki profile badge
                put("card_helps", prefs[CARD_HELPS] == "true")
                put("configured", true)
                put("donations", false) // paid for by the subscription: no "Support Notosaurus" (Ko-fi)
                put("apkg", false) // the cards go to AnkiDroid: no .apkg to download
                put("review_in_anki", true) // a lesson sent: reviewed in AnkiDroid from here
            }
        }

        // --- The settings (assets/page/admin.html)
        api("GET", "/api/admin") { buildJsonObject { put("allowed", true) } }
        api("GET", "/api/admin/settings") { settings() }
        api("PUT", "/api/admin/settings") {
            val changes = body()
            changes.string(RELAY).trim().takeIf { it.isNotEmpty() }?.let { prefs[RELAY] = it.trimEnd('/') }
            (changes[KEY] as? JsonPrimitive)?.let { prefs[KEY] = it.content.trim() }
            (changes[INSTRUCTIONS] as? JsonPrimitive)?.let { prefs[INSTRUCTIONS] = it.content.take(4000) }
            (changes[CARD_HELPS] as? JsonPrimitive)?.let { prefs[CARD_HELPS] = it.content }
            (changes[TTS_RATE] as? JsonPrimitive)?.content?.takeIf { it in Speech.RATES }?.let { prefs[TTS_RATE] = it }
            settings()
        }
        api("GET", "/api/admin/account") { json.encodeToJsonElement(Account.serializer(), relay().account()) }
        api("GET", "/api/admin/anki") {
            buildJsonObject {
                put("installed", anki.installed())
                put("permitted", anki.installed() && anki.permitted())
            }
        }
        api("POST", "/api/admin/anki/permission") { buildJsonObject { put("permitted", requestAnkiPermission()) } }
        api("GET", "/api/admin/data") {
            buildJsonObject {
                put("lessons", lessons.list().size)
                put("bytes", lessons.bytes() + speech.bytes()) // with their sound
            }
        }
        api("DELETE", "/api/admin/lessons") {
            speech.deleteAll() // their sound too (AnkiDroid keeps its own copy)
            buildJsonObject { put("deleted", lessons.deleteAll()) }
        }

        // --- With my computer (the Anki add-on's Notosaurus)
        api("POST", "/api/admin/computer/scan") {
            val read = try {
                scan()
            } catch (e: Exception) {
                throw BadRequest("computer.scan_unavailable")
            } ?: return@api buildJsonObject { put("cancelled", true) }
            computer.connect(read)
        }
        api("PUT", "/api/admin/computer") { computer.connect(body().string("address")) }
        api("POST", "/api/admin/mode") {
            val mode = body().string("mode")
            if (mode == COMPUTER_MODE && prefs[COMPUTER].isNullOrEmpty()) throw BadRequest("computer.not_found")
            prefs[MODE] = if (mode == COMPUTER_MODE) COMPUTER_MODE else PHONE_MODE
            modeChanged()
            buildJsonObject { put("url", if (mode == COMPUTER_MODE) prefs[COMPUTER]!! else "/") }
        }
        api("GET", "/api/lang") {
            val codes = texts.codes()
            buildJsonObject {
                put("lang", JsonNull) // the page uses the phone's language
                put("available", JsonArray(codes.map(::JsonPrimitive)))
                put("names", JsonObject(codes.associateWith { JsonPrimitive(texts.get(it, "meta", "name") ?: it) }))
            }
        }
        api("GET", "/api/voices") {
            try {
                speech.voices()
            } catch (e: RelayException) {
                throw BadRequest("tts.voices_unavailable", buildJsonObject { put("detail", e.code) })
            }
        }
        // Listen to a text (🔊), read by the relay's voice
        get("/api/tts") {
            if (!allowed()) return@get
            val text = call.request.queryParameters["text"].orEmpty()
            val voice = call.request.queryParameters["voice"].orEmpty()
            val mp3 = runCatching { speech.read(text, voice) }.getOrNull()
            if (mp3 == null) call.respondText("", status = HttpStatusCode.BadGateway)
            else call.respondBytes(mp3.readBytes(), ContentType.Audio.MPEG)
        }

        // --- Prompts: Notosaurus's (from the page's languages), then the user's
        api("GET", "/api/prompts") { JsonArray(prompts.all(lang())) }
        api("POST", "/api/prompts") { prompts.save(null, body()) }
        api("PUT", "/api/prompts/{id}") { prompts.save(param("id").toInt(), body()) }
        api("DELETE", "/api/prompts/{id}") {
            prompts.delete(param("id"))
            JsonNull
        }
        api("POST", "/api/prompts/{id}/duplicate") { prompts.duplicate(lang(), param("id")) }

        // --- Lessons
        api("GET", "/api/lessons") { JsonArray(lessons.list().map(lessons::summary)) }
        api("GET", "/api/lessons/{id}") { lesson() }
        api("PUT", "/api/lessons/{id}") { lessons.update(param("id"), body()) ?: notFound() }
        // Deleting a lesson: its notes in AnkiDroid counted first; deleted too when asked (?anki=true)
        api("GET", "/api/lessons/{id}/anki-notes") {
            val found = withContext(Dispatchers.IO) { runCatching { anki.lessonNotes(lesson().string("id")) }.getOrNull() }
            buildJsonObject {
                put("available", found != null)
                put("count", found?.size ?: 0)
            }
        }
        api("DELETE", "/api/lessons/{id}") {
            val id = lesson().string("id")
            var inAnki = 0
            if (call.request.queryParameters["anki"] == "true") {
                inAnki = withContext(Dispatchers.IO) {
                    val notes = runCatching { anki.lessonNotes(id) }.getOrNull() ?: throw BadRequest("anki.android_failed")
                    anki.delete(notes)
                }
            }
            lessons.delete(id)
            buildJsonObject {
                put("deleted", true)
                put("anki_deleted", inAnki)
                put("synced", false)
            }
        }
        // A photo turned a quarter turn clockwise (it came out sideways), its masks and frame with it
        api("POST", "/api/lessons/{id}/photos/{n}/rotate") {
            val lesson = lesson()
            val id = lesson.string("id")
            val n = param("n").toIntOrNull() ?: notFound()
            val photo = lessons.photo(id, n) ?: notFound()
            photo.writeBytes(turnPhoto(photo.readBytes(), 90))
            val cards = lesson.cards().map { Diagrams.turnedMask(it, n, 90) }
            val frames = (lesson["frames"] as? JsonArray)?.map { Diagrams.turnedFrame(it.jsonObject, n, 90) }.orEmpty()
            lessons.update(id, buildJsonObject { put("cards", JsonArray(cards)); put("frames", JsonArray(frames)) }) ?: notFound()
        }
        get("/api/lessons/{id}/photos/{n}") {
            if (!allowed()) return@get
            val photo = lessons.photo(param("id"), param("n").toInt())
            if (photo == null) call.respondText("", status = HttpStatusCode.NotFound)
            else call.respondBytes(photo.readBytes(), ContentType.Image.JPEG)
        }
        api("GET", "/api/decks") {
            val known = (lessons.list().map { it.string("deck") } + anki.deckNames()).filter { it.isNotBlank() }
            JsonArray(known.distinct().sorted().map(::JsonPrimitive))
        }

        // --- The AI, through the relay
        making("/api/extract") { form, onCard ->
            val made = generation.make(form, onCard)
            lessons.create(made.content, made.photos)
        }
        // "Cancel" while waiting: the relay call stops, no lesson is saved
        api("POST", "/api/generations/{job}/cancel") {
            buildJsonObject { put("cancelled", generation.cancel(param("job"))) }
        }
        // Generated again in its place (another prompt, photos, or carefully this time)
        making("/api/lessons/{id}/regenerate") { form, onCard ->
            val old = lesson()
            val made = generation.make(form, onCard)
            lessons.regenerated(old.string("id"), made.content, made.photos) ?: notFound()
        }
        api("POST", "/api/lessons/{id}/revise") {
            val lesson = lesson()
            val req = body()
            val request = buildJsonObject {
                put("prompt", lesson.string("prompt"))
                put("deck", buildJsonObject { put("deck", req["deck"]!!); put("cards", req["cards"]!!) })
                put("instruction", req["instruction"]!!)
                put("language", languageName())
                put("instructions", generation.instructions())
            }
            val revised = relay().withPhotos("revise", request, lessons.photos(lesson.string("id")))
            val changes = JsonObject(req + mapOf("deck" to revised["deck"]!!, "cards" to revised["cards"]!!))
            buildJsonObject {
                put("lesson", lessons.update(lesson.string("id"), changes)!!)
                put("summary", revised["summary"]!!)
            }
        }
        api("POST", "/api/lessons/{id}/explain") {
            val lesson = lesson()
            val req = body()
            val request = buildJsonObject {
                put("card", req["card"]!!)
                put("kind", req["kind"] ?: JsonPrimitive("explain"))
                put("prompt", lesson.string("prompt"))
                put("deck", lesson.string("deck"))
                put("language", languageName())
                put("page_texts", lesson["page_texts"] ?: JsonArray(emptyList()))
                put("instructions", generation.instructions())
            }
            JsonObject(relay().post("explain", request) - "usage")
        }
        // --- Pictures, through the relay (as app/main.py): drawn, the user's own, none
        api("POST", "/api/lessons/{id}/pictures") { pictures.drawMissing(lesson()) }
        // A card's picture drawn again: its subject (or figure), or the one the user wrote
        api("POST", "/api/lessons/{id}/cards/{card}/picture/draw") {
            val lesson = lesson()
            val subject = body()["subject"]?.takeIf { it !is JsonNull }?.jsonPrimitive?.content
            pictures.redraw(lesson, cardIndex(lesson), subject)
        }
        // The user's own photo as the card's picture (the page made it card size)
        post("/api/lessons/{id}/cards/{card}/picture") {
            if (!allowed()) return@post
            val (status, answer) = try {
                val lesson = lesson()
                val i = cardIndex(lesson)
                var photo: ByteArray? = null
                call.receiveMultipart(formFieldLimit = 20L * 1024 * 1024).forEachPart { part ->
                    if (part is PartData.FileItem && part.name == "photo") photo = part.provider().toByteArray()
                    part.dispose()
                }
                HttpStatusCode.Created to pictures.own(lesson, i, photo ?: throw BadRequest("extract.no_input"))
            } catch (e: Exception) {
                failure(e) ?: throw e
            }
            call.respondText(answer.toString(), ContentType.Application.Json, status)
        }
        // No picture on the card any more: a text card
        api("DELETE", "/api/lessons/{id}/cards/{card}/picture") {
            val lesson = lesson()
            pictures.remove(lesson, cardIndex(lesson))
        }
        get("/api/lessons/{id}/pictures/{name}") {
            if (!allowed()) return@get
            val name = param("name")
            val file = pictures.file(param("id"), name)
            when {
                file == null -> call.respondText("", status = HttpStatusCode.NotFound)
                name.endsWith(".svg") -> {
                    // Cleaned by the relay; and even opened on its own, nothing in it may run or load
                    call.response.headers.append("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'")
                    call.response.headers.append("X-Content-Type-Options", "nosniff")
                    call.respondBytes(file.readBytes(), ContentType.Image.SVG)
                }
                else -> call.respondBytes(file.readBytes(), ContentType.Image.JPEG)
            }
        }

        // --- AnkiDroid
        api("GET", "/api/anki/status") {
            buildJsonObject {
                // Always: "Add to Anki" asks for AnkiDroid (installed, allowed) when it's used
                put("available", true)
                put("version", 6)
                put("profile", JsonNull)
                put("sync", JsonNull)
            }
        }
        api("POST", "/api/anki/send") {
            val req = body()
            req.string("lesson_id").takeIf { it.isNotEmpty() }?.let { lessons.update(it, req, exported = true) }
            val deck = json.decodeFromJsonElement(Deck.serializer(), buildJsonObject {
                put("deck", req["deck"]!!)
                put("cards", req["cards"]!!)
            })
            readyAnki()
            val (sounds, failures) = speech.sounds(deck, req.string("voice"))
            val lessonId = req.string("lesson_id")
            val folder = lessons.images(lessonId)
            val pictures = deck.cards.mapNotNull { c -> folder?.resolve(c.picture)?.takeIf { c.picture.isNotEmpty() && it.isFile }?.let { c.picture to it } }.toMap()
            // The diagrams: the photos their labels are on
            val photos = deck.cards.mapNotNull { it.mask?.page }.distinct().mapNotNull { n -> lessons.photo(lessonId, n)?.let { n to it } }.toMap()
            // The diagram frames as the page has them (the user may have moved one), else the lesson's
            val frames = (req["frames"]?.takeIf { it is JsonArray } ?: lessons.get(lessonId)?.get("frames"))
                ?.jsonArray?.associate { it.jsonObject["page"]!!.jsonPrimitive.content.toInt() to it.jsonObject["box"]!!.jsonArray.map { v -> v.jsonPrimitive.content.toDouble() } }
                .orEmpty()
            val media = Media(sounds, pictures, photos, lessonId, frames)
            fun on(option: String) = req[option]?.jsonPrimitive?.content == "true"
            val options = Options(reverse = on("reverse"), typing = on("typing"), dictation = on("dictation"))
            val sent = try {
                withContext(Dispatchers.IO) { anki.send(deck, media, options) }
            } catch (e: Exception) { // e.g. AnkiDroid never opened: no collection yet
                throw BadRequest("anki.android_failed", buildJsonObject { put("detail", e.message ?: e.javaClass.simpleName) })
            }
            buildJsonObject {
                put("added", sent.added)
                put("updated", sent.updated) // the lesson's notes sent before, changed since
                put("synced", false)
                if (failures > 0) put("audio_failures", failures) // the page says some have no sound
            }
        }

        // AnkiDroid's Google Play page, asked from the message saying it's missing
        api("POST", "/api/anki/install") {
            installAnki()
            buildJsonObject { put("opened", true) }
        }
        // A lesson's deck reviewed in AnkiDroid ("Review" after sending it)
        api("POST", "/api/anki/review") {
            val deck = body().string("deck")
            val opened = withContext(Dispatchers.IO) { runCatching { anki.review(deck) }.getOrDefault(false) }
            if (!opened) throw BadRequest("anki.android_no_deck", buildJsonObject { put("deck", deck) })
            buildJsonObject { put("opened", true) }
        }

        // --- The page
        get("/{path...}") {
            val path = call.parameters.getAll("path").orEmpty().joinToString("/").ifEmpty { "index.html" }
            val bytes = path.takeUnless { ".." in it }?.let(web)
            if (bytes == null) call.respondText("", status = HttpStatusCode.NotFound)
            else call.respondBytes(bytes, ContentType.defaultForFilePath(path))
        }
    }

    // --- Routes: the token checked, errors as the page expects them (Errors.kt)

    /** AnkiDroid installed and allowed, asked for when the cards are first added: its Play
     * Store page when it's missing, its permission dialog when it isn't allowed yet. */
    private suspend fun readyAnki() {
        // Not installed: said, with a button to install it (Google Play doesn't open by surprise)
        if (!anki.installed()) throw BadRequest("anki.android_missing")
        if (!anki.permitted() && !requestAnkiPermission()) throw BadRequest("anki.android_refused")
    }

    private fun Route.api(method: String, path: String, handler: suspend RoutingContext.() -> JsonElement) {
        val body: suspend RoutingContext.() -> Unit = {
            if (allowed()) {
                val (status, answer) = try {
                    HttpStatusCode.OK to handler()
                } catch (e: Exception) {
                    failure(e) ?: throw e
                }
                call.respondText(answer.toString(), ContentType.Application.Json, status)
            }
        }
        when (method) {
            "GET" -> get(path, body)
            "POST" -> post(path, body)
            "PUT" -> put(path, body)
            "DELETE" -> delete(path, body)
        }
    }

    private suspend fun RoutingContext.allowed(): Boolean {
        if (call.request.cookies[COOKIE] == token) return true
        call.respondText(error("device.not_paired", JsonObject(emptyMap())).toString(), ContentType.Application.Json, HttpStatusCode.Unauthorized)
        return false
    }

    private fun settings() = buildJsonObject {
        put(RELAY, prefs[RELAY] ?: DEFAULT_RELAY)
        put(KEY, masked(prefs[KEY].orEmpty())) // shown, not given back whole
        put("has_key", prefs[KEY].orEmpty().isNotEmpty())
        put(INSTRUCTIONS, prefs[INSTRUCTIONS].orEmpty())
        put(CARD_HELPS, prefs[CARD_HELPS] == "true")
        put(TTS_RATE, prefs[TTS_RATE] ?: "-10%")
        put("version", version)
        put(MODE, prefs[MODE] ?: PHONE_MODE)
        prefs[COMPUTER]?.let {
            put(COMPUTER, it)
            put("computer_address", Computer.origin(URI(it))) // without its token
            put("computer_name", prefs[COMPUTER_NAME].orEmpty())
        }
    }

    private fun masked(key: String) = if (key.length <= 8) "•".repeat(key.length) else "${key.take(4)}…${key.takeLast(4)}"

    /**
     * A lesson made (a new one, or again in its place): as JSON, or as the AI writes
     * it when the page asks Relay.STREAM_TYPE, as the computer answers (app/main.py,
     * _streamed): {"card"} (or {"restart"}) lines, then {"lesson"}, {"error"} or
     * {"cancelled"}. The form is read first: the answer then outlives the request.
     */
    private fun Route.making(path: String, make: suspend RoutingContext.(GenerationForm, OnCard) -> JsonObject) {
        post(path) {
            if (!allowed()) return@post
            val form = form()
            if (call.request.headers[HttpHeaders.Accept]?.contains(Relay.STREAM_TYPE) != true) {
                val (status, answer) = try {
                    HttpStatusCode.OK to make(form) {}
                } catch (e: Exception) {
                    failure(e) ?: throw e
                }
                call.respondText(answer.toString(), ContentType.Application.Json, status)
                return@post
            }
            val routing = this
            call.respondTextWriter(ContentType.parse(Relay.STREAM_TYPE)) {
                val writer = this
                suspend fun line(item: JsonObject) = withContext(Dispatchers.IO) {
                    writer.write("$item\n")
                    writer.flush()
                }
                val last = try {
                    val lesson = routing.make(form) { card ->
                        line(if (card != null) buildJsonObject { put("card", card) } else buildJsonObject { put("restart", true) })
                    }
                    buildJsonObject { put("lesson", lesson) }
                } catch (e: Cancelled) {
                    buildJsonObject { put("cancelled", true) }
                } catch (e: Exception) {
                    val (_, answer) = failure(e) ?: throw e
                    buildJsonObject { put("error", answer["detail"]!!) }
                }
                line(last)
            }
        }
    }

    private fun RoutingContext.param(name: String) = call.parameters[name]!!
    private suspend fun RoutingContext.body() = json.parseToJsonElement(call.receiveText()).jsonObject
    private fun RoutingContext.lesson() = lessons.get(param("id")) ?: notFound()
    private fun RoutingContext.lang() = call.request.headers["X-Notosaurus-Lang"]?.lowercase() ?: "en"
    private fun RoutingContext.languageName() = texts.get(lang(), "meta", "englishName") ?: "English"

    private fun RoutingContext.cardIndex(lesson: JsonObject): Int =
        lesson.cards().indexOfFirst { it.string("id") == param("card") }.takeIf { it >= 0 } ?: throw BadRequest("card.not_found")

    /** The page's form for making a lesson, read whole first (the answer may outlive the request). */
    private suspend fun RoutingContext.form(): GenerationForm {
        val fields = mutableMapOf<String, String>()
        val images = mutableListOf<ByteArray>()
        call.receiveMultipart(formFieldLimit = 20L * 1024 * 1024).forEachPart { part ->
            when (part) {
                is PartData.FormItem -> fields[part.name!!] = part.value
                is PartData.FileItem -> images += part.provider().toByteArray()
                else -> {}
            }
            part.dispose()
        }
        return GenerationForm(fields, images, lang())
    }

    companion object {
        const val COOKIE = "notosaurus_app"

        // The settings
        const val RELAY = "relay"
        const val KEY = "key"
        const val INSTRUCTIONS = "instructions"
        const val CARD_HELPS = "card_helps"

        const val TTS_RATE = Speech.TTS_RATE

        // The relay of a fresh install, by the build (app/build.gradle.kts): the test instance
        // while developing, the real one in a release (changed in the settings, "Advanced")
        val DEFAULT_RELAY: String = BuildConfig.DEFAULT_RELAY

        // Which Notosaurus the app shows: its own (phone) or the computer's (the add-on's)
        const val MODE = "mode"
        const val PHONE_MODE = "phone"
        const val COMPUTER_MODE = "computer"
        const val COMPUTER = "computer" // the computer's address, as its QR code gives it (with its token)
        const val COMPUTER_NAME = "computer_name" // its name, shown in the settings ("" when it didn't say)

        /** The computer's Notosaurus address, from its QR code or as typed (Computer.url). */
        fun computerUrl(raw: String): URI? = Computer.url(raw)

        fun origin(url: URI) = Computer.origin(url)

        /** The app's: the page from its assets (its own files in page/ first, then the
         * repository's static/, in web/), data in its own files, AnkiDroid. */
        fun forApp(
            context: Context,
            version: String,
            requestAnkiPermission: suspend () -> Boolean,
            installAnki: () -> Unit,
            scan: suspend () -> String?,
            modeChanged: () -> Unit,
        ) = LocalServer(
            dataDir = context.filesDir,
            web = { path -> asset(context, "page/$path") ?: asset(context, "web/$path") },
            languages = {
                context.assets.list("web/i18n").orEmpty().filter { it.endsWith(".json") }.map { it.removeSuffix(".json") }
            },
            anki = Anki(context),
            prefs = SharedPreferencesStore(context),
            version = version,
            requestAnkiPermission = requestAnkiPermission,
            installAnki = installAnki,
            scan = scan,
            modeChanged = modeChanged,
            turnPhoto = Photos::turn,
        )

        private fun asset(context: Context, path: String) =
            runCatching { context.assets.open(path).use { it.readBytes() } }.getOrNull()
    }
}
