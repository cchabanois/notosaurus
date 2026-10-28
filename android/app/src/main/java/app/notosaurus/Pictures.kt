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
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.put
import java.io.File
import java.util.Base64
import java.security.MessageDigest

/** The cards' pictures, as the computer's (core's pictures.card_picture, through the relay's
 * /v1/card-picture): a figure or a picture, the user's own photo, or none; kept in
 * the lesson's images/, named as the computer names them, unused ones removed. */
class Pictures(
    private val lessons: Lessons,
    private val relay: () -> Relay,
    private val cardSize: (ByteArray) -> ByteArray = { it }, // the user's photo as a card shows it (Photos.cardSize)
) {
    /** The missing pictures, a few at a time: figures drawn, free pictures found; those no
     * free one fits drawn by the image model only when `draw` (the user said yes), else in
     * "to_draw". {"lesson", "failures", "error", "to_draw"}. A card without its picture is
     * still a card: counted, not fatal. `step`: each card's steps as they begin, {"card": its
     * id, "step"…} (what the page shows on it meanwhile, as the computer's), then {"card", "step":
     * "ready", its picture's fields (READY)} as soon as it has it. */
    suspend fun drawMissing(lesson: JsonObject, draw: Boolean = false, step: Step = {}): JsonObject {
        val id = lesson.string("id")
        val cards = lesson.cards()
        val failures = mutableListOf<JsonObject>()
        val toDraw = mutableListOf<String>()
        val few = Semaphore(AT_ONCE)
        coroutineScope {
            cards.indices.filter { i -> cards[i].missingPicture() }.map { i ->
                async {
                    few.withPermit {
                        try {
                            val card = cards[i].string("id")
                            cards[i] = drawn(id, cards[i], fresh = false, draw = draw, find = !draw) {
                                step(JsonObject(mapOf("card" to JsonPrimitive(card)) + it))
                            }
                            // Shown at once, not when the others are done
                            val ready = READY.mapNotNull { field -> cards[i][field]?.let { field to it } }
                            step(JsonObject(mapOf("card" to JsonPrimitive(card), "step" to JsonPrimitive("ready")) + ready))
                        } catch (e: RelayException) {
                            if (e.code == NEEDS_DRAWING) toDraw += cards[i].string("id")
                            else failures += buildJsonObject { put("code", e.code); put("params", e.params) }
                        }
                    }
                }
            }.awaitAll()
        }
        return buildJsonObject {
            put("lesson", saved(id, cards))
            put("failures", failures.size)
            put("error", failures.firstOrNull() ?: JsonNull)
            put("to_draw", JsonArray(toDraw.map(::JsonPrimitive)))
        }
    }

    /** "✨ Image", its first step (as the computer's /picture/make): from what the user wrote
     * (`subject`; null: its own description) the relay's AI decides a figure, then drawn
     * (cheap), or a picture, its description and search words set, nothing drawn: the page
     * then looks for free ones and asks before the image model draws one. {"card", "lesson",
     * "search" (a picture's)}. */
    suspend fun make(lesson: JsonObject, i: Int, subject: String?, language: String = "English", step: Step = {}): JsonObject {
        val cards = lesson.cards()
        try {
            cards[i] = drawn(lesson.string("id"), cards[i], fresh = true, asked = subject, language = language, draw = false, find = false, onStep = step)
            return answer(lesson, cards, i)
        } catch (e: RelayException) {
            if (e.code != NEEDS_DRAWING) throw e
            val description = e.params.string("description")
            val search = e.params.string("search")
            cards[i] = cards[i].with(
                "figure" to JsonPrimitive(""), "figure_kind" to JsonPrimitive(""), "picture_prompt" to JsonPrimitive(description),
                "picture_search" to JsonPrimitive(search),
            )
            return JsonObject(answer(lesson, cards, i) + ("search" to JsonPrimitive(search.ifEmpty { description })))
        }
    }

    /** Card `i`'s picture drawn by the image model, now: the user said yes (no free one fit). A
     * figure: drawn again, told what its check found (`problem`) when there is one, with the
     * model's thinking when `careful`. {"card", "lesson"}. */
    suspend fun draw(lesson: JsonObject, i: Int, problem: String = "", careful: Boolean = false, step: Step = {}): JsonObject {
        val cards = lesson.cards()
        cards[i] = drawn(lesson.string("id"), cards[i], fresh = true, draw = true, find = false, problem = problem, careful = careful, onStep = step)
        return answer(lesson, cards, i)
    }

    /** "🔍 Check": card `i`'s figure looked at by the relay's AI against its description
     * (/v1/check-figure), nothing changed. {"ok", "problem"}. */
    suspend fun check(lesson: JsonObject, i: Int): JsonObject {
        val card = lesson.cards()[i]
        val figure = card.string("figure")
        val svg = file(lesson.string("id"), card.string("picture"))?.takeIf { figure.isNotBlank() && it.extension == "svg" }
            ?: throw BadRequest("card.not_found")
        val checked = relay().post("check-figure", buildJsonObject {
            put("description", figure)
            put("svg", svg.readText())
        })
        return buildJsonObject {
            put("ok", checked["ok"]!!)
            put("problem", checked["problem"]!!)
        }
    }

    /** The user's own photo as card `i`'s picture, made card size (512 px, as the computer's). */
    fun own(lesson: JsonObject, i: Int, photo: ByteArray, source: JsonObject? = PHOTO): JsonObject {
        val cards = lesson.cards()
        val data = if (source == PHOTO) cardSize(photo) else photo // a found one is card size already
        val name = save(lesson.string("id"), cards[i].string("id"), data, "jpg")
        cards[i] = cards[i].with("picture" to JsonPrimitive(name), "picture_source" to (source ?: JsonNull))
        return answer(lesson, cards, i)
    }

    /** No picture on card `i` any more: a text card. */
    fun remove(lesson: JsonObject, i: Int): JsonObject {
        val cards = lesson.cards()
        cards[i] = cards[i].with(
            "picture" to JsonPrimitive(""), "picture_prompt" to JsonPrimitive(""), "figure" to JsonPrimitive(""),
            "figure_kind" to JsonPrimitive(""), "picture_source" to JsonNull,
        )
        return answer(lesson, cards, i)
    }

    /** A lesson's picture file, by its name (ours only: no "../"); null when there is none. */
    fun file(lessonId: String, name: String): File? =
        lessons.images(lessonId)?.resolve(name)?.takeIf { NAME.matches(name) && it.isFile }

    /** The card with its figure (SVG) or picture (JPEG) saved: decided, found or drawn by the relay
     * (/v1/card-picture: the core's pictures.card_picture, the computer's rule too), with what it
     * shows and where it comes from. */
    private suspend fun drawn(
        lessonId: String,
        card: JsonObject,
        fresh: Boolean,
        asked: String? = null,
        language: String = "English",
        draw: Boolean = true,
        find: Boolean = true,
        problem: String = "",
        careful: Boolean = false,
        onStep: Step = {},
    ): JsonObject {
        val made = relay().cardPicture(buildJsonObject {
            put("card", card)
            put("asked", asked?.let(::JsonPrimitive) ?: JsonNull)
            put("language", language)
            put("fresh", fresh)
            put("find", find) // a free picture found first for a real thing
            put("draw", draw) // else picture.needs_drawing: the image model costs, the user is asked
            put("problem", problem) // its figure's, the check found it: drawn again, told it
            put("careful", careful) // with the model's thinking
        }, onStep)
        val decided = made["card"]!!.jsonObject
        val extension = if (made.string("media_type") == "image/svg+xml") "svg" else "jpg"
        val name = save(lessonId, card.string("id"), Base64.getDecoder().decode(made.string("data")), extension)
        val fields = PICTURE_FIELDS.mapNotNull { field -> decided[field]?.let { field to it } }
        return card.with(*fields.toTypedArray(), "picture" to JsonPrimitive(name))
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
        private const val NEEDS_DRAWING = "picture.needs_drawing" // no free picture fits: the user is asked
        private val PHOTO = buildJsonObject { put("source", "photo") }
        // What the relay decides of a card's picture (Card's fields): taken into the card
        private val PICTURE_FIELDS = listOf("figure", "figure_kind", "picture_prompt", "picture_search", "picture_source")
        // A card's picture fields, told with "ready" (drawMissing) the moment it has them (core's pictures.READY)
        private val READY = PICTURE_FIELDS + "picture"
        private val CLOZE = Regex("""\{\{c\d+::""") // a gap, as core/notosaurus_core/cards.py
        private val NAME = Regex("""^picture-[a-z0-9]+-[a-f0-9]{8}\.(jpg|svg)$""") // the files we write
    }
}
