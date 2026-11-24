package app.notosaurus

import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonArray
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.int
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.time.LocalDate

/** Lessons on the phone, in the computer's format (app/lessons.py). */
class LessonsTest {
    @get:Rule val folder = TemporaryFolder()

    private fun cards(vararg fronts: String) = buildJsonArray {
        fronts.forEach { add(buildJsonObject { put("front", it); put("back", "b") }) }
    }

    private fun lessons() = Lessons(folder.root)

    @Test
    fun changedInTheSecondOfItsSendStillAfterIt() {
        val sent = buildJsonObject { put("exported_at", "2026-10-30T10:15") } // LocalDateTime writes no ":00"
        val now = java.time.LocalDateTime.parse("2026-10-30T10:15:00")
        assertEquals("2026-10-30T10:15:01", Lessons.changedAt(sent, now))
        assertEquals("2026-10-30T10:16", Lessons.changedAt(sent, now.plusMinutes(1)))
        assertEquals("2026-10-30T10:15", Lessons.changedAt(buildJsonObject {}, now)) // never sent
    }

    @Test
    fun aNewLessonHasItsFolderPhotosAndCardIds() {
        val lessons = lessons()
        val lesson = lessons.create(
            mapOf("deck" to JsonPrimitive("Espagnol::Leçon 5 - La famille"), "cards" to cards("la mère", "le père")),
            listOf(byteArrayOf(1, 2), byteArrayOf(3)),
        )
        assertEquals("${LocalDate.now()}-espagnol-lecon-5-la-famille", lesson.string("id"))
        assertEquals(2, lesson["photo_count"]!!.jsonPrimitive.int)
        assertArrayEquals(byteArrayOf(3), lessons.photo(lesson.string("id"), 2)!!.readBytes())
        assertEquals(listOf(byteArrayOf(1, 2), byteArrayOf(3)).map { it.toList() }, lessons.photos(lesson.string("id")).values.map { it.toList() })
        val ids = lesson["cards"]!!.jsonArray.map { it.jsonObject.string("id") }
        assertTrue(ids.all { it.length == 12 } && ids.distinct().size == 2)
        // The page's defaults, as the computer writes them
        assertEquals(JsonPrimitive(false), lesson["typing"])
        assertEquals(JsonNull, lesson["exported_at"])
        assertEquals(lesson, lessons.get(lesson.string("id"))) // as read back
    }

    /** A lesson of 5 pages (page n holding n), cards from pages 3 and 5, its page `missing` then removed. */
    private fun lessonWithout(lessons: Lessons, missing: Int): String {
        val cards = buildJsonArray {
            for (page in listOf(3, 5)) add(buildJsonObject { put("front", "p$page"); put("back", "b"); put("page", page) })
        }
        val id = lessons.create(mapOf("deck" to JsonPrimitive("D"), "cards" to cards), (1..5).map { byteArrayOf(it.toByte()) }).string("id")
        assertTrue(folder.root.resolve("$id/page-$missing.jpg").delete())
        return id
    }

    private fun pages(lesson: JsonObject) = lesson["pages"]!!.jsonArray.map { it.jsonPrimitive.int }

    @Test
    fun aLessonsPagesByTheirNumbers() {
        // Page 3 removed: the others keep their number (page 4 is page-4.jpg, not the 4th there)
        val lessons = lessons()
        val id = lessonWithout(lessons, 3)
        val lesson = lessons.get(id)!!
        assertEquals(4, lesson["photo_count"]!!.jsonPrimitive.int)
        assertEquals(listOf(1, 2, 4, 5), pages(lesson))
        assertEquals(mapOf(1 to 1, 2 to 2, 4 to 4, 5 to 5), lessons.photos(id).mapValues { it.value.single().toInt() })
        assertFalse(folder.root.resolve("$id/lesson.json").readText().contains("\"pages\"")) // its folder's, not kept
    }

    @Test
    fun aPageAddedNeverTakesANumberUsedNorWritesOverOne() {
        val lessons = lessons()
        fun completed(id: String) = lessons.completed(
            id,
            mapOf("cards" to buildJsonArray { add(buildJsonObject { put("front", "new"); put("back", "b"); put("page", 1) }) },
                "page_texts" to buildJsonArray { add(JsonPrimitive("its text")) }),
            listOf(byteArrayOf(9)),
        )!!
        // Page 3 missing: page 5 untouched, the new page 6
        val middle = lessonWithout(lessons, 3)
        val done = completed(middle)
        assertArrayEquals(byteArrayOf(5), lessons.photo(middle, 5)!!.readBytes())
        assertArrayEquals(byteArrayOf(9), lessons.photo(middle, 6)!!.readBytes())
        assertEquals(listOf(1, 2, 4, 5, 6), pages(done))
        assertEquals(5, done["photo_count"]!!.jsonPrimitive.int)
        assertEquals(listOf(3, 5, 6), done.cards().map { it["page"]!!.jsonPrimitive.int })
        assertEquals(listOf("", "", "", "", "", "its text"), done["page_texts"]!!.jsonArray.map { it.jsonPrimitive.content })
        // The last page (5) missing, a card still from it: the new page 6, never 5 again
        val last = lessonWithout(lessons, 5)
        assertEquals(listOf(1, 2, 3, 4, 6), pages(completed(last)))
        assertArrayEquals(byteArrayOf(9), lessons.photo(last, 6)!!.readBytes())
        assertNull(lessons.photo(last, 5))
    }

    @Test
    fun twoLessonsOfTheSameDeckHaveTheirOwnFolder() {
        val lessons = lessons()
        val a = lessons.create(mapOf("deck" to JsonPrimitive("Maths")), emptyList())
        val b = lessons.create(mapOf("deck" to JsonPrimitive("Maths")), emptyList())
        assertNotEquals(a.string("id"), b.string("id"))
        assertEquals(2, lessons.list().size)
    }

    @Test
    fun updateKeepsWhatThePageDidntChange() {
        val lessons = lessons()
        val id = lessons.create(mapOf("deck" to JsonPrimitive("D"), "cards" to cards("a")), emptyList()).string("id")
        val first = lessons.get(id)!!["cards"]!!.jsonArray[0].jsonObject
        val changes = buildJsonObject {
            put("deck", "D2")
            put("cards", JsonArray(listOf(first) + cards("added")))
            put("frames", JsonNull) // null: unchanged
            put("photo_count", 99) // not the page's to change
            put("id", "other")
        }
        val updated = lessons.update(id, changes, exported = true)!!
        assertEquals("D2", updated.string("deck"))
        assertEquals(id, updated.string("id"))
        assertEquals(0, updated["photo_count"]!!.jsonPrimitive.int)
        assertEquals(JsonArray(emptyList()), updated["frames"])
        val ids = updated["cards"]!!.jsonArray.map { it.jsonObject.string("id") }
        assertEquals(first.string("id"), ids[0]) // kept: Anki knows the note by it
        assertEquals(12, ids[1].length) // the added card gets one
        assertTrue(updated.string("exported_at").isNotEmpty())
        assertNull(lessons.update("nope", changes))
    }

    @Test
    fun summaryHasNoCards() {
        val lessons = lessons()
        val summary = lessons.summary(lessons.create(mapOf("cards" to cards("a", "b")), emptyList()))
        assertFalse("cards" in summary)
        assertEquals(2, summary["card_count"]!!.jsonPrimitive.int)
    }

    @Test
    fun onlyItsOwnFolders() {
        val lessons = lessons()
        folder.newFolder("outside").resolve("lesson.json").writeText(JsonObject(emptyMap()).toString())
        assertNull(lessons.get("../outside"))
        assertNull(lessons.photo("../outside", 1))
        assertFalse(lessons.delete("../outside"))
        val id = lessons.create(mapOf("deck" to JsonPrimitive("x")), emptyList()).string("id")
        assertTrue(lessons.delete(id))
        assertNull(lessons.get(id))
    }

    @Test
    fun slugs() {
        assertEquals("espagnol-lecon-5-la-famille", Lessons.slug("Espagnol::Leçon 5 - La famille"))
        assertEquals("", Lessons.slug("!!!"))
        assertTrue(Lessons.slug("x".repeat(100)).length <= 40)
    }

    @Test
    fun anyDeckGivesAFolderOfItsOwnInsideTheLessons() {
        val lessons = lessons()
        val random = java.util.Random(42)
        val odd = listOf("", "..", "../..", "/", "\\..\\", "::", ".", "🦕", "İıßÆœ", "e\u0301\u200b", "\u0000\t\n", "%2e%2e/x", "-", "a".repeat(500))
        val pieces = listOf(".", "/", "\\", ":", "-", " ", "İ", "🦕", "\u0301")
        val generated = List(200) { // any characters (no lone surrogate), those above more often
            (1..random.nextInt(60)).joinToString("") {
                if (random.nextBoolean()) pieces[random.nextInt(pieces.size)] else random.nextInt(0xD000).toChar().toString()
            }
        }
        for (deck in odd + generated) {
            val lesson = lessons.create(mapOf("deck" to JsonPrimitive(deck)), emptyList())
            val id = lesson.string("id")
            assertTrue(id, Regex("^[a-z0-9][a-z0-9-]*$").matches(id))
            assertEquals(deck, lessons.get(id)!!.string("deck")) // found again by its id
            assertEquals(folder.root.canonicalFile, folder.root.resolve(id).canonicalFile.parentFile)
        }
    }
}
