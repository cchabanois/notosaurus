package app.notosaurus

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.put
import okhttp3.Headers.Companion.headersOf
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.IOException
import java.util.concurrent.TimeUnit

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

    private suspend fun call(route: String, body: RequestBody?): JsonObject = withContext(Dispatchers.IO) {
        val request = Request.Builder().url("$base/v1/$route")
            .header("Authorization", "Bearer ${key.trim()}")
            .header(CLIENT_HEADER, CLIENT_VERSION)
            .apply { if (body != null) post(body) }
            .build()
        val response = try {
            client.newCall(request).execute()
        } catch (e: IOException) {
            throw RelayException("relay.unreachable", buildJsonObject { put("detail", e.message ?: "") })
        }
        response.use {
            val text = it.body.string()
            if (!it.isSuccessful) {
                val error = runCatching { json.decodeFromString<ApiError>(text) }.getOrNull()
                throw RelayException(error?.code ?: "relay.http_${it.code}", error?.params ?: JsonObject(emptyMap()))
            }
            json.parseToJsonElement(text).jsonObject
        }
    }

    companion object {
        const val CLIENT_HEADER = "X-Notosaurus-Version"

        // The relay's oldest client is a Notosaurus (PC) version for now: the app says
        // the one its API matches. To do: a version of its own (see README).
        const val CLIENT_VERSION = "1.1.0"

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
