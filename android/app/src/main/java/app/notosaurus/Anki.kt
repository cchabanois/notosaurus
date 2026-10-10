package app.notosaurus

import android.content.ContentValues
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.net.Uri
import androidx.core.content.ContextCompat
import androidx.core.content.FileProvider
import com.ichi2.anki.FlashCardsContract
import com.ichi2.anki.api.AddContentApi
import java.io.File
import java.math.BigDecimal
import java.math.RoundingMode
import java.security.MessageDigest
import kotlin.math.roundToInt
import kotlin.random.Random

/** What was done with the cards: added, updated (sent before, changed since), already in
 * AnkiDroid (another lesson's), left out (a diagram card without its photo). */
data class Sent(val added: Int, val duplicates: Int, val skipped: Int, val deck: String, val updated: Int = 0)

/** The lesson's options, as the computer's note types have them. */
data class Options(
    val reverse: Boolean = false, // a card the other way too (back → front)
    val typing: Boolean = false, // the answer typed, compared letter by letter
    val dictation: Boolean = false, // the back heard, then written
)

/** The files the cards show, on the phone. */
data class Media(
    val audio: Map<String, File> = emptyMap(), // a back (trimmed) → its mp3
    val pictures: Map<String, File> = emptyMap(), // a card's picture (Card.picture) → its file
    val photos: Map<Int, File> = emptyMap(), // a photo's number → its file: the diagrams
    val lesson: String = "", // the lesson's id: with a label's number, which note a diagram card is
    val frames: Map<Int, List<Double>> = emptyMap(), // a photo's number → its diagram's frame (fractions)
)

/** Where the cards go (AnkiDroid; a fake in the tests). */
interface AnkiTarget {
    fun installed(): Boolean
    fun permitted(): Boolean
    fun deckNames(): List<String>

    /** The cards into their decks, with the files they show; the lesson's notes sent
     * before are updated. */
    fun send(deck: Deck, media: Media = Media(), options: Options = Options()): Sent

    /** The lesson's notes in AnkiDroid (those sent with its tag); null when AnkiDroid can't tell. */
    fun lessonNotes(lesson: String): List<Long>? = null

    /** These notes deleted (their review history with them); how many were. */
    fun delete(notes: List<Long>): Int = 0

    /** AnkiDroid opened to review the deck (and its sub-decks); false when it has no such deck. */
    fun review(deck: String): Boolean = false
}

/**
 * Cards into AnkiDroid, through its API (the "Instant-Add" content provider): our
 * note type, the lesson's deck and sub-decks, the notes. Needs AnkiDroid installed
 * and its READ_WRITE_DATABASE permission granted.
 *
 * Our note types, as the computer's (app/anki.py): text cards (with their picture and
 * the back's sound), diagram labels (the photo, its labels hidden, one asked), texts
 * with gaps (Anki's own cloze: a card per gap number) and multiple choices.
 */
class Anki(private val context: Context) : AnkiTarget {
    private val api = AddContentApi(context)

    override fun installed(): Boolean = AddContentApi.getAnkiDroidPackageName(context) != null

    override fun permitted(): Boolean =
        ContextCompat.checkSelfPermission(context, PERMISSION) == PackageManager.PERMISSION_GRANTED

    /** The decks in AnkiDroid ("" when it can't tell). */
    override fun deckNames(): List<String> =
        if (installed() && permitted()) firstUse { api.deckList?.values?.toList().orEmpty() } else emptyList()

    override fun send(deck: Deck, media: Media, options: Options): Sent = firstUse { add(deck, media, options) }

    override fun lessonNotes(lesson: String): List<Long>? = if (!installed() || !permitted()) null else firstUse {
        context.contentResolver.query(
            FlashCardsContract.Note.CONTENT_URI, arrayOf(FlashCardsContract.Note._ID), "tag:${lessonTag(lesson)}", null, null,
        )?.use { cursor -> buildList { while (cursor.moveToNext()) add(cursor.getLong(0)) } }
            ?: emptyList() // AnkiDroid answers no cursor when the search finds nothing
    }

    /** The deck selected (the API's own way), then AnkiDroid's reviewer on it, as its deck
     * shortcuts open it; AnkiDroid's home on that deck if the reviewer won't open. */
    override fun review(deck: String): Boolean {
        val package_ = AddContentApi.getAnkiDroidPackageName(context) ?: return false
        val did = firstUse { api.deckList?.entries?.firstOrNull { it.value == deck.ifBlank { "Notosaurus" } }?.key } ?: return false
        runCatching {
            context.contentResolver.update(
                FlashCardsContract.Deck.CONTENT_SELECTED_URI, ContentValues().apply { put(FlashCardsContract.Deck.DECK_ID, did) }, null, null,
            )
        }
        val reviewer = Intent(Intent.ACTION_VIEW).setClassName(package_, "com.ichi2.anki.Reviewer").putExtra("deckId", did)
        val home = context.packageManager.getLaunchIntentForPackage(package_) ?: return false
        for (intent in listOf(reviewer, home)) {
            if (runCatching { context.startActivity(intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) }.isSuccess) return true
        }
        return false
    }

    override fun delete(notes: List<Long>): Int = notes.count { id ->
        context.contentResolver.delete(Uri.withAppendedPath(FlashCardsContract.Note.CONTENT_URI, id.toString()), null, null) > 0
    }

    /** AnkiDroid installed but never opened: its first request fails ("storage is not
     * configured") and sets it up; the next ones work. So: once more. */
    private fun <T> firstUse(request: () -> T): T = try {
        request()
    } catch (e: IllegalStateException) {
        if ("storage is not configured" !in e.message.orEmpty()) throw e
        Thread.sleep(1000)
        request()
    }

    /** A note to send: its note type, deck, fields (the first: its key, what tells it's
     * there already), tags. */
    private class Note(val model: Long, val deck: String, val fields: Array<String>, val tags: Set<String>)

    private fun add(deck: Deck, media: Media, options: Options): Sent {
        val added = mutableMapOf<File, String?>() // a file into AnkiDroid once, however many cards show it
        val diagrams = mutableMapOf<Int, File>() // a photo's diagram image, made once
        fun file(f: File, kind: String) = added.getOrPut(f) { media(f, kind) } ?: ""
        val own = listOfNotNull(media.lesson.takeIf { it.isNotEmpty() }?.let(::lessonTag)) // to find the lesson's notes again
        val notes = deck.cards.withIndex().filter { it.value.front.isNotBlank() }.mapNotNull { (i, card) ->
            val name = deckName(deck.deck, card.subdeck)
            val tags = (card.tags.map { it.trim().replace(' ', '_') }.filter { it.isNotEmpty() } + "notosaurus" + own).toSet()
            val sound = media.audio[card.back.trim()]?.let { file(it, "audio") } ?: ""
            val helps = arrayOf(html(card.explanation), html(card.mnemonic))
            // Which note it is, sent again: the card's own id; else its place in the lesson; else its text
            val key = card.id.ifBlank { if (media.lesson.isNotEmpty()) "${media.lesson}:$i" else html(card.front) }
            when {
                card.isChoice() -> {
                    // Not heard: the options are read. Its picture on the question, or with the answer
                    val picture = media.pictures[card.picture]?.let { file(it, "image") } ?: ""
                    Note(
                        choiceModel() ?: error("AnkiDroid refused the multiple-choice note type"), name,
                        arrayOf(
                            key, html(card.front), html(card.back),
                            choicesHtml(card, reveal = false), choicesHtml(card, reveal = true),
                            if (card.pictureOnBack) "" else picture, if (card.pictureOnBack) picture else "", info(card), *helps,
                        ),
                        tags,
                    )
                }
                GAP.containsMatchIn(card.front) -> Note(
                    clozeModel() ?: error("AnkiDroid refused the cloze note type"), name,
                    arrayOf(key, html(card.front), html(card.back), info(card), *helps), tags,
                )
                card.mask != null -> {
                    if (card.back.isBlank()) return@mapNotNull null
                    val photo = media.photos[card.mask.page] ?: return@mapNotNull null
                    val page = deck.cards.mapNotNull { it.mask }.filter { it.page == card.mask.page }
                    // The diagram only (its frame, holding every label), light: shared by its cards
                    val box = crop(media.frames[card.mask.page], page)
                    val image = diagrams.getOrPut(card.mask.page) { diagramImage(photo, box) }
                    Note(
                        diagramModel(options.typing) ?: error("AnkiDroid refused the diagram note type"), name,
                        arrayOf(
                            "${media.lesson}:${card.mask.page}:${card.mask.n}", html(card.front), html(card.back), info(card), sound,
                            file(image, "image"), masksHtml(page, card.mask.n, reveal = false, box), masksHtml(page, card.mask.n, reveal = true, box),
                            *helps,
                        ),
                        tags,
                    )
                }
                else -> {
                    if (card.back.isBlank()) return@mapNotNull null
                    // The picture on the side it belongs to: the question's, or the answer's. A
                    // picture card isn't reversed nor heard (as the computer's)
                    val picture = media.pictures[card.picture]?.let { "${file(it, "image")}<br>" } ?: ""
                    val front = if (card.pictureOnBack || picture.isEmpty()) html(card.front) else picture + html(card.front)
                    val back = if (card.pictureOnBack) picture + html(card.back) else html(card.back)
                    val model = if (picture.isNotEmpty()) textModel(Options(typing = options.typing)) else textModel(options, sound.isNotEmpty())
                    Note(model ?: error("AnkiDroid refused the note type"), name, arrayOf(front, back, info(card), sound, *helps), tags)
                }
            }
        }
        var count = 0
        var updated = 0
        var duplicates = 0
        notes.groupBy { it.model to it.deck }.forEach { (key, group) ->
            val (model, name) = key
            // There already: the same key (first field) in that note type. This lesson's (its
            // tag), or one sent before the lessons had tags: updated; another lesson's: left
            val known = api.findDuplicateNotes(model, group.map { it.fields[0] })
            val fresh = mutableListOf<Note>()
            group.forEachIndexed { i, note ->
                val found = known?.get(i).orEmpty()
                val mine = found.firstOrNull { info -> own.any { it in info.tags } || info.tags.none { it.startsWith(TAG_PREFIX) } }
                when {
                    found.isEmpty() -> fresh += note
                    mine == null -> duplicates++
                    else -> if (!mine.fields.contentEquals(note.fields) || !mine.tags.containsAll(note.tags)) {
                        api.updateNoteFields(mine.id, note.fields)
                        api.updateNoteTags(mine.id, mine.tags + note.tags)
                        updated++
                    }
                }
            }
            if (fresh.isEmpty()) return@forEach
            val did = deckId(name) ?: error("AnkiDroid refused the deck $name")
            count += maxOf(0, api.addNotes(model, did, fresh.map { it.fields }, fresh.map { it.tags }))
        }
        return Sent(count, duplicates, deck.cards.size - notes.size, deck.deck, updated)
    }

    /** The photo as AnkiDroid shows the diagram: cropped to `box` (the whole photo
     * without one), at most CARD_SIDE, as the computer's (diagrams.page_image). Next to
     * the lesson's pictures, named after its content. */
    private fun diagramImage(photo: File, box: List<Double>?): File {
        val bytes = photo.readBytes()
        val key = MessageDigest.getInstance("SHA-1").digest(bytes + box.toString().toByteArray())
            .joinToString("") { "%02x".format(it) }.take(10)
        val image = File(photo.parentFile, "images/diagram-${photo.nameWithoutExtension}-$key.jpg")
        if (image.isFile) return image
        var bitmap = BitmapFactory.decodeByteArray(bytes, 0, bytes.size) ?: return photo
        if (box != null) {
            val (x0, y0, x1, y1) = box
            val left = (x0 * bitmap.width).roundToInt()
            val top = (y0 * bitmap.height).roundToInt()
            val width = ((x1 * bitmap.width).roundToInt() - left).coerceIn(1, bitmap.width - left)
            val height = ((y1 * bitmap.height).roundToInt() - top).coerceIn(1, bitmap.height - top)
            bitmap = Bitmap.createBitmap(bitmap, left, top, width, height)
        }
        val scale = minOf(1.0, CARD_SIDE.toDouble() / maxOf(bitmap.width, bitmap.height))
        if (scale < 1) bitmap = Bitmap.createScaledBitmap(bitmap, (bitmap.width * scale).roundToInt(), (bitmap.height * scale).roundToInt(), true)
        image.parentFile!!.mkdirs()
        image.outputStream().use { bitmap.compress(Bitmap.CompressFormat.JPEG, CARD_QUALITY, it) }
        return image
    }

    /** A file into AnkiDroid's media (read through our FileProvider): how a field shows
     * it ("[sound:…]" for "audio", "<img src=…>" for "image"). */
    private fun media(file: File, kind: String): String? {
        val uri = FileProvider.getUriForFile(context, "${context.packageName}.photos", file)
        AddContentApi.getAnkiDroidPackageName(context)?.let {
            context.grantUriPermission(it, uri, Intent.FLAG_GRANT_READ_URI_PERMISSION)
        }
        return api.addMediaFromUri(uri, file.nameWithoutExtension, kind)
    }

    /** A note type, made the first time (AnkiDroid tells note types apart by name). */
    private fun model(name: String, make: () -> Long?): Long? =
        api.modelList?.entries?.firstOrNull { it.value == name }?.key ?: make()

    /** Text cards, as the computer's "Notosaurus recto/verso": front → back, and with the
     * lesson's options, back → front, the answer typed, the back heard then written (with
     * a voice). Each combination its own note type. */
    private fun textModel(options: Options, heard: Boolean = false): Long? {
        val dictation = options.dictation && heard // nothing to hear without a voice
        val name = "Notosaurus recto/verso" + (if (options.reverse) " + inverse" else "") + variant(options.typing, dictation)
        return model(name) {
            val templates = mutableListOf(Triple("Recto → Verso", "{{Front}}", "{{FrontSide}}<hr id=answer>{{Back}}{{Audio}}$BACK_INFO"))
            if (options.reverse) templates += Triple("Verso → Recto", "{{Back}}{{Audio}}", "{{FrontSide}}<hr id=answer>{{Front}}$BACK_INFO")
            if (options.typing) templates.replaceAll { (n, q, a) -> typed(n, q, a, if (n == "Recto → Verso") "Back" else "Front") }
            if (dictation) {
                val heardCard = "<div class=dictation>🎧</div>{{Audio}}{{type:Back}}"
                templates += Triple("Dictée", heardCard, "$heardCard<hr id=answer>{{Front}}$BACK_INFO")
            }
            api.addNewCustomModel(
                name, arrayOf("Front", "Back", "Info", "Audio", *HELP_FIELDS), templates.map { it.first }.toTypedArray(),
                templates.map { it.second }.toTypedArray(), templates.map { it.third }.toTypedArray(), CSS + PICTURE_CSS, null, null,
            )
        }
    }

    /** Diagram labels: the photo with every label hidden and the question, then the answer
     * with that label shown again. "Id" first: the questions ("What is (1)?") repeat. */
    private fun diagramModel(typing: Boolean): Long? {
        val name = "Notosaurus légendes" + variant(typing, false)
        return model(name) {
            var card = Triple(
                "Schéma",
                """<div class="notosaurus-diagram">{{Image}}{{Masks}}</div><div>{{Front}}</div>""",
                """<div class="notosaurus-diagram">{{Image}}{{AnswerMasks}}</div><div>{{Front}}</div><hr id=answer>{{Back}}{{Audio}}$BACK_INFO""",
            )
            if (typing) card = typed(card.first, card.second, card.third, "Back")
            api.addNewCustomModel(
                name, arrayOf("Id", "Front", "Back", "Info", "Audio", "Image", "Masks", "AnswerMasks", *HELP_FIELDS),
                arrayOf(card.first), arrayOf(card.second), arrayOf(card.third), CSS + DIAGRAM_CSS, null, 1, // sorted by the question
            )
        }
    }

    /** Multiple choice or true/false: the question and its options, then the options again
     * with the right one marked. Plain HTML, no script: the same on every Anki. "Id"
     * first: the card's own (questions may repeat). */
    private fun choiceModel(): Long? = model(CHOICE_MODEL) {
        val picture = "{{#Picture}}<div class=notosaurus-picture>{{Picture}}</div>{{/Picture}}"
        val backPicture = "{{#BackPicture}}<div class=notosaurus-picture>{{BackPicture}}</div>{{/BackPicture}}"
        val question = "$picture<div>{{Question}}</div>"
        api.addNewCustomModel(
            CHOICE_MODEL,
            arrayOf("Id", "Question", "Answer", "Choices", "AnswerChoices", "Picture", "BackPicture", "Info", *HELP_FIELDS),
            arrayOf("QCM"), arrayOf("$question{{Choices}}"), arrayOf("$question<hr id=answer>{{AnswerChoices}}$backPicture$BACK_INFO"),
            CSS + PICTURE_CSS + CHOICE_CSS, null, 1, // sorted by the question
        )
    }

    /** A text with gaps: Anki's own cloze note type (a card per gap number). The API
     * makes standard note types only: this one through AnkiDroid's provider, as the API
     * does, with its type. "Id" first: the text is what gets corrected. */
    private fun clozeModel(): Long? = model(CLOZE_MODEL) {
        val values = ContentValues().apply {
            put(FlashCardsContract.Model.NAME, CLOZE_MODEL)
            put(FlashCardsContract.Model.FIELD_NAMES, listOf("Id", "Text", "Extra", "Info", *HELP_FIELDS).joinToString("\u001f"))
            put(FlashCardsContract.Model.NUM_CARDS, 1)
            put(FlashCardsContract.Model.CSS, CSS + CLOZE_CSS)
            put(FlashCardsContract.Model.SORT_FIELD_INDEX, 1) // sorted by the text
            put(FlashCardsContract.Model.TYPE, 1) // cloze
        }
        val resolver = context.contentResolver
        val made = resolver.insert(FlashCardsContract.Model.CONTENT_URI, values) ?: return@model null
        val template = ContentValues().apply {
            put(FlashCardsContract.CardTemplate.NAME, "Texte à trous")
            put(FlashCardsContract.CardTemplate.QUESTION_FORMAT, "{{cloze:Text}}")
            put(FlashCardsContract.CardTemplate.ANSWER_FORMAT, "{{cloze:Text}}{{#Extra}}<div class=extra>{{Extra}}</div>{{/Extra}}$BACK_INFO")
        }
        resolver.update(Uri.withAppendedPath(Uri.withAppendedPath(made, "templates"), "0"), template, null, null)
        made.lastPathSegment?.toLong()
    }

    private fun deckId(name: String): Long? =
        api.deckList?.entries?.firstOrNull { it.value == name }?.key ?: api.addNewDeck(name)

    private fun deckName(deck: String, subdeck: String) =
        if (subdeck.isBlank()) deck.ifBlank { "Notosaurus" } else "${deck.ifBlank { "Notosaurus" }}::$subdeck"

    companion object {
        const val PERMISSION = AddContentApi.READ_WRITE_PERMISSION
        // The note types' names, as the computer's with " (Android)" (their fields differ:
        // never one of the computer's synced from Anki). Before, "… (app)" and "(prototype)".
        private const val ANDROID = " (Android)"
        val CLOZE_MODEL = "Notosaurus texte à trous$ANDROID"
        val CHOICE_MODEL = "Notosaurus QCM$ANDROID"
        fun variant(typing: Boolean, dictation: Boolean) =
            (if (typing) " à taper" else "") + (if (dictation) " + dictée" else "") + ANDROID

        // The tag of every note sent for a lesson (as the computer's): its notes found again
        const val TAG_PREFIX = "notosaurus::"
        fun lessonTag(lesson: String) = "$TAG_PREFIX$lesson"

        // On the back, under the info: the helps asked for at generation, each when written
        private val HELP_FIELDS = arrayOf("Explanation", "Mnemonic")
        private const val BACK_INFO = "{{#Info}}<div class=info>{{Info}}</div>{{/Info}}" +
            "{{#Explanation}}<div class=notosaurus-help>💬 {{Explanation}}</div>{{/Explanation}}" +
            "{{#Mnemonic}}<div class=notosaurus-help>🧠 {{Mnemonic}}</div>{{/Mnemonic}}"

        /** The card asking to type `field`: a box on the question, AnkiDroid's letter by letter
         * comparison in its place on the answer (which repeats the question: not {{FrontSide}},
         * the box twice). */
        private fun typed(name: String, question: String, answer: String, field: String) =
            Triple(name, "$question{{type:$field}}", answer.replace("{{FrontSide}}", question).replaceFirst("{{$field}}", "{{type:$field}}"))

        /** A card's text as an AnkiDroid field: escaped, its line breaks kept. */
        fun html(text: String) = escape(text.trim())

        /** The Info field: the card's info, then its "did you know" (💡, in italics). */
        fun info(card: Card): String {
            val fact = card.funFact.trim()
            return html(card.info) + if (fact.isEmpty()) "" else """<div style="margin-top:8px;font-style:italic">💡 ${html(fact)}</div>"""
        }
        private val GAP = Regex("""\{\{c\d+::""")
        private const val CSS = """.card { font-family: sans-serif; font-size: 24px; text-align: center; }
.info { margin-top: 12px; font-size: 18px; color: #666; }
.card img { max-width: 100%; height: auto; }
.dictation { font-size: 40px; }
.notosaurus-help {
  max-width: 32em; margin: 10px auto 0; padding: 4px 10px; border-left: 3px solid #8bb8c4;
  font-size: 18px; color: #555; text-align: left;
}
.nightMode .notosaurus-help { color: #bbb; }"""

        // As the computer's (app/anki.py)
        private const val DIAGRAM_CSS = """
.notosaurus-diagram { position: relative; display: inline-block; max-width: 100%; line-height: 0; }
.notosaurus-diagram img { display: block; }
.notosaurus-mask {
  position: absolute; box-sizing: border-box; display: flex; align-items: center; justify-content: center;
  overflow: hidden; line-height: 1; font-size: 13px; font-weight: 700;
  background: #ffe08a; border: 2px solid #c77700; border-radius: 3px; color: #3d2b00;
}
.notosaurus-mask.target { background: #ff7a59; border-color: #b3261e; color: #fff; }
.notosaurus-mask.revealed { background: transparent; border: 3px solid #1b873f; }"""
        private const val PICTURE_CSS = """
.notosaurus-picture img { max-width: min(100%, 320px); max-height: 50vh; border-radius: 12px; }"""
        private const val CHOICE_CSS = """
.notosaurus-choices {
  display: inline-block; margin: 12px auto 0; padding-left: 1.8em; text-align: left; list-style: upper-alpha;
}
.notosaurus-choices li { margin: 6px 0; }
.notosaurus-choices li.right { color: #1b873f; font-weight: 700; }
.notosaurus-choices li.right::after { content: " ✔"; }"""
        private const val CLOZE_CSS = """
.cloze { font-weight: 700; color: #0b5cad; }
.extra { margin-top: 12px; }"""

        /** A multiple-choice or true/false card, as the computer's (cards.is_choice): a
         * right answer (its back) and wrong ones; a gap text or a diagram label stays one. */
        fun Card.isChoice() = front.isNotBlank() && back.isNotBlank() && choices.any { it.isNotBlank() } &&
            mask == null && !GAP.containsMatchIn(front)

        /** The options as AnkiDroid shows them: always the same order for a card (its
         * question and answer, review after review), the right one anywhere; two
         * options (true/false): alphabetical. `reveal`: the right one marked. */
        fun choicesHtml(card: Card, reveal: Boolean): String {
            val right = card.back.trim()
            val options = (listOf(card.back) + card.choices).map { it.trim() }.filter { it.isNotEmpty() }.distinct().toMutableList()
            if (options.size == 2) {
                options.sortBy { it.lowercase() }
            } else {
                val seed = MessageDigest.getInstance("SHA-256").digest(card.front.trim().toByteArray()).fold(0L) { a, b -> a * 31 + b }
                options.shuffle(Random(seed))
            }
            val items = options.joinToString("") { option ->
                val mark = if (!reveal) "" else if (option == right) " class=\"right\"" else " class=\"wrong\""
                "<li$mark>${escape(option)}</li>"
            }
            return "<ol class=\"notosaurus-choices\">$items</ol>"
        }

        private fun escape(text: String) =
            text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\"", "&quot;").replace("\n", "<br>")

        // The diagram in AnkiDroid: enough to read it, light to sync (the computer's)
        private const val CARD_SIDE = 1000
        private const val CARD_QUALITY = 75
        private const val CROP_MARGIN = 0.03 // around the diagram and its masks, a fraction of the photo

        /** What AnkiDroid shows of a photo, as the computer's (diagrams.crop): the
         * diagram's frame stretched to hold every mask with a margin, so a frame never
         * cuts a label. No frame: null, the whole photo. */
        fun crop(frame: List<Double>?, masks: List<Mask>): List<Double>? {
            if (frame == null) return null
            val m = CROP_MARGIN
            val boxes = listOf(frame) + masks.map { listOf(it.box[0] - m, it.box[1] - m, it.box[2] + m, it.box[3] + m) }
            return listOf(boxes.minOf { it[0] }, boxes.minOf { it[1] }, boxes.maxOf { it[2] }, boxes.maxOf { it[3] })
                .map { BigDecimal(it.coerceIn(0.0, 1.0)).setScale(4, RoundingMode.HALF_EVEN).toDouble() }
        }

        /** The masks over a diagram, in % of the image (cropped to `box`), as the
         * computer's (diagrams.masks_html): every label hidden behind its number,
         * `target` highlighted (question) or shown again (answer). */
        fun masksHtml(masks: List<Mask>, target: Int, reveal: Boolean, box: List<Double>? = null): String = masks.sortedBy { it.n }.joinToString("") { mask ->
            fun round2(v: Double) = BigDecimal(v).setScale(2, RoundingMode.HALF_EVEN).toDouble() // as Python's round(v, 2)
            val (cx, cy, cw, ch) = box?.let { listOf(it[0], it[1], it[2] - it[0], it[3] - it[1]) } ?: listOf(0.0, 0.0, 1.0, 1.0)
            val relative = listOf((mask.box[0] - cx) / cw, (mask.box[1] - cy) / ch, (mask.box[2] - cx) / cw, (mask.box[3] - cy) / ch)
            val (x0, y0, x1, y1) = relative.map { round2(it * 100) }
            val style = "left:$x0%;top:$y0%;width:${round2(x1 - x0)}%;height:${round2(y1 - y0)}%"
            val (kind, text) = when {
                mask.n != target -> "" to "(${mask.n})"
                reveal -> "revealed" to ""
                else -> "target" to "(${mask.n})"
            }
            """<div class="${listOf("notosaurus-mask", kind).filter { it.isNotEmpty() }.joinToString(" ")}" style="$style">$text</div>"""
        }
    }
}
