package app.notosaurus

import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
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

    /** A case's lesson photos: a number n (its pages 1 to n), or the numbers of its pages there. */
    private fun photos(element: JsonElement?): List<Int> =
        (element as? JsonArray)?.map { it.jsonPrimitive.int } ?: (1..element!!.jsonPrimitive.int).toList()

    @Test
    fun thePhotosSentToCorrectACard() = cases("fix_photos").forEach { c ->
        val out = c["out"]!!.jsonArray.map { it.jsonPrimitive.int } to c.string("sent")
        assertEquals(c.string("name"), out, Generation.fixPhotos(c["page"]!!.jsonPrimitive.int, photos(c["photos"])))
        if (c["photos"] !is JsonArray) assertEquals(c.string("name"), out, Generation.fixPhotos(c["page"]!!.jsonPrimitive.int, c["photos"]!!.jsonPrimitive.int))
    }

    @Test
    fun theCallsLookingForTheLessonsDrawings() = cases("drawing_calls").forEach { c ->
        fun ints(numbers: JsonArray) = numbers.map { it.jsonPrimitive.int }
        val out = c["out"]!!.jsonArray.map { it.jsonObject }.map { ints(it["pages"]!!.jsonArray) to ints(it["cards"]!!.jsonArray) }
        assertEquals(c.string("name"), out, Pictures.drawingCalls(ints(c["pages"]!!.jsonArray), photos(c["photos"])))
    }

    @Test
    fun thePhotosSentToCorrectALesson() = cases("revise_photos").forEach { c ->
        val out = c["out"]!!.jsonArray.map { it.jsonPrimitive.int } to c.string("sent")
        assertEquals(c.string("name"), out, Generation.revisePhotos(photos(c["photos"])))
    }

    @Test
    fun theNumberOfAPageAddedToALesson() = cases("next_page").forEach { c ->
        assertEquals(c.string("name"), c["out"]!!.jsonPrimitive.int, Lessons.nextPage(photos(c["files"]), c["lesson"]!!.jsonObject))
    }

    @Test
    fun aCardsInfoField() = cases("info_field").forEach { c ->
        val card = Card(front = "f", back = "b", info = c.string("info"), funFact = c.string("fun_fact"))
        assertEquals(c.string("name"), c.string("out"), Anki.info(card))
    }

    @Test
    fun aCardsFormulasAsTheyGoToAnkiDroid() = cases("anki_formula").forEach { c ->
        assertEquals(c.string("name"), c.string("out"), Formulas.ankiText(c.string("in")))
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
    fun anEditsCardMergedIntoTheSavedOne() = cases("merged_card").forEach { c ->
        val (before, after, now) = listOf("before", "after", "now").map { c[it]!!.jsonObject }
        assertEquals(c.string("name"), listOf(c["out"]!!.jsonObject), Pictures.mergedCards(listOf(before), listOf(after), listOf(now)))
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

    private fun strings(element: JsonElement?): List<String> = element!!.jsonArray.map { it.jsonPrimitive.content }

    private fun child(element: JsonElement?): Child? = (element as? JsonObject)?.let { json.decodeFromJsonElement(Child.serializer(), it) }

    private fun children(element: JsonElement?): List<Child> = element!!.jsonArray.mapNotNull(::child)

    @Test
    fun twoDeckLevelsTheSame() = cases("same_level").forEach { c ->
        val (a, b) = c.string("a") to c.string("b")
        assertEquals("$a | $b", c["out"]!!.jsonPrimitive.boolean, Children.same(a) == Children.same(b))
    }

    @Test
    fun aDeckSplitIntoTheChildrensLevelsAndTheRest() = cases("split_deck").forEach { c ->
        val (private, rest) = Children.splitDeck(c.string("deck"), children(c["children"]))
        assertEquals(c.string("deck"), strings(c["out"]), listOf(private, rest))
    }

    @Test
    fun aLessonsDeckInItsChildsDecks() = cases("deck_for").forEach { c ->
        assertEquals(c.toString(), c.string("out"), Children.deckFor(child(c["child"]), c.string("deck")))
    }

    @Test
    fun theDecksTheAiMayReuse() = cases("decks_for_ai").forEach { c ->
        val every = children(c["children"])
        val chosen = every.firstOrNull { it.id == c.string("child") }
        assertEquals(c.string("child"), strings(c["out"]), Children.decksForAi(strings(c["decks"]), every, chosen))
    }

    @Test
    fun eachLessonItsOwnDeck() = cases("new_deck_name").forEach { c ->
        val taken = Generation.existing(strings(c["anki"]), strings(c["lessons"]), c.string("own"))
        assertEquals(c.string("name"), c.string("out"), Generation.freeName(c.string("deck"), taken))
    }

    @Test
    fun aLessonsDeckInASharedPackage() = cases("shared_deck").forEach { c ->
        assertEquals(c.toString(), c.string("out"), sharedDeck(c.string("top"), c.string("rest"), c.string("common")))
    }

    @Test
    fun aLessonsIdInASharedPackage() = cases("shared_id").forEach { c ->
        assertEquals(c.string("in"), c.string("out"), sharedId(c.string("in")))
    }

    @Test
    fun aPackagesFileName() = cases("package_name").forEach { c ->
        assertEquals(c.string("in"), c.string("out"), packageName(c.string("in")))
    }

    @Test
    fun aSharedPackagesOwnDeck() = cases("package_deck").forEach { c ->
        assertEquals(c.toString(), c.string("out"), packageDeck(c.string("name"), c.string("default"), c.string("common")))
    }

    @Test
    fun aLessonsSpeechRate() = cases("speech_rate").forEach { c ->
        val rate = Speech.rate(c.string("slowed"), c.string("speed"), c["foreign"]!!.jsonPrimitive.boolean, c["dictation"]!!.jsonPrimitive.boolean)
        assertEquals(c.toString(), c.string("out"), rate)
    }

    @Test
    fun theLanguageBeingLearned() = cases("learned_language").forEach { c ->
        assertEquals(c.toString(), c.string("out"), Speech.learned(c.string("language"), c.string("pupil"), c["spelling"]!!.jsonPrimitive.boolean))
    }

    @Test
    fun thePagesTextsSentByThePage() = cases("page_texts").forEach { c ->
        assertEquals(c.toString(), strings(c["out"]), strings(Generation.pageTexts(c.string("raw"), c["photos"]!!.jsonPrimitive.int)))
    }

    @Test
    fun theStandingInstructionsToldTheAi() = cases("standing_instructions").forEach { c ->
        val child = (c["child"] as? JsonObject)?.let { Child("c", "Jules", grade = it.string("grade"), instructions = it.string("instructions")) }
        assertEquals(c.toString(), c.string("out"), Generation.standingInstructions(c.string("instructions"), Children.forAi(child)))
    }
}
