package app.notosaurus

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.builtins.ListSerializer
import kotlinx.serialization.builtins.MapSerializer
import kotlinx.serialization.builtins.nullable
import kotlinx.serialization.builtins.serializer
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.longOrNull
import kotlinx.serialization.json.put
import java.time.Instant

/** A lesson in a test: whole (cards null) or some of its cards. */
@Serializable
data class ExamLesson(val lesson: String, val cards: List<String>? = null)

/** A test to prepare (as the computer's app/exams.py): a name, a date, the lessons to
 * revise for it; its tag on their notes in AnkiDroid, `Exam::<name>`, gathers them in
 * AnkiDroid's custom study (by tag). */
@Serializable
data class Exam(
    val id: String,
    val name: String,
    val date: String = "",
    val lessons: List<ExamLesson> = emptyList(),
    @SerialName("created_at") val createdAt: String = "",
) {
    val tag: String get() = Exams.TAG_PREFIX + Exams.tagText(name)
}

/** The tests to prepare, kept on the phone; what each tags, and what the page shows of it. */
class Exams(private val prefs: Preferences, private val lessons: Lessons) {
    fun list(): List<Exam> =
        runCatching { json.decodeFromString(ListSerializer(Exam.serializer()), prefs[KEY].orEmpty()) }.getOrDefault(emptyList())

    fun get(id: String): Exam? = list().firstOrNull { it.id == id }

    /** The test saved under `id` (made, or changed); refused when it isn't one (BadRequest).
     * Lessons that don't exist (any more) are left out. */
    // Read, changed, written back: one at a time (two requests at once would lose one's change)
    @Synchronized
    fun save(id: String, name: String, date: String, parts: List<ExamLesson>): Exam {
        if (!ID.matches(id) || name.isBlank() || name.length > 60 || !DATE.matches(date) || parts.size > 50) {
            throw BadRequest("exams.invalid")
        }
        val every = list()
        val before = every.firstOrNull { it.id == id }
        if (before == null && every.size >= MAX) throw BadRequest("exams.too_many", buildJsonObject { put("max", MAX) })
        // AnkiDroid tells tags apart without their case: "Maths lundi" and "maths lundi" would be one
        val tag = fold(tagText(name.trim()))
        if (every.any { it.id != id && fold(tagText(it.name)) == tag }) throw BadRequest("exams.same_name")
        val kept = parts.filter { lessons.get(it.lesson) != null }
        val exam = Exam(id, name.trim(), date, kept, before?.createdAt?.ifEmpty { null } ?: Instant.now().toString())
        write(if (before == null) every + exam else every.map { if (it.id == id) exam else it })
        return exam
    }

    @Synchronized
    fun delete(id: String): Boolean {
        val every = list()
        val kept = every.filter { it.id != id }
        if (kept.size != every.size) write(kept)
        return kept.size != every.size
    }

    /** A lesson deleted: out of every test. */
    @Synchronized
    fun forgetLesson(lessonId: String) {
        val every = list()
        val changed = every.map { e -> e.copy(lessons = e.lessons.filter { it.lesson != lessonId }) }
        if (changed != every) write(changed)
    }

    private fun write(exams: List<Exam>) {
        prefs[KEY] = json.encodeToString(ListSerializer(Exam.serializer()), exams)
    }

    /** The tests changed while AnkiDroid couldn't follow (not installed, not allowed): {id:
     * the test as AnkiDroid's notes still have it (its tag, its notes); null: made since}. */
    fun pending(): Map<String, Exam?> =
        runCatching { json.decodeFromString(PENDING_TYPE, prefs[PENDING].orEmpty()) }.getOrDefault(emptyMap())

    /** A change AnkiDroid followed (`done`: the test's notes now as it is), or not yet: the
     * first state AnkiDroid's notes still have kept until then, whatever changes come after. */
    @Synchronized
    fun setPending(id: String, before: Exam?, done: Boolean) {
        val waiting = pending()
        if (waiting.containsKey(id) != done) return // nothing to change
        prefs[PENDING] = json.encodeToString(PENDING_TYPE, if (done) waiting - id else waiting + (id to before))
    }

    // --- What a test tags

    /** The tests' tags of each of the lesson's cards (card id → tags; cards in no test left
     * out): put on their notes when they are sent. */
    fun cardTags(lessonId: String, cardIds: List<String>): Map<String, Set<String>> {
        val found = mutableMapOf<String, MutableSet<String>>()
        for (exam in list()) for (part in exam.lessons) if (part.lesson == lessonId) {
            for (card in part.cards?.filter { it in cardIds } ?: cardIds) found.getOrPut(card) { linkedSetOf() } += exam.tag
        }
        return found
    }

    /** The notes in AnkiDroid of the test's cards: those the lessons recorded when sent. */
    fun notesOf(exam: Exam): Set<Long> = exam.lessons.flatMap { part ->
        val lesson = lessons.get(part.lesson) ?: return@flatMap emptyList()
        val notes = (lesson["anki_notes"] as? JsonObject)?.mapNotNull { (card, note) -> note.jsonPrimitive.longOrNull?.let { card to it } }?.toMap().orEmpty()
        val cards = part.cards ?: lesson.cards().map { it.string("id") }
        cards.mapNotNull { notes[it] }
    }.toSet()

    /** The tags to add and to remove ({tag: notes}) so that AnkiDroid's notes follow a change
     * of the test (`before` → `after`; null: made, or deleted). */
    fun retagging(before: Exam?, after: Exam?): Pair<Map<String, Set<Long>>, Map<String, Set<Long>>> {
        val add = mutableMapOf<String, Set<Long>>()
        val remove = mutableMapOf<String, Set<Long>>()
        val old = before?.let(::notesOf).orEmpty()
        val new = after?.let(::notesOf).orEmpty()
        if (before != null && after != null && before.tag == after.tag) {
            if ((new - old).isNotEmpty()) add[after.tag] = new - old
            if ((old - new).isNotEmpty()) remove[after.tag] = old - new
        } else {
            if (before != null && old.isNotEmpty()) remove[before.tag] = old
            if (after != null && new.isNotEmpty()) add[after.tag] = new
        }
        return add to remove
    }

    // --- What the page shows

    /** The test as the page shows it: its lessons that still exist, each with how many of
     * its cards are in the test and how many of those are in AnkiDroid; the tag; where to
     * find them in AnkiDroid. */
    fun view(exam: Exam): JsonObject {
        val parts = exam.lessons.mapNotNull { part ->
            val lesson = lessons.get(part.lesson) ?: return@mapNotNull null
            val ids = lesson.cards().map { it.string("id") }
            val chosen = part.cards?.filter { it in ids } ?: ids
            val notes = (lesson["anki_notes"] as? JsonObject)?.keys.orEmpty()
            buildJsonObject {
                put("lesson", part.lesson)
                part.cards?.let { put("cards", JsonArray(it.map(::JsonPrimitive))) } ?: put("cards", JsonNull)
                put("deck", lesson.string("deck"))
                put("total", chosen.size)
                put("in_anki", chosen.count { it in notes })
            }
        }
        return buildJsonObject {
            put("id", exam.id)
            put("name", exam.name)
            put("date", exam.date)
            put("created_at", exam.createdAt)
            put("lessons", JsonArray(parts))
            put("tag", exam.tag)
            put("deck", commonDeck(parts.map { it.string("deck") }))
            put("search", "tag:${exam.tag}")
        }
    }

    companion object {
        const val TAG_PREFIX = "Exam::"
        private const val KEY = "exams"
        private const val PENDING = "exams_pending"
        private val PENDING_TYPE = MapSerializer(String.serializer(), Exam.serializer().nullable)
        private const val MAX = 50
        private val ID = Regex("^[a-z0-9-]{1,40}$")
        private val DATE = Regex("""^(\d{4}-\d{2}-\d{2})?$""")

        /** The name as an Anki tag's last part: no space (they separate tags), none of the
         * characters Anki's search or hierarchy use. */
        fun tagText(name: String): String =
            name.replace(Regex("""[:"*\\]"""), " ").trim().replace(Regex("[\\s\\p{Z}]+"), "_").ifEmpty { "exam" } // any space, a non-breaking one too

        /** The deck holding every one of these (itself or a subdeck): where AnkiDroid's custom
         * study finds all the test's cards; "" when they share none. */
        /** A name without its case, as Python's casefold: "Straße" and "STRASSE" one. */
        internal fun fold(name: String): String = name.uppercase().lowercase()

        fun commonDeck(decks: List<String>): String {
            val parts = decks.map { it.trim() }.filter { it.isNotEmpty() }.map { it.split("::") }
            if (parts.isEmpty()) return ""
            val common = mutableListOf<String>()
            for (level in 0 until parts.minOf { it.size }) {
                if (parts.map { fold(it[level]) }.toSet().size != 1) break
                common += parts[0][level]
            }
            return common.joinToString("::")
        }
    }
}
