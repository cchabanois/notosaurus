package app.notosaurus

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.ByteArrayOutputStream
import java.io.File

/** The app's own .apkg (Apkg.kt): the collection Anki and AnkiDroid import, as the computer's
 * (genanki) writes it: its note types by their computer's ids, decks, notes and their cards,
 * no review history, the media numbered beside it. */
class ApkgTest {
    @get:Rule val folder = TemporaryFolder()
    private val noteTypes = NoteTypes.parse(File(System.getProperty("notosaurus.web") ?: "../../static").resolve("note-types.json").readText())

    private fun written(notes: List<Built>, files: Set<File>): OpenedApkg {
        val out = ByteArrayOutputStream()
        Apkg.write(notes, files, out, folder.newFile("work.anki2"), ::JdbcApkgDb, now = 1_700_000_000_000)
        return OpenedApkg(out.toByteArray(), folder.newFolder())
    }

    @Test
    fun aLessonsCardsAsTheComputersPackage() {
        val sound = folder.newFile("la-madre-3f2a1c9e.mp3").apply { writeText("mp3") }
        val deck = Deck(
            "Espagnol::Leçon 5",
            listOf(
                Card(id = "c1", front = "la mère", back = "la madre"),
                Card(id = "c2", front = "La {{c1::Révolution}} commence en {{c2::1789}}.", back = ""),
                Card(id = "c3", front = "Quel est le féminin ?", back = "la madre", choices = listOf("el padre")),
            ),
        )
        val files = mutableSetOf<File>()
        fun shown(f: File, kind: String) = Apkg.shown(f.also { files += it }, kind)
        val media = Media(audio = mapOf(Speech.spoken(deck.cards[0], false) to sound))
        val notes = Anki.buildNotes(noteTypes, deck, media, Options(reverse = true), ::shown, { f, k, _ -> shown(f, k) }) { _, f, _ -> f }
        val apkg = written(notes, files)

        assertEquals(3, apkg.query("SELECT count(*) FROM notes") { it.getInt(1) }.single())
        // Reversed: two cards; a gap text: one per gap; a choice: one
        assertEquals(listOf(0, 1, 0, 1, 0), apkg.query("SELECT ord FROM cards ORDER BY id") { it.getInt(1) })
        assertEquals(0, apkg.query("SELECT count(*) FROM revlog") { it.getInt(1) }.single()) // no review history
        assertEquals(setOf(0 to 0), apkg.query("SELECT type, queue FROM cards") { it.getInt(1) to it.getInt(2) }.toSet()) // new cards
        // The computer's note types, by their ids: an importer who has them gets no second copy
        val mids = apkg.query("SELECT DISTINCT mid FROM notes") { it.getLong(1) }.toSet()
        val known = noteTypes.all.values.map { it.model!!["id"]!!.toString().trim('"').toLong() }.toSet()
        assertTrue(mids.isNotEmpty() && known.containsAll(mids))
        // Its sound in the package, the field naming it
        assertEquals(mapOf("0" to "la-madre-3f2a1c9e.mp3"), apkg.media)
        assertEquals("mp3", apkg.entries.getValue("0").decodeToString())
        assertTrue(apkg.query("SELECT flds FROM notes") { it.getString(1) }.any { "[sound:la-madre-3f2a1c9e.mp3]" in it })
        assertEquals(setOf("Default", "Espagnol::Leçon 5"), apkg.deckNames)
    }

    @Test
    fun theComputersGuidsAndDeckIds() {
        // genanki.guid_for and note_types.common.stable_id, run on the computer for these values
        assertEquals("H:y>fXo5(e", Apkg.guidFor(listOf("Histoire::Révolution", "c1")))
        assertEquals("y3%F&}7l[3", Apkg.guidFor(listOf("Histoire::Révolution", "c1", "1")))
        assertEquals(1266251675L, Apkg.stableId("deck", "Histoire::Révolution"))
    }
}
