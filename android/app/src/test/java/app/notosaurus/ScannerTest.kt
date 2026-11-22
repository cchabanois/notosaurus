package app.notosaurus

import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
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

    /** As MainActivity.capture takes the scanner's answer: a cancellation rethrown, any other
     * failure the camera. */
    private suspend fun captured(scan: suspend () -> String): String = try {
        scan()
    } catch (e: CancellationException) {
        throw e
    } catch (e: Exception) {
        "camera"
    }

    @Test
    fun googlePlayServicesTooSlowGivesTheCamera() = runBlocking {
        // Its screens never ready (Play services fetching the module, offline): the camera,
        // not the 📷 left unanswered
        assertEquals("camera", captured { Scanner.within(50) { awaitCancellation() } })
        assertEquals("pages", captured { Scanner.within(5_000) { "pages" } })
    }

    @Test
    fun aRealCancellationStillEnds() = runBlocking {
        // The activity gone: the scan ends with it, no camera opened
        var answer: String? = null
        val job = launch(start = CoroutineStart.UNDISPATCHED) { answer = captured { Scanner.within(60_000) { awaitCancellation() } } }
        job.cancel()
        job.join()
        assertTrue(job.isCancelled)
        assertNull(answer)
        assertFalse(job.isActive)
    }
}
