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
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
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
 * The routes only, by subject in *Routes.kt (SettingsRoutes, LessonRoutes…), with
 * what they share here (api, making…); the work in: Generation (a lesson made by the relay), Pictures,
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
    internal val anki: AnkiTarget,
    internal val prefs: Preferences,
    internal val version: String = "",
    internal val requestAnkiPermission: suspend () -> Boolean = { false }, // AnkiDroid's permission dialog: granted?
    internal val installAnki: () -> Unit = {}, // AnkiDroid's Play Store page
    internal val scan: suspend () -> String? = { null }, // a QR code read by the camera (null: cancelled)
    internal val modeChanged: () -> Unit = {}, // the app's shortcuts follow
    internal val turnPhoto: (ByteArray, Int) -> ByteArray = { data, _ -> data }, // a JPEG turned clockwise (Photos.turn)
    internal val cardSize: (ByteArray) -> ByteArray = { it }, // a picture as a card shows it (Photos.cardSize)
    recorder: Recorder? = null, // the microphone, for the page's 🎤 (none: no 🎤)
    internal val requestMicPermission: suspend () -> Boolean = { false }, // the microphone's permission dialog: granted?
    relayDirectory: String? = null, // where the relays are listed (RelayDirectory.URL); null: the built-in ones
    internal val subscriptions: SubscriptionStore? = null, // Google Play's subscription (none: a licence key only)
    val token: String = UUID.randomUUID().toString(),
) {
    internal val relays = RelayDirectory(prefs, relayDirectory)
    internal val lessons = Lessons(File(dataDir, "lessons").apply { mkdirs() })
    internal val children = Children(prefs) // the children the lessons are for (the page's "For: …")
    internal val texts = PageTexts(web, languages)
    internal val prompts = Prompts(File(dataDir, "prompts.json"), texts)
    internal val speech = Speech(File(dataDir, "audio").apply { mkdirs() }, prefs, ::relay) // the backs read aloud, kept
    internal val pictures = Pictures(lessons, ::relay, cardSize)
    internal val generation = Generation(lessons, prefs, ::relay, speech, turnPhoto, children)
    internal val computer = Computer(prefs, modeChanged)
    internal val switches = Switches(prefs, version)
    internal val dictation = recorder?.let { Dictation(File(dataDir, "dictation").apply { mkdirs() }, it, ::relay) }
    private lateinit var server: EmbeddedServer<*, *>

    /** Starts it; returns its port. */
    fun start(): Int {
        server = embeddedServer(CIO, port = 0, host = "127.0.0.1") { module() }
        server.start(wait = false)
        return runBlocking { server.engine.resolvedConnectors().first().port }
    }

    fun stop() {
        if (::server.isInitialized) server.stop(gracePeriodMillis = 0, timeoutMillis = 1000)
    }

    init {
        // A key saved before keys were per relay: the relay in use then is its own
        prefs[KEY]?.takeIf { it.isNotEmpty() }?.let {
            prefs[keyOf(relayUrl())] = it
            prefs[KEY] = ""
        }
    }

    /** The relay, with its licence key. */
    internal fun relay() = Relay(relayUrl(), licence(), lost = relays::refreshSoon)

    internal fun relayUrl() = prefs[RELAY] ?: if (DEFAULT_RELAY == TEST_RELAY) relays.test() else relays.real()

    /** The licence key of the relay in use: each relay keeps its own (the test one has its own licences). */
    internal fun licence() = prefs[keyOf(relayUrl())].orEmpty()

    /** A text of the page's languages (the app's shortcuts), English when missing. */
    fun text(lang: String, vararg keys: String): String? = texts.get(lang, *keys) ?: texts.get("en", *keys)

    fun Application.module() = routing {
        settingsRoutes(this@LocalServer)
        languageRoutes(this@LocalServer)
        promptRoutes(this@LocalServer)
        lessonRoutes(this@LocalServer)
        generationRoutes(this@LocalServer)
        dictationRoutes(this@LocalServer)
        pictureRoutes(this@LocalServer)
        ankiRoutes(this@LocalServer)
        subscriptionRoutes(this@LocalServer)

        // --- The page
        get("/{path...}") {
            val path = call.parameters.getAll("path").orEmpty().joinToString("/").ifEmpty { "index.html" }
            val bytes = path.takeUnless { ".." in it }?.let(web)
            if (bytes == null) call.respondText("", status = HttpStatusCode.NotFound)
            else call.respondBytes(bytes, ContentType.defaultForFilePath(path))
        }
    }

    // --- Routes: the token checked, errors as the page expects them (Errors.kt)

    internal fun Route.api(method: String, path: String, handler: suspend RoutingContext.() -> JsonElement) {
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

    internal suspend fun RoutingContext.allowed(): Boolean {
        if (call.request.cookies[COOKIE] == token) return true
        call.respondText(error("device.not_paired", JsonObject(emptyMap())).toString(), ContentType.Application.Json, HttpStatusCode.Unauthorized)
        return false
    }

    /**
     * A lesson made (a new one, or again in its place): as JSON, or as the AI writes
     * it when the page asks Relay.STREAM_TYPE, as the computer answers (app/main.py,
     * _streamed): {"card"} (or {"restart"}) lines, then {"lesson"}, {"error"} or
     * {"cancelled"}. The form is read first: the answer then outlives the request.
     */
    internal fun Route.making(path: String, make: suspend RoutingContext.(GenerationForm, OnCard) -> JsonObject) {
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

    internal fun RoutingContext.param(name: String) = call.parameters[name]!!
    internal suspend fun RoutingContext.body() = json.parseToJsonElement(call.receiveText()).jsonObject
    internal fun RoutingContext.lesson() = lessons.get(param("id")) ?: notFound()
    internal fun RoutingContext.lang() = call.request.headers["X-Notosaurus-Lang"]?.lowercase() ?: "en"
    internal fun RoutingContext.languageName() = texts.get(lang(), "meta", "englishName") ?: "English"

    internal fun RoutingContext.cardIndex(lesson: JsonObject): Int =
        lesson.cards().indexOfFirst { it.string("id") == param("card") }.takeIf { it >= 0 } ?: throw BadRequest("card.not_found")

    /** The page's form for making a lesson, read whole first (the answer may outlive the request). */
    internal suspend fun RoutingContext.form(): GenerationForm {
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
        const val MAX_PHOTOS = 10 // a lesson's pages, as on the computer (MAX_IMAGES)

        // The welcome accepted (its version): raised when what it says changes a lot, so it shows again
        const val WELCOME = "welcome"
        const val WELCOME_VERSION = 1

        // The settings
        const val RELAY = "relay"
        const val KEY = "key" // the licence key: saved per relay (keyOf), this name only before

        fun keyOf(relay: String) = "$KEY@${relay.trimEnd('/')}"
        const val INSTRUCTIONS = "instructions"
        // Asked of the AI at every generation, on unless turned off ("false"), as the computer's
        const val FUN_FACTS = "fun_facts"
        const val HELPS = "helps"

        const val TTS_RATE = Speech.TTS_RATE

        // The relay of a fresh install, by the build (app/build.gradle.kts): the test instance
        // while developing, the real one in a release (changed in the settings, "Advanced").
        // Built in; where they are now: RelayDirectory
        val DEFAULT_RELAY: String = BuildConfig.DEFAULT_RELAY
        val REAL_RELAY: String = BuildConfig.REAL_RELAY
        val TEST_RELAY: String = BuildConfig.TEST_RELAY // "" in a release

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
            requestMicPermission: suspend () -> Boolean,
            activity: () -> android.app.Activity?, // Google Play's purchase screen shows over it
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
            cardSize = Photos::cardSize,
            recorder = MicRecorder(context),
            requestMicPermission = requestMicPermission,
            relayDirectory = RelayDirectory.URL,
            subscriptions = PlayStore(context, activity),
        )

        private fun asset(context: Context, path: String) =
            runCatching { context.assets.open(path).use { it.readBytes() } }.getOrNull()
    }
}
