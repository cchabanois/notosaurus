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
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.contentOrNull
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
     * counted as failures. `previous`: by card id, the figure a correction replaced, {"source": its
     * picture_source (its sources), "kind": its family}: drawn again from it, what is asked
     * changed and the rest kept (as the computer's /pictures). */
    suspend fun drawMissing(
        lesson: JsonObject,
        draw: Boolean = false,
        step: Step = {},
        notFromLesson: Set<String> = emptySet(),
        previous: Map<String, JsonObject> = emptyMap(),
    ): JsonObject = drawing(lesson.string("id")) { drawnMissing(lesson, draw, step, notFromLesson, previous) }

    private suspend fun drawnMissing(
        lesson: JsonObject,
        draw: Boolean,
        step: Step,
        notFromLesson: Set<String>,
        previous: Map<String, JsonObject>,
    ): JsonObject {
        val id = lesson.string("id")
        val cards = lesson.cards()
        fromTheLesson(id, cards, step, notFromLesson)
        val failures = mutableListOf<JsonObject>()
        val toDraw = mutableListOf<String>()
        val few = Semaphore(AT_ONCE)
        coroutineScope {
            val figuresOff = off("figures.draw")
            cards.indices.filter { i -> needsPicture(cards[i]) && !(figuresOff && cards[i].string("figure").isNotBlank()) }.map { i ->
                async {
                    few.withPermit {
                        try {
                            val card = cards[i].string("id")
                            val redraw = redrawFrom(lessons.images(id), cards[i], replaced = previous[card])
                            cards[i] = drawn(id, cards[i], fresh = false, draw = draw, find = !draw, redraw = redraw) {
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
     * pictures then looked for, as without). {"card", "step": "lesson"} while looked at. Each
     * card's drawing looked for on its page and its neighbours, a page unknown on every page,
     * LocalServer.MAX_PER_CALL at a time (drawingCalls: the relay's cap, a lesson holds more),
     * one call after another, each asked only for the cards still without a drawing; a call
     * the relay refuses: its pages skipped, the others still looked at. */
    private suspend fun fromTheLesson(lessonId: String, cards: MutableList<JsonObject>, step: Step, notFromLesson: Set<String>) {
        val wanted = cards.indices.filter { i ->
            needsPicture(cards[i]) && cards[i].string("picture_prompt").isNotBlank() && cards[i].string("figure").isBlank() &&
                cards[i].string("id") !in notFromLesson
        }
        val photos = lessons.photos(lessonId)
        if (wanted.isEmpty() || photos.isEmpty()) return
        wanted.forEach { i -> step(buildJsonObject { put("card", cards[i].string("id")); put("step", "lesson") }) }
        val left = wanted.toMutableList()
        val pages = wanted.map { (cards[it]["page"] as? JsonPrimitive)?.intOrNull ?: 0 }
        for ((numbers, among) in drawingCalls(pages, photos.keys.toList())) { // by their page number: a page missing, none
            val asked = among.map { wanted[it] }.filter { it in left } // the drawings' "card": an index into these
            if (asked.isEmpty()) continue
            val found = try {
                val sent = numbers.map { photos.getValue(it) } // the relay cuts each drawing out of its own
                relay().withPhotos("lesson-drawings", buildJsonObject { put("cards", JsonArray(asked.map { cards[it] })) }, sent)
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
     * then looks for free ones and asks before the image model draws one. A figure whose
     * description was changed: drawn again from what it was drawn from (its kept sources), what is
     * asked changed and the rest kept; the same: drawn anew (as the computer's). {"card", "lesson",
     * "search" (a picture's)}. A card with a figure the AI turns into a picture keeps its figure until
     * a picture replaces it (the user may give up the search: never a figure's drawing left without
     * its description): the picture's fields then come as "decided" ({"picture_prompt",
     * "picture_search", "picture_on_back"}), sent back with the picture chosen (draw, own).
     * `replaced`: the figure a correction replaced, not drawn again since ({"source", "kind"}, as
     * drawMissing's `previous`): drawn again from it, whatever the description asked (it always
     * differs from what that figure was drawn from). */
    suspend fun make(
        lesson: JsonObject,
        i: Int,
        subject: String?,
        language: String = "English",
        replaced: JsonObject? = null,
        step: Step = {},
    ): JsonObject = drawing(lesson.string("id")) {
        val id = lesson.string("id")
        val cards = lesson.cards()
        val card = cards[i]
        val redraw = redrawFrom(lessons.images(id), card, replaced, subject)
        try {
            cards[i] = drawn(
                id, card, fresh = true, asked = subject, language = language, draw = false, find = false, redraw = redraw, onStep = step,
            )
            answer(lesson, cards, i)
        } catch (e: RelayException) {
            if (e.code != NEEDS_DRAWING) throw e
            val description = e.params.string("description")
            val search = e.params.string("search")
            // The side the relay decided it shows on (as the computer's); an older relay's 409 says
            // none: the card's
            val onBack = (e.params["on_back"] as? JsonPrimitive)?.booleanOrNull ?: card.onBack()
            val found = "search" to JsonPrimitive(search.ifEmpty { description }) // what the page looks for
            if (card.string("figure").isNotBlank()) {
                val decided = buildJsonObject {
                    put("picture_prompt", description)
                    put("picture_search", search)
                    put("picture_on_back", onBack)
                }
                return@drawing buildJsonObject {
                    put("card", card)
                    put("lesson", lesson)
                    put("search", found.second)
                    put("decided", decided)
                }
            }
            cards[i] = cards[i].with(
                "figure" to JsonPrimitive(""), "figure_kind" to JsonPrimitive(""), "picture_prompt" to JsonPrimitive(description),
                "picture_search" to JsonPrimitive(search), "picture_on_back" to JsonPrimitive(onBack),
            )
            JsonObject(answer(lesson, cards, i) + found)
        }
    }

    /** Card `i`'s picture drawn by the image model, now: the user said yes (no free one fit). A
     * figure: drawn again, told what its check found (`problem`) when there is one, with the
     * model's thinking when `careful`; from what it was drawn from (its kept sources, as the
     * computer's /picture/draw). {"card", "lesson"}. */
    suspend fun draw(
        lesson: JsonObject,
        i: Int,
        problem: String = "",
        careful: Boolean = false,
        decided: JsonObject? = null, // a picture "make" decided for a figure: drawn now, the figure replaced
        step: Step = {},
    ): JsonObject = drawing(lesson.string("id")) {
        val id = lesson.string("id")
        val cards = lesson.cards()
        val card = decided?.let { cards[i].decide(it) } ?: cards[i]
        cards[i] = drawn(
            id, card, fresh = true, draw = true, find = false, problem = problem, careful = careful,
            redraw = redrawFrom(lessons.images(id), card, again = true), onStep = step,
        )
        answer(lesson, cards, i)
    }

    /** "🔍 Check": card `i`'s picture looked at by the relay's AI, nothing changed: its figure
     * as drawn against its description (/v1/check-figure); any other picture (a photo found,
     * drawn by the image model, the user's) against the card (/v1/check-picture). An SVG without
     * its figure's description (a figure an older version turned into a picture without replacing
     * its drawing): still a figure, checked against what the card's picture should show, else the
     * card itself (as the computer's). A card's text longer than the relay takes cut to it, not
     * refused. {"ok", "problem"}. */
    suspend fun check(lesson: JsonObject, i: Int): JsonObject {
        val card = lesson.cards()[i]
        val figure = card.string("figure")
        val picture = file(lesson.string("id"), card.string("picture")) ?: throw BadRequest("card.not_found")
        val text = "${card.string("front")} → ${card.string("back")}"
        val checked = if (picture.extension == "svg") {
            relay().post("check-figure", buildJsonObject {
                put("description", cut(figure.trim().ifEmpty { card.string("picture_prompt").trim() }.ifEmpty { text }))
                put("svg", picture.readText())
            })
        } else {
            if (picture.extension != "jpg") throw BadRequest("card.not_found")
            relay().post("check-picture", buildJsonObject {
                put("card", cut(text))
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

    /** The user's own photo as card `i`'s picture, made card size (512 px, as the computer's), or
     * a found one (`source`); `decided`: a picture "make" decided for its figure, the card's now. */
    fun own(lesson: JsonObject, i: Int, photo: ByteArray, source: JsonObject? = PHOTO, decided: JsonObject? = null): JsonObject = drawing(lesson.string("id")) {
        val cards = lesson.cards()
        val data = if (source == PHOTO) cardSize(photo) else photo // a found one is card size already
        val name = save(lesson.string("id"), cards[i].string("id"), data, "jpg")
        if (decided != null) cards[i] = cards[i].decide(decided)
        cards[i] = cards[i].with("picture" to JsonPrimitive(name), "picture_source" to (source ?: JsonNull))
        answer(lesson, cards, i)
    }

    /** No picture on card `i` any more: a text card. */
    fun remove(lesson: JsonObject, i: Int): JsonObject {
        val cards = lesson.cards()
        cards[i] = cards[i].with(*REMOVED.map { it to if (it == "picture_source") JsonNull else JsonPrimitive("") }.toTypedArray())
        return answer(lesson, cards, i)
    }

    /** A lesson's picture file, by its name (ours only: no "../"); null when there is none. */
    fun file(lessonId: String, name: String): File? =
        lessons.images(lessonId)?.resolve(name)?.takeIf { NAME.matches(name) && it.isFile }

    /** The card with its figure (SVG) or picture (JPEG) saved: decided, found or drawn by the relay
     * (/v1/card-picture: the core's pictures.card_picture, the computer's rule too), with what it
     * shows and where it comes from. A figure's sources (what it was drawn from) kept beside it,
     * named in its picture_source.sources (as the core's figure_or_picture); `redraw`: the earlier
     * figure it is drawn again from (redrawFrom), none: drawn anew. */
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
        redraw: Redraw? = null,
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
            put("previous", JsonArray(redraw?.sources.orEmpty().map(::JsonPrimitive))) // drawn again from it: the rest kept
            put("previous_kind", redraw?.kind.orEmpty())
            put("previous_engine", redraw?.engine.orEmpty())
        }, onStep)
        var decided = made["card"]!!.jsonObject
        val extension = if (made.string("media_type") == "image/svg+xml") "svg" else "jpg"
        val name = save(lessonId, card.string("id"), Base64.getDecoder().decode(made.string("data")), extension)
        val origin = decided["picture_source"] as? JsonObject
        if (extension == "svg" && origin != null) {
            val sources = (made["sources"] as? JsonArray).orEmpty().mapNotNull { (it as? JsonPrimitive)?.contentOrNull }
            decided = decided.with("picture_source" to origin.with("sources" to keepSources(lessons.images(lessonId)!!, name, sources)))
        }
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
     * card is edited. Read and written under the lessons' lock (Lessons.locked): a save landing
     * meanwhile (the page's correction) waits, never written over by cards read before it. */
    private fun saved(lesson: JsonObject, cards: List<JsonObject>): JsonObject {
        val id = lesson.string("id")
        return lessons.locked {
            val now = lessons.get(id)?.cards() ?: notFound()
            merging()
            lessons.update(id, buildJsonObject { put("cards", JsonArray(mergedCards(lesson.cards(), cards, now))) })
        } ?: notFound()
    }

    /** Called between a merge's reading of the lesson and its writing (tests: a save landing there). */
    internal var merging: () -> Unit = {}

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
     * more and no correction to undo, or the lesson just opened; never by a send), with the
     * sources a figure was drawn from (named after it), as the core's pictures.prune. How many
     * pictures.
     * None while its pictures are being drawn (a picture just drawn is in no saved card yet,
     * another tab or a reload asking meanwhile): the next time. The lesson read again then. */
    fun prune(lesson: JsonObject): Int {
        val id = lesson.string("id")
        synchronized(writing) {
            if ((writing[id] ?: 0) > 0) return 0
            val used = (lessons.get(id) ?: return 0).cards().map { it.string("picture") }.toSet()
            return pruned(lessons.images(id) ?: return 0, used)
        }
    }

    /** The card with a picture "make" decided for its figure (`decided`: {"picture_prompt",
     * "picture_search", "picture_on_back"}), now that a picture replaces the figure's drawing: its
     * fields set, the figure's cleared (as the computer's). */
    private fun JsonObject.decide(decided: JsonObject) = with(
        "figure" to JsonPrimitive(""), "figure_kind" to JsonPrimitive(""),
        "picture_prompt" to JsonPrimitive(decided.string("picture_prompt")),
        "picture_search" to JsonPrimitive(decided.string("picture_search")),
        "picture_on_back" to JsonPrimitive((decided["picture_on_back"] as? JsonPrimitive)?.booleanOrNull ?: onBack()),
    )

    private fun JsonObject.onBack() = (this["picture_on_back"] as? JsonPrimitive)?.booleanOrNull ?: false

    /** An earlier figure a card's figure is drawn again from: what it was drawn from (its sources'
     * contents), its family and its engine (the relay's previous, previous_kind and
     * previous_engine): redrawFrom. */
    internal data class Redraw(val sources: List<String>, val kind: String, val engine: String)

    companion object {
        /** A card whose picture is still to be made: it says what to show (a picture_prompt or a
         * figure) and has none. A sentence with gaps' too: its note type shows it (Anki.kt sends its
         * Picture and BackPicture fields), on its question or its answer. As the computer's and the
         * page's (pictures.needs_picture, core/shared-cases.json). */
        internal fun needsPicture(card: JsonObject) =
            card.string("picture").isEmpty() && (card.string("picture_prompt").isNotBlank() || card.string("figure").isNotBlank())

        /** The calls looking for the lesson's own drawings of cards whose pages are `pages` (each
         * card's, from 1; 0 unknown) among the lesson's `photos` (the numbers of its pages there): each
         * call's pages sent and the cards it asks (their indexes; a later call asks only those still
         * without a drawing). A card's drawing looked for on its own page and its neighbours (the page
         * before, the page after, those the lesson has): the cards taken by their page, each call
         * sends the pages around as many as fit in `perCall` photos. The cards whose page is unknown
         * (0, or not one of the lesson's: a page missing is never replaced by another): every page,
         * `perCall` at a time. As the computer (pictures.drawing_calls, core/shared-cases.json). */
        internal fun drawingCalls(pages: List<Int>, photos: List<Int>, perCall: Int = LocalServer.MAX_PER_CALL): List<Pair<List<Int>, List<Int>>> {
            val present = photos.toSortedSet()
            val calls = mutableListOf<Pair<List<Int>, List<Int>>>()
            val sent = sortedSetOf<Int>()
            val asked = mutableListOf<Int>()
            for (i in pages.indices.filter { pages[it] in present }.sortedWith(compareBy({ pages[it] }, { it }))) {
                val near = (pages[i] - 1..pages[i] + 1).filter { it in present }.toSet()
                if (asked.isNotEmpty() && (sent + near).size > perCall) {
                    calls += sent.toList() to asked.sorted()
                    sent.clear(); asked.clear()
                }
                sent += near
                asked += i
            }
            if (asked.isNotEmpty()) calls += sent.toList() to asked.sorted()
            val unknown = pages.indices.filter { pages[it] !in present }
            if (unknown.isNotEmpty()) present.toList().chunked(perCall).forEach { calls += it to unknown }
            return calls
        }

        /** drawingCalls of a lesson whose pages are 1 to `photos` (none missing). */
        internal fun drawingCalls(pages: List<Int>, photos: Int, perCall: Int = LocalServer.MAX_PER_CALL): List<Pair<List<Int>, List<Int>>> =
            drawingCalls(pages, (1..photos).toList(), perCall)

        /** The cards an edit made of `before` (`after`), merged into the lesson's as saved now
         * (`now`), card by card (by id): of each card the edit changed, only the fields it
         * changed; a card added since kept, one it removed gone, one it added at the end. A
         * picture the edit drew for a card described anew meanwhile, or given another picture
         * meanwhile (stalePicture): none of its picture's fields, the card left as it is now. As app/lessons.py's
         * merged_cards. Without ids to go by (or twice the same): `after`. */
        internal fun mergedCards(before: List<JsonObject>, after: List<JsonObject>, now: List<JsonObject>): List<JsonObject> {
            fun ids(cards: List<JsonObject>) = cards.map { it.string("id") }
            if (listOf(before, after, now).any { cards -> ids(cards).let { it.any(String::isEmpty) || it.toSet().size != it.size } }) return after
            val was = before.associateBy { it.string("id") }
            val made = after.associateBy { it.string("id") }
            return now.mapNotNull { card ->
                val old = was[card.string("id")] ?: return@mapNotNull card // added since
                val new = made[card.string("id")] ?: return@mapNotNull null // removed by the edit
                val changed = (old.keys + new.keys).filter { old[it] != new[it] && !(it in READY && stalePicture(old, new, card)) }
                JsonObject(card.filterKeys { it !in changed || it in new } + changed.mapNotNull { k -> new[k]?.let { k to it } })
            } + after.filter { it.string("id") !in was }
        }

        /** The picture an edit gave a card (`before` → `after`) no longer the card's to take: its
         * picture changed meanwhile in the lesson as saved `now` (another edit gave it one: a photo
         * the user chose while a batch drew it, written over then pruned), or it was drawn from
         * what the card no longer says, its description (DESCRIBED) changed meanwhile (a correction
         * saved while it was drawn), not to what the edit set itself. The user's own photo is not
         * drawn from it (chosen as the card's, kept); nor is a picture removed. As app/lessons.py's
         * stale_picture. */
        internal fun stalePicture(before: JsonObject, after: JsonObject, now: JsonObject): Boolean {
            val picture = after.string("picture")
            if (picture.isEmpty() || picture == before.string("picture")) return false
            if ((after["picture_source"] as? JsonObject)?.string("source") == "photo") return false
            if (now.string("picture") != before.string("picture") && now.string("picture") != picture) return true
            fun described(card: JsonObject) = DESCRIBED.map { card.string(it) }
            return described(now) != described(before) && described(now) != described(after)
        }

        /** The pictures in `folder` no card uses (`used`) removed, with the sources a figure was
         * drawn from (named after it), as the core's pictures.prune: how many pictures. */
        internal fun pruned(folder: File, used: Set<String>): Int {
            val stems = used.map { it.substringBeforeLast('.') }.toSet()
            folder.listFiles { f -> SOURCE_NAME.matchEntire(f.name)?.let { it.groupValues[1] !in stems } == true }.orEmpty().forEach { it.delete() }
            return folder.listFiles { f -> NAME.matches(f.name) && f.name !in used }.orEmpty().count { it.delete() }
        }

        /** What a figure was drawn from written beside its picture: the files, in order, as
         * picture_source.sources names them (the core's pictures.keep_sources). */
        internal fun keepSources(folder: File, picture: String, contents: List<String>): JsonArray {
            val stem = picture.substringBeforeLast('.')
            return JsonArray(contents.mapIndexed { n, content ->
                val name = if (n == 0) "$stem.typ" else "$stem-${n + 1}.typ"
                File(folder, name).writeText(content)
                buildJsonObject { put("file", name) }
            })
        }

        /** Which earlier figure a card's figure is drawn again from, what is asked changed and the
         * rest kept (the core's pictures.redraw_from, core/shared-cases.json redraw_from).
         * `replaced`: the figure a correction replaced, not drawn again since ({"source": its
         * picture_source, "kind": its family}): that one, whatever is asked; its source missing,
         * nothing (never the card's own). Else the card's own figure, when it is drawn again
         * (`again`: the drawing button, a check's problem) or its description written anew
         * (`asked`, changedFigure). Null: drawn anew (nothing to draw again from, or not in an
         * engine figures are drawn again from, REDRAWN_FROM, or one of its sources missing). */
        internal fun redrawFrom(folder: File?, card: JsonObject, replaced: JsonObject? = null, asked: String? = null, again: Boolean = false): Redraw? {
            val (origin, kind) = when {
                replaced != null -> replaced["source"] as? JsonObject to replaced.string("kind")
                card.string("figure").isNotBlank() && (again || changedFigure(card, asked)) ->
                    card["picture_source"] as? JsonObject to card.string("figure_kind")
                else -> return null
            }
            val engine = origin?.string("engine").orEmpty()
            if (origin == null || engine !in REDRAWN_FROM) return null
            val sources = keptSources(folder, origin)
            return if (sources.isEmpty()) null else Redraw(sources, kind, engine)
        }

        /** A figure's description written anew (`asked`, "✨ Image"'s): drawn again from what it was
         * drawn from; the same, or none: drawn anew (the core's pictures.changed_figure). */
        internal fun changedFigure(card: JsonObject, asked: String?): Boolean {
            val written = asked.orEmpty().trim()
            val figure = card.string("figure").trim()
            return figure.isNotEmpty() && written.isNotEmpty() && written != figure
        }

        /** What a figure was drawn from, as its picture_source names it: none when it names none
         * (drawn as SVG, before sources were kept), or one is missing or not one of ours (the
         * core's pictures.kept_sources). */
        internal fun keptSources(folder: File?, origin: JsonObject?): List<String> {
            val files = (origin?.get("sources") as? JsonArray).orEmpty().map { (it as? JsonObject)?.string("file").orEmpty() }
            val paths = files.filter { SOURCE_NAME.matches(it) }.mapNotNull { folder?.resolve(it) }
            if (paths.size != files.size || !paths.all { it.isFile }) return emptyList()
            return paths.map { it.readText() }
        }

        /** A whole card's text the relay takes ("front → back": /v1/check-picture's card), as
         * relay_api.MAX_CARD: a card has no length limit of its own, so a longer one is cut to it
         * (with "…") rather than refused. */
        internal const val MAX_CARD = 4000

        /** `text` cut to `max` characters, "…" last when it was longer (never half a character). */
        internal fun cut(text: String, max: Int = MAX_CARD): String {
            if (text.length <= max) return text
            val kept = text.take(max - 1)
            return (if (kept.lastOrNull()?.isHighSurrogate() == true) kept.dropLast(1) else kept) + "…"
        }

        private const val AT_ONCE = 4
        private const val NEEDS_DRAWING = "picture.needs_drawing" // no free picture fits: the user is asked
        // The engines a figure is drawn again from, its sources given (the core's pictures.REDRAWN_FROM)
        private val REDRAWN_FROM = listOf("typst")
        private val PHOTO = buildJsonObject { put("source", "photo") }
        private val LESSON = buildJsonObject { put("source", "lesson") } // its own pages' drawing
        // What the relay decides of a card's picture (Card's fields): taken into the card (core's pictures.PICTURE_FIELDS)
        private val PICTURE_FIELDS = listOf("figure", "figure_kind", "picture_prompt", "picture_search", "picture_source", "picture_on_back")
        // What removing a card's picture clears ("" each, picture_source null): its search words and
        // where it shows kept (core's pictures.REMOVED)
        private val REMOVED = listOf("picture", "picture_prompt", "figure", "figure_kind", "picture_source")
        // What a card's picture is drawn from (its description and its family): described anew
        // while an edit drew its picture, that picture is not the card's (core's pictures.DESCRIBED)
        private val DESCRIBED = listOf("figure", "figure_kind", "picture_prompt")
        // A card's picture fields, told with "ready" (drawMissing) the moment it has them (core's pictures.READY)
        private val READY = PICTURE_FIELDS + "picture"
        private val NAME = Regex("""^picture-[a-z0-9]+-[a-f0-9]{8}\.(jpg|svg)$""") // the files we write
        // A figure's source files: named after its picture ("picture-c1-ab12cd34.typ", "-2.typ" for
        // a second), read back only by such a name; its group 1 the picture's stem (core's SOURCE_NAME)
        internal val SOURCE_NAME = Regex("""^(picture-[a-z0-9]+-[a-f0-9]{8})(-\d+)?\.typ$""")
    }
}
