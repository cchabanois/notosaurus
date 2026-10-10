package app.notosaurus

import kotlinx.coroutines.CancellationException
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
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException

/**
 * The relay's client: `baseUrl` (e.g. "http://192.168.1.10:8080", a relay run on
 * the computer) and the licence key. Requests and answers as JSON objects: the
 * cards go through as the page has them (every field, ids included).
 */
/** Told each card as soon as the AI has written it, or null: start again (another model). */
typealias OnCard = suspend (JsonObject?) -> Unit

class Relay(baseUrl: String, private val key: String) {
    private val base = baseUrl.trimEnd('/')

    suspend fun account(): Account = json.decodeFromJsonElement(Account.serializer(), call("account", null))

    /** A route with photos (extract, revise): the JSON request, then the photos (JPEG). */
    suspend fun withPhotos(route: String, request: JsonObject, photos: List<ByteArray>): JsonObject =
        call(route, multipart(request, photos))

    /**
     * /v1/extract as the AI writes (STREAM_TYPE, relay_api.ExtractLine): each card told
     * to `onCard` as it comes (null: start again), then the answer. A relay answering
     * all at once (an older one): its answer. Cancelled, the request stops: so does the AI.
     */
    suspend fun extract(request: JsonObject, photos: List<ByteArray>, onCard: OnCard): JsonObject {
        return open("extract", multipart(request, photos), stream = true).use { answer(it, onCard) }
    }

    private suspend fun answer(response: Response, onCard: OnCard): JsonObject {
        if (response.header("Content-Type")?.startsWith(STREAM_TYPE) != true) {
            return json.parseToJsonElement(response.body.string()).jsonObject
        }
        val source = response.body.source()
        while (true) {
            val line = withContext(Dispatchers.IO) { source.readUtf8Line() }
                ?: throw RelayException("relay.unreachable", buildJsonObject { put("detail", "cut") })
            if (line.isBlank()) continue
            val item = json.parseToJsonElement(line).jsonObject
            item["result"]?.let { return it.jsonObject }
            item["error"]?.jsonObject?.let {
                throw RelayException(it.string("code"), it["params"]?.jsonObject ?: JsonObject(emptyMap()))
            }
            onCard(item["card"]?.jsonObject)
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

    /** A card's picture (/v1/picture): the JPEG, card size. `fresh`: drawn again. */
    suspend fun picture(subject: String, fresh: Boolean): ByteArray {
        val request = buildJsonObject {
            put("subject", subject)
            put("fresh", fresh)
        }
        return open("picture", request.toString().toRequestBody(JSON)).use { it.body.bytes() }
    }

    /** Free pictures of a subject to choose from (/v1/pictures/search): {"results": [stock.Found…]}. */
    suspend fun searchPictures(subject: String): JsonObject = post("pictures/search", buildJsonObject { put("subject", subject) })

    /** One of the pictures found (/v1/pictures/found): the JPEG, card size. */
    suspend fun foundPicture(source: String, id: String): ByteArray {
        val request = buildJsonObject {
            put("source", source)
            put("id", id)
        }
        return open("pictures/found", request.toString().toRequestBody(JSON)).use { it.body.bytes() }
    }

    /** A JSON route (explain, figure). */
    suspend fun post(route: String, request: JsonObject): JsonObject = call(route, request.toString().toRequestBody(JSON))

    private suspend fun call(route: String, body: RequestBody?): JsonObject =
        open(route, body).use { json.parseToJsonElement(it.body.string()).jsonObject }

    /** The relay's answer, when it is one (its errors thrown); `stream`: asked as it comes. */
    private suspend fun open(route: String, body: RequestBody?, stream: Boolean = false): Response {
        val request = Request.Builder().url("$base/v1/$route")
            .header("Authorization", "Bearer ${key.trim()}")
            .header(CLIENT_HEADER, CLIENT_VERSION)
            .apply { if (stream) header("Accept", STREAM_TYPE) }
            .apply { if (body != null) post(body) }
            .build()
        val response = try {
            client.newCall(request).await()
        } catch (e: IOException) {
            throw RelayException("relay.unreachable", buildJsonObject { put("detail", e.message ?: "") })
        }
        if (!response.isSuccessful) {
            val text = response.use { it.body.string() }
            val error = runCatching { json.decodeFromString<ApiError>(text) }.getOrNull()
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

    companion object {
        const val CLIENT_HEADER = "X-Notosaurus-Version"
        const val STREAM_TYPE = "application/x-ndjson"

        // A little slower than normal, for learners (the computer's "-10%")
        const val SPEECH_RATE = 0.9

        // Notosaurus's version (the root pyproject.toml's, as the app's): the relay may
        // refuse one too old for its API
        val CLIENT_VERSION: String = BuildConfig.VERSION_NAME

        private val JSON = "application/json".toMediaType()
        private val JPEG = "image/jpeg".toMediaType()
        private val AAC = "audio/aac".toMediaType()

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
