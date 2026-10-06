package app.notosaurus

import android.content.Context
import io.ktor.http.ContentType
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
import kotlinx.serialization.json.put
import java.io.File
import java.net.URI
import java.util.UUID

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
                put("card_helps", prefs[CARD_HELPS] == "true")
                put("configured", true)
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
                put("bytes", lessons.bytes())
            }
        }
        api("DELETE", "/api/admin/lessons") { buildJsonObject { put("deleted", lessons.deleteAll()) } }

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
        api("GET", "/api/voices") { JsonArray(emptyList()) } // to do: Android's voices

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
        api("POST", "/api/extract") {
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
            val texts = fields["page_texts"]?.let { json.parseToJsonElement(it) } ?: JsonArray(emptyList())
            val request = buildJsonObject {
                put("prompt", fields["prompt"] ?: "")
                put("deck", fields["deck"] ?: "")
                put("decks", JsonArray(lessons.list().map { JsonPrimitive(it.string("deck")) }.distinct()))
                put("fun_facts", fields["fun_facts"] == "true")
                put("helps", fields["helps"] == "true")
                put("page_texts", texts)
                put("instructions", instructions())
            }
            val found = relay().withPhotos("extract", request, images)
            val voice = fields["voice"].orEmpty().takeUnless { it.equals("auto", ignoreCase = true) } ?: ""
            lessons.create(
                mapOf(
                    "deck" to found["deck"]!!.jsonObject["deck"]!!,
                    "cards" to found["deck"]!!.jsonObject["cards"]!!,
                    "prompt" to JsonPrimitive(fields["prompt"] ?: ""),
                    "voice" to JsonPrimitive(voice),
                    "typing" to JsonPrimitive(fields["typing"] == "true"),
                    "dictation" to JsonPrimitive(fields["dictation"] == "true"),
                    "choice" to (found["choice"] ?: JsonPrimitive("")),
                    "page_texts" to texts,
                ),
                images, // to do: turned upright (found["turns"]), as the computer does
            )
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
        api("POST", "/api/lessons/{id}/pictures") { // to do: /v1/picture and /v1/figure
            buildJsonObject {
                put("lesson", lesson())
                put("failures", 0)
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
            val sent = try {
                withContext(Dispatchers.IO) { anki.send(deck) }
            } catch (e: Exception) { // e.g. AnkiDroid never opened: no collection yet
                throw BadRequest("anki.android_failed", buildJsonObject { put("detail", e.message ?: e.javaClass.simpleName) })
            }
            buildJsonObject {
                put("added", sent.added)
                put("updated", 0) // to do: update the notes sent before (stable ids)
                put("synced", false)
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
                } catch (e: NotFound) {
                    HttpStatusCode.NotFound to error("lesson.not_found", JsonObject(emptyMap()))
                } catch (e: RelayException) {
                    HttpStatusCode.BadGateway to error(e.code, e.params)
                } catch (e: BadRequest) {
                    HttpStatusCode.BadRequest to error(e.code, e.params)
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
        prefs[MODE] = COMPUTER_MODE
        modeChanged()
        return buildJsonObject { put("url", url.toString()) }
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
        prefs[COMPUTER]?.let { put(COMPUTER, it); put("computer_address", origin(URI(it))) } // the address, without its token
    }

    private fun masked(key: String) = if (key.length <= 8) "•".repeat(key.length) else "${key.take(4)}…${key.takeLast(4)}"

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

        // Prototype: the relay on the computer, seen from the emulator (changed in the settings, "Advanced")
        const val DEFAULT_RELAY = "http://10.0.2.2:8080"

        // Which Notosaurus the app shows: its own (phone) or the computer's (the add-on's)
        const val MODE = "mode"
        const val PHONE_MODE = "phone"
        const val COMPUTER_MODE = "computer"
        const val COMPUTER = "computer" // the computer's address, as its QR code gives it (with its token)

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
