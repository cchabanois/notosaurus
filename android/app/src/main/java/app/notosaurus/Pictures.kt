package app.notosaurus

import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.sync.Semaphore
import kotlinx.coroutines.sync.withPermit
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import java.io.File
import java.security.MessageDigest

/** The cards' pictures, as the computer's (app/main.py, pictures.py): found or drawn through
 * the relay (/v1/picture, or /v1/figure for a figure), the user's own photo, or none; kept in
 * the lesson's images/, named as the computer names them, unused ones removed. */
class Pictures(
    private val lessons: Lessons,
    private val relay: () -> Relay,
    private val find: () -> Boolean = { true }, // a free picture found first for a real thing (the settings)
) {
    /** The missing pictures drawn, a few at a time: {"lesson", "failures", "error"}. A
     * card without its picture is still a card: counted, not fatal. */
    suspend fun drawMissing(lesson: JsonObject): JsonObject {
        val id = lesson.string("id")
        val cards = lesson.cards()
        val failures = mutableListOf<JsonObject>()
        val few = Semaphore(AT_ONCE)
        coroutineScope {
            cards.indices.filter { i -> cards[i].missingPicture() }.map { i ->
                async {
                    few.withPermit {
                        try {
                            cards[i] = cards[i].with("picture" to JsonPrimitive(drawn(id, cards[i], fresh = false)))
                        } catch (e: RelayException) {
                            failures += buildJsonObject { put("code", e.code); put("params", e.params) }
                        }
                    }
                }
            }.awaitAll()
        }
        return buildJsonObject {
            put("lesson", saved(id, cards))
            put("failures", failures.size)
            put("error", failures.firstOrNull() ?: JsonNull)
        }
    }

    /** Card `i`'s picture drawn again: from its subject (or figure), or `subject` written by
     * the user. {"card", "lesson"}. */
    suspend fun redraw(lesson: JsonObject, i: Int, subject: String?): JsonObject {
        val cards = lesson.cards()
        val field = if (cards[i].string("figure").isNotBlank()) "figure" else "picture_prompt"
        val asked = (subject ?: cards[i].string(field)).trim()
        if (asked.isEmpty()) throw BadRequest("picture.no_subject")
        val card = cards[i].with(field to JsonPrimitive(asked))
        cards[i] = card.with("picture" to JsonPrimitive(drawn(lesson.string("id"), card, fresh = true)))
        return answer(lesson, cards, i)
    }

    /** The user's own photo as card `i`'s picture (the page made it card size). */
    fun own(lesson: JsonObject, i: Int, photo: ByteArray): JsonObject {
        val cards = lesson.cards()
        cards[i] = cards[i].with("picture" to JsonPrimitive(save(lesson.string("id"), cards[i].string("id"), photo, "jpg")))
        return answer(lesson, cards, i)
    }

    /** No picture on card `i` any more: a text card. */
    fun remove(lesson: JsonObject, i: Int): JsonObject {
        val cards = lesson.cards()
        cards[i] = cards[i].with("picture" to JsonPrimitive(""), "picture_prompt" to JsonPrimitive(""), "figure" to JsonPrimitive(""))
        return answer(lesson, cards, i)
    }

    /** A lesson's picture file, by its name (ours only: no "../"); null when there is none. */
    fun file(lessonId: String, name: String): File? =
        lessons.images(lessonId)?.resolve(name)?.takeIf { NAME.matches(name) && it.isFile }

    /** A card's figure (SVG) or picture (JPEG), drawn by the relay and saved; its file name. */
    private suspend fun drawn(lessonId: String, card: JsonObject, fresh: Boolean): String {
        val figure = card.string("figure").trim()
        return if (figure.isNotEmpty()) {
            val svg = relay().post("figure", buildJsonObject { put("description", figure) }).string("svg")
            save(lessonId, card.string("id"), svg.toByteArray(), "svg")
        } else {
            // A real thing (Card.picture_search): the relay finds a free picture first, unless always drawn
            val search = if (find() && !fresh) card.string("picture_search").trim() else ""
            val context = "${card.string("front").trim()} → ${card.string("back").trim()}"
            save(lessonId, card.string("id"), relay().picture(card.string("picture_prompt"), fresh, search, context), "jpg")
        }
    }

    private fun save(lessonId: String, cardId: String, data: ByteArray, extension: String): String {
        val folder = lessons.images(lessonId) ?: notFound()
        folder.mkdirs()
        val digest = MessageDigest.getInstance("SHA-1").digest(data).joinToString("") { "%02x".format(it) }
        val name = "picture-$cardId-${digest.take(8)}.$extension"
        File(folder, name).writeBytes(data)
        return name
    }

    private fun answer(lesson: JsonObject, cards: List<JsonObject>, i: Int) = buildJsonObject {
        put("card", cards[i])
        put("lesson", saved(lesson.string("id"), cards))
    }

    /** The lesson with these cards, its pictures no card uses any more removed. */
    private fun saved(lessonId: String, cards: List<JsonObject>): JsonObject {
        val lesson = lessons.update(lessonId, buildJsonObject { put("cards", JsonArray(cards)) }) ?: notFound()
        val used = cards.map { it.string("picture") }.toSet()
        lessons.images(lessonId)?.listFiles { f -> NAME.matches(f.name) && f.name !in used }?.forEach { it.delete() }
        return lesson
    }

    // Not on a sentence with gaps: AnkiDroid shows no picture on it (not paid for, then)
    private fun JsonObject.missingPicture() =
        string("picture").isEmpty() && (string("picture_prompt").isNotBlank() || string("figure").isNotBlank()) &&
            !CLOZE.containsMatchIn(string("front"))

    companion object {
        private const val AT_ONCE = 4
        private val CLOZE = Regex("""\{\{c\d+::""") // a gap, as core/notosaurus_core/cards.py
        private val NAME = Regex("""^picture-[a-z0-9]+-[a-f0-9]{8}\.(jpg|svg)$""") // the files we write
    }
}
