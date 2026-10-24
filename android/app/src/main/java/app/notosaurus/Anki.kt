package app.notosaurus

import android.content.ContentValues
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.util.Log
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
data class Sent(
    val added: Int,
    val duplicates: Int,
    val skipped: Int,
    val deck: String,
    val updated: Int = 0,
    val moved: Int = 0, // the lesson's notes moved to the deck they go to now (its deck changed)
    val notes: Map<String, Long> = emptyMap(), // a card's id → its note: kept with the lesson
)

/** The lesson's options, as the computer's note types have them. */
data class Options(
    val reverse: Boolean = false, // a card the other way too (back → front)
    val typing: Boolean = false, // the answer typed, compared letter by letter
    val dictation: Boolean = false, // the back heard, then written
    val dictationOnly: Boolean = false, // that card alone (no front → back card)
    val move: Boolean = true, // a note sent before, now in another deck: its cards moved there
)

/** The files the cards show, on the phone. */
data class Media(
    val audio: Map<String, File> = emptyMap(), // a back (trimmed) → its mp3
    val pictures: Map<String, File> = emptyMap(), // a card's picture (Card.picture) → its file
    val photos: Map<Int, File> = emptyMap(), // a photo's number → its file: the diagrams
    val lesson: String = "", // the lesson's id: with a label's number, which note a diagram card is
    val frames: Map<Int, List<Double>> = emptyMap(), // a photo's number → its diagram's frame (fractions)
    val sentBefore: Map<String, Long> = emptyMap(), // a card's id → its note at the lesson's last send
    val extraTags: Map<String, Set<String>> = emptyMap(), // a card's id → the tags of the tests it is in (Exams.kt)
)

/** A note of a lesson no card has any more: what it shows first (plain), its deck. */
data class Leftover(val id: Long, val text: String, val deck: String)

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

    /** The lesson's notes (its tag) that none of its cards updated (`keep`: those they
     * did), never another lesson's too: left from cards deleted or remade. */
    fun leftovers(lesson: String, keep: Set<Long>): List<Leftover> = emptyList()

    /** AnkiDroid opened to review the deck (and its sub-decks); false when it has no such deck. */
    fun review(deck: String): Boolean = false

    /** Tags put on notes and taken off others ({tag: note ids}): a test's tag following its
     * lessons (Exams.retagging); false when AnkiDroid couldn't be asked. */
    fun retag(add: Map<String, Set<Long>>, remove: Map<String, Set<Long>>): Boolean = true
    /** AnkiDroid opened, on its own screen (the page's "Open AnkiDroid"); false when it can't be. */
    fun open(): Boolean = false

    /** AnkiDroid's card browser opened on a search (a test's cards): its menu's "Create filtered
     * deck" takes the search from there, as no other app may make one; false when it can't be. */
    fun browse(search: String): Boolean = false

    /** AnkiDroid's own icon as installed on this phone (a PNG), for the page's "Open AnkiDroid":
     * read from the installed app, never shipped with Notosaurus; null when it isn't installed. */
    fun icon(): ByteArray? = null
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
    private val noteTypes by lazy { NoteTypes.parse(context.assets.open("web/note-types.json").use { it.readBytes().decodeToString() }) }

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

    override fun browse(search: String): Boolean {
        val package_ = AddContentApi.getAnkiDroidPackageName(context) ?: return false
        val link = Uri.parse(browserLink(search, System.currentTimeMillis()))
        val intent = Intent(Intent.ACTION_VIEW, link).setPackage(package_).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        return runCatching { context.startActivity(intent) }.isSuccess
    }

    override fun open(): Boolean {
        val package_ = AddContentApi.getAnkiDroidPackageName(context) ?: return false
        val home = context.packageManager.getLaunchIntentForPackage(package_) ?: return false
        // Its own task: Android's Back from AnkiDroid's first screen comes back here
        return runCatching { context.startActivity(home.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) }.isSuccess
    }

    override fun icon(): ByteArray? {
        val package_ = AddContentApi.getAnkiDroidPackageName(context) ?: return null
        return runCatching {
            val drawable = context.packageManager.getApplicationIcon(package_)
            val size = ICON_PX
            val bitmap = Bitmap.createBitmap(size, size, Bitmap.Config.ARGB_8888)
            drawable.setBounds(0, 0, size, size)
            drawable.draw(android.graphics.Canvas(bitmap))
            java.io.ByteArrayOutputStream().also { bitmap.compress(Bitmap.CompressFormat.PNG, 100, it) }.toByteArray()
        }.getOrNull()
    }

    override fun leftovers(lesson: String, keep: Set<Long>): List<Leftover> {
        val ids = lessonNotes(lesson).orEmpty().filter { it !in keep }
        val decks = api.deckList.orEmpty()
        return ids.mapNotNull { id ->
            val note = Uri.withAppendedPath(FlashCardsContract.Note.CONTENT_URI, id.toString())
            val (text, tags) = context.contentResolver.query(
                note, arrayOf(FlashCardsContract.Note.SFLD, FlashCardsContract.Note.TAGS), null, null, null,
            )?.use { c -> if (c.moveToFirst()) c.getString(0).orEmpty() to c.getString(1).orEmpty() else null } ?: return@mapNotNull null
            if (tags.split(' ').any { it.startsWith(TAG_PREFIX) && it != lessonTag(lesson) }) return@mapNotNull null
            val did = context.contentResolver.query(
                Uri.withAppendedPath(note, "cards"), arrayOf(FlashCardsContract.Card.DECK_ID), null, null, null,
            )?.use { c -> if (c.moveToFirst()) c.getLong(0) else null }
            val plain = text.replace(Regex("<[^>]+>"), " ").split(Regex("\\s+")).filter { it.isNotEmpty() }.joinToString(" ")
            Leftover(id, if (plain.length <= LEFTOVER_TEXT) plain else plain.take(LEFTOVER_TEXT - 1) + "…", decks[did].orEmpty())
        }
    }

    override fun delete(notes: List<Long>): Int = notes.count { id ->
        context.contentResolver.delete(Uri.withAppendedPath(FlashCardsContract.Note.CONTENT_URI, id.toString()), null, null) > 0
    }

    override fun retag(add: Map<String, Set<Long>>, remove: Map<String, Set<Long>>): Boolean {
        if (!installed() || !permitted()) return false
        return runCatching {
            firstUse {
                val wanted = mutableMapOf<Long, MutableSet<String>>() // a note: the tags it gets, those it loses
                val dropped = mutableMapOf<Long, MutableSet<String>>()
                add.forEach { (tag, ids) -> ids.forEach { wanted.getOrPut(it) { mutableSetOf() } += tag } }
                remove.forEach { (tag, ids) -> ids.forEach { dropped.getOrPut(it) { mutableSetOf() } += tag } }
                for (id in wanted.keys + dropped.keys) {
                    val note = api.getNote(id) ?: continue // gone from AnkiDroid: nothing to tag
                    val tags = (note.tags - dropped[id].orEmpty()) + wanted[id].orEmpty()
                    if (tags != note.tags) api.updateNoteTags(id, tags)
                }
            }
        }.isSuccess
    }

    /** AnkiDroid installed but never opened: its first request fails ("storage is not
     * configured") and sets it up; the next ones work. So: once more. */
    private fun <T> firstUse(request: () -> T): T {
        // Setting its storage up takes AnkiDroid a moment, more on a slow phone: a few tries (~7 s)
        for (wait in FIRST_USE_WAITS) {
            try {
                return request()
            } catch (e: IllegalStateException) {
                if ("storage is not configured" !in e.message.orEmpty()) throw e
                Thread.sleep(wait)
            }
        }
        return request()
    }

    /** A note to send: its note type, deck, fields (the first: its key, what tells it's
     * there already), tags. */
    private class Note(val model: Long, val deck: String, val fields: Array<String>, val tags: Set<String>, val card: String)

    private fun add(deck: Deck, media: Media, options: Options): Sent {
        everyCurrent()
        // The files the cards show: a mark in the fields until a note needs them, then into
        // AnkiDroid once, however many cards show them; not again for a note showing them already
        val files = mutableListOf<Pair<File, String>>()
        val added = mutableMapOf<Int, String>()
        val diagrams = mutableMapOf<Int, File>() // a photo's diagram image, made once
        fun index(f: File, kind: String) = files.indexOf(f to kind).takeIf { it >= 0 } ?: files.size.also { files += f to kind }
        fun file(f: File, kind: String) = "$FILE_MARK${index(f, kind)}$FILE_MARK"
        // A file deciding the note's type (a picture card's, a dictation's sound): into AnkiDroid
        // now unless the card's note from the last send shows it, so that one AnkiDroid refuses
        // makes the card it would be without it (text, not heard): ""
        fun deciding(f: File, kind: String, key: String): String {
            val before = media.sentBefore[key]?.let { api.getNote(it) }
            if (before != null && shown(before.fields, f, kind) != null) return file(f, kind)
            return if (added.getOrPut(index(f, kind)) { media(f, kind) ?: "" }.isEmpty()) "" else file(f, kind)
        }
        fun withFiles(fields: Array<String>, there: Array<String>?): Array<String> = Array(fields.size) { k ->
            FILE_REF.replace(fields[k]) { mark ->
                val i = mark.groupValues[1].toInt()
                val (f, kind) = files[i]
                there?.let { shown(it, f, kind) } ?: added.getOrPut(i) { media(f, kind) ?: "" }
            }
        }
        val own = listOfNotNull(media.lesson.takeIf { it.isNotEmpty() }?.let(::lessonTag)) // to find the lesson's notes again
        val notes = deck.cards.withIndex().filter { it.value.front.isNotBlank() }.mapNotNull { (i, card) ->
            val name = deckName(deck.deck, card.subdeck)
            val tags = (card.tags.map { it.trim().replace(' ', '_') }.filter { it.isNotEmpty() } + "notosaurus" + own + media.extraTags[card.id].orEmpty()).toSet()
            val common = mapOf("Info" to info(card), "Explanation" to html(card.explanation), "Mnemonic" to html(card.mnemonic))
            // Which note it is, sent again: the card's own id; else its place in the lesson; else its text
            val key = card.id.ifBlank { if (media.lesson.isNotEmpty()) "${media.lesson}:$i" else html(card.front) }
            val sound by lazy { media.audio[Speech.spoken(card, options.dictation)]?.let { if (options.dictation) deciding(it, "audio", key) else file(it, "audio") }.orEmpty() }
            fun note(variant: String, fields: Map<String, String>): Note {
                val type = noteTypes[variant]
                return Note(model(type) ?: error("AnkiDroid refused the note type ${type.androidName}"), name, type.values(common + fields), tags, key)
            }
            // Only for the cards showing them (lazy): no file into AnkiDroid that no note shows
            val picture by lazy { media.pictures[card.picture]?.let { if (card.isChoice()) file(it, "image") else deciding(it, "image", key) }.orEmpty() }
            when {
                card.isChoice() -> note( // not heard: the options are read
                    "choice",
                    mapOf(
                        "Id" to key, "Question" to html(card.front), "Answer" to html(card.back),
                        "Choices" to choicesHtml(card, reveal = false), "AnswerChoices" to choicesHtml(card, reveal = true),
                        (if (card.pictureOnBack) "BackPicture" else "Picture") to picture,
                    ),
                )
                GAP.containsMatchIn(card.front) -> note("cloze", mapOf("Id" to key, "Text" to html(card.front), "Extra" to html(card.back)))
                card.mask != null -> {
                    if (card.back.isBlank()) return@mapNotNull null
                    val photo = media.photos[card.mask.page] ?: return@mapNotNull null
                    val page = deck.cards.mapNotNull { it.mask }.filter { it.page == card.mask.page }
                    // The diagram only (its frame, holding every label), light: shared by its cards
                    val box = crop(media.frames[card.mask.page], page)
                    val image = diagrams.getOrPut(card.mask.page) { diagramImage(photo, box) }
                    note(
                        "diagram" + if (options.typing) "+typing" else "",
                        mapOf(
                            "Id" to "${media.lesson}:${card.mask.page}:${card.mask.n}", "Front" to html(card.front), "Back" to html(card.back),
                            "Audio" to sound, "Image" to file(image, "image"),
                            "Masks" to masksHtml(page, card.mask.n, reveal = false, box), "AnswerMasks" to masksHtml(page, card.mask.n, reveal = true, box),
                        ),
                    )
                }
                card.back.isBlank() -> null
                // A picture card: the picture on the question, or with the answer; not reversed nor heard
                picture.isNotEmpty() -> note(
                    "picture" + (if (card.pictureOnBack) "+back" else "") + (if (options.typing) "+typing" else ""),
                    mapOf("Id" to key, "Front" to html(card.front), "Back" to html(card.back), "Audio" to sound, "Picture" to picture),
                )
                else -> {
                    val heard = options.dictation && sound.isNotEmpty() // nothing to hear without a voice
                    val variant = if (heard && options.dictationOnly) listOf("text", "dictation-only")
                    else listOf("text") + listOfNotNull("reverse".takeIf { options.reverse }, "typing".takeIf { options.typing }, "dictation".takeIf { heard })
                    note(variant.joinToString("+"), mapOf("Front" to html(card.front), "Back" to html(card.back), "Audio" to sound))
                }
            }
        }
        var count = 0
        var updated = 0
        var moved = 0
        var duplicates = 0
        val sent = mutableMapOf<String, Long>()
        notes.groupBy { it.model to it.deck }.forEach { (key, group) ->
            val (model, name) = key
            val did by lazy { deckId(name) ?: error("AnkiDroid refused the deck $name") }
            // The card's own note from the last send (its front may have been corrected): updated
            // there, history kept; none (deleted in AnkiDroid, other options), another lesson's: as below
            val rest = group.filter { note ->
                val id = media.sentBefore[note.card] ?: return@filter true
                val there = api.getNote(id)?.takeIf { noteModel(id) == model } ?: return@filter true
                if (there.tags.any { it.startsWith(TAG_PREFIX) && it !in own }) return@filter true
                val fields = withFiles(note.fields, there.fields)
                if (!there.fields.contentEquals(fields) || !there.tags.containsAll(note.tags)) {
                    api.updateNoteFields(id, fields)
                    api.updateNoteTags(id, there.tags + note.tags)
                    updated++
                }
                if (options.move && moveCards(id, did)) moved++
                sent[note.card] = id
                false
            }
            if (rest.isEmpty()) return@forEach
            // There already: the same key (first field) in that note type. This lesson's (its
            // tag), or one sent before the lessons had tags: updated; another lesson's: left
            val known = api.findDuplicateNotes(model, rest.map { it.fields[0] })
            val fresh = mutableListOf<Note>()
            rest.forEachIndexed { i, note ->
                val found = known?.get(i).orEmpty()
                val mine = found.firstOrNull { info -> own.any { it in info.tags } || info.tags.none { it.startsWith(TAG_PREFIX) } }
                when {
                    found.isEmpty() -> fresh += note
                    mine == null -> duplicates++
                    else -> {
                        val fields = withFiles(note.fields, mine.fields)
                        if (!mine.fields.contentEquals(fields) || !mine.tags.containsAll(note.tags)) {
                            api.updateNoteFields(mine.id, fields)
                            api.updateNoteTags(mine.id, mine.tags + note.tags)
                            updated++
                        }
                        // The lesson's deck (or the card's part) changed: its cards follow, history kept
                        if (options.move && moveCards(mine.id, did)) moved++
                        sent[note.card] = mine.id
                    }
                }
            }
            if (fresh.isEmpty()) return@forEach
            count += maxOf(0, api.addNotes(model, did, fresh.map { withFiles(it.fields, null) }, fresh.map { it.tags }))
            // Their ids (addNotes gives only how many): this lesson's notes with their keys
            api.findDuplicateNotes(model, fresh.map { it.fields[0] })?.let { added ->
                fresh.forEachIndexed { i, note ->
                    added.get(i)?.firstOrNull { info -> own.any { it in info.tags } }?.let { sent[note.card] = it.id }
                }
            }
        }
        return Sent(count, duplicates, deck.cards.size - notes.size, deck.deck, updated, moved, sent)
    }

    /** The note type of a note; null when it isn't in AnkiDroid any more. */
    private fun noteModel(note: Long): Long? = context.contentResolver.query(
        Uri.withAppendedPath(FlashCardsContract.Note.CONTENT_URI, note.toString()), arrayOf(FlashCardsContract.Note.MID), null, null, null,
    )?.use { cursor -> if (cursor.moveToFirst()) cursor.getLong(0) else null }

    /** The note's cards moved into the deck `did` (AnkiDroid lets a card's deck be changed,
     * nothing else: its review history stays); whether any was elsewhere. */
    private fun moveCards(note: Long, did: Long): Boolean {
        val cards = Uri.withAppendedPath(Uri.withAppendedPath(FlashCardsContract.Note.CONTENT_URI, note.toString()), "cards")
        val elsewhere = context.contentResolver.query(
            cards, arrayOf(FlashCardsContract.Card.CARD_ORD, FlashCardsContract.Card.DECK_ID), null, null, null,
        )?.use { cursor ->
            buildList { while (cursor.moveToNext()) if (cursor.getLong(1) != did) add(cursor.getInt(0)) }
        }.orEmpty()
        val values = ContentValues().apply { put(FlashCardsContract.Card.DECK_ID, did) }
        elsewhere.forEach { ord -> context.contentResolver.update(Uri.withAppendedPath(cards, ord.toString()), values, null, null) }
        return elsewhere.isNotEmpty()
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

    /** How a note's fields show `file` already ("[sound:…]", "<img src=…>"): AnkiDroid names its
     * copy after ours, a number added ("ab12_8455….mp3"), and ours are named after their
     * content (Speech, Pictures, diagramImage); null when none does. That naming is AnkiDroid's,
     * not documented: AnkiDroidTest.theBacksSoundIntoAnkiDroidsMedia and diagramLabelsAndGaps
     * check it (a version naming copies otherwise: they fail, every send copying the files again). */
    private fun shown(fields: Array<String>, file: File, kind: String): String? {
        val name = Regex.escape(file.nameWithoutExtension) + "(?:_\\d+)?\\." + Regex.escape(file.extension)
        val ref = Regex(if (kind == "audio") "\\[sound:$name]" else "<img src=\"$name\"[^>]*>")
        return fields.firstNotNullOfOrNull { ref.find(it)?.value }
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

    /** The note type in AnkiDroid, made the first time (AnkiDroid tells note types apart by
     * name), else brought up to date (current). A cloze note type through AnkiDroid's
     * provider, as its API makes the others, with its type: the API makes standard ones only. */
    private fun model(type: NoteType): Long? {
        api.modelList?.entries?.firstOrNull { it.value == type.androidName }?.key?.let { id ->
            // its look an older one's: the cards still go in, the failure said in the log
            runCatching { current(id, type) }.onFailure { Log.w(TAG, "note type ${type.androidName} not brought up to date", it) }
            return id
        }
        val cards = type.cards
        if (!type.cloze) {
            return api.addNewCustomModel(
                type.androidName, type.androidFields.toTypedArray(), cards.map { it.name }.toTypedArray(),
                cards.map { it.front }.toTypedArray(), cards.map { it.back }.toTypedArray(), type.signedCss, null, type.sortField,
            )
        }
        val values = ContentValues().apply {
            put(FlashCardsContract.Model.NAME, type.androidName)
            put(FlashCardsContract.Model.FIELD_NAMES, type.androidFields.joinToString("\u001f"))
            put(FlashCardsContract.Model.NUM_CARDS, 1)
            put(FlashCardsContract.Model.CSS, type.signedCss)
            put(FlashCardsContract.Model.SORT_FIELD_INDEX, type.sortField)
            put(FlashCardsContract.Model.TYPE, 1) // cloze
        }
        val resolver = context.contentResolver
        val made = resolver.insert(FlashCardsContract.Model.CONTENT_URI, values) ?: return null
        val template = ContentValues().apply {
            put(FlashCardsContract.CardTemplate.NAME, cards[0].name)
            put(FlashCardsContract.CardTemplate.QUESTION_FORMAT, cards[0].front)
            put(FlashCardsContract.CardTemplate.ANSWER_FORMAT, cards[0].back)
        }
        resolver.update(Uri.withAppendedPath(Uri.withAppendedPath(made, "templates"), "0"), template, null, null)
        return made.lastPathSegment?.toLong()
    }

    private val current = mutableSetOf<Long>() // the note types brought up to date already

    /** Every note type of ours already in AnkiDroid brought up to date, not only the sent
     * lesson's: an older lesson's cards (pictures, diagrams…) get the change too, sent or not. */
    private fun everyCurrent() {
        val there = api.modelList ?: return
        noteTypes.all.values.distinctBy { it.androidName }.forEach { type ->
            val id = there.entries.firstOrNull { it.value == type.androidName }?.key ?: return@forEach
            runCatching { current(id, type) }.onFailure { Log.w(TAG, "note type ${type.androidName} not brought up to date", it) }
        }
    }

    /** A note type made by an older app (its style without today's signature) brought up to
     * date: its cards' templates and its style, as the computer does; its notes, cards and
     * reviews kept. One with another number of cards (one added or removed) is left as it is. */
    private fun current(id: Long, type: NoteType) {
        if (!current.add(id)) return
        val resolver = context.contentResolver
        val model = Uri.withAppendedPath(FlashCardsContract.Model.CONTENT_URI, id.toString())
        val (css, count) = resolver.query(model, arrayOf(FlashCardsContract.Model.CSS, FlashCardsContract.Model.NUM_CARDS), null, null, null)
            ?.use { c -> if (c.moveToFirst()) c.getString(0).orEmpty() to c.getInt(1) else null } ?: return
        if ("version ${type.signature}:" in css || count != type.cards.size) {
            Log.i(TAG, "note type ${type.androidName}: kept (${if (count != type.cards.size) "$count cards" else "up to date"})")
            return
        }
        Log.i(TAG, "note type ${type.androidName}: bringing it up to date")
        type.cards.forEachIndexed { ord, card ->
            val template = ContentValues().apply {
                put(FlashCardsContract.CardTemplate.NAME, card.name)
                put(FlashCardsContract.CardTemplate.QUESTION_FORMAT, card.front)
                put(FlashCardsContract.CardTemplate.ANSWER_FORMAT, card.back)
            }
            resolver.update(Uri.withAppendedPath(Uri.withAppendedPath(model, "templates"), ord.toString()), template, null, null)
        }
        resolver.update(model, ContentValues().apply { put(FlashCardsContract.Model.CSS, type.signedCss) }, null, null)
    }

    private fun deckId(name: String): Long? =
        api.deckList?.entries?.firstOrNull { it.value == name }?.key ?: api.addNewDeck(name)

    companion object {
        private const val TAG = "Notosaurus"
        private const val LEFTOVER_TEXT = 80 // characters of a leftover note's text shown, as the computer's
        private const val ICON_PX = 96 // AnkiDroid's icon for the page: a chip's size, sharp on any screen
        private val FIRST_USE_WAITS = listOf(500L, 1_000L, 2_000L, 3_500L) // ms between the tries

        /** The card's deck: the lesson's, then its part; a part named as the deck's last level
         * (the lesson's own title, often as the deck was chosen) isn't added again, as on the
         * computer (app/anki.py: _deck_name). Anki doesn't tell decks apart by case. */
        internal fun deckName(deck: String, subdeck: String): String {
            val base = deck.trim().ifBlank { "Notosaurus" }
            val part = subdeck.trim()
            val last = base.substringAfterLast("::").trim()
            return if (part.isEmpty() || last.equals(part, ignoreCase = true)) base else "$base::$part"
        }

        const val PERMISSION = AddContentApi.READ_WRITE_PERMISSION
        // The tag of every note sent for a lesson (as the computer's): its notes found again
        const val TAG_PREFIX = "notosaurus::"
        private const val FILE_MARK = '\uE000' // a file in a note's fields, until it is in AnkiDroid
        private val FILE_REF = Regex("$FILE_MARK(\\d+)$FILE_MARK")
        fun lessonTag(lesson: String) = "$TAG_PREFIX$lesson"

        /** AnkiDroid's link to its card browser on a search. "deck:" in the search: AnkiDroid
         * 2.25 puts the browser's deck before a search without one, and opened by this link it
         * has none ("null tag:…": an empty filtered deck). A new link each time (`at`, ignored
         * by AnkiDroid): the same one again only brings its task back where it was left. */
        internal fun browserLink(search: String, at: Long): String {
            val query = if ("deck:" in search) search else "deck:* $search"
            val encoded = java.net.URLEncoder.encode(query, "UTF-8").replace("+", "%20")
            return "anki://x-callback-url/browser?search=$encoded&at=$at"
        }

        /** A card's text as an AnkiDroid field: escaped, its line breaks kept. */
        fun html(text: String) = escape(text.trim())

        /** The Info field: the card's info, then its "did you know" (💡, in italics). */
        fun info(card: Card): String {
            val fact = card.funFact.trim()
            return html(card.info) + if (fact.isEmpty()) "" else """<div style="margin-top:8px;font-style:italic">💡 ${html(fact)}</div>"""
        }
        private val GAP = Regex("""\{\{c\d+::""")
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
