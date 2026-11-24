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

    /** Every change to a lesson's file made under it, from its reading to its writing (update,
     * completed, regenerated, copy, create, setAnkiNotes, delete; Pictures' merges, the photos
     * turned): a save landing between another's reading and writing is never written over by it
     * (the page's correction lost to a picture's merge read before it). Short work only: files,
     * never a relay call. Reentrant (a block calling update). Reading alone needs none: a lesson's
     * file is replaced whole (write). */
    private val lock = Any()

    fun <T> locked(block: () -> T): T = synchronized(lock) { block() }

    fun list(): List<JsonObject> = (root.listFiles() ?: emptyArray())
        .mapNotNull { get(it.name) }
        .sortedByDescending { it.string("updated_at") }

    /** The lesson, with its pages as its folder has them: their count ("photo_count") and their
     * numbers ("pages", in order: a page missing leaves a gap), as the computer's lessons._read. */
    fun get(id: String): JsonObject? {
        val dir = folder(id) ?: return null
        val lesson = dir.resolve("lesson.json").takeIf { it.isFile }?.let { json.parseToJsonElement(it.readText()).jsonObject } ?: return null
        val pages = pageNumbers(dir)
        return JsonObject(lesson + mapOf("photo_count" to JsonPrimitive(pages.size), "pages" to JsonArray(pages.map(::JsonPrimitive))))
    }

    /** The lesson's pictures (drawn, or the user's photos), as the computer: images/. */
    fun images(id: String): File? = folder(id)?.resolve("images")

    fun photo(id: String, n: Int): File? = folder(id)?.resolve("page-$n.jpg")?.takeIf { it.isFile }

    /** The numbers of the lesson's pages there (page-N.jpg), in order: page 3 missing, [1, 2, 4…]. */
    fun pages(id: String): List<Int> = folder(id)?.let(::pageNumbers).orEmpty()

    /** The lesson's photos by their page number, in order; a page missing is not there (never
     * another in its place: a card's page is its number). */
    fun photos(id: String): Map<Int, ByteArray> = pages(id).mapNotNull { n -> photo(id, n)?.let { n to it.readBytes() } }.toMap()

    /** A new lesson from what the AI made: its own folder, named after the date and deck. */
    fun create(content: Map<String, JsonElement>, photos: List<ByteArray>): JsonObject = locked {
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
        get(id) ?: lesson // its pages, as read back
    }

    /** A copy for another child (its `deck`): photos, cards, pictures; new card ids (other
     * notes in AnkiDroid, with their own history); not sent yet, no AI calls (nothing asked
     * of the AI), as the computer's lessons.copy. Null: no such lesson. */
    fun copy(id: String, deck: String, child: String): JsonObject? = locked {
        val source = folder(id) ?: return@locked null
        val lesson = get(id) ?: return@locked null
        val copyId = newId(deck)
        val dir = root.resolve(copyId)
        source.copyRecursively(dir) // photos, pictures
        val cards = lesson.cards().map { card ->
            val fresh = UUID.randomUUID().toString().replace("-", "").take(12)
            val picture = card.string("picture")
            val file = dir.resolve("images").resolve(picture)
            if (!PICTURE.matches(picture) || !file.isFile) return@map card.with("id" to JsonPrimitive(fresh), "picture" to JsonPrimitive(""))
            val renamed = picture.replaceFirst(Regex("^picture-[a-z0-9]+-"), "picture-$fresh-").also { moved(file, file.resolveSibling(it)) }
            val copied = card.with("id" to JsonPrimitive(fresh), "picture" to JsonPrimitive(renamed))
            val origin = card["picture_source"] as? JsonObject
            val files = (origin?.get("sources") as? JsonArray).orEmpty().map { (it as? JsonObject)?.string("file").orEmpty() }
            if (origin == null || files.isEmpty()) return@map copied
            // A figure's sources, named after it too (as the computer's lessons.copy); the copied
            // ones, under its old name, gone
            val kept = Pictures.keptSources(source.resolve("images"), origin)
            files.filter { Pictures.SOURCE_NAME.matches(it) }.forEach { dir.resolve("images").resolve(it).delete() }
            copied.with("picture_source" to origin.with("sources" to Pictures.keepSources(dir.resolve("images"), renamed, kept)))
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
        get(copyId) ?: copy
    }

    /** A new lesson's folder name: the date and its deck, another if taken. */
    private fun newId(deck: String): String {
        val base = "${LocalDate.now()}-${slug(deck).ifBlank { "lesson" }}"
        return generateSequence(base) { "$base-${UUID.randomUUID().toString().take(4)}" }.first { !root.resolve(it).exists() }
    }

    /** Generated again in its place: new cards and photos; the options set in the review
     * stay, the prompt's (or the AI's) are added (reverse, typing, dictation), as the computer's. */
    fun regenerated(id: String, content: Map<String, JsonElement>, photos: List<ByteArray>): JsonObject? = locked {
        val lesson = get(id) ?: return@locked null
        val dir = folder(id) ?: return@locked null
        dir.listFiles { f -> f.name.matches(PHOTO) }?.forEach { it.delete() }
        photos.forEachIndexed { i, data -> dir.resolve("page-${i + 1}.jpg").writeBytes(data) }
        fun either(key: String) = JsonPrimitive(
            content[key]?.jsonPrimitive?.booleanOrNull == true || lesson[key]?.jsonPrimitive?.booleanOrNull == true,
        )
        val updated = JsonObject(
            lesson + content + mapOf(
                "cards" to withIds(keptIds(content["cards"], lesson["cards"])), // the same cards: their ids, their notes
                "reverse" to either("reverse"),
                "typing" to either("typing"),
                "dictation" to either("dictation"),
                "dictation_only" to either("dictation_only"),
                "child" to JsonPrimitive(content["child"]?.jsonPrimitive?.contentOrNull?.ifEmpty { null } ?: lesson.string("child")), // still for its child
                "photo_count" to JsonPrimitive(photos.size),
                "updated_at" to JsonPrimitive(changedAt(lesson)),
            ),
        )
        write(updated)
        get(id) // its new pages, as read back
    }

    /** Its next pages added (/complete): their photos after its own, their cards after its
     * cards (untouched: their ids, so their notes in AnkiDroid, stay), as app/lessons.py's
     * completed. `content`'s masks and frames count pages from the first new photo; numbered here
     * from the lesson's next page (nextPage: a number never used in it, so no file written over). */
    fun completed(id: String, content: Map<String, JsonElement>, photos: List<ByteArray>): JsonObject? = locked {
        val lesson = get(id) ?: return@locked null
        val dir = folder(id) ?: return@locked null
        val before = nextPage(pageNumbers(dir), lesson) - 1
        photos.forEachIndexed { i, data -> dir.resolve("page-${before + i + 1}.jpg").writeBytes(data) }
        fun shifted(item: JsonObject, key: String): JsonObject {
            val mask = item[key] as? JsonObject ?: return item
            val page = mask["page"]?.jsonPrimitive?.intOrNull ?: return item
            return JsonObject(item + (key to JsonObject(mask + ("page" to JsonPrimitive(page + before)))))
        }
        // Their page too (0: unknown, stays so)
        fun paged(card: JsonObject): JsonObject {
            val page = card["page"]?.jsonPrimitive?.intOrNull ?: 0
            return if (page > 0) card.with("page" to JsonPrimitive(page + before)) else card
        }
        val cards = content["cards"]?.jsonArray.orEmpty().map { paged(shifted(it.jsonObject, "mask")) }
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
                "photo_count" to JsonPrimitive(pageNumbers(dir).size),
                "updated_at" to JsonPrimitive(changedAt(lesson)),
            ),
        )
        write(updated)
        get(id) // its new pages, as read back
    }

    /** Its notes in AnkiDroid after a send, by card id (not a content change). */
    fun setAnkiNotes(id: String, notes: Map<String, Long>): Unit = locked {
        val lesson = get(id) ?: return@locked
        write(JsonObject(lesson + ("anki_notes" to JsonObject(notes.mapValues { JsonPrimitive(it.value) }))))
    }

    /** The page's changes (LessonIn): null fields leave the lesson's as they are. */
    fun update(id: String, changes: JsonObject, exported: Boolean = false): JsonObject? = locked {
        val lesson = get(id) ?: return@locked null
        val kept = changes.filterKeys { it in EDITABLE }.filterValues { it !is JsonNull }
        val updated = JsonObject(
            lesson + kept + buildMap {
                if ("cards" in kept) put("cards", withIds(kept["cards"]))
                val now = if (exported) now() else changedAt(lesson)
                put("updated_at", JsonPrimitive(now))
                if (exported) put("exported_at", JsonPrimitive(now))
            },
        )
        write(updated)
        updated
    }

    fun delete(id: String): Boolean = locked { folder(id)?.deleteRecursively() ?: false }

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
        tmp.writeText(JsonObject(lesson - "pages").toString()) // its folder's (get), not kept
        moved(tmp, dir.resolve("lesson.json")) // never half a file
    }

    /** The lesson's sounds' folder (Speech: its mp3s and what they say); null: no such lesson. */
    fun audio(id: String): File? = folder(id)?.resolve("audio")

    private fun folder(id: String): File? = root.resolve(id).takeIf { NAME.matches(id) && it.isDirectory }

    companion object {
        private val NAME = Regex("^[a-z0-9][a-z0-9-]*$") // our folder names only: no "../"
        private val PHOTO = Regex("^page-\\d+\\.jpg$")
        private val PAGE = Regex("^page-([1-9][0-9]*)\\.jpg$")

        /** The numbers of the pages in a lesson's folder (page-N.jpg), in order. */
        private fun pageNumbers(dir: File): List<Int> =
            dir.list().orEmpty().mapNotNull { PAGE.matchEntire(it)?.groupValues?.get(1)?.toIntOrNull() }.sorted()

        /** The number of a page added to a lesson: after the highest one used anywhere in it, its
         * pages' files (`files`, their numbers), its cards' pages, their masks', its frames' and its
         * pages' texts (one per page): a page missing (its file removed) is never numbered again, so
         * a card that came from it never points at another, and no page is written over. As the
         * computer's lessons.next_page (core/shared-cases.json). */
        fun nextPage(files: List<Int>, lesson: JsonObject): Int {
            fun page(item: JsonObject?) = (item?.get("page") as? JsonPrimitive)?.intOrNull ?: 0
            val cards = (lesson["cards"] as? JsonArray).orEmpty().mapNotNull { it as? JsonObject }
            val used = files + cards.map(::page) + cards.map { page(it["mask"] as? JsonObject) } +
                (lesson["frames"] as? JsonArray).orEmpty().map { page(it as? JsonObject) } +
                (lesson["page_texts"] as? JsonArray).orEmpty().size
            return (used.maxOrNull() ?: 0) + 1
        }
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

        /** Now, as a change's date: after its last send, even in the same second (the dates are
         * to the second): the page says "Update in Anki" for a lesson changed since it was sent. */
        fun changedAt(lesson: JsonObject, now: LocalDateTime = LocalDateTime.now().truncatedTo(ChronoUnit.SECONDS)): String {
            val sent = lesson.string("exported_at").takeIf { it.isNotEmpty() }?.let { runCatching { LocalDateTime.parse(it) }.getOrNull() }
            return (if (sent != null && !now.isAfter(sent)) sent.plusSeconds(1) else now).toString()
        }

        /** Cards from the AI, or added in the review, get their stable id (lessons.with_ids). */
        fun withIds(cards: JsonElement?): JsonArray = JsonArray(
            (cards as? JsonArray ?: JsonArray(emptyList())).map { card ->
                val c = card.jsonObject
                if (c.string("id").isNotEmpty()) c
                else JsonObject(c + ("id" to JsonPrimitive(UUID.randomUUID().toString().replace("-", "").take(12))))
            },
        )

        // What two texts of a card may differ by and still be the same (core's cards.same_text): never
        // the accents, the punctuation inside, the digits; nothing fuzzy
        private val SPACES = Regex("[ \\t\\n\\r\\u000B\\u000C\\u00A0\\u2007\\u202F]+")
        private val GUILLEMETS = Regex("(?<=\\u00AB)[ \\u00A0\\u202F]+|[ \\u00A0\\u202F]+(?=\\u00BB)")
        private val QUOTES = mapOf(
            '\u2019' to '\'', '\u2018' to '\'', '\u201B' to '\'', '\u02BC' to '\'',
            '\u201C' to '"', '\u201D' to '"', '\u201E' to '"', '\u00AB' to '"', '\u00BB' to '"',
        )
        private const val FINAL = ".!?\u2026:;"

        /** A card's text as sameText compares it (core's cards.text_key): NFC, lower case, typographic
         * quotes made straight (« oui » as "oui"), spaces (non-breaking too) as one, one final
         * . ! ? … : ; taken off. The blank alone ("…") gives "". */
        fun textKey(text: String): String {
            val lower = GUILLEMETS.replace(Normalizer.normalize(text, Normalizer.Form.NFC).lowercase(java.util.Locale.ROOT), "")
            val plain = SPACES.replace(lower.map { QUOTES[it] ?: it }.joinToString(""), " ").trim()
            return if (plain.isNotEmpty() && plain.last() in FINAL) plain.dropLast(1).trimEnd() else plain
        }

        fun sameText(a: String, b: String): Boolean = textKey(a) == textKey(b)

        /** A lesson made again in its place (core's cards.kept_ids): each new card with the id of
         * the lesson's card it is, so its note and history in AnkiDroid; none, a new card. The same
         * front and back, else the same front, in the same part of the deck, each old card given
         * once; never by a front empty or the blank alone (every dictation without a sentence). Else
         * its front written otherwise (ID-02), the same back where it tells one card: not empty, the
         * lesson's only one, no choices on either side. A new card with an id keeps it; an old card
         * whose id one of them has goes to no other. */
        fun keptIds(made: JsonElement?, before: JsonElement?): JsonArray {
            val taken = (made as? JsonArray).orEmpty().map { it.jsonObject.string("id") }.filter { it.isNotEmpty() }.toSet()
            val left = (before as? JsonArray).orEmpty().map { it.jsonObject }
                .filter { it.string("id").isNotEmpty() && it.string("id") !in taken }.toMutableList()
            val backs = (before as? JsonArray).orEmpty().groupingBy { textKey(it.jsonObject.string("back")) }.eachCount()
            fun choices(c: JsonObject) = (c["choices"] as? JsonArray).orEmpty().any { it.jsonPrimitive.content.isNotBlank() }
            // Its front written otherwise (ID-02): the same back where it tells one card, no choices
            fun byBack(a: JsonObject, b: JsonObject): Boolean {
                val key = textKey(a.string("back"))
                return key.isNotEmpty() && key == textKey(b.string("back")) && backs[key] == 1 && !choices(a) && !choices(b) &&
                    sameText(a.string("subdeck"), b.string("subdeck"))
            }
            fun same(a: JsonObject, b: JsonObject, back: Boolean): Boolean =
                sameText(a.string("subdeck"), b.string("subdeck")) && sameText(a.string("front"), b.string("front")) &&
                    (if (back) sameText(a.string("back"), b.string("back")) else textKey(a.string("front")).isNotEmpty()) // "…" too: ""
            return JsonArray(
                (made as? JsonArray).orEmpty().map { card ->
                    val c = card.jsonObject
                    if (c.string("id").isNotEmpty()) return@map c
                    val match = left.firstOrNull { same(c, it, back = true) } ?: left.firstOrNull { same(c, it, back = false) }
                        ?: left.firstOrNull { byBack(c, it) }
                    if (match == null) c else JsonObject(c + ("id" to JsonPrimitive(match.string("id")))).also { left.remove(match) }
                },
            )
        }

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

/** `from` moved to `to`, replacing it: renamed, else (a rename refused) copied then removed;
 * neither: IOException, never the old file left as if it were the new one. */
internal fun moved(from: java.io.File, to: java.io.File) {
    if (from.renameTo(to)) return
    from.copyTo(to, overwrite = true)
    if (!from.delete()) from.deleteOnExit()
}
