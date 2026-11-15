package app.notosaurus

import android.content.Intent
import android.os.Build
import android.os.Bundle
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith

/** PhoneListener with the service it is given: what it sends the service, and what it makes of
 * its answers (the segmented session from Android 13, a refusal, restarts), whatever the
 * device's own service does (an emulator's hears nothing: DictationTest). */
@RunWith(AndroidJUnit4::class)
class PhoneListenerServiceTest {
    /** A service driven by the test: the intents it is sent, its listener to answer through. */
    private class FakeRecognizer : Recognizer {
        val sent = mutableListOf<Intent>()
        var stopped = 0
        lateinit var listener: RecognitionListener
        override fun setRecognitionListener(listener: RecognitionListener) { this.listener = listener }
        override fun startListening(intent: Intent) { sent += intent }
        override fun stopListening() { stopped++ }
        override fun destroy() {}
    }

    private val instrumentation = InstrumentationRegistry.getInstrumentation()
    private val service = FakeRecognizer()
    private val listener = PhoneListener(instrumentation.targetContext) { service }
    private val heard = mutableListOf<String>()
    private val failed = mutableListOf<String>()

    @Before
    fun fresh() {
        assumeTrue("segmented sessions: Android 13 and later", Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU)
        PhoneListener.segmentsRefused = false
        listener.start("fr-FR", { heard += it }, { failed += it })
        instrumentation.waitForIdleSync()
    }

    @After
    fun forget() {
        PhoneListener.segmentsRefused = false
    }

    private fun segmented(intent: Intent) = intent.hasExtra(RecognizerIntent.EXTRA_SEGMENTED_SESSION)

    private fun said(words: String) = Bundle().apply { putStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION, arrayListOf(words)) }

    private fun answer(what: RecognitionListener.() -> Unit) {
        instrumentation.runOnMainSync { service.listener.what() }
        Thread.sleep(400) // a restart comes after a short delay
        instrumentation.waitForIdleSync()
    }

    @Test
    fun oneSegmentedSessionItsPartsKept() {
        val (first) = service.sent
        assertTrue("asked segmented", segmented(first))
        assertEquals("fr-FR", first.getStringExtra(RecognizerIntent.EXTRA_LANGUAGE))
        answer { onPartialResults(said("douze")) }
        answer { onSegmentResults(said("douze cartes")) }
        answer { onSegmentResults(said("sur el abuelo")) }
        assertEquals("douze cartes sur el abuelo", heard.last())
        assertEquals("one start: no sound at each pause", 1, service.sent.size)

        var done = false
        instrumentation.runOnMainSync { listener.stop { done = true } }
        instrumentation.waitForIdleSync()
        assertEquals(1, service.stopped)
        answer { onEndOfSegmentedSession() }
        assertTrue("done once the session ended", done)
        assertEquals(1, listener.starts)
        assertFalse(PhoneListener.segmentsRefused)
        assertTrue("$failed", failed.isEmpty())
    }

    @Test
    fun aPlainAnswerToASegmentedSessionIsARefusal() {
        // The service stopped at the pause, as it does without segments: restarts from then on
        answer { onResults(said("douze cartes")) }
        assertTrue(PhoneListener.segmentsRefused)
        assertEquals(2, service.sent.size)
        assertFalse("started again, not segmented", segmented(service.sent[1]))
        assertEquals("douze cartes", heard.last())
        answer { onResults(said("sur el abuelo")) }
        assertEquals("douze cartes sur el abuelo", heard.last())
        assertTrue("$failed", failed.isEmpty())
    }

    @Test
    fun anErrorBeforeAnyWordIsARefusal() {
        answer { onError(SpeechRecognizer.ERROR_CLIENT) }
        assertTrue(PhoneListener.segmentsRefused)
        assertEquals(2, service.sent.size)
        assertFalse("started again, not segmented", segmented(service.sent[1]))
        assertTrue("$failed", failed.isEmpty())
    }

    @Test
    fun anErrorAfterWordsHeardIsNoRefusal() {
        answer { onPartialResults(said("douze")) }
        answer { onError(SpeechRecognizer.ERROR_SERVER) }
        assertFalse(PhoneListener.segmentsRefused)
        assertEquals(listOf("dictation.recognizer"), failed)
    }
}
