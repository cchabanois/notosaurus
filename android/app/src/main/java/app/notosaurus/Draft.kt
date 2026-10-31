package app.notosaurus

import io.ktor.http.ContentType
import io.ktor.http.HttpHeaders
import io.ktor.http.HttpStatusCode
import io.ktor.http.content.PartData
import io.ktor.http.content.forEachPart
import io.ktor.server.request.receiveMultipart
import io.ktor.server.response.header
import io.ktor.server.response.respondBytes
import io.ktor.server.response.respondText
import io.ktor.server.routing.Route
import io.ktor.server.routing.get
import io.ktor.utils.io.toByteArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.jsonObject
import java.io.File

/**
 * The lesson in progress, kept as the page changes it (static/app-draft.js), as the computer's
 * (app/draft.py): found again when the page opens again, after the settings, or Android having
 * closed the app meanwhile. `dir`: draft.json (what the page said of it: its prompt, the open
 * lesson, its photos' texts) and photo-N.jpg (its photos, in order).
 */
class Draft(private val dir: File) {
    /** What the page said, and how many photos it has; empty when there is none. */
    @Synchronized
    fun get(): JsonObject {
        val text = File(dir, DRAFT).takeIf { it.isFile }?.readText() ?: return JsonObject(emptyMap())
        val draft = runCatching { json.parseToJsonElement(text).jsonObject }.getOrNull() ?: return JsonObject(emptyMap())
        return JsonObject(draft + ("photos" to JsonPrimitive(photos().size)))
    }

    fun photo(n: Int): File? = File(dir, "photo-$n.jpg").takeIf { n >= 1 && it.isFile }

    /** `text`: the draft's JSON (an object); `photos`: all of them, replacing those kept (null: kept). */
    @Synchronized
    fun save(text: String, photos: List<ByteArray>?) {
        if (text.length > MAX_TEXT) throw BadRequest("draft.too_large")
        val draft = runCatching { json.parseToJsonElement(text).jsonObject }.getOrNull() ?: throw BadRequest("draft.invalid")
        if (photos != null && (photos.size > LocalServer.MAX_PHOTOS || photos.any { it.size > MAX_PHOTO_BYTES })) {
            throw BadRequest("draft.too_large")
        }
        dir.mkdirs()
        if (photos != null) {
            photos().forEach { it.delete() }
            photos.forEachIndexed { i, data -> File(dir, "photo-${i + 1}.jpg").writeBytes(data) }
        }
        val written = File(dir, "$DRAFT.tmp")
        written.writeText(draft.toString())
        written.renameTo(File(dir, DRAFT)) // whole or not at all
    }

    @Synchronized
    fun clear() {
        dir.deleteRecursively()
    }

    private fun photos() = dir.listFiles { f -> f.name.matches(Regex("photo-\\d+\\.jpg")) }.orEmpty().toList()

    companion object {
        private const val DRAFT = "draft.json"
        const val MAX_TEXT = 200_000 // a prompt and its photos' PDF texts
        const val MAX_PHOTO_BYTES = 10 * 1024 * 1024 // a photo as the page prepared it weighs a few hundred KB
    }
}

internal fun Route.draftRoutes(server: LocalServer) {
    with(server) {
        api("GET", "/api/draft") { draft.get() }
        get("/api/draft/photos/{n}") {
            if (!allowed()) return@get
            val photo = param("n").toIntOrNull()?.let(draft::photo)
            if (photo == null) call.respondText("", status = HttpStatusCode.NotFound)
            else {
                call.response.header(HttpHeaders.CacheControl, "no-store")
                call.respondBytes(photo.readBytes(), ContentType.Image.JPEG)
            }
        }
        // `photos`: all of them, when "photos_sent" (none: no photo); else those kept stay
        api("PUT", "/api/draft") {
            var text = ""
            var sent = false
            val photos = mutableListOf<ByteArray>()
            call.receiveMultipart(formFieldLimit = 20L * 1024 * 1024).forEachPart { part ->
                when (part) {
                    is PartData.FormItem -> when (part.name) {
                        "draft" -> text = part.value
                        "photos_sent" -> sent = part.value == "true"
                    }
                    is PartData.FileItem -> photos += part.provider().toByteArray()
                    else -> {}
                }
                part.dispose()
            }
            draft.save(text, photos.takeIf { sent })
            JsonObject(emptyMap())
        }
        api("DELETE", "/api/draft") {
            draft.clear()
            JsonObject(emptyMap())
        }
    }
}
