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
import kotlinx.serialization.json.intOrNull
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonPrimitive
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
    private val off: (String) -> Boolean = { false }, // a feature turned off for now (Switches.off)
) {
    /** The missing pictures, a few at a time: figures drawn, free pictures found; those no
     * free one fits drawn by the image model only when `draw` (the user said yes), else in
     * "to_draw". {"lesson", "failures", "error", "to_draw"}. A card without its picture is
     * still a card: counted, not fatal. `step`: each card's steps as they begin, {"card": its
     * id, "step"…} (what the page shows on it meanwhile, as the computer's), then {"card", "step":
     * "ready", its picture's fields (READY)} as soon as it has it. The lesson's own drawings
     * first (fromTheLesson), for the cards whose thing its photos show, but those in
     * `notFromLesson` (their ids: a correction replaced their picture, the lesson's drawing
     * would only come back). Figures turned off (figures.draw): their cards left without, not
     * counted as failures. */
    suspend fun drawMissing(lesson: JsonObject, draw: Boolean = false, step: Step = {}, notFromLesson: Set<String> = emptySet()): JsonObject =
        drawing(lesson.string("id")) { drawnMissing(lesson, draw, step, notFromLesson) }

    private suspend fun drawnMissing(lesson: JsonObject, draw: Boolean, step: Step, notFromLesson: Set<String>): JsonObject {
        val id = lesson.string("id")
        val cards = lesson.cards()
        fromTheLesson(id, cards, step, notFromLesson)
        val failures = mutableListOf<JsonObject>()
        val toDraw = mutableListOf<String>()
        val few = Semaphore(AT_ONCE)
        coroutineScope {
            val figuresOff = off("figures.draw")
            cards.indices.filter { i -> cards[i].missingPicture() && !(figuresOff && cards[i].string("figure").isNotBlank()) }.map { i ->
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
            put("lesson", saved(lesson, cards))
            put("failures", failures.size)
            put("error", failures.firstOrNull() ?: JsonNull)
            put("to_draw", JsonArray(toDraw.map(::JsonPrimitive)))
        }
    }

    /** The pictures (not the figures: drawn exact) the lesson's own drawings give, cut out of
     * its photos by the relay (/v1/lesson-drawings, the core's pictures.lesson_drawings), in
     * `cards` at once and told ready; none, or the relay failing: the cards as they were (their
     * pictures then looked for, as without). {"card", "step": "lesson"} while looked at. The
     * photos sent LocalServer.MAX_PER_CALL at a time (the relay's cap: a lesson holds more),
     * one call after another, each asked only for the cards still without a drawing; a call
     * the relay refuses: its pages skipped, the others still looked at. */
    private suspend fun fromTheLesson(lessonId: String, cards: MutableList<JsonObject>, step: Step, notFromLesson: Set<String>) {
        val wanted = cards.indices.filter { i ->
            cards[i].missingPicture() && cards[i].string("picture_prompt").isNotBlank() && cards[i].string("figure").isBlank() &&
                cards[i].string("id") !in notFromLesson
        }
        val photos = lessons.photos(lessonId)
        if (wanted.isEmpty() || photos.isEmpty()) return
        wanted.forEach { i -> step(buildJsonObject { put("card", cards[i].string("id")); put("step", "lesson") }) }
        val left = wanted.toMutableList()
        for (pages in photos.chunked(LocalServer.MAX_PER_CALL)) {
            if (left.isEmpty()) return
            val asked = left.toList() // the drawings' "card": an index into these
            val found = try {
                relay().withPhotos("lesson-drawings", buildJsonObject { put("cards", JsonArray(asked.map { cards[it] })) }, pages)
            } catch (e: RelayException) {
                continue // these pages' cards looked for one by one, as without
            }
            for (drawing in found["drawings"]?.jsonArray.orEmpty().map { it.jsonObject }) {
                val i = asked.getOrNull(drawing["card"]?.jsonPrimitive?.intOrNull ?: -1) ?: continue
                if (i !in left) continue // found twice in one answer: its first drawing
                left.remove(i)
                val name = save(lessonId, cards[i].string("id"), Base64.getDecoder().decode(drawing.string("data")), "jpg")
                cards[i] = cards[i].with("picture" to JsonPrimitive(name), "picture_source" to LESSON)
                val ready = READY.mapNotNull { field -> cards[i][field]?.let { field to it } }
                step(JsonObject(mapOf("card" to JsonPrimitive(cards[i].string("id")), "step" to JsonPrimitive("ready")) + ready))
            }
        }
    }

    /** "✨ Image", its first step (as the computer's /picture/make): from what the user wrote
     * (`subject`; null: its own description) the relay's AI decides a figure, then drawn
     * (cheap), or a picture, its description and search words set, nothing drawn: the page
     * then looks for free ones and asks before the image model draws one. {"card", "lesson",
     * "search" (a picture's)}. */
    suspend fun make(lesson: JsonObject, i: Int, subject: String?, language: String = "English", step: Step = {}): JsonObject = drawing(lesson.string("id")) {
        val cards = lesson.cards()
        try {
            cards[i] = drawn(lesson.string("id"), cards[i], fresh = true, asked = subject, language = language, draw = false, find = false, onStep = step)
            answer(lesson, cards, i)
        } catch (e: RelayException) {
            if (e.code != NEEDS_DRAWING) throw e
            val description = e.params.string("description")
            val search = e.params.string("search")
            cards[i] = cards[i].with(
                "figure" to JsonPrimitive(""), "figure_kind" to JsonPrimitive(""), "picture_prompt" to JsonPrimitive(description),
                "picture_search" to JsonPrimitive(search),
            )
            JsonObject(answer(lesson, cards, i) + ("search" to JsonPrimitive(search.ifEmpty { description })))
        }
    }

    /** Card `i`'s picture drawn by the image model, now: the user said yes (no free one fit). A
     * figure: drawn again, told what its check found (`problem`) when there is one, with the
     * model's thinking when `careful`. {"card", "lesson"}. */
    suspend fun draw(lesson: JsonObject, i: Int, problem: String = "", careful: Boolean = false, step: Step = {}): JsonObject = drawing(lesson.string("id")) {
        val cards = lesson.cards()
        cards[i] = drawn(lesson.string("id"), cards[i], fresh = true, draw = true, find = false, problem = problem, careful = careful, onStep = step)
        answer(lesson, cards, i)
    }

    /** "🔍 Check": card `i`'s picture looked at by the relay's AI, nothing changed: its figure
     * as drawn against its description (/v1/check-figure); any other picture (a photo found,
     * drawn by the image model, the user's) against the card (/v1/check-picture).
     * {"ok", "problem"}. */
    suspend fun check(lesson: JsonObject, i: Int): JsonObject {
        val card = lesson.cards()[i]
        val figure = card.string("figure")
        val picture = file(lesson.string("id"), card.string("picture")) ?: throw BadRequest("card.not_found")
        val checked = if (figure.isNotBlank() && picture.extension == "svg") {
            relay().post("check-figure", buildJsonObject {
                put("description", figure)
                put("svg", picture.readText())
            })
        } else {
            if (picture.extension != "jpg") throw BadRequest("card.not_found")
            relay().post("check-picture", buildJsonObject {
                put("card", "${card.string("front")} → ${card.string("back")}")
                put("meant", card.string("picture_prompt").ifBlank { figure })
                put("image", Base64.getEncoder().encodeToString(picture.readBytes()))
                put("media_type", "image/jpeg")
            })
        }
        return buildJsonObject {
            put("ok", checked["ok"]!!)
            put("problem", checked["problem"]!!)
        }
    }

    /** The user's own photo as card `i`'s picture, made card size (512 px, as the computer's). */
    fun own(lesson: JsonObject, i: Int, photo: ByteArray, source: JsonObject? = PHOTO): JsonObject = drawing(lesson.string("id")) {
        val cards = lesson.cards()
        val data = if (source == PHOTO) cardSize(photo) else photo // a found one is card size already
        val name = save(lesson.string("id"), cards[i].string("id"), data, "jpg")
        cards[i] = cards[i].with("picture" to JsonPrimitive(name), "picture_source" to (source ?: JsonNull))
        answer(lesson, cards, i)
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
        put("lesson", saved(lesson, cards))
    }

    /** The lesson with these cards: what they changed of `lesson`'s (their picture's fields)
     * written onto the lesson as saved now (mergedCards: the cards a /complete added while
     * they were drawn, a card the page changed, stay). The pictures no card uses any more stay
     * until prune(): a card's picture drawn again can still be undone on the page while the
     * card is edited. */
    private fun saved(lesson: JsonObject, cards: List<JsonObject>): JsonObject {
        val id = lesson.string("id")
        return synchronized(lessons) {
            val now = lessons.get(id)?.cards() ?: notFound()
            lessons.update(id, buildJsonObject { put("cards", JsonArray(mergedCards(lesson.cards(), cards, now))) })
        } ?: notFound()
    }

    /** The lessons whose pictures are being written (id → how many at once): a picture is in
     * images/ before it is in the saved lesson. prune() waits for none (its check and their
     * start under one lock: none begins while it removes). */
    private val writing = mutableMapOf<String, Int>()

    private inline fun <T> drawing(lessonId: String, block: () -> T): T {
        synchronized(writing) { writing[lessonId] = (writing[lessonId] ?: 0) + 1 }
        try {
            return block()
        } finally {
            synchronized(writing) {
                val left = (writing[lessonId] ?: 1) - 1
                if (left > 0) writing[lessonId] = left else writing.remove(lessonId)
            }
        }
    }

    /** The saved lesson's pictures no card uses removed (asked by the page: no card edited any
     * more and no correction to undo, or the lesson just opened; never by a send). How many.
     * None while its pictures are being drawn (a picture just drawn is in no saved card yet,
     * another tab or a reload asking meanwhile): the next time. The lesson read again then. */
    fun prune(lesson: JsonObject): Int {
        val id = lesson.string("id")
        synchronized(writing) {
            if ((writing[id] ?: 0) > 0) return 0
            val used = (lessons.get(id) ?: return 0).cards().map { it.string("picture") }.toSet()
            val gone = lessons.images(id)?.listFiles { f -> NAME.matches(f.name) && f.name !in used }.orEmpty()
            return gone.count { it.delete() }
        }
    }

    // Not on a sentence with gaps: AnkiDroid shows no picture on it (not paid for, then)
    private fun JsonObject.missingPicture() =
        string("picture").isEmpty() && (string("picture_prompt").isNotBlank() || string("figure").isNotBlank()) &&
            !CLOZE.containsMatchIn(string("front"))

    companion object {
        /** The cards an edit made of `before` (`after`), merged into the lesson's as saved now
         * (`now`), card by card (by id): of each card the edit changed, only the fields it
         * changed; a card added since kept, one it removed gone, one it added at the end. As
         * app/lessons.py's merged_cards. Without ids to go by (or twice the same): `after`. */
        internal fun mergedCards(before: List<JsonObject>, after: List<JsonObject>, now: List<JsonObject>): List<JsonObject> {
            fun ids(cards: List<JsonObject>) = cards.map { it.string("id") }
            if (listOf(before, after, now).any { cards -> ids(cards).let { it.any(String::isEmpty) || it.toSet().size != it.size } }) return after
            val was = before.associateBy { it.string("id") }
            val made = after.associateBy { it.string("id") }
            return now.mapNotNull { card ->
                val old = was[card.string("id")] ?: return@mapNotNull card // added since
                val new = made[card.string("id")] ?: return@mapNotNull null // removed by the edit
                val changed = (old.keys + new.keys).filter { old[it] != new[it] }
                JsonObject(card.filterKeys { it !in changed || it in new } + changed.mapNotNull { k -> new[k]?.let { k to it } })
            } + after.filter { it.string("id") !in was }
        }

        private const val AT_ONCE = 4
        private const val NEEDS_DRAWING = "picture.needs_drawing" // no free picture fits: the user is asked
        private val PHOTO = buildJsonObject { put("source", "photo") }
        private val LESSON = buildJsonObject { put("source", "lesson") } // its own pages' drawing
        // What the relay decides of a card's picture (Card's fields): taken into the card
        private val PICTURE_FIELDS = listOf("figure", "figure_kind", "picture_prompt", "picture_search", "picture_source", "picture_on_back")
        // A card's picture fields, told with "ready" (drawMissing) the moment it has them (core's pictures.READY)
        private val READY = PICTURE_FIELDS + "picture"
        private val CLOZE = Regex("""\{\{c\d+::""") // a gap, as core/notosaurus_core/cards.py
        private val NAME = Regex("""^picture-[a-z0-9]+-[a-f0-9]{8}\.(jpg|svg)$""") // the files we write
    }
}
