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
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.sync.Semaphore
import kotlinx.coroutines.sync.withPermit
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.isActive
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
import java.security.MessageDigest
import java.util.UUID
import java.util.concurrent.ConcurrentHashMap

/**
 * The computer's server, as the page sees it: the same /api routes (app/main.py),
 * answered on the phone. The page itself (assets/web/, the repository's
 * static/) is served from here too, so it runs unchanged.
 *
 * - The AI: the relay (`relay()`, with the licence).
 * - The lessons: on the phone (Lessons).
 * - Anki: AnkiDroid (Anki).
 * - The settings: the app's own page (assets/page/admin.html, at the address of the
 *   computer's), its /api/admin/… here.
 * - "With my computer": the app shows the add-on's page instead (MainActivity); here,
 *   connecting to it (its QR code, its address) and switching between the two.
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
    val token: String = UUID.randomUUID().toString(),
) {
    private val lessons = Lessons(File(dataDir, "lessons").apply { mkdirs() })
    private val audio = File(dataDir, "audio").apply { mkdirs() } // the backs read aloud, kept
    private val prompts = File(dataDir, "prompts.json")
    private lateinit var server: EmbeddedServer<*, *>

    /** Starts it; returns its port. */
    fun start(): Int {
        server = embeddedServer(CIO, port = 0, host = "127.0.0.1") { module() }
        server.start(wait = false)
        return runBlocking { server.engine.resolvedConnectors().first().port }
    }

    /** The relay, with the licence key of the settings. */
    private fun relay() = Relay(prefs[RELAY] ?: DEFAULT_RELAY, prefs[KEY].orEmpty())

    /** The settings' standing instructions, put before every request to the AI
     * (app/settings.py, standing_instructions). */
    /** The lessons being made, by the page's id for each: what "Cancel" stops. */
    private val generating = ConcurrentHashMap<String, Job>()

    /** `work`, stopped by "Cancel" (`job`: the page's id for it): Cancelled then. */
    private suspend fun <T> cancellable(job: String?, work: suspend () -> T): T = coroutineScope {
        val running = async { work() }
        if (!job.isNullOrBlank()) generating[job] = running
        try {
            running.await()
        } catch (e: CancellationException) {
            if (running.isCancelled && isActive) throw Cancelled() else throw e
        } finally {
            if (!job.isNullOrBlank()) generating.remove(job, running)
        }
    }

    /** What generating sends: the lesson's new content and its photos. */
    private class Made(val content: Map<String, JsonElement>, val photos: List<ByteArray>)

    /** The page's form for making a lesson: its fields and its photos. */
    private class Form(val fields: Map<String, String>, val images: List<ByteArray>, val lang: String)

    private suspend fun RoutingContext.form(): Form {
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
        return Form(fields, images, lang())
    }

    /** The page's form (photos, prompt, options) made into cards by the relay, each
     * card told to `onCard` as it is written. */
    private suspend fun generate(form: Form, onCard: OnCard): Made {
        val (fields, images) = form.fields to form.images
        val texts = fields["page_texts"]?.let { json.parseToJsonElement(it) } ?: JsonArray(emptyList())
        val request = buildJsonObject {
            put("prompt", fields["prompt"] ?: "")
            put("deck", fields["deck"] ?: "")
            put("decks", JsonArray(lessons.list().map { JsonPrimitive(it.string("deck")) }.distinct()))
            put("fun_facts", fields["fun_facts"] == "true")
            put("helps", fields["helps"] == "true")
            put("page_texts", texts)
            put("instructions", instructions())
            put("quick", fields["quick"] == "true")
        }
        val found = cancellable(fields["job"]) { relay().extract(request, images, onCard) }
        val spelling = fields["typing"] == "true" || fields["dictation"] == "true"
        val voice = fields["voice"].orEmpty().let {
            if (!it.equals("auto", ignoreCase = true)) it
            else voiceFor(learned(found.string("back_language"), form.lang, spelling)) // the language learned
        }
        val content = mapOf(
            "deck" to found["deck"]!!.jsonObject["deck"]!!,
            "cards" to found["deck"]!!.jsonObject["cards"]!!,
            "prompt" to JsonPrimitive(fields["prompt"] ?: ""),
            "voice" to JsonPrimitive(voice),
            "typing" to JsonPrimitive(fields["typing"] == "true"),
            "dictation" to JsonPrimitive(fields["dictation"] == "true"),
            "choice" to (found["choice"] ?: JsonPrimitive("")),
            "page_texts" to texts,
        )
        return Made(content, images) // to do: turned upright (found["turns"]), as the computer does
    }

    /** A card's figure (SVG, /v1/figure) or picture (JPEG, /v1/picture), saved in the
     * lesson; its file name. */
    private suspend fun drawn(lessonId: String, card: JsonObject, fresh: Boolean): String {
        val figure = card.string("figure").trim()
        return if (figure.isNotEmpty()) {
            val svg = relay().post("figure", buildJsonObject { put("description", figure) }).string("svg")
            savePicture(lessonId, card.string("id"), svg.toByteArray(), "svg")
        } else {
            savePicture(lessonId, card.string("id"), relay().picture(card.string("picture_prompt"), fresh), "jpg")
        }
    }

    /** A picture in the lesson's images/, named as the computer names them. */
    private fun savePicture(lessonId: String, cardId: String, data: ByteArray, extension: String): String {
        val folder = lessons.images(lessonId) ?: throw NotFound()
        folder.mkdirs()
        val digest = MessageDigest.getInstance("SHA-1").digest(data).joinToString("") { "%02x".format(it) }
        val name = "picture-$cardId-${digest.take(8)}.$extension"
        File(folder, name).writeBytes(data)
        return name
    }

    /** The lesson with these cards, its pictures no card uses any more removed. */
    private fun savedCards(lessonId: String, cards: List<JsonObject>): JsonObject {
        val saved = lessons.update(lessonId, buildJsonObject { put("cards", JsonArray(cards)) }) ?: throw NotFound()
        val used = cards.map { it.string("picture") }.toSet()
        lessons.images(lessonId)?.listFiles { f -> PICTURE.matches(f.name) && f.name !in used }?.forEach { it.delete() }
        return saved
    }

    private fun RoutingContext.cardIndex(cards: List<JsonObject>): Int =
        cards.indexOfFirst { it.string("id") == param("card") }.takeIf { it >= 0 } ?: throw BadRequest("card.not_found")

    /** The relay's voices, asked once. */
    private var voiceList: JsonArray? = null

    private suspend fun voices(): JsonArray = voiceList ?: relay().voices().also { voiceList = it }

    /** A text read aloud by the relay's voice, kept on the phone: the same text and
     * voice aren't paid for twice (the 🔊 preview, then the cards). */
    private suspend fun speech(text: String, voice: String): File {
        val said = text.trim().take(200) // as the computer: a back's first 200 characters
        val digest = MessageDigest.getInstance("SHA-1").digest("$voice|${Relay.SPEECH_RATE}|$said".toByteArray())
        val mp3 = File(audio, digest.joinToString("") { "%02x".format(it) }.take(16) + ".mp3")
        if (!mp3.isFile) {
            val bytes = relay().speak(said, voice)
            withContext(Dispatchers.IO) {
                val tmp = File(audio, mp3.name + ".tmp")
                tmp.writeBytes(bytes)
                tmp.renameTo(mp3)
            }
        }
        return mp3
    }

    /** The backs' sound for AnkiDroid, with `voice` (none: no sound), and how many
     * couldn't be made. */
    private suspend fun sounds(deck: Deck, voice: String): Pair<Map<String, File>, Int> {
        if (!VOICE.matches(voice)) return emptyMap<String, File>() to 0
        val backs = deck.cards.map { it.back.trim() }.filter { it.isNotEmpty() }.distinct()
        val made = backs.associateWith { runCatching { speech(it, voice) }.getOrNull() }
        return made.filterValues { it != null }.mapValues { it.value!! } to made.count { it.value == null }
    }

    /** The voice for the backs' language ("es-ES", "en"…): the relay's DEFAULT_VOICE in
     * that variety, else in another of the language; "" when none (or no relay). */
    private suspend fun voiceFor(language: String): String {
        val tag = language.trim().replace('_', '-').lowercase()
        if (tag.isEmpty()) return ""
        val all = runCatching { voices() }.getOrNull()?.map { it.jsonObject } ?: return ""
        val base = tag.substringBefore('-')
        val ranked = all.filter { it.string("locale").lowercase().substringBefore('-') == base }.sortedWith(
            compareBy(
                { it.string("locale").lowercase() != tag }, // the variety asked for
                { it.string("locale").lowercase() != "$base-$base" }, // else the language's own (es-ES, fr-FR)
                { !it.string("voice").endsWith("-$DEFAULT_VOICE") },
            ),
        )
        return ranked.firstOrNull()?.string("voice") ?: ""
    }

    /** The backs' language when it is one being learned: not the pupil's own (the page's)
     * unless the cards are for writing what is heard, as the computer (app/main.py). */
    private fun learned(language: String, pupil: String, spelling: Boolean): String =
        if (!spelling && language.lowercase().substringBefore('-') == pupil.substringBefore('-')) "" else language

    private fun instructions(): String {
        val text = prefs[INSTRUCTIONS].orEmpty().trim()
        if (text.isEmpty()) return ""
        return "Standing instructions, for every lesson:\n$text\n(The request below wins if it says otherwise.)\n\n"
    }

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
                put("bytes", lessons.bytes() + audio.walkTopDown().filter { it.isFile }.sumOf { it.length() }) // with their sound
            }
        }
        api("DELETE", "/api/admin/lessons") {
            audio.listFiles()?.forEach { it.delete() } // their sound too (AnkiDroid keeps its own copy)
            buildJsonObject { put("deleted", lessons.deleteAll()) }
        }

        // --- With my computer (the Anki add-on's Notosaurus)
        api("POST", "/api/admin/computer/scan") {
            val read = try {
                scan()
            } catch (e: Exception) {
                throw BadRequest("computer.scan_unavailable")
            } ?: return@api buildJsonObject { put("cancelled", true) }
            connect(read)
        }
        api("PUT", "/api/admin/computer") { connect(body().string("address")) }
        api("POST", "/api/admin/mode") {
            val mode = body().string("mode")
            if (mode == COMPUTER_MODE && prefs[COMPUTER].isNullOrEmpty()) throw BadRequest("computer.not_found")
            prefs[MODE] = if (mode == COMPUTER_MODE) COMPUTER_MODE else PHONE_MODE
            modeChanged()
            buildJsonObject { put("url", if (mode == COMPUTER_MODE) prefs[COMPUTER]!! else "/") }
        }
        api("GET", "/api/lang") {
            val codes = i18nCodes()
            buildJsonObject {
                put("lang", JsonNull) // the page uses the phone's language
                put("available", JsonArray(codes.map(::JsonPrimitive)))
                put("names", JsonObject(codes.associateWith { JsonPrimitive(i18n(it, "meta", "name") ?: it) }))
            }
        }
        api("GET", "/api/voices") {
            try {
                voices()
            } catch (e: RelayException) {
                throw BadRequest("tts.voices_unavailable", buildJsonObject { put("detail", e.code) })
            }
        }
        // Listen to a text (🔊), read by the relay's voice
        get("/api/tts") {
            if (!allowed()) return@get
            val text = call.request.queryParameters["text"].orEmpty()
            val voice = call.request.queryParameters["voice"].orEmpty()
            val mp3 = runCatching { speech(text, voice) }.getOrNull()
            if (mp3 == null) call.respondText("", status = HttpStatusCode.BadGateway)
            else call.respondBytes(mp3.readBytes(), ContentType.Audio.MPEG)
        }

        // --- Prompts: Notosaurus's (from the page's languages), then the user's
        api("GET", "/api/prompts") { JsonArray(builtinPrompts(lang()) + userPrompts()) }
        api("POST", "/api/prompts") { savePrompt(null, body()) }
        api("PUT", "/api/prompts/{id}") { savePrompt(param("id").toInt(), body()) }
        api("DELETE", "/api/prompts/{id}") {
            writePrompts(userPrompts().filter { it.jsonObject["id"]!!.toPlain() != param("id") })
            JsonNull
        }
        api("POST", "/api/prompts/{id}/duplicate") {
            val source = (builtinPrompts(lang()) + userPrompts()).first { it.jsonObject["id"]!!.toPlain() == param("id") }
            savePrompt(null, source.jsonObject)
        }

        // --- Lessons
        api("GET", "/api/lessons") { JsonArray(lessons.list().map(lessons::summary)) }
        api("GET", "/api/lessons/{id}") { lesson() }
        api("PUT", "/api/lessons/{id}") { lessons.update(param("id"), body()) ?: notFound() }
        api("DELETE", "/api/lessons/{id}") {
            lessons.delete(param("id"))
            buildJsonObject { put("deleted", true) }
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
            val made = generate(form, onCard)
            lessons.create(made.content, made.photos)
        }
        // "Cancel" while waiting: the relay call stops, no lesson is saved
        api("POST", "/api/generations/{job}/cancel") {
            buildJsonObject { put("cancelled", generating[param("job")]?.also { it.cancel() } != null) }
        }
        // Generated again in its place (another prompt, photos, or carefully this time)
        making("/api/lessons/{id}/regenerate") { form, onCard ->
            val old = lesson()
            val made = generate(form, onCard)
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
                put("instructions", instructions())
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
                put("instructions", instructions())
            }
            JsonObject(relay().post("explain", request) - "usage")
        }
        // --- Pictures, through the relay (as app/main.py): drawn, the user's own, none
        api("POST", "/api/lessons/{id}/pictures") {
            val lesson = lesson()
            val id = lesson.string("id")
            val cards = lesson["cards"]!!.jsonArray.map { it.jsonObject }.toMutableList()
            val failures = mutableListOf<JsonObject>()
            val todo = cards.indices.filter { i ->
                cards[i].string("picture").isEmpty() && (cards[i].string("picture_prompt").isNotBlank() || cards[i].string("figure").isNotBlank())
            }
            val few = Semaphore(PICTURES_AT_ONCE)
            coroutineScope {
                todo.map { i ->
                    async {
                        few.withPermit {
                            try {
                                cards[i] = JsonObject(cards[i] + ("picture" to JsonPrimitive(drawn(id, cards[i], fresh = false))))
                            } catch (e: RelayException) { // a card without its picture is still a card
                                failures += buildJsonObject { put("code", e.code); put("params", e.params) }
                            }
                        }
                    }
                }.awaitAll()
            }
            buildJsonObject {
                put("lesson", savedCards(id, cards))
                put("failures", failures.size)
                put("error", failures.firstOrNull() ?: JsonNull)
            }
        }
        // A card's picture drawn again: its subject (or figure), or the one the user wrote
        api("POST", "/api/lessons/{id}/cards/{card}/picture/draw") {
            val lesson = lesson()
            val cards = lesson["cards"]!!.jsonArray.map { it.jsonObject }.toMutableList()
            val i = cardIndex(cards)
            val card = cards[i]
            val figure = card.string("figure").isNotBlank()
            val given = body()["subject"]?.takeIf { it !is JsonNull }?.jsonPrimitive?.content
            val subject = (given ?: card.string(if (figure) "figure" else "picture_prompt")).trim()
            if (subject.isEmpty()) throw BadRequest("picture.no_subject")
            val asked = JsonObject(card + ((if (figure) "figure" else "picture_prompt") to JsonPrimitive(subject)))
            cards[i] = JsonObject(asked + ("picture" to JsonPrimitive(drawn(lesson.string("id"), asked, fresh = true))))
            buildJsonObject {
                put("card", cards[i])
                put("lesson", savedCards(lesson.string("id"), cards))
            }
        }
        // The user's own photo as the card's picture (the page made it card size)
        post("/api/lessons/{id}/cards/{card}/picture") {
            if (!allowed()) return@post
            val (status, answer) = try {
                val lesson = lesson()
                val cards = lesson["cards"]!!.jsonArray.map { it.jsonObject }.toMutableList()
                val i = cardIndex(cards)
                var photo: ByteArray? = null
                call.receiveMultipart(formFieldLimit = 20L * 1024 * 1024).forEachPart { part ->
                    if (part is PartData.FileItem && part.name == "photo") photo = part.provider().toByteArray()
                    part.dispose()
                }
                val name = savePicture(lesson.string("id"), cards[i].string("id"), photo ?: throw BadRequest("extract.no_input"), "jpg")
                cards[i] = JsonObject(cards[i] + ("picture" to JsonPrimitive(name)))
                HttpStatusCode.Created to buildJsonObject {
                    put("card", cards[i])
                    put("lesson", savedCards(lesson.string("id"), cards))
                }
            } catch (e: Exception) {
                failure(e) ?: throw e
            }
            call.respondText(answer.toString(), ContentType.Application.Json, status)
        }
        // No picture on the card any more: a text card
        api("DELETE", "/api/lessons/{id}/cards/{card}/picture") {
            val lesson = lesson()
            val cards = lesson["cards"]!!.jsonArray.map { it.jsonObject }.toMutableList()
            val i = cardIndex(cards)
            cards[i] = JsonObject(cards[i] + listOf("picture", "picture_prompt", "figure").associateWith { JsonPrimitive("") })
            buildJsonObject {
                put("card", cards[i])
                put("lesson", savedCards(lesson.string("id"), cards))
            }
        }
        get("/api/lessons/{id}/pictures/{name}") {
            if (!allowed()) return@get
            val name = param("name")
            val file = lessons.images(param("id"))?.resolve(name)?.takeIf { PICTURE.matches(name) && it.isFile }
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
            val (sounds, failures) = sounds(deck, req.string("voice"))
            val lessonId = req.string("lesson_id")
            val folder = lessons.images(lessonId)
            val pictures = deck.cards.mapNotNull { c -> folder?.resolve(c.picture)?.takeIf { c.picture.isNotEmpty() && it.isFile }?.let { c.picture to it } }.toMap()
            // The diagrams: the photos their labels are on
            val photos = deck.cards.mapNotNull { it.mask?.page }.distinct().mapNotNull { n -> lessons.photo(lessonId, n)?.let { n to it } }.toMap()
            val media = Media(sounds, pictures, photos, lessonId)
            val sent = try {
                withContext(Dispatchers.IO) { anki.send(deck, media) }
            } catch (e: Exception) { // e.g. AnkiDroid never opened: no collection yet
                throw BadRequest("anki.android_failed", buildJsonObject { put("detail", e.message ?: e.javaClass.simpleName) })
            }
            buildJsonObject {
                put("added", sent.added)
                put("updated", 0) // to do: update the notes sent before (stable ids)
                put("synced", false)
                if (failures > 0) put("audio_failures", failures) // the page says some have no sound
            }
        }

        // --- The page
        get("/{path...}") {
            val path = call.parameters.getAll("path").orEmpty().joinToString("/").ifEmpty { "index.html" }
            val bytes = path.takeUnless { ".." in it }?.let(web)
            if (bytes == null) call.respondText("", status = HttpStatusCode.NotFound)
            else call.respondBytes(bytes, ContentType.defaultForFilePath(path))
        }
    }

    // --- Routes: the token checked, errors as the page expects them ({"detail": {code, params}})

    private class NotFound : Exception()

    /** "Cancel" stopped the lesson being made. */
    private class Cancelled : Exception()

    private class BadRequest(val code: String, val params: JsonObject = JsonObject(emptyMap())) : Exception(code)

    /** AnkiDroid installed and allowed, asked for when the cards are first added: its Play
     * Store page when it's missing, its permission dialog when it isn't allowed yet. */
    private suspend fun readyAnki() {
        if (!anki.installed()) {
            installAnki()
            throw BadRequest("anki.android_missing")
        }
        if (!anki.permitted() && !requestAnkiPermission()) throw BadRequest("anki.android_refused")
    }

    private fun notFound(): Nothing = throw NotFound()

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

    /** Connect to the computer's Notosaurus: its QR code's address (or one typed), checked,
     * kept, and the app switched to it. Returns where to go. */
    private suspend fun connect(raw: String): JsonObject {
        val url = computerUrl(raw) ?: throw BadRequest("computer.not_a_qr")
        if (!isNotosaurus(url)) throw BadRequest("computer.not_found")
        prefs[COMPUTER] = url.toString()
        prefs[COMPUTER_NAME] = computerName(url).orEmpty()
        prefs[MODE] = COMPUTER_MODE
        modeChanged()
        return buildJsonObject { put("url", url.toString()) }
    }

    /** The computer's name, which its /api/config gives a paired phone (the QR code's
     * token pairs it); null from an add-on older than that, or without a token. */
    private suspend fun computerName(url: URI): String? = withContext(Dispatchers.IO) {
        val request = okhttp3.Request.Builder().url("${origin(url)}/api/config?${url.rawQuery.orEmpty()}").build()
        runCatching {
            computerClient.newCall(request).execute().use {
                if (it.isSuccessful) json.parseToJsonElement(it.body.string()).jsonObject.string("computer_name") else null
            }
        }.getOrNull()?.takeIf { it.isNotBlank() }
    }

    /** Notosaurus answers there: its /api/lang, which a phone not paired yet may read. */
    private suspend fun isNotosaurus(url: URI): Boolean = withContext(Dispatchers.IO) {
        val request = okhttp3.Request.Builder().url("${origin(url)}/api/lang").build()
        runCatching {
            computerClient.newCall(request).execute().use { it.isSuccessful && "\"available\"" in it.body.string() }
        }.getOrDefault(false)
    }

    private fun settings() = buildJsonObject {
        put(RELAY, prefs[RELAY] ?: DEFAULT_RELAY)
        put(KEY, masked(prefs[KEY].orEmpty())) // shown, not given back whole
        put("has_key", prefs[KEY].orEmpty().isNotEmpty())
        put(INSTRUCTIONS, prefs[INSTRUCTIONS].orEmpty())
        put(CARD_HELPS, prefs[CARD_HELPS] == "true")
        put("version", version)
        put(MODE, prefs[MODE] ?: PHONE_MODE)
        prefs[COMPUTER]?.let {
            put(COMPUTER, it)
            put("computer_address", origin(URI(it))) // without its token
            put("computer_name", prefs[COMPUTER_NAME].orEmpty())
        }
    }

    private fun masked(key: String) = if (key.length <= 8) "•".repeat(key.length) else "${key.take(4)}…${key.takeLast(4)}"

    /** The answer to an error the page translates; null: not one of ours. */
    private fun failure(e: Exception): Pair<HttpStatusCode, JsonObject>? = when (e) {
        is NotFound -> HttpStatusCode.NotFound to error("lesson.not_found", JsonObject(emptyMap()))
        is RelayException -> HttpStatusCode.BadGateway to error(e.code, e.params)
        is BadRequest -> HttpStatusCode.BadRequest to error(e.code, e.params)
        is Cancelled -> HttpStatusCode.Conflict to error("extract.cancelled", JsonObject(emptyMap()))
        else -> null
    }

    /**
     * A lesson made (a new one, or again in its place): as JSON, or as the AI writes
     * it when the page asks Relay.STREAM_TYPE, as the computer answers (app/main.py,
     * _streamed): {"card"} (or {"restart"}) lines, then {"lesson"}, {"error"} or
     * {"cancelled"}. The form is read first: the answer then outlives the request.
     */
    private fun Route.making(path: String, make: suspend RoutingContext.(Form, OnCard) -> JsonObject) {
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

    private fun error(code: String, params: JsonObject) = buildJsonObject {
        put("detail", buildJsonObject { put("code", code); put("params", params) })
    }

    private fun RoutingContext.param(name: String) = call.parameters[name]!!
    private suspend fun RoutingContext.body() = json.parseToJsonElement(call.receiveText()).jsonObject
    private fun RoutingContext.lesson() = lessons.get(param("id")) ?: notFound()
    private fun RoutingContext.lang() = call.request.headers["X-Notosaurus-Lang"]?.lowercase() ?: "en"
    private fun RoutingContext.languageName() = i18n(lang(), "meta", "englishName") ?: "English"

    // --- The page's files and languages

    private fun i18nCodes(): List<String> = languages().sorted()

    private fun i18nFile(lang: String): JsonObject =
        web("i18n/$lang.json")?.let { json.parseToJsonElement(it.decodeToString()).jsonObject } ?: JsonObject(emptyMap())

    /** A text of the page's languages (the app's shortcuts), English when missing. */
    fun text(lang: String, vararg keys: String): String? = i18n(lang, *keys) ?: i18n("en", *keys)

    private fun i18n(lang: String, vararg keys: String): String? {
        var value: JsonElement? = i18nFile(lang)
        for (key in keys) value = (value as? JsonObject)?.get(key)
        return (value as? JsonPrimitive)?.content
    }

    // --- Prompts (app/prompts.py)

    private fun builtinPrompts(lang: String): List<JsonElement> {
        val texts = i18nFile(lang)["builtinPrompts"] as? JsonObject ?: JsonObject(emptyMap())
        val english = i18nFile("en")["builtinPrompts"] as? JsonObject ?: JsonObject(emptyMap())
        return BUILTIN.mapNotNull { key ->
            val prompt = (texts[key] ?: english[key])?.jsonObject ?: return@mapNotNull null
            JsonObject(PROMPT_DEFAULTS + prompt + mapOf("id" to JsonPrimitive("notosaurus:$key"), "builtin" to JsonPrimitive(true)))
        }
    }

    private fun userPrompts(): List<JsonElement> =
        if (prompts.isFile) json.parseToJsonElement(prompts.readText()).jsonArray else emptyList()

    private fun writePrompts(list: List<JsonElement>) = prompts.writeText(JsonArray(list).toString())

    private fun savePrompt(id: Int?, prompt: JsonObject): JsonObject {
        val list = userPrompts().toMutableList()
        val newId = id ?: ((list.maxOfOrNull { it.jsonObject["id"]!!.toPlain().toIntOrNull() ?: 0 } ?: 0) + 1)
        val saved = JsonObject(PROMPT_DEFAULTS + prompt.filterKeys { it in PROMPT_FIELDS } + mapOf("id" to JsonPrimitive(newId), "builtin" to JsonPrimitive(false)))
        val at = list.indexOfFirst { it.jsonObject["id"]!!.toPlain() == newId.toString() }
        if (at >= 0) list[at] = saved else list += saved
        writePrompts(list)
        return saved
    }

    private fun JsonElement.toPlain() = (this as? JsonPrimitive)?.content ?: toString()

    companion object {
        const val COOKIE = "notosaurus_app"

        // The settings
        const val RELAY = "relay"
        const val KEY = "key"
        const val INSTRUCTIONS = "instructions"
        const val CARD_HELPS = "card_helps"

        // The voice chosen for a lesson whose voice is "auto" (Google Chirp 3 HD: the same
        // name in every language); a voice's name, as the page tells them from Anki locales
        const val DEFAULT_VOICE = "Aoede"
        private const val PICTURES_AT_ONCE = 4
        private val PICTURE = Regex("""^picture-[a-z0-9]+-[a-f0-9]{8}\.(jpg|svg)$""") // ours only: no "../"
        private val VOICE = Regex("""^[a-z]{2,3}-[A-Z]{2}-[\w-]+$""")

        // Prototype: the relay on the computer, seen from the emulator (changed in the settings, "Advanced")
        const val DEFAULT_RELAY = "http://10.0.2.2:8080"

        // Which Notosaurus the app shows: its own (phone) or the computer's (the add-on's)
        const val MODE = "mode"
        const val PHONE_MODE = "phone"
        const val COMPUTER_MODE = "computer"
        const val COMPUTER = "computer" // the computer's address, as its QR code gives it (with its token)
        const val COMPUTER_NAME = "computer_name" // its name, shown in the settings ("" when it didn't say)

        private val computerClient = okhttp3.OkHttpClient.Builder()
            .connectTimeout(3, java.util.concurrent.TimeUnit.SECONDS)
            .readTimeout(5, java.util.concurrent.TimeUnit.SECONDS)
            .build()

        /** The computer's Notosaurus address, from its QR code or as typed ("192.168.1.10:8000"):
         * http(s), a host; null when it isn't one. */
        fun computerUrl(raw: String): URI? {
            val text = raw.trim().let { if ("://" in it) it else "http://$it" }
            val url = runCatching { URI(text) }.getOrNull() ?: return null
            if (url.scheme !in setOf("http", "https") || url.host.isNullOrEmpty()) return null
            return if (url.path.isNullOrEmpty()) URI(url.scheme, url.userInfo, url.host, url.port, "/", url.query, null) else url
        }

        fun origin(url: URI) = "${url.scheme}://${url.host}${if (url.port > 0) ":${url.port}" else ""}"

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
        )

        private fun asset(context: Context, path: String) =
            runCatching { context.assets.open(path).use { it.readBytes() } }.getOrNull()

        // Notosaurus's prompts, in order (app/prompts.py, BUILTIN)
        private val BUILTIN = listOf(
            "auto", "vocabulary", "sentences", "questions", "cloze", "quiz", "true_false", "formulas",
            "school_formulas", "geometry", "diagram", "pictures", "wordlist",
        )
        private val PROMPT_FIELDS = setOf("name", "text", "deck", "voice", "typing", "dictation")
        private val PROMPT_DEFAULTS = mapOf(
            "deck" to JsonPrimitive(""), "voice" to JsonPrimitive(""), "typing" to JsonPrimitive(false),
            "dictation" to JsonPrimitive(false), "used_at" to JsonNull,
        )
    }
}
