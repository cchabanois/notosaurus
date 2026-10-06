package app.notosaurus

import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith

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
                Card("la Révolution commence en {{c1::1789}} $run", ""), // gaps: not done by the app yet
            ),
        )
        val first = anki.send(deck)
        assertEquals(2, first.added)
        assertEquals(1, first.skipped)
        assertTrue(anki.deckNames().contains("Notosaurus test $run::Animaux"))

        // Sent again: already there, nothing added
        val again = anki.send(deck)
        assertEquals(0, again.added)
        assertEquals(2, again.duplicates)
    }
}
