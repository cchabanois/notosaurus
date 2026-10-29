package app.notosaurus

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/** What doesn't need AnkiDroid: the diagrams' masks, as the computer writes them. */
class AnkiTest {
    @Test
    fun aPartNamedAsTheDeckIsntAddedTwice() {
        assertEquals("Anglais::5ème::School subjects", Anki.deckName("Anglais::5ème::School subjects", "School subjects"))
        assertEquals("Anglais::5ème::School subjects", Anki.deckName("Anglais::5ème::School subjects", " school SUBJECTS "))
        assertEquals("Anglais::5ème::School subjects", Anki.deckName("Anglais::5ème", "School subjects"))
        assertEquals("Anglais::5ème", Anki.deckName("Anglais::5ème", ""))
        assertEquals("Notosaurus::Phrases", Anki.deckName("", "Phrases"))
    }

    private val types by lazy {
        // static/note-types.json, as the app's assets have it
        val web = File(System.getProperty("notosaurus.web") ?: "../../static")
        NoteTypes.parse(web.resolve("note-types.json").readText())
    }

    @Test
    fun theComputersNoteTypesAsTheyAre() {
        val text = types["text+reverse+typing+dictation"]
        assertEquals("Notosaurus recto/verso + inverse à taper + dictée (audio)", text.name) // the computer's name
        assertEquals("Notosaurus recto/verso + inverse à taper + dictée (Android)", text.legacyName) // the test versions'
        assertEquals(listOf("Front", "Back", "Info", "Audio", "Explanation", "Mnemonic"), text.fields)
        assertEquals(3, text.cards.size)
        assertTrue(text.cards[0].front.contains("{{type:Back}}"))

        // The computer's order (the key where it puts it), its hidden Source too
        val picture = types["picture"]
        assertEquals(listOf("Front", "Back", "Info", "Audio", "Picture", "Id", "Explanation", "Mnemonic", "Source"), picture.fields)
        assertEquals("Id", picture.key)
        assertTrue(types["cloze"].cloze)
        // A note's values in its note type's order; a field not written keeps its value there (Source)
        val names = picture.fields
        val there = arrayOf("", "", "", "", "", "", "", "", "Wikimedia Commons")
        assertEquals(listOf("le chat", "el gato", "", "", "", "k", "", "", "Wikimedia Commons"), picture.values(names, mapOf("Front" to "le chat", "Back" to "el gato", "Id" to "k"), there).toList())
    }

    @Test
    fun theSameNoteTypesAsTheComputers() {
        // Each note type made here is the computer's to the letter (name, fields in their order,
        // card templates, style): the same signature, so neither device brings the other's "up
        // to date", and a lesson's notes from one are found from the other
        types.all.forEach { (variant, type) ->
            assertTrue(variant, type.computerSignature.isNotEmpty())
            assertEquals(variant, type.computerSignature, type.signature)
            assertTrue(variant, "version ${type.computerSignature}:" in type.signedCss)
        }
    }

    @Test
    fun theFieldsAsTheComputersFields() {
        assertEquals("a &lt; b &amp; c<br>d", Anki.html(" a < b & c\nd "))
        assertEquals("nom féminin", Anki.info(Card("q", "r", info = "nom féminin")))
        assertEquals(
            """nom<div style="margin-top:8px;font-style:italic">💡 Vient du latin &quot;mater&quot;.</div>""",
            Anki.info(Card("q", "r", info = "nom", funFact = "Vient du latin \"mater\".")),
        )
        assertEquals("notosaurus::2026-10-10-espagnol", Anki.lessonTag("2026-10-10-espagnol"))
    }

    @Test
    fun multipleChoicesInAFixedOrder() {
        val card = Card("La Révolution commence en ?", "1789", choices = listOf("1715", "1799", "1804"))
        with(Anki) { assertTrue(card.isChoice()) }
        val question = Anki.choicesHtml(card, reveal = false)
        val options = Regex("<li>(.*?)</li>").findAll(question).map { it.groupValues[1] }.toList()
        assertEquals(setOf("1789", "1715", "1799", "1804"), options.toSet())
        assertEquals(question, Anki.choicesHtml(card.copy(), reveal = false)) // the same order, review after review
        // The answer: the same order, the right one marked
        val answer = Anki.choicesHtml(card, reveal = true)
        assertEquals(options, Regex("<li[^>]*>(.*?)</li>").findAll(answer).map { it.groupValues[1] }.toList())
        assertTrue(answer.contains("<li class=\"right\">1789</li>"))
        assertEquals(3, Regex("class=\"wrong\"").findAll(answer).count())

        // True/false: alphabetical, the same for every card; options escaped
        val trueFalse = Card("Paris est la capitale de l'Italie.", "Faux", choices = listOf("Vrai"))
        assertEquals("""<ol class="notosaurus-choices"><li>Faux</li><li>Vrai</li></ol>""", Anki.choicesHtml(trueFalse, reveal = false))
        assertTrue(Anki.choicesHtml(Card("q", "a < b", choices = listOf("x")), reveal = false).contains("a &lt; b"))

        // A gap text or a diagram label stays one
        with(Anki) {
            assertFalse(Card("en {{c1::1789}}", "x", choices = listOf("y")).isChoice())
            assertFalse(Card("(1) ?", "x", choices = listOf("y"), mask = Mask(1, 1, listOf(0.0, 0.0, 0.1, 0.1))).isChoice())
        }
    }

    @Test
    fun masksAsTheComputersMasks() {
        val masks = listOf(Mask(1, 2, listOf(0.5, 0.1, 0.75, 0.2)), Mask(1, 1, listOf(0.123456, 0.3, 0.25, 0.333333)))
        // diagrams.masks_html(masks, 1, reveal) on the computer, for the same masks
        assertEquals(
            """<div class="notosaurus-mask target" style="left:12.35%;top:30.0%;width:12.65%;height:3.33%">(1)</div>""" +
                """<div class="notosaurus-mask" style="left:50.0%;top:10.0%;width:25.0%;height:10.0%">(2)</div>""",
            Anki.masksHtml(masks, 1, reveal = false),
        )
        assertEquals(
            """<div class="notosaurus-mask revealed" style="left:12.35%;top:30.0%;width:12.65%;height:3.33%"></div>""" +
                """<div class="notosaurus-mask" style="left:50.0%;top:10.0%;width:25.0%;height:10.0%">(2)</div>""",
            Anki.masksHtml(masks, 1, reveal = true),
        )
    }

    @Test
    fun theDiagramCroppedAsOnTheComputer() {
        val masks = listOf(Mask(1, 2, listOf(0.5, 0.1, 0.75, 0.2)), Mask(1, 1, listOf(0.123456, 0.3, 0.25, 0.333333)))
        // diagrams.crop and masks_html(…, box) on the computer, for the same frame and masks
        val box = Anki.crop(listOf(0.2, 0.05, 0.7, 0.5), masks)
        assertEquals(listOf(0.0935, 0.05, 0.78, 0.5), box) // stretched to hold the labels, with a margin
        assertEquals(
            """<div class="notosaurus-mask" style="left:4.36%;top:55.56%;width:18.44%;height:7.4%">(1)</div>""" +
                """<div class="notosaurus-mask target" style="left:59.21%;top:11.11%;width:36.42%;height:22.22%">(2)</div>""",
            Anki.masksHtml(masks, 2, reveal = false, box),
        )
        assertEquals(null, Anki.crop(null, masks)) // no frame: the whole photo
        assertEquals(listOf(0.0, 0.0, 0.99, 0.99), Anki.crop(listOf(0.0, 0.0, 0.99, 0.99), masks))
    }

    @Test
    fun aSearchOpenedInAnkiDroidsBrowser() {
        // "deck:*" added (AnkiDroid would put "null" before the search), the search encoded, a new link each time
        assertEquals("anki://x-callback-url/browser?search=deck%3A*%20tag%3AExam%3A%3AInterro&at=1", Anki.browserLink("tag:Exam::Interro", 1))
        assertEquals("anki://x-callback-url/browser?search=deck%3AEspagnol%20tag%3Ax&at=2", Anki.browserLink("deck:Espagnol tag:x", 2))
    }
}
