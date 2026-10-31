package app.notosaurus

import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.put
import okhttp3.Call
import okhttp3.Callback
import okhttp3.Headers.Companion.headersOf
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.Response
import java.io.IOException
import java.util.concurrent.TimeUnit
import kotlin.coroutines.AbstractCoroutineContextElement
import kotlin.coroutines.CoroutineContext
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException

/**
 * The relay's client: `baseUrl` (e.g. "http://192.168.1.10:8080", a relay run on
 * the computer) and the licence key. Requests and answers as JSON objects: the
 * cards go through as the page has them (every field, ids included).
 */
/** A card's picture from the relay: the JPEG, and where it comes from (models.PictureSource, as JSON). */
class Picture(val jpeg: ByteArray, val source: JsonObject?)

/** Told each card as soon as the AI has written it, or null: start again (another model). */
typealias OnCard = suspend (JsonObject?) -> Unit

/** Who listens to what the AI is at (relay_api.AiStep: slow, the fallback model, the figures)
 * while it works, as the core's calls.telling: set around a call, read by the relay's lines. */
class Telling(val step: Step) : AbstractCoroutineContextElement(Key) {
    companion object Key : CoroutineContext.Key<Telling>
}

/** A step of the AI told to whoever listens (Telling), if anyone does. */
suspend fun tell(step: JsonObject) {
    currentCoroutineContext()[Telling]?.step?.invoke(step)
}

class Relay(
    baseUrl: String,
    private val key: String,
    private val lost: () -> Unit = {}, // not reached, or nothing there: where the relays are, asked again (RelayDirectory)
    private val lapsed: () -> Unit = {}, // the subscription ended or on hold: Google Play's purchases checked again
    private val rejected: (String) -> Unit = {}, // the key sent, unknown or ended at the relay: no longer kept
    // No key yet, an AI call: the free trial's key (started then), or an error thrown (null: none, the call without it)
    private val noKey: (suspend () -> String)? = null,
) {
    private val base = baseUrl.trimEnd('/')

    suspend fun account(): Account = json.decodeFromJsonElement(Account.serializer(), call("account", null))

    /** A route with photos (extract, revise): the JSON request, then the photos (JPEG). */
    suspend fun withPhotos(route: String, request: JsonObject, photos: List<ByteArray>): JsonObject =
        call(route, multipart(request, photos))

    /** /v1/revise asked as it goes (relay_api.ReviseLine): what the AI is at told (Telling),
     * then the answer. */
    suspend fun revise(request: JsonObject, photos: List<ByteArray>): JsonObject =
        open("revise", multipart(request, photos), stream = true).use { response ->
            streamed(response, "result") { line -> line["step"]?.jsonObject?.let { tell(it) } }
        }

    /**
     * /v1/extract as the AI writes (STREAM_TYPE, relay_api.ExtractLine): each card told
     * to `onCard` as it comes (null: start again), then the answer. A relay answering
     * all at once (an older one): its answer. Cancelled, the request stops: so does the AI.
     */
    suspend fun extract(request: JsonObject, photos: List<ByteArray>, onCard: OnCard): JsonObject {
        return open("extract", multipart(request, photos), stream = true).use { response ->
            streamed(response, "result") { line ->
                val step = line["step"]?.jsonObject
                if (step != null) tell(step) else onCard(line["card"]?.jsonObject)
            }
        }
    }

    /** A card's figure or picture (/v1/card-picture, relay_api.CardPictureLine): each step told
     * to `onStep` as it begins ({"step", "problem", "first"}: what the page shows on the card
     * meanwhile), then the answer (relay_api.CardPictureResponse). */
    suspend fun cardPicture(request: JsonObject, onStep: Step): JsonObject {
        return open("card-picture", request.toString().toRequestBody(JSON), stream = true).use { response ->
            streamed(response, "result") { line -> line["step"]?.jsonObject?.let { onStep(it) } }
        }
    }

    /** An answer asked as it comes (STREAM_TYPE): each line told to `onLine`, until the
     * `last` one, its value the answer; an {"error"} line thrown. A relay answering all at
     * once: its answer. */
    private suspend fun streamed(response: Response, last: String, onLine: suspend (JsonObject) -> Unit): JsonObject {
        if (response.header("Content-Type")?.startsWith(STREAM_TYPE) != true) {
            return json.parseToJsonElement(response.body.string()).jsonObject
        }
        val source = response.body.source()
        // A line is waited for in a blocking read, which a cancelled coroutine doesn't stop:
        // "Cancel" stops its call beside it, the read stops at once (else it waits for the relay)
        return coroutineScope {
            val closer = launch(start = CoroutineStart.UNDISPATCHED) {
                try {
                    awaitCancellation()
                } finally {
                    // Its call cancelled: the socket closed, the read fails at once (the answer
                    // itself closed by its reader, `use`: closed from here meanwhile, okio refuses)
                    response.request.tag(Streaming::class.java)?.call?.cancel()
                }
            }
            try {
                while (true) {
                    val line = try {
                        withContext(Dispatchers.IO) { source.readUtf8Line() }
                    } catch (e: IOException) {
                        ensureActive() // closed by "Cancel": cancelled, not a relay unreachable
                        throw e
                    } ?: throw RelayException("relay.unreachable", buildJsonObject { put("detail", "cut") })
                    if (line.isBlank()) continue
                    val item = json.parseToJsonElement(line).jsonObject
                    item[last]?.let { return@coroutineScope it.jsonObject }
                    item["error"]?.jsonObject?.let {
                        throw RelayException(it.string("code"), it["params"]?.jsonObject ?: JsonObject(emptyMap()))
                    }
                    onLine(item)
                }
                @Suppress("UNREACHABLE_CODE")
                error("unreachable")
            } finally {
                closer.cancel()
            }
        }
    }

    private fun multipart(request: JsonObject, photos: List<ByteArray>): RequestBody {
        val body = MultipartBody.Builder().setType(MultipartBody.FORM)
            .addPart(headersOf("Content-Disposition", "form-data; name=\"request\""), request.toString().toRequestBody(JSON))
        photos.forEachIndexed { i, data ->
            body.addFormDataPart("images", "page-${i + 1}.jpg", data.toRequestBody(JPEG))
        }
        return body.build()
    }

    /** A dictation (/v1/transcribe) as the text its speaker meant to type: `audio` is AAC
     * (ADTS); `kind` "prompt" or "correction"; `language` the page's, its English name. */
    suspend fun transcribe(kind: String, language: String, audio: ByteArray): String {
        val request = buildJsonObject {
            put("kind", kind)
            put("language", language)
        }
        val body = MultipartBody.Builder().setType(MultipartBody.FORM)
            .addPart(headersOf("Content-Disposition", "form-data; name=\"request\""), request.toString().toRequestBody(JSON))
            .addFormDataPart("audio", "dictation.aac", audio.toRequestBody(AAC))
            .build()
        return call("transcribe", body).string("text")
    }

    /** The voices /v1/speak reads with: {"voice", "locale", "gender"}, as the page lists them. */
    suspend fun voices(): JsonArray = open("voices", null).use { json.parseToJsonElement(it.body.string()).jsonArray }

    /** A text read aloud (/v1/speak): the mp3. */
    suspend fun speak(text: String, voice: String, rate: Double = SPEECH_RATE): ByteArray {
        val request = buildJsonObject {
            put("text", text)
            put("voice", voice)
            put("rate", rate)
        }
        return open("speak", request.toString().toRequestBody(JSON)).use { it.body.bytes() }
    }

    /** A picture answer: the JPEG, and where it comes from (PICTURE_SOURCE_HEADER; null from an older relay). */
    private fun picture(response: Response): Picture {
        val source = response.header(PICTURE_SOURCE_HEADER)?.let { runCatching { json.parseToJsonElement(it).jsonObject }.getOrNull() }
        return Picture(response.body.bytes(), source)
    }

    /** Free pictures of a subject to choose from (/v1/pictures/search), the AI keeping those
     * that show it (1 credit): each source's [stock.Found…] told to `onFound` as it answers
     * (relay_api.PictureSearchLine), then the answer ({"words", "usage"}). `words`: its
     * English search words when known (the card's picture_search), else what the user wrote
     * is translated. Cancelled, the request stops. */
    suspend fun searchPictures(
        subject: String,
        context: String = "",
        words: String = "",
        onFound: suspend (JsonArray) -> Unit = {},
    ): JsonObject {
        val request = buildJsonObject {
            put("subject", words.ifBlank { subject })
            put("context", context.take(8000))
            put("translate", words.isBlank()) // what the user wrote, any language
            put("sort", true)
        }
        return open("pictures/search", request.toString().toRequestBody(JSON), stream = true).use { response ->
            val answer = streamed(response, "done") { line -> line["found"]?.jsonArray?.let { onFound(it) } }
            answer["results"]?.jsonArray?.takeIf { it.isNotEmpty() }?.let { onFound(it) } // all at once
            answer
        }
    }

    /** One of the pictures found (/v1/pictures/found): the JPEG, card size, and where it comes from. */
    suspend fun foundPicture(source: String, id: String): Picture {
        val request = buildJsonObject {
            put("source", source)
            put("id", id)
        }
        return open("pictures/found", request.toString().toRequestBody(JSON)).use(::picture)
    }

    /** A JSON route (explain, figure). */
    suspend fun post(route: String, request: JsonObject): JsonObject = call(route, request.toString().toRequestBody(JSON))

    private suspend fun call(route: String, body: RequestBody?): JsonObject =
        open(route, body).use { json.parseToJsonElement(it.body.string()).jsonObject }

    /** The relay's answer, when it is one (its errors thrown); `stream`: asked as it comes. */
    private suspend fun open(route: String, body: RequestBody?, stream: Boolean = false): Response {
        val key = key.trim().ifEmpty { if (route in AI_ROUTES) noKey?.invoke().orEmpty() else "" }
        val request = Request.Builder().url("$base/v1/$route")
            .header("Authorization", "Bearer $key")
            .header(CLIENT_HEADER, CLIENT_VERSION)
            .apply { if (stream) header("Accept", STREAM_TYPE).tag(Streaming::class.java, Streaming()) }
            .apply { if (body != null) post(body) }
            .build()
        val response = try {
            client.newCall(request).also { request.tag(Streaming::class.java)?.call = it }.await()
        } catch (e: IOException) {
            lost()
            throw RelayException("relay.unreachable", buildJsonObject { put("detail", e.message ?: "") })
        }
        if (!response.isSuccessful) {
            val text = response.use { it.body.string() }
            val error = runCatching { json.decodeFromString<ApiError>(text) }.getOrNull()
            if (error == null && response.code == 404) lost() // not a relay's answer: a service gone
            if (error?.code in LAPSED) lapsed()
            if (error?.code == INVALID_KEY && key.isNotEmpty()) rejected(key)
            throw RelayException(error?.code ?: "relay.http_${response.code}", error?.params ?: JsonObject(emptyMap()))
        }
        return response
    }

    /** The call's answer; cancelled with the coroutine ("Cancel" on the page): the
     * request stops, the relay stops the AI. */
    private suspend fun Call.await(): Response = suspendCancellableCoroutine { waiting ->
        waiting.invokeOnCancellation { cancel() }
        // Cancelled later, while the answer is read (a stream): the call stops too
        waiting.context[Job]?.invokeOnCompletion { if (it is CancellationException) cancel() }
        enqueue(object : Callback {
            override fun onFailure(call: Call, e: IOException) = waiting.resumeWithException(e)
            override fun onResponse(call: Call, response: Response) =
                waiting.resume(response) { _, _, _ -> response.close() }
        })
    }

    /** A streamed answer's call, kept with its request: "Cancel" stops it (streamed). */
    private class Streaming {
        @Volatile var call: Call? = null
    }

    companion object {
        const val CLIENT_HEADER = "X-Notosaurus-Version"
        const val STREAM_TYPE = "application/x-ndjson"
        const val PICTURE_SOURCE_HEADER = "X-Notosaurus-Picture-Source"

        // The AI's routes: the first one called without a key starts the free trial (not reading
        // aloud, the voices, the free pictures, a report: they come after a lesson, or need none)
        val AI_ROUTES = setOf("extract", "revise", "fix-card", "explain", "rephrase", "figure", "check-figure", "picture", "card-picture", "plan-picture", "transcribe")

        // The relay's answers for a subscription past its end: ended, on hold, or the free trial over
        const val INVALID_KEY = "relay.invalid_key"
        val LAPSED = setOf("relay.subscription_ended", "relay.payment_pending", "relay.trial_ended")

        // A little slower than normal, for learners (the computer's "-10%")
        const val SPEECH_RATE = 0.9

        // Notosaurus's version (the root pyproject.toml's, as the app's): the relay may
        // refuse one too old for its API
        val CLIENT_VERSION: String = BuildConfig.VERSION_NAME

        private val JSON = "application/json".toMediaType()
        private val JPEG = "image/jpeg".toMediaType()
        private val AAC = "audio/aac".toMediaType()
        private const val MAX_CONTEXT = 8000 // relay_api.MAX_PROMPT

        // An extraction takes up to a minute or two: the AI reads every page. Silent at most
        // 3 minutes (a model stalled, then the next one: core's gemini.FIRST_PART_S twice)
        // before the relay says so: waited for a little longer, under Cloud Run's 5 minutes
        private val client = OkHttpClient.Builder()
            .connectTimeout(10, TimeUnit.SECONDS)
            .readTimeout(240, TimeUnit.SECONDS)
            .writeTimeout(60, TimeUnit.SECONDS)
            .build()
    }
}
