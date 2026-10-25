package app.notosaurus

import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.boolean
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Test
import org.junit.runner.RunWith

/** The shared cases (core/shared-cases.json, in the test APK's assets) with Android's own regex
 * engine (ICU): the unit tests (SharedCasesTest) run on the JVM's, which differs (its \w is
 * ASCII; it knows (?U), Android doesn't: Speech failed to load on a phone while every unit test
 * passed). */
@RunWith(AndroidJUnit4::class)
class RegexOnDeviceTest {
    private val cases = InstrumentationRegistry.getInstrumentation().context.assets.open("shared-cases.json")
        .use { json.parseToJsonElement(it.readBytes().decodeToString()).jsonObject }

    private fun cases(name: String): List<JsonObject> = cases[name]!!.jsonArray.map { it.jsonObject }

    @Test
    fun aTestsTag() = cases("tag_text").forEach { c -> assertEquals(c.string("in"), c.string("out"), Exams.tagText(c.string("in"))) }

    @Test
    fun theDeckHoldingATestsLessons() = cases("common_deck").forEach { c ->
        val decks = c["in"]!!.jsonArray.map { it.jsonPrimitive.content }
        assertEquals(decks.toString(), c.string("out"), Exams.commonDeck(decks))
    }

    @Test
    fun whatAVoiceReads() = cases("speakable").forEach { c -> assertEquals(c.string("in"), c.string("out"), Speech.speakable(c.string("in"))) }

    @Test
    fun aCardsSound() = cases("spoken").forEach { c ->
        val card = Card(c.string("front"), c.string("back"))
        assertEquals("${c.string("front")} | ${c.string("back")}", c.string("out"), Speech.spoken(card, c["dictation"]!!.jsonPrimitive.boolean))
    }
}
