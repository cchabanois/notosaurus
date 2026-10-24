package app.notosaurus

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.net.Uri
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.ichi2.anki.FlashCardsContract
import com.ichi2.anki.api.AddContentApi
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File

/** Anki.kt against AnkiDroid's real API (the JVM tests use a fake). */
@RunWith(AndroidJUnit4::class)
class AnkiDroidTest {
    private val run = System.currentTimeMillis() // AnkiDroid keeps the cards: each run its own
    private val types = NoteTypes.parse(Device.context.assets.open("web/note-types.json").use { it.readBytes().decodeToString() })

    @Before fun ready() = Device.ankiDroidReady()

    @Test
    fun cardsIntoTheirDecksAndNotTwice() {
        val anki = Anki(Device.context)
        val deck = Deck(
            "Notosaurus test $run",
            listOf(
                Card("chat $run", "gato", info = "nom masculin", subdeck = "Animaux", tags = listOf("famille proche")),
                Card("chien $run", "perro", subdeck = "Animaux"),
                Card("la Révolution commence en {{c1::1789}} $run", ""), // gaps: Anki's cloze
            ),
        )
        val first = anki.send(deck, Media(lesson = "a-$run"))
        assertEquals(3, first.added)
        assertEquals(0, first.skipped)
        assertTrue(anki.deckNames().contains("Notosaurus test $run::Animaux"))

        // Sent again, unchanged: the same notes, nothing added nor updated
        val again = anki.send(deck, Media(lesson = "a-$run"))
        assertEquals(listOf(0, 0, 0), listOf(again.added, again.updated, again.duplicates))

        // Another lesson with the same words: lesson A's notes left as they are (its text
        // with gaps is its own: a note of its own)
        val other = anki.send(deck, Media(lesson = "b-$run"))
        assertEquals(listOf(1, 0, 2), listOf(other.added, other.updated, other.duplicates))
    }

    @Test
    fun aNoteTypeOfAnOlderAppBroughtUpToDate() {
        val anki = Anki(Device.context)
        anki.send(Deck("Notosaurus test $run", listOf(Card("soleil $run", "sol"))))
        val type = types["text"]
        val api = AddContentApi(Device.context)
        val model = Uri.withAppendedPath(FlashCardsContract.Model.CONTENT_URI, api.modelList!!.entries.first { it.value == type.androidName }.key.toString())
        val resolver = Device.context.contentResolver

        // As an older app made it: another template, another style (no signature)
        val old = android.content.ContentValues().apply {
            put(FlashCardsContract.CardTemplate.QUESTION_FORMAT, "{{Front}} (old)")
            put(FlashCardsContract.CardTemplate.ANSWER_FORMAT, "{{Back}} (old)")
        }
        resolver.update(Uri.withAppendedPath(Uri.withAppendedPath(model, "templates"), "0"), old, null, null)
        resolver.update(model, android.content.ContentValues().apply { put(FlashCardsContract.Model.CSS, ".card { color: red; }") }, null, null)

        // The next send (a new run of the app): brought up to date, the note kept
        assertEquals(1, Anki(Device.context).send(Deck("Notosaurus test $run", listOf(Card("lune $run", "luna")))).added)
        val template = resolver.query(Uri.withAppendedPath(Uri.withAppendedPath(model, "templates"), "0"), arrayOf(FlashCardsContract.CardTemplate.QUESTION_FORMAT, FlashCardsContract.CardTemplate.ANSWER_FORMAT), null, null, null)!!
            .use { c -> c.moveToFirst(); c.getString(0) to c.getString(1) }
        assertEquals(type.cards[0].front to type.cards[0].back, template)
        val css = resolver.query(model, arrayOf(FlashCardsContract.Model.CSS), null, null, null)!!.use { c -> c.moveToFirst(); c.getString(0) }
        assertTrue(css, "version ${type.signature}:" in css)
        assertEquals(1, api.findDuplicateNotes(api.modelList!!.entries.first { it.value == type.androidName }.key, "soleil $run").size)
    }

    @Test
    fun aSearchOpensAnkiDroidsBrowserEachTime() {
        // Each call a browser of its own on top (the link processed again, not AnkiDroid only
        // brought back as it was left: what a phone did with the same link twice)
        val anki = Anki(Device.context)
        val seen = mutableSetOf<String>()
        repeat(2) { time ->
            assertTrue(anki.browse("tag:notosaurus"))
            seen += waitForTop("com.ichi2.anki/.CardBrowser", seen, "AnkiDroid's browser, time ${time + 1}")
        }
        Device.shell("input keyevent KEYCODE_HOME") // back from AnkiDroid: not on top of the next test's
    }

    /** The resumed activity once it is `activity`, a record not in `before`; its record. */
    private fun waitForTop(activity: String, before: Set<String>, what: String): String {
        val deadline = System.currentTimeMillis() + 15_000
        var top = ""
        while (System.currentTimeMillis() < deadline) {
            top = Device.shell("dumpsys activity activities").lines().firstOrNull { "ResumedActivity" in it }.orEmpty().trim()
            val record = Regex("""ActivityRecord\{(\w+)""").find(top)?.groupValues?.get(1).orEmpty()
            if (activity in top && record !in before) return record
            Thread.sleep(300)
        }
        error("$what not on top: $top")
    }

    @Test
    fun anotherLessonsNoteTypeBroughtUpToDateToo() {
        // A text with gaps sent once: its note type in AnkiDroid
        Anki(Device.context).send(Deck("Notosaurus test $run", listOf(Card("Le {{c1::soleil}} brille $run", ""))))
        val type = types["cloze"]
        val api = AddContentApi(Device.context)
        val model = Uri.withAppendedPath(FlashCardsContract.Model.CONTENT_URI, api.modelList!!.entries.first { it.value == type.androidName }.key.toString())
        val resolver = Device.context.contentResolver
        resolver.update(model, android.content.ContentValues().apply { put(FlashCardsContract.Model.CSS, ".card { color: red; }") }, null, null)

        // A lesson without any gap sent next (a new run of the app): the cloze type brought up to date all the same
        Anki(Device.context).send(Deck("Notosaurus test $run", listOf(Card("étoile $run", "estrella"))))
        val css = resolver.query(model, arrayOf(FlashCardsContract.Model.CSS), null, null, null)!!.use { c -> c.moveToFirst(); c.getString(0) }
        assertTrue(css, "version ${type.signature}:" in css)
    }

    @Test
    fun theLessonsDeckChangedItsCardsMove() {
        val anki = Anki(Device.context)
        val lesson = "move-$run"
        val cards = listOf(Card("rouge $run", "rojo", subdeck = "Couleurs"), Card("bleu $run", "azul"))
        assertEquals(2, anki.send(Deck("Notosaurus test $run", cards), Media(lesson = lesson)).added)
        val notes = anki.lessonNotes(lesson)!!

        // Sent again to another deck: the same notes, their cards moved there
        val moved = anki.send(Deck("Notosaurus test $run::5ème", cards), Media(lesson = lesson))
        assertEquals(listOf(0, 2), listOf(moved.added, moved.moved))
        assertEquals(notes.sorted(), anki.lessonNotes(lesson)!!.sorted())
        val decks = notes.flatMap { note ->
            val uri = Uri.withAppendedPath(Uri.withAppendedPath(FlashCardsContract.Note.CONTENT_URI, note.toString()), "cards")
            Device.context.contentResolver.query(uri, arrayOf(FlashCardsContract.Card.DECK_ID), null, null, null)!!.use { c ->
                buildList { while (c.moveToNext()) add(c.getLong(0)) }
            }
        }.map { AddContentApi(Device.context).deckList!![it] }
        assertEquals(setOf("Notosaurus test $run::5ème::Couleurs", "Notosaurus test $run::5ème"), decks.toSet())

        // Sent again as it is: nothing moves
        assertEquals(0, anki.send(Deck("Notosaurus test $run::5ème", cards), Media(lesson = lesson)).moved)
    }

    @Test
    fun aCorrectedFrontUpdatesItsOwnNote() {
        val anki = Anki(Device.context)
        val lesson = "front-$run"
        val card = Card("vert $run", "verde", id = "c1-$run")
        val first = anki.send(Deck("Notosaurus test $run", listOf(card)), Media(lesson = lesson))
        assertEquals(1, first.added)
        val note = first.notes.getValue("c1-$run")

        // Its front corrected, sent with the notes of the last send: the same note, updated
        val corrected = card.copy(front = "le vert $run")
        val again = anki.send(Deck("Notosaurus test $run", listOf(corrected)), Media(lesson = lesson, sentBefore = first.notes))
        assertEquals(listOf(0, 1), listOf(again.added, again.updated))
        assertEquals(mapOf("c1-$run" to note), again.notes)
        assertEquals("le vert $run", AddContentApi(Device.context).getNote(note)!!.fields[0])
        assertEquals(listOf(note), anki.lessonNotes(lesson))
    }

    @Test
    fun notesNoCardHasAnyMoreAreFound() {
        val anki = Anki(Device.context)
        val lesson = "left-$run"
        val cards = listOf(Card("jaune $run", "amarillo", id = "j-$run"), Card("noir $run", "negro", id = "n-$run"))
        val first = anki.send(Deck("Notosaurus test $run", cards), Media(lesson = lesson))
        assertEquals(emptyList<Leftover>(), anki.leftovers(lesson, first.notes.values.toSet()))

        // "noir" deleted from the lesson: its note is left, with its text and deck
        val again = anki.send(Deck("Notosaurus test $run", cards.take(1)), Media(lesson = lesson, sentBefore = first.notes))
        val left = anki.leftovers(lesson, again.notes.values.toSet())
        assertEquals(listOf(first.notes.getValue("n-$run")), left.map { it.id })
        assertEquals("noir $run", left.single().text)
        assertEquals("Notosaurus test $run", left.single().deck)
        assertEquals(1, anki.delete(left.map { it.id }))
    }

    @Test
    fun completeCardsUpdatedThenDeletedWithTheLesson() {
        val anki = Anki(Device.context)
        val lesson = "test-$run"
        val card = Card("la mère $run", "la madre", info = "nom", funFact = "Du latin mater.", explanation = "Mère se dit madre.", mnemonic = "maternelle")
        val options = Options(reverse = true, typing = true)
        assertEquals(1, anki.send(Deck("Notosaurus test $run", listOf(card)), Media(lesson = lesson), options).added)

        // Its note type: front → back and back → front, each typed; its helps and "did you know"
        val api = AddContentApi(Device.context)
        val name = types["text+reverse+typing"].androidName
        val model = api.modelList!!.entries.first { it.value == name }.key
        val note = api.findDuplicateNotes(model, card.front).single()
        assertEquals(listOf("Mère se dit madre.", "maternelle"), note.fields.takeLast(2))
        assertTrue(note.fields[2], note.fields[2].contains("💡 Du latin mater."))
        assertTrue(Anki.lessonTag(lesson) in note.tags)
        assertEquals(2, api.previewNewNote(model, note.fields)!!.size) // two cards

        // Corrected, sent again: the same note, updated
        val corrected = anki.send(Deck("Notosaurus test $run", listOf(card.copy(back = "la mamá"))), Media(lesson = lesson), options)
        assertEquals(listOf(0, 1), listOf(corrected.added, corrected.updated))
        assertEquals("la mamá", api.findDuplicateNotes(model, card.front).single().fields[1])

        // Found by the lesson's tag, deleted with it
        val notes = anki.lessonNotes(lesson)!!
        assertEquals(listOf(note.id), notes)
        assertEquals(1, anki.delete(notes))
        assertEquals(emptyList<Long>(), anki.lessonNotes(lesson))
    }

    @Test
    fun aTestsTagPutOnItsNotesAndTakenOff() {
        val anki = Anki(Device.context)
        val lesson = "exam-$run"
        val cards = listOf(Card("gris $run", "gris", id = "g-$run", tags = listOf("couleurs")), Card("blanc $run", "blanco", id = "b-$run"))
        val sent = anki.send(Deck("Notosaurus test $run", cards), Media(lesson = lesson))
        val (grey, white) = listOf(sent.notes.getValue("g-$run"), sent.notes.getValue("b-$run"))
        val api = AddContentApi(Device.context)
        api.updateNoteTags(white, api.getNote(white)!!.tags + "mon_tag") // one the user put in AnkiDroid
        val exam = "Exam::Interro_$run"

        // Put on both: every other tag kept, AnkiDroid's search finds them
        assertTrue(anki.retag(mapOf(exam to setOf(grey, white)), emptyMap()))
        assertEquals(setOf("couleurs", "notosaurus", Anki.lessonTag(lesson), exam), api.getNote(grey)!!.tags)
        assertEquals(setOf("notosaurus", Anki.lessonTag(lesson), "mon_tag", exam), api.getNote(white)!!.tags)
        assertEquals(setOf(grey, white), search("tag:$exam"))

        // The lesson sent again: the test's tag stays
        anki.send(Deck("Notosaurus test $run", cards), Media(lesson = lesson, sentBefore = sent.notes))
        assertEquals(setOf(grey, white), search("tag:$exam"))

        // Taken off one (its card out of the test), another test's put on it: nothing else touched
        assertTrue(anki.retag(mapOf("Exam::Brevet_$run" to setOf(white)), mapOf(exam to setOf(white))))
        assertEquals(setOf("notosaurus", Anki.lessonTag(lesson), "mon_tag", "Exam::Brevet_$run"), api.getNote(white)!!.tags)
        assertEquals(setOf(grey), search("tag:$exam"))

        // A note deleted in AnkiDroid meanwhile: the others tagged all the same
        assertEquals(1, anki.delete(listOf(grey)))
        assertTrue(anki.retag(emptyMap(), mapOf("Exam::Brevet_$run" to setOf(grey, white))))
        assertEquals(setOf("notosaurus", Anki.lessonTag(lesson), "mon_tag"), api.getNote(white)!!.tags)
    }

    /** The notes AnkiDroid's search finds. */
    private fun search(query: String): Set<Long> = Device.context.contentResolver.query(
        FlashCardsContract.Note.CONTENT_URI, arrayOf(FlashCardsContract.Note._ID), query, null, null,
    )?.use { c -> buildSet { while (c.moveToNext()) add(c.getLong(0)) } }.orEmpty()

    @Test
    fun theBacksSoundIntoAnkiDroidsMedia() {
        val anki = Anki(Device.context)
        val lesson = "sound-$run"
        fun mp3(name: String) = File(Device.context.filesDir, "audio/$name-$run.mp3").apply {
            parentFile!!.mkdirs()
            writeBytes(ByteArray(64) { (it + name.length).toByte() }) // AnkiDroid doesn't read it: any bytes
        }
        val card = Card("le chat $run", "el gato", id = "s-$run")
        val first = anki.send(Deck("Notosaurus test $run", listOf(card)), Media(audio = mapOf("el gato" to mp3("gato")), lesson = lesson))
        assertEquals(1, first.added)
        val api = AddContentApi(Device.context)
        val note = first.notes.getValue("s-$run")
        val sound = soundOf(api.getNote(note)!!.fields)
        assertTrue(sound, sound.startsWith("gato-$run"))
        assertTrue("$sound not in AnkiDroid's media", sound in media())

        // Sent again as it is: the same note, its sound not copied again
        val again = anki.send(Deck("Notosaurus test $run", listOf(card)), Media(audio = mapOf("el gato" to mp3("gato")), lesson = lesson, sentBefore = first.notes))
        assertEquals(listOf(0, 0), listOf(again.added, again.updated))
        assertEquals(sound, soundOf(api.getNote(note)!!.fields))
        assertEquals(listOf(sound), media().filter { it.startsWith("gato-$run") })

        // Its back corrected, a new sound: the note's field says the new one
        val corrected = card.copy(back = "la gata")
        val fixed = anki.send(Deck("Notosaurus test $run", listOf(corrected)), Media(audio = mapOf("la gata" to mp3("gata")), lesson = lesson, sentBefore = first.notes))
        assertEquals(listOf(0, 1), listOf(fixed.added, fixed.updated))
        val now = soundOf(api.getNote(note)!!.fields)
        assertTrue(now, now.startsWith("gata-$run") && now in media())
    }

    /** The file a note's "[sound:…]" names (one field has it). */
    private fun soundOf(fields: Array<String>): String =
        fields.firstNotNullOfOrNull { Regex("""\[sound:([^\]]+)]""").find(it)?.groupValues?.get(1) } ?: error("no sound in ${fields.toList()}")

    /** The files in AnkiDroid's media folder. */
    private fun media(): List<String> =
        Device.shell("ls /sdcard/Android/data/com.ichi2.anki/files/AnkiDroid/collection.media").lines().map { it.trim() }.filter { it.isNotEmpty() }

    @Test
    fun theLessonReviewedInAnkiDroid() {
        val anki = Anki(Device.context)
        val deck = "Notosaurus test $run::Leçon"
        anki.send(Deck(deck, listOf(Card("le chat $run", "el gato"))))
        assertTrue(anki.review(deck))
        // The deck selected, AnkiDroid's reviewer on top
        assertEquals(deck, AddContentApi(Device.context).selectedDeckName)
        val deadline = System.currentTimeMillis() + 10_000
        var top = ""
        while (System.currentTimeMillis() < deadline) {
            top = Device.shell("dumpsys activity activities").lines().firstOrNull { "ResumedActivity" in it }.orEmpty()
            if ("com.ichi2.anki/.Reviewer" in top) break
            Thread.sleep(300)
        }
        assertTrue(top, "com.ichi2.anki/.Reviewer" in top)
        Device.shell("input keyevent KEYCODE_HOME") // back from AnkiDroid
        assertFalse(anki.review("No such deck $run"))
    }

    @Test
    fun multipleChoices() {
        val anki = Anki(Device.context)
        val question = "La Révolution commence en ? $run"
        val deck = Deck("Notosaurus test $run", listOf(Card(question, "1789", choices = listOf("1715", "1799"), id = "c$run")))
        assertEquals(1, anki.send(deck).added)
        val api = AddContentApi(Device.context)
        val model = api.modelList!!.entries.first { it.value == types["choice"].androidName }.key
        val note = api.findDuplicateNotes(model, "c$run").single() // "Id" first: told apart by the card's own id
        assertEquals(question, note.fields[1])
        assertTrue(note.fields[3], note.fields[3].startsWith("<ol class=\"notosaurus-choices\">"))
        assertTrue(note.fields[4].contains("<li class=\"right\">1789</li>"))
        assertEquals(0, anki.send(deck).added) // not twice
    }

    @Test
    fun diagramLabelsAndGaps() {
        val anki = Anki(Device.context)
        // A photo where the lessons are kept (AnkiDroid reads it through our FileProvider)
        val photo = File(Device.context.filesDir, "lessons/test-$run/page-1.jpg").apply {
            parentFile!!.mkdirs()
            val bitmap = Bitmap.createBitmap(40, 30, Bitmap.Config.ARGB_8888)
            outputStream().use { bitmap.compress(Bitmap.CompressFormat.JPEG, 80, it) }
        }
        val gaps = "La Révolution commence en {{c1::1789}} avec la prise de {{c2::la Bastille}} $run."
        val deck = Deck(
            "Notosaurus test $run",
            listOf(
                Card("Qu'est-ce que (1) ?", "la bouche", mask = Mask(1, 1, listOf(0.1, 0.1, 0.3, 0.2))),
                Card("Qu'est-ce que (2) ?", "l'estomac", mask = Mask(1, 2, listOf(0.5, 0.5, 0.7, 0.6))),
                Card(gaps, ""),
            ),
        )
        val sent = anki.send(deck, Media(photos = mapOf(1 to photo), lesson = "test-$run", frames = mapOf(1 to listOf(0.0, 0.0, 0.5, 0.5))))
        assertEquals(3, sent.added)
        assertEquals(0, sent.skipped)

        // The gaps: Anki's own cloze, a card per gap number
        val api = AddContentApi(Device.context)
        val cloze = api.modelList!!.entries.first { it.value == types["cloze"].androidName }.key
        val note = api.findDuplicateNotes(cloze, "test-$run:2").single() // "Id" first: the lesson and the card's place
        val cards = Device.context.contentResolver.query(
            Uri.withAppendedPath(Uri.withAppendedPath(FlashCardsContract.Note.CONTENT_URI, note.id.toString()), "cards"),
            null, null, null, null,
        )!!.use { it.count }
        assertEquals(2, cards)

        // The diagram's questions repeat ("What is (1)?"): told apart by lesson, photo and label
        val diagram = api.modelList!!.entries.first { it.value == types["diagram"].androidName }.key
        val label = api.findDuplicateNotes(diagram, "test-$run:1:1").single()
        assertTrue(label.fields[5], label.fields[5].startsWith("<img"))
        assertTrue(label.fields[6].contains("notosaurus-mask target"))
        // Cropped to the diagram's frame (stretched to hold the labels): smaller than the photo
        val cropped = File(photo.parentFile, "images").listFiles()!!.single { it.name.startsWith("diagram-page-1-") }
        val size = BitmapFactory.decodeFile(cropped.path)
        assertTrue("${size.width}×${size.height}", size.width < 40 && size.height < 30)
        // Sent again: not twice, the diagram's image not copied into AnkiDroid again
        val again = anki.send(deck, Media(photos = mapOf(1 to photo), lesson = "test-$run", frames = mapOf(1 to listOf(0.0, 0.0, 0.5, 0.5))))
        assertEquals(listOf(0, 0), listOf(again.added, again.updated))
        assertEquals(label.fields[5], api.findDuplicateNotes(diagram, "test-$run:1:1").single().fields[5])
    }
}
