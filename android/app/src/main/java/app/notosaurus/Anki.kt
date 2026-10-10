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

/** What was done with the cards: added, already in AnkiDroid, left out (a diagram card
 * without its photo). */
data class Sent(val added: Int, val duplicates: Int, val skipped: Int, val deck: String)

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

    /** The cards into their decks, with the files they show. */
    fun send(deck: Deck, media: Media = Media()): Sent
}

/**
 * Cards into AnkiDroid, through its API (the "Instant-Add" content provider): our
 * note type, the lesson's deck and sub-decks, the notes. Needs AnkiDroid installed
 * and its READ_WRITE_DATABASE permission granted.
 *
 * Our note types, as the computer's (app/anki.py): text cards (with their picture and
 * the back's sound), diagram labels (the photo, its labels hidden, one asked) and texts
 * with gaps (Anki's own cloze: a card per gap number).
 */
class Anki(private val context: Context) : AnkiTarget {
    private val api = AddContentApi(context)

    override fun installed(): Boolean = AddContentApi.getAnkiDroidPackageName(context) != null

    override fun permitted(): Boolean =
        ContextCompat.checkSelfPermission(context, PERMISSION) == PackageManager.PERMISSION_GRANTED

    /** The decks in AnkiDroid ("" when it can't tell). */
    override fun deckNames(): List<String> =
        if (installed() && permitted()) firstUse { api.deckList?.values?.toList().orEmpty() } else emptyList()

    override fun send(deck: Deck, media: Media): Sent = firstUse { add(deck, media) }

    /** AnkiDroid installed but never opened: its first request fails ("storage is not
     * configured") and sets it up; the next ones work. So: once more. */
    private fun <T> firstUse(request: () -> T): T = try {
        request()
    } catch (e: IllegalStateException) {
        if ("storage is not configured" !in e.message.orEmpty()) throw e
        Thread.sleep(1000)
        request()
    }

    /** A note to add: its note type, deck, fields (the first: what tells it's there already), tags. */
    private class Note(val model: Long, val deck: String, val fields: Array<String>, val tags: Set<String>)

    private fun add(deck: Deck, media: Media): Sent {
        val added = mutableMapOf<File, String?>() // a file into AnkiDroid once, however many cards show it
        val diagrams = mutableMapOf<Int, File>() // a photo's diagram image, made once
        fun file(f: File, kind: String) = added.getOrPut(f) { media(f, kind) } ?: ""
        val notes = deck.cards.filter { it.front.isNotBlank() }.mapNotNull { card ->
            val name = deckName(deck.deck, card.subdeck)
            val tags = (card.tags.map { it.replace(' ', '_') } + "notosaurus").toSet()
            val sound = media.audio[card.back.trim()]?.let { file(it, "audio") } ?: ""
            when {
                GAP.containsMatchIn(card.front) -> Note(
                    clozeModel() ?: error("AnkiDroid refused the cloze note type"), name,
                    arrayOf(card.front, card.back, card.info), tags,
                )
                card.mask != null -> {
                    val photo = media.photos[card.mask.page] ?: return@mapNotNull null
                    val page = deck.cards.mapNotNull { it.mask }.filter { it.page == card.mask.page }
                    // The diagram only (its frame, holding every label), light: shared by its cards
                    val box = crop(media.frames[card.mask.page], page)
                    val image = diagrams.getOrPut(card.mask.page) { diagramImage(photo, box) }
                    Note(
                        diagramModel() ?: error("AnkiDroid refused the diagram note type"), name,
                        arrayOf(
                            "${media.lesson}:${card.mask.page}:${card.mask.n}", card.front, card.back, card.info, sound,
                            file(image, "image"), masksHtml(page, card.mask.n, reveal = false, box), masksHtml(page, card.mask.n, reveal = true, box),
                        ),
                        tags,
                    )
                }
                else -> {
                    // The picture on the side it belongs to: the question's, or the answer's
                    val picture = media.pictures[card.picture]?.let { "${file(it, "image")}<br>" } ?: ""
                    val front = if (card.pictureOnBack) card.front else picture + card.front
                    val back = if (card.pictureOnBack) picture + card.back else card.back
                    Note(model() ?: error("AnkiDroid refused the note type"), name, arrayOf(front, back, card.info, sound), tags)
                }
            }
        }
        var count = 0
        var duplicates = 0
        notes.groupBy { it.model to it.deck }.forEach { (key, group) ->
            val (model, name) = key
            // Already there: the same first field in that note type (the API's duplicate check)
            val known = api.findDuplicateNotes(model, group.map { it.fields[0] })
            val fresh = group.filterIndexed { i, _ -> known?.get(i).isNullOrEmpty() }
            duplicates += group.size - fresh.size
            if (fresh.isEmpty()) return@forEach
            val did = deckId(name) ?: error("AnkiDroid refused the deck $name")
            count += maxOf(0, api.addNotes(model, did, fresh.map { it.fields }, fresh.map { it.tags }))
        }
        return Sent(count, duplicates, deck.cards.size - notes.size, deck.deck)
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

    /** Diagram labels: the photo with every label hidden and the question, then the answer
     * with that label shown again. "Id" first: the questions ("What is (1)?") repeat. */
    private fun diagramModel(): Long? =
        api.modelList?.entries?.firstOrNull { it.value == DIAGRAM_MODEL }?.key
            ?: api.addNewCustomModel(
                DIAGRAM_MODEL,
                arrayOf("Id", "Front", "Back", "Info", "Audio", "Image", "Masks", "AnswerMasks"),
                arrayOf("Card 1"),
                arrayOf("""<div class="notosaurus-diagram">{{Image}}{{Masks}}</div><div>{{Front}}</div>"""),
                arrayOf(
                    """<div class="notosaurus-diagram">{{Image}}{{AnswerMasks}}</div><div>{{Front}}</div>""" +
                        "<hr id=answer>{{Back}}{{#Info}}<div class=info>{{Info}}</div>{{/Info}}{{Audio}}",
                ),
                CSS + DIAGRAM_CSS,
                null,
                1, // sorted by the question
            )

    /** A text with gaps: Anki's own cloze note type (a card per gap number). The API
     * makes standard note types only: this one through AnkiDroid's provider, as the API
     * does, with its type. */
    private fun clozeModel(): Long? {
        api.modelList?.entries?.firstOrNull { it.value == CLOZE_MODEL }?.key?.let { return it }
        val values = ContentValues().apply {
            put(FlashCardsContract.Model.NAME, CLOZE_MODEL)
            put(FlashCardsContract.Model.FIELD_NAMES, listOf("Text", "Extra", "Info").joinToString("\u001f"))
            put(FlashCardsContract.Model.NUM_CARDS, 1)
            put(FlashCardsContract.Model.CSS, CSS + CLOZE_CSS)
            put(FlashCardsContract.Model.TYPE, 1) // cloze
        }
        val resolver = context.contentResolver
        val model = resolver.insert(FlashCardsContract.Model.CONTENT_URI, values) ?: return null
        val template = ContentValues().apply {
            put(FlashCardsContract.CardTemplate.NAME, "Cloze")
            put(FlashCardsContract.CardTemplate.QUESTION_FORMAT, "{{cloze:Text}}")
            put(
                FlashCardsContract.CardTemplate.ANSWER_FORMAT,
                "{{cloze:Text}}{{#Extra}}<div class=extra>{{Extra}}</div>{{/Extra}}{{#Info}}<div class=info>{{Info}}</div>{{/Info}}",
            )
        }
        resolver.update(Uri.withAppendedPath(Uri.withAppendedPath(model, "templates"), "0"), template, null, null)
        return model.lastPathSegment?.toLong()
    }

    private fun model(): Long? =
        api.modelList?.entries?.firstOrNull { it.value == MODEL }?.key
            ?: api.addNewCustomModel(
                MODEL,
                arrayOf("Front", "Back", "Info", "Audio"),
                arrayOf("Card 1"),
                arrayOf("{{Front}}"),
                arrayOf("{{FrontSide}}<hr id=answer>{{Back}}{{#Info}}<div class=info>{{Info}}</div>{{/Info}}{{Audio}}"),
                CSS,
                null,
                null,
            )

    private fun deckId(name: String): Long? =
        api.deckList?.entries?.firstOrNull { it.value == name }?.key ?: api.addNewDeck(name)

    private fun deckName(deck: String, subdeck: String) =
        if (subdeck.isBlank()) deck.ifBlank { "Notosaurus" } else "${deck.ifBlank { "Notosaurus" }}::$subdeck"

    companion object {
        const val PERMISSION = AddContentApi.READ_WRITE_PERMISSION
        const val MODEL = "Notosaurus (app)" // with the back's sound (before: "Notosaurus (prototype)")
        const val DIAGRAM_MODEL = "Notosaurus légendes (app)"
        const val CLOZE_MODEL = "Notosaurus texte à trous (app)"
        private val GAP = Regex("""\{\{c\d+::""")
        private const val CSS = """.card { font-family: sans-serif; font-size: 24px; text-align: center; }
.info { margin-top: 12px; font-size: 18px; color: #666; }
.card img { max-width: 100%; height: auto; }"""

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
        private const val CLOZE_CSS = """
.cloze { font-weight: 700; color: #0b5cad; }
.extra { margin-top: 12px; }"""

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
