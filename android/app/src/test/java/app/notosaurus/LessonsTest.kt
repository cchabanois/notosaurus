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
    fun aNewLessonHasItsFolderPhotosAndCardIds() {
        val lessons = lessons()
        val lesson = lessons.create(
            mapOf("deck" to JsonPrimitive("Espagnol::Leçon 5 - La famille"), "cards" to cards("la mère", "le père")),
            listOf(byteArrayOf(1, 2), byteArrayOf(3)),
        )
        assertEquals("${LocalDate.now()}-espagnol-lecon-5-la-famille", lesson.string("id"))
        assertEquals(2, lesson["photo_count"]!!.jsonPrimitive.int)
        assertArrayEquals(byteArrayOf(3), lessons.photo(lesson.string("id"), 2)!!.readBytes())
        assertEquals(listOf(byteArrayOf(1, 2), byteArrayOf(3)).map { it.toList() }, lessons.photos(lesson.string("id")).map { it.toList() })
        val ids = lesson["cards"]!!.jsonArray.map { it.jsonObject.string("id") }
        assertTrue(ids.all { it.length == 12 } && ids.distinct().size == 2)
        // The page's defaults, as the computer writes them
        assertEquals(JsonPrimitive(false), lesson["typing"])
        assertEquals(JsonNull, lesson["exported_at"])
        assertEquals(lesson, lessons.get(lesson.string("id"))) // as read back
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
}
