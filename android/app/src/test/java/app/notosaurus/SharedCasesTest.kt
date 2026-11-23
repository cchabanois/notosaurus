package app.notosaurus

import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.boolean
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.int
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put
import org.junit.Assert.assertEquals
import org.junit.Test
import java.io.File
import java.nio.file.Files

/** The cases the computer's Python, the page's JavaScript and this app must agree on
 * (core/shared-cases.json, Python's answers the reference). */
class SharedCasesTest {
    private val cases = json.parseToJsonElement(File(System.getProperty("notosaurus.cases")!!).readText()).jsonObject

    private fun cases(name: String): List<JsonObject> = cases[name]!!.jsonArray.map { it.jsonObject }

    @Test
    fun aTestsTag() = cases("tag_text").forEach { c ->
        assertEquals(c.string("in"), c.string("out"), Exams.tagText(c.string("in")))
    }

    @Test
    fun aCardsDeck() = cases("deck_name").forEach { c ->
        assertEquals(c.toString(), c.string("out"), Anki.deckName(c.string("deck"), c.string("subdeck")))
    }

    @Test
    fun theDeckHoldingATestsLessons() = cases("common_deck").forEach { c ->
        val decks = (c["in"] as JsonArray).map { it.jsonPrimitive.content }
        assertEquals(decks.toString(), c.string("out"), Exams.commonDeck(decks))
    }

    @Test
    fun whatAVoiceReads() = cases("speakable").forEach { c ->
        assertEquals(c.string("in"), c.string("out"), Speech.speakable(c.string("in")))
    }

    @Test
    fun aCardMadeAgainKeepsItsId() = cases("kept_ids").forEach { c ->
        val ids = Lessons.keptIds(c["made"], c["before"]).map { it.jsonObject["id"]?.jsonPrimitive?.content.orEmpty() }
        assertEquals(c["name"]!!.jsonPrimitive.content, c["out"]!!.jsonArray.map { it.jsonPrimitive.content }, ids)
    }

    @Test
    fun aCardsInfoField() = cases("info_field").forEach { c ->
        val card = Card(front = "f", back = "b", info = c.string("info"), funFact = c.string("fun_fact"))
        assertEquals(c.string("name"), c.string("out"), Anki.info(card))
    }

    @Test
    fun twoTextsTheSame() = cases("same_text").forEach { c ->
        val (a, b) = c.string("a") to c.string("b")
        assertEquals("$a | $b", c.string("key") to c["out"]!!.jsonPrimitive.boolean, Lessons.textKey(a) to Lessons.sameText(a, b))
    }

    @Test
    fun aSoundsFile() = cases("sound_file").forEach { c ->
        assertEquals(c.string("text"), c.string("out"), Speech.fileName(c.string("text"), c.string("voice"), c.string("rate")))
    }

    @Test
    fun aFiguresSourceFiles() = cases("figure_source_files").forEach { c ->
        val folder = Files.createTempDirectory("sources").toFile()
        val contents = List(c["count"]!!.jsonPrimitive.int) { n -> "// source $n" }
        val files = Pictures.keepSources(folder, c.string("picture"), contents)
        assertEquals(c.toString(), c["out"]!!.jsonArray.map { it.jsonPrimitive.content }, files.map { it.jsonObject.string("file") })
        val origin = buildJsonObject { put("source", "drawn"); put("engine", "typst"); put("sources", files) }
        assertEquals(c.toString(), contents, Pictures.keptSources(folder, origin))
        folder.deleteRecursively()
    }

    @Test
    fun aFiguresSourcesPrunedWithIt() = cases("figure_sources_pruned").forEach { c ->
        val folder = Files.createTempDirectory("pruned").toFile()
        c["files"]!!.jsonArray.forEach { folder.resolve(it.jsonPrimitive.content).writeText("x") }
        val used = c["pictures"]!!.jsonArray.map { it.jsonPrimitive.content }.toSet()
        assertEquals(c.string("name"), c["removed"]!!.jsonPrimitive.int, Pictures.pruned(folder, used))
        assertEquals(c.string("name"), c["out"]!!.jsonArray.map { it.jsonPrimitive.content }, folder.list()!!.sorted())
        folder.deleteRecursively()
    }

    @Test
    fun aCardsSound() = cases("spoken").forEach { c ->
        val card = Card(c.string("front"), c.string("back"))
        assertEquals("${c.string("front")} | ${c.string("back")}", c.string("out"), Speech.spoken(card, c["dictation"]!!.jsonPrimitive.boolean))
    }

    @Test
    fun whatEachSideSays() = cases("spoken_sides").forEach { c ->
        val choices = c["choices"]!!.jsonArray.map { it.jsonPrimitive.content }
        val card = Card(c.string("front"), c.string("back"), choices = choices, sound = c.string("sound"))
        val out = c["out"]!!.jsonArray.map { it.jsonPrimitive.content }
        val said = Speech.spokenSides(card, c["dictation"]!!.jsonPrimitive.boolean)
        assertEquals("${c.string("front")} | ${c.string("sound")}", out, listOf(said.first, said.second))
    }
}
