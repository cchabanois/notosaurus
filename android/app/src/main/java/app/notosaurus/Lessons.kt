package app.notosaurus

import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.int
import kotlinx.serialization.json.intOrNull
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
        val id = newId(content["deck"]?.jsonPrimitive?.content ?: "")
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

    /** A copy for another child (its `deck`): photos, cards, pictures; new card ids (other
     * notes in AnkiDroid, with their own history); not sent yet, no AI calls (nothing asked
     * of the AI), as the computer's lessons.copy. Null: no such lesson. */
    fun copy(id: String, deck: String, child: String): JsonObject? {
        val source = folder(id) ?: return null
        val lesson = get(id) ?: return null
        val copyId = newId(deck)
        val dir = root.resolve(copyId)
        source.copyRecursively(dir) // photos, pictures
        val cards = lesson.cards().map { card ->
            val fresh = UUID.randomUUID().toString().replace("-", "").take(12)
            val picture = card.string("picture")
            val file = dir.resolve("images").resolve(picture)
            val renamed = if (PICTURE.matches(picture) && file.isFile) {
                picture.replaceFirst(Regex("^picture-[a-z0-9]+-"), "picture-$fresh-").also { file.renameTo(file.resolveSibling(it)) }
            } else ""
            card.with("id" to JsonPrimitive(fresh), "picture" to JsonPrimitive(renamed))
        }
        val now = now()
        val copy = JsonObject(
            lesson - "anki_notes" + mapOf(
                "id" to JsonPrimitive(copyId), "deck" to JsonPrimitive(deck), "child" to JsonPrimitive(child),
                "shared" to JsonPrimitive(false), "cards" to JsonArray(cards), "ai_calls" to JsonArray(emptyList()),
                "created_at" to JsonPrimitive(now), "updated_at" to JsonPrimitive(now), "exported_at" to JsonNull,
            ),
        )
        write(copy)
        return copy
    }

    /** A new lesson's folder name: the date and its deck, another if taken. */
    private fun newId(deck: String): String {
        val base = "${LocalDate.now()}-${slug(deck).ifBlank { "lesson" }}"
        return generateSequence(base) { "$base-${UUID.randomUUID().toString().take(4)}" }.first { !root.resolve(it).exists() }
    }

    /** Generated again in its place: new cards and photos; the options set in the review
     * stay, the prompt's (or the AI's) are added (reverse, typing, dictation), as the computer's. */
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
                "reverse" to either("reverse"),
                "typing" to either("typing"),
                "dictation" to either("dictation"),
                "dictation_only" to either("dictation_only"),
                "child" to JsonPrimitive(content["child"]?.jsonPrimitive?.contentOrNull?.ifEmpty { null } ?: lesson.string("child")), // still for its child
                "photo_count" to JsonPrimitive(photos.size),
                "updated_at" to JsonPrimitive(now()),
            ),
        )
        write(updated)
        return updated
    }

    /** Its next pages added (/complete): their photos after its own, their cards after its
     * cards (untouched: their ids, so their notes in AnkiDroid, stay), as app/lessons.py's
     * completed. `content`'s masks and frames count pages from the first new photo. */
    fun completed(id: String, content: Map<String, JsonElement>, photos: List<ByteArray>): JsonObject? {
        val lesson = get(id) ?: return null
        val dir = folder(id) ?: return null
        val before = lesson["photo_count"]?.jsonPrimitive?.intOrNull ?: 0
        photos.forEachIndexed { i, data -> dir.resolve("page-${before + i + 1}.jpg").writeBytes(data) }
        fun shifted(item: JsonObject, key: String): JsonObject {
            val mask = item[key] as? JsonObject ?: return item
            val page = mask["page"]?.jsonPrimitive?.intOrNull ?: return item
            return JsonObject(item + (key to JsonObject(mask + ("page" to JsonPrimitive(page + before)))))
        }
        val cards = content["cards"]?.jsonArray.orEmpty().map { shifted(it.jsonObject, "mask") }
        val frames = (content["frames"] as? JsonArray).orEmpty().map { f ->
            val page = f.jsonObject["page"]?.jsonPrimitive?.intOrNull ?: 0
            JsonObject(f.jsonObject + ("page" to JsonPrimitive(page + before)))
        }
        val texts = content["page_texts"]?.jsonArray.orEmpty()
        val oldTexts = lesson["page_texts"]?.jsonArray.orEmpty()
        val pageTexts = if (texts.none { it.jsonPrimitive.content.isNotEmpty() }) oldTexts
        else oldTexts + List(maxOf(0, before - oldTexts.size)) { JsonPrimitive("") } + texts
        val updated = JsonObject(
            lesson + mapOf(
                "cards" to withIds(JsonArray(lesson["cards"]?.jsonArray.orEmpty() + cards)),
                "frames" to JsonArray((lesson["frames"] as? JsonArray).orEmpty() + frames),
                "page_texts" to JsonArray(pageTexts),
                "photo_count" to JsonPrimitive(before + photos.size),
                "updated_at" to JsonPrimitive(now()),
            ),
        )
        write(updated)
        return updated
    }

    /** Its notes in AnkiDroid after a send, by card id (not a content change). */
    fun setAnkiNotes(id: String, notes: Map<String, Long>) {
        val lesson = get(id) ?: return
        write(JsonObject(lesson + ("anki_notes" to JsonObject(notes.mapValues { JsonPrimitive(it.value) }))))
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

    /** The lesson's sounds' folder (Speech: its mp3s and what they say); null: no such lesson. */
    fun audio(id: String): File? = folder(id)?.resolve("audio")

    private fun folder(id: String): File? = root.resolve(id).takeIf { NAME.matches(id) && it.isDirectory }

    companion object {
        private val NAME = Regex("^[a-z0-9][a-z0-9-]*$") // our folder names only: no "../"
        private val PHOTO = Regex("^page-\\d+\\.jpg$")
        private val PICTURE = Regex("""^picture-[a-z0-9]+-[a-f0-9]{8}\.(jpg|svg)$""") // Pictures.NAME
        private val EDITABLE = setOf(
            "deck", "cards", "voice", "rate", "reverse", "typing", "dictation", "dictation_only", "shared", "frames", "prompt", "choice",
        )
        private val DEFAULTS = mapOf(
            "voice" to JsonPrimitive(""), "rate" to JsonPrimitive(""), "reverse" to JsonPrimitive(false), "typing" to JsonPrimitive(false),
            "dictation" to JsonPrimitive(false), "dictation_only" to JsonPrimitive(false), "owner" to JsonPrimitive(""),
            "child" to JsonPrimitive(""), "shared" to JsonPrimitive(false),
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
