package app.notosaurus

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import okhttp3.Headers.Companion.headersOf
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.Response
import java.io.IOException
import java.util.concurrent.TimeUnit

/**
 * The relay's client: `baseUrl` (e.g. "http://192.168.1.10:8080", a relay run on
 * the computer) and the licence key.
 */
class Relay(baseUrl: String, private val key: String) {
    private val base = baseUrl.trimEnd('/')

    suspend fun account(): Account = call(Request.Builder().url("$base/v1/account").get())

    /** Cards from the photos (JPEG, as Photos.prepare makes them), in order. */
    suspend fun extract(request: ExtractRequest, photos: List<ByteArray>): ExtractResponse {
        val body = MultipartBody.Builder().setType(MultipartBody.FORM)
            .addPart(
                headersOf("Content-Disposition", "form-data; name=\"request\""),
                json.encodeToString(request).toRequestBody(JSON),
            )
        photos.forEachIndexed { i, data ->
            body.addFormDataPart("images", "page-${i + 1}.jpg", data.toRequestBody(JPEG))
        }
        return call(Request.Builder().url("$base/v1/extract").post(body.build()))
    }

    private suspend inline fun <reified T> call(request: Request.Builder): T = withContext(Dispatchers.IO) {
        val built = request
            .header("Authorization", "Bearer ${key.trim()}")
            .header(CLIENT_HEADER, CLIENT_VERSION)
            .build()
        val response = try {
            client.newCall(built).execute()
        } catch (e: IOException) {
            throw RelayException("relay.unreachable", buildJsonObject { put("detail", e.message ?: "") })
        }
        response.use { read(it) }
    }

    private inline fun <reified T> read(response: Response): T {
        val text = response.body.string()
        if (!response.isSuccessful) {
            val error = runCatching { json.decodeFromString<ApiError>(text) }.getOrNull()
            throw RelayException(error?.code ?: "relay.http_${response.code}", error?.params ?: JsonObject(emptyMap()))
        }
        return json.decodeFromString(text)
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
