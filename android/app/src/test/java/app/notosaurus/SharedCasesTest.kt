package app.notosaurus

import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.boolean
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Test
import java.io.File

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
    fun theDeckHoldingATestsLessons() = cases("common_deck").forEach { c ->
        val decks = (c["in"] as JsonArray).map { it.jsonPrimitive.content }
        assertEquals(decks.toString(), c.string("out"), Exams.commonDeck(decks))
    }

    @Test
    fun whatAVoiceReads() = cases("speakable").forEach { c ->
        assertEquals(c.string("in"), c.string("out"), Speech.speakable(c.string("in")))
    }

    @Test
    fun aCardsSound() = cases("spoken").forEach { c ->
        val card = Card(c.string("front"), c.string("back"))
        assertEquals("${c.string("front")} | ${c.string("back")}", c.string("out"), Speech.spoken(card, c["dictation"]!!.jsonPrimitive.boolean))
    }
}
