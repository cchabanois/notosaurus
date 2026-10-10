package app.notosaurus

import android.graphics.Bitmap
import android.net.Uri
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.ichi2.anki.FlashCardsContract
import com.ichi2.anki.api.AddContentApi
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File

/** Anki.kt against AnkiDroid's real API (the JVM tests use a fake). */
@RunWith(AndroidJUnit4::class)
class AnkiDroidTest {
    private val run = System.currentTimeMillis() // AnkiDroid keeps the cards: each run its own

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
        val first = anki.send(deck)
        assertEquals(3, first.added)
        assertEquals(0, first.skipped)
        assertTrue(anki.deckNames().contains("Notosaurus test $run::Animaux"))

        // Sent again: already there, nothing added
        val again = anki.send(deck)
        assertEquals(0, again.added)
        assertEquals(3, again.duplicates)
    }

    @Test
    fun multipleChoices() {
        val anki = Anki(Device.context)
        val question = "La Révolution commence en ? $run"
        val deck = Deck("Notosaurus test $run", listOf(Card(question, "1789", choices = listOf("1715", "1799"), id = "c$run")))
        assertEquals(1, anki.send(deck).added)
        val api = AddContentApi(Device.context)
        val model = api.modelList!!.entries.first { it.value == Anki.CHOICE_MODEL }.key
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
        val sent = anki.send(deck, Media(photos = mapOf(1 to photo), lesson = "test-$run"))
        assertEquals(3, sent.added)
        assertEquals(0, sent.skipped)

        // The gaps: Anki's own cloze, a card per gap number
        val api = AddContentApi(Device.context)
        val cloze = api.modelList!!.entries.first { it.value == Anki.CLOZE_MODEL }.key
        val note = api.findDuplicateNotes(cloze, gaps).single()
        val cards = Device.context.contentResolver.query(
            Uri.withAppendedPath(Uri.withAppendedPath(FlashCardsContract.Note.CONTENT_URI, note.id.toString()), "cards"),
            null, null, null, null,
        )!!.use { it.count }
        assertEquals(2, cards)

        // The diagram's questions repeat ("What is (1)?"): told apart by lesson, photo and label
        val diagram = api.modelList!!.entries.first { it.value == Anki.DIAGRAM_MODEL }.key
        val label = api.findDuplicateNotes(diagram, "test-$run:1:1").single()
        assertTrue(label.fields[5], label.fields[5].startsWith("<img"))
        assertTrue(label.fields[6].contains("notosaurus-mask target"))
        assertEquals(0, anki.send(deck, Media(photos = mapOf(1 to photo), lesson = "test-$run")).added) // not twice
    }
}
