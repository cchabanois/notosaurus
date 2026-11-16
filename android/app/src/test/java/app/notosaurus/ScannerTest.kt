package app.notosaurus

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/** How many pages one scan may give: the lesson's places left, one for a single photo. */
class ScannerTest {
    @Test
    fun theLessonsPlacesLeft() {
        assertEquals(7, Scanner.pageLimit(multiple = true, free = 7))
        assertEquals(1, Scanner.pageLimit(multiple = true, free = 1))
        // Unknown (another page): a whole lesson's, the page saying which didn't fit
        assertEquals(LocalServer.MAX_PHOTOS, Scanner.pageLimit(multiple = true, free = null))
        // Never none, never more than a lesson has (the scanner takes 1 at least)
        assertEquals(1, Scanner.pageLimit(multiple = true, free = 0))
        assertEquals(1, Scanner.pageLimit(multiple = true, free = -3))
        assertEquals(LocalServer.MAX_PHOTOS, Scanner.pageLimit(multiple = true, free = 500))
    }

    @Test
    fun aSinglePhotoInputTakesOnePage() {
        // A page served by an older add-on: its camera input takes one photo
        assertEquals(1, Scanner.pageLimit(multiple = false, free = null))
        assertEquals(1, Scanner.pageLimit(multiple = false, free = 12))
    }

    @Test
    fun whatThePageAnswers() {
        assertEquals(12, Scanner.free("12"))
        assertEquals(0, Scanner.free("0"))
        assertNull(Scanner.free("null"))
        assertNull(Scanner.free(null))
        assertNull(Scanner.free("\"twelve\""))
        assertNull(Scanner.free(""))
    }
}
