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
import java.util.UUID

/**
 * The computer's server, as the page sees it: the same /api routes (app/main.py),
 * answered on the phone. The page itself (assets/web/, the public repository's
 * static/) is served from here too, so it runs unchanged.
 *
 * - The AI: the relay (`relay()`, with the licence).
 * - The lessons: on the phone (Lessons).
 * - Anki: AnkiDroid (Anki).
 *
 * Listens on 127.0.0.1 only, and answers /api only with the cookie the app's WebView
 * has: another app on the phone can't use it.
 */
class LocalServer(
    dataDir: File,
    private val web: (String) -> ByteArray?, // a file of the page, by its path ("index.html", "i18n/fr.json")
    private val languages: () -> List<String>, // the page's languages ("en", "fr"…)
    private val anki: AnkiTarget,
    private val relay: () -> Relay,
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

    fun Application.module() = routing {
        api("GET", "/api/admin") { buildJsonObject { put("allowed", false) } } // settings: the app's own screen
        api("GET", "/api/config") {
            buildJsonObject {
                put("version", "android-prototype")
                put("diagram_warning", false)
                put("max_photos", 10)
                put("card_helps", false)
                put("configured", true)
            }
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
                put("available", anki.installed() && anki.permitted())
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
            val sent = withContext(Dispatchers.IO) { anki.send(deck) }
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

        /** The app's: the page from its assets (web/), data in its own files, AnkiDroid. */
        fun forApp(context: Context, relay: () -> Relay) = LocalServer(
            dataDir = context.filesDir,
            web = { path -> runCatching { context.assets.open("web/$path").use { it.readBytes() } }.getOrNull() },
            languages = {
                context.assets.list("web/i18n").orEmpty().filter { it.endsWith(".json") }.map { it.removeSuffix(".json") }
            },
            anki = Anki(context),
            relay = relay,
        )

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
