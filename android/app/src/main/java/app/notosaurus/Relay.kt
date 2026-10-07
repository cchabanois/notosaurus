package app.notosaurus

import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
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
class Relay(baseUrl: String, private val key: String) {
    private val base = baseUrl.trimEnd('/')

    suspend fun account(): Account = json.decodeFromJsonElement(Account.serializer(), call("account", null))

    /** A route with photos (extract, revise): the JSON request, then the photos (JPEG). */
    suspend fun withPhotos(route: String, request: JsonObject, photos: List<ByteArray>): JsonObject {
        val body = MultipartBody.Builder().setType(MultipartBody.FORM)
            .addPart(headersOf("Content-Disposition", "form-data; name=\"request\""), request.toString().toRequestBody(JSON))
        photos.forEachIndexed { i, data ->
            body.addFormDataPart("images", "page-${i + 1}.jpg", data.toRequestBody(JPEG))
        }
        return call(route, body.build())
    }

    /** A JSON route (explain, figure). */
    suspend fun post(route: String, request: JsonObject): JsonObject = call(route, request.toString().toRequestBody(JSON))

    private suspend fun call(route: String, body: RequestBody?): JsonObject {
        val request = Request.Builder().url("$base/v1/$route")
            .header("Authorization", "Bearer ${key.trim()}")
            .header(CLIENT_HEADER, CLIENT_VERSION)
            .apply { if (body != null) post(body) }
            .build()
        val response = try {
            client.newCall(request).await()
        } catch (e: IOException) {
            throw RelayException("relay.unreachable", buildJsonObject { put("detail", e.message ?: "") })
        }
        return response.use {
            val text = it.body.string()
            if (!it.isSuccessful) {
                val error = runCatching { json.decodeFromString<ApiError>(text) }.getOrNull()
                throw RelayException(error?.code ?: "relay.http_${it.code}", error?.params ?: JsonObject(emptyMap()))
            }
            json.parseToJsonElement(text).jsonObject
        }
    }

    /** The call's answer; cancelled with the coroutine ("Cancel" on the page): the
     * request stops, the relay stops the AI. */
    private suspend fun Call.await(): Response = suspendCancellableCoroutine { waiting ->
        waiting.invokeOnCancellation { cancel() }
        enqueue(object : Callback {
            override fun onFailure(call: Call, e: IOException) = waiting.resumeWithException(e)
            override fun onResponse(call: Call, response: Response) =
                waiting.resume(response) { _, _, _ -> response.close() }
        })
    }

    companion object {
        const val CLIENT_HEADER = "X-Notosaurus-Version"

        // Notosaurus's version (the root pyproject.toml's, as the app's): the relay may
        // refuse one too old for its API
        val CLIENT_VERSION: String = BuildConfig.VERSION_NAME

        private val JSON = "application/json".toMediaType()
        private val JPEG = "image/jpeg".toMediaType()

        // An extraction takes up to a minute or two: the AI reads every page
        private val client = OkHttpClient.Builder()
            .connectTimeout(10, TimeUnit.SECONDS)
            .readTimeout(180, TimeUnit.SECONDS)
            .writeTimeout(60, TimeUnit.SECONDS)
            .build()
    }
}
