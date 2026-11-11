package app.notosaurus

import io.ktor.http.ContentType
import io.ktor.http.HttpHeaders
import io.ktor.http.HttpStatusCode
import io.ktor.server.response.header
import io.ktor.server.response.respondBytes
import io.ktor.server.response.respondText
import io.ktor.server.routing.Route
import io.ktor.server.routing.get
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import java.io.File
import java.io.InputStream

/**
 * What was shared to the app (Android's "Share" to Notosaurus: photos, PDFs, a text), kept until
 * the page takes it (static/app-photos.js, takeShared): copied here at once, the grant to read
 * another app's files lasting only a while. `dir`: file-N (what was shared, in order), files.json
 * (their names and types), text.txt, skipped.json (what the page can't take: their names).
 * A new share replaces what the page hasn't taken.
 */
class Shared(private val dir: File) {
    /** One thing shared: its name, its type ("image/jpeg", "application/pdf", "text/plain"…), its bytes. */
    class Item(val name: String, val type: String?, val open: () -> InputStream?)

    /** Kept, replacing what was there: the photos and PDFs (at most MAX_BYTES each), a text file's
     * text added to `text`; anything else skipped, by name. */
    @Synchronized
    fun take(items: List<Item>, text: String?) {
        clear()
        dir.mkdirs()
        val files = mutableListOf<JsonObject>()
        val skipped = mutableListOf<String>()
        val texts = mutableListOf<String>()
        text?.trim()?.takeIf { it.isNotEmpty() }?.let(texts::add)
        for (item in items.take(MAX_ITEMS)) {
            val type = item.type?.lowercase().orEmpty()
            val kind = when {
                type.startsWith("image/") -> "image"
                type == PDF || item.name.lowercase().endsWith(".pdf") -> "pdf"
                type.startsWith("text/") -> "text"
                else -> null
            }
            if (kind == null) {
                skipped += item.name
                continue
            }
            val bytes = runCatching { item.open()?.use { it.readAtMost(MAX_BYTES) } }.getOrNull()
            when {
                bytes == null -> skipped += item.name // unreadable, or too large
                kind == "text" -> bytes.decodeToString().trim().takeIf { it.isNotEmpty() }?.let(texts::add)
                else -> {
                    val n = files.size + 1
                    File(dir, "file-$n").writeBytes(bytes)
                    files += buildJsonObject {
                        put("n", n)
                        put("name", item.name)
                        put("type", if (kind == "pdf") PDF else type)
                    }
                }
            }
        }
        File(dir, FILES).writeText(JsonArray(files).toString())
        File(dir, TEXT).writeText(texts.joinToString("\n\n").take(MAX_TEXT))
        File(dir, SKIPPED).writeText(JsonArray(skipped.map(::JsonPrimitive)).toString())
    }

    /** What the page may take: {files: [{n, name, type}], text, skipped: [names]}; empty when nothing waits. */
    @Synchronized
    fun get(): JsonObject {
        val files = File(dir, FILES).takeIf { it.isFile }?.let { json.parseToJsonElement(it.readText()) } ?: JsonArray(emptyList())
        val skipped = File(dir, SKIPPED).takeIf { it.isFile }?.let { json.parseToJsonElement(it.readText()) } ?: JsonArray(emptyList())
        return buildJsonObject {
            put("files", files)
            put("text", File(dir, TEXT).takeIf { it.isFile }?.readText().orEmpty())
            put("skipped", skipped)
        }
    }

    fun file(n: Int): File? = File(dir, "file-$n").takeIf { n >= 1 && it.isFile }

    @Synchronized
    fun clear() {
        dir.deleteRecursively()
    }

    companion object {
        const val PDF = "application/pdf"
        const val MAX_ITEMS = 30 // a lesson holds 10 pages: the page says which didn't fit
        const val MAX_BYTES = 50L * 1024 * 1024 // a school's PDF, a phone's photo (the page shrinks it)
        const val MAX_TEXT = 100_000 // characters: the page makes pages of it, 10 at most
        private const val FILES = "files.json"
        private const val TEXT = "text.txt"
        private const val SKIPPED = "skipped.json"

        /** The stream's bytes, null when it holds more than `max`. */
        internal fun InputStream.readAtMost(max: Long): ByteArray? {
            val out = java.io.ByteArrayOutputStream()
            val buffer = ByteArray(64 * 1024)
            while (true) {
                val read = read(buffer)
                if (read < 0) return out.toByteArray()
                out.write(buffer, 0, read)
                if (out.size() > max) return null
            }
        }
    }
}

internal fun Route.sharedRoutes(server: LocalServer) {
    with(server) {
        api("GET", "/api/shared") { shared.get() }
        get("/api/shared/{n}") {
            if (!allowed()) return@get
            val file = param("n").toIntOrNull()?.let(shared::file)
            if (file == null) call.respondText("", status = HttpStatusCode.NotFound)
            else {
                call.response.header(HttpHeaders.CacheControl, "no-store")
                call.respondBytes(file.readBytes(), ContentType.Application.OctetStream)
            }
        }
        api("DELETE", "/api/shared") {
            shared.clear()
            JsonObject(emptyMap())
        }
    }
}
