package app.notosaurus

import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.int
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import java.io.File
import java.text.Normalizer
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.temporal.ChronoUnit
import java.util.UUID

/**
 * The lessons, on the phone, as the computer keeps them (app/lessons.py): one folder
 * each, lesson.json and page-N.jpg. Kept as JSON objects, in the format the page
 * reads and writes (app/models.py, Lesson).
 */
class Lessons(private val root: File) {

    fun list(): List<JsonObject> = (root.listFiles() ?: emptyArray())
        .mapNotNull { get(it.name) }
        .sortedByDescending { it.string("updated_at") }

    fun get(id: String): JsonObject? =
        folder(id)?.resolve("lesson.json")?.takeIf { it.isFile }?.let { json.parseToJsonElement(it.readText()).jsonObject }

    /** The lesson's pictures (drawn, or the user's photos), as the computer: images/. */
    fun images(id: String): File? = folder(id)?.resolve("images")

    fun photo(id: String, n: Int): File? = folder(id)?.resolve("page-$n.jpg")?.takeIf { it.isFile }

    fun photos(id: String): List<ByteArray> = (1..(get(id)?.get("photo_count")?.jsonPrimitive?.int ?: 0))
        .mapNotNull { photo(id, it)?.readBytes() }

    /** A new lesson from what the AI made: its own folder, named after the date and deck. */
    fun create(content: Map<String, JsonElement>, photos: List<ByteArray>): JsonObject {
        val deck = content["deck"]?.jsonPrimitive?.content ?: ""
        val base = "${LocalDate.now()}-${slug(deck).ifBlank { "lesson" }}"
        val id = generateSequence(base) { "$base-${UUID.randomUUID().toString().take(4)}" }.first { !root.resolve(it).exists() }
        val dir = root.resolve(id).apply { mkdirs() }
        photos.forEachIndexed { i, data -> dir.resolve("page-${i + 1}.jpg").writeBytes(data) }
        val now = now()
        val lesson = JsonObject(
            DEFAULTS + content + mapOf(
                "id" to JsonPrimitive(id),
                "cards" to withIds(content["cards"]),
                "photo_count" to JsonPrimitive(photos.size),
                "created_at" to JsonPrimitive(now),
                "updated_at" to JsonPrimitive(now),
            ),
        )
        write(lesson)
        return lesson
    }

    /** Generated again in its place: new cards and photos; the options set in the review
     * stay (reverse), the prompt's are added (typing, dictation), as app/main.py does. */
    fun regenerated(id: String, content: Map<String, JsonElement>, photos: List<ByteArray>): JsonObject? {
        val lesson = get(id) ?: return null
        val dir = folder(id) ?: return null
        dir.listFiles { f -> f.name.matches(PHOTO) }?.forEach { it.delete() }
        photos.forEachIndexed { i, data -> dir.resolve("page-${i + 1}.jpg").writeBytes(data) }
        fun either(key: String) = JsonPrimitive(
            content[key]?.jsonPrimitive?.booleanOrNull == true || lesson[key]?.jsonPrimitive?.booleanOrNull == true,
        )
        val updated = JsonObject(
            lesson + content + mapOf(
                "cards" to withIds(content["cards"]),
                "typing" to either("typing"),
                "dictation" to either("dictation"),
                "photo_count" to JsonPrimitive(photos.size),
                "updated_at" to JsonPrimitive(now()),
            ),
        )
        write(updated)
        return updated
    }

    /** The page's changes (LessonIn): null fields leave the lesson's as they are. */
    fun update(id: String, changes: JsonObject, exported: Boolean = false): JsonObject? {
        val lesson = get(id) ?: return null
        val kept = changes.filterKeys { it in EDITABLE }.filterValues { it !is JsonNull }
        val updated = JsonObject(
            lesson + kept + buildMap {
                if ("cards" in kept) put("cards", withIds(kept["cards"]))
                put("updated_at", JsonPrimitive(now()))
                if (exported) put("exported_at", JsonPrimitive(now()))
            },
        )
        write(updated)
        return updated
    }

    fun delete(id: String): Boolean = folder(id)?.deleteRecursively() ?: false

    /** Every lesson deleted; returns how many there were. */
    fun deleteAll(): Int = list().count { delete(it.string("id")) }

    /** What the lessons take on the phone (photos mostly). */
    fun bytes(): Long = root.walkTopDown().filter { it.isFile }.sumOf { it.length() }

    /** For the lessons list: everything but the cards, and how many there are. */
    fun summary(lesson: JsonObject): JsonObject = JsonObject(
        lesson.filterKeys { it != "cards" } + ("card_count" to JsonPrimitive(lesson["cards"]?.jsonArray?.size ?: 0)),
    )

    private fun write(lesson: JsonObject) {
        val dir = root.resolve(lesson.string("id"))
        val tmp = dir.resolve("lesson.json.tmp")
        tmp.writeText(lesson.toString())
        tmp.renameTo(dir.resolve("lesson.json")) // never half a file
    }

    private fun folder(id: String): File? = root.resolve(id).takeIf { NAME.matches(id) && it.isDirectory }

    companion object {
        private val NAME = Regex("^[a-z0-9][a-z0-9-]*$") // our folder names only: no "../"
        private val PHOTO = Regex("^page-\\d+\\.jpg$")
        private val EDITABLE = setOf(
            "deck", "cards", "voice", "reverse", "typing", "dictation", "shared", "frames", "prompt", "choice",
        )
        private val DEFAULTS = mapOf(
            "voice" to JsonPrimitive(""), "reverse" to JsonPrimitive(false), "typing" to JsonPrimitive(false),
            "dictation" to JsonPrimitive(false), "owner" to JsonPrimitive(""), "shared" to JsonPrimitive(false),
            "frames" to JsonArray(emptyList()), "ai_calls" to JsonArray(emptyList()), "choice" to JsonPrimitive(""),
            "page_texts" to JsonArray(emptyList()), "exported_at" to JsonNull,
        )

        fun now(): String = LocalDateTime.now().truncatedTo(ChronoUnit.SECONDS).toString()

        /** Cards from the AI, or added in the review, get their stable id (lessons.with_ids). */
        fun withIds(cards: JsonElement?): JsonArray = JsonArray(
            (cards as? JsonArray ?: JsonArray(emptyList())).map { card ->
                val c = card.jsonObject
                if (c.string("id").isNotEmpty()) c
                else JsonObject(c + ("id" to JsonPrimitive(UUID.randomUUID().toString().replace("-", "").take(12))))
            },
        )

        fun slug(text: String): String = Normalizer.normalize(text, Normalizer.Form.NFKD)
            .replace(Regex("\\p{M}"), "").lowercase().replace(Regex("[^a-z0-9]+"), "-").trim('-').take(40).trimEnd('-')
    }
}

fun JsonObject.string(key: String): String = (this[key] as? JsonPrimitive)?.takeIf { it.isString }?.content ?: ""

/** The object with these fields changed (or added). */
fun JsonObject.with(vararg changes: Pair<String, JsonElement>): JsonObject = JsonObject(this + changes)

/** A lesson's cards, to change. */
fun JsonObject.cards(): MutableList<JsonObject> = (this["cards"] as? JsonArray)?.map { it.jsonObject }.orEmpty().toMutableList()

/** A value as text: a string's content, else its JSON (an id may be either). */
fun JsonElement.plain(): String = (this as? JsonPrimitive)?.content ?: toString()
