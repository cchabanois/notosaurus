package app.notosaurus

import android.content.Intent
import android.os.Build
import android.os.Bundle
import android.os.ParcelFileDescriptor
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
import java.io.FileInputStream

/** PhoneListener with the service and the sound it is given: what it sends the service, and
 * what it makes of its answers (the app's sound from Android 13, else the segmented session, a
 * refusal, restarts), whatever the device's own service does (an emulator's hears nothing:
 * DictationTest). */
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

    /** The microphone as the test plays it: each chunk given when the test says. */
    private class FakeSound : Sound {
        var heard: ((ByteArray) -> Unit)? = null
        @Volatile var stopped = false // set on the main thread, waited for on the test's
        override fun start(heard: (ByteArray) -> Unit): Boolean { this.heard = heard; return true }
        override fun stop() { stopped = true }
        fun say(text: String) = heard!!(text.toByteArray())
    }

    private val instrumentation = InstrumentationRegistry.getInstrumentation()
    private val service = FakeRecognizer()
    private val sound = FakeSound()
    private val listener = PhoneListener(instrumentation.targetContext, { service }, { sound })
    private val heard = mutableListOf<String>()
    private val failed = mutableListOf<String>()

    @Before
    fun fresh() {
        assumeTrue("segmented sessions: Android 13 and later", Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU)
        // The service opening the microphone itself (a service that refused the app's sound):
        // the tests of the segmented session; the app's sound has its own (fed*)
        PhoneListener.feedRefused = true
        PhoneListener.segmentsRefused = false
    }

    @After
    fun forget() {
        PhoneListener.feedRefused = false
        PhoneListener.segmentsRefused = false
    }

    private fun begin(fed: Boolean = false) {
        PhoneListener.feedRefused = !fed
        listener.start("fr-FR", { heard += it }, { failed += it })
        instrumentation.waitForIdleSync()
    }

    private fun fed(intent: Intent) = intent.getParcelableExtra(RecognizerIntent.EXTRA_AUDIO_SOURCE, ParcelFileDescriptor::class.java)

    // What the session's pipe was given: `bytes` of it, read as the service would
    private fun read(source: ParcelFileDescriptor, bytes: Int): String {
        val got = ByteArray(bytes)
        var n = 0
        val input = FileInputStream(source.fileDescriptor)
        while (n < bytes) n += input.read(got, n, bytes - n).also { require(it > 0) { "the pipe ended" } }
        return String(got)
    }

    private fun segmented(intent: Intent) = intent.hasExtra(RecognizerIntent.EXTRA_SEGMENTED_SESSION)

    private fun said(words: String) = Bundle().apply { putStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION, arrayListOf(words)) }

    private fun answer(what: RecognitionListener.() -> Unit) {
        instrumentation.runOnMainSync { service.listener.what() }
        // A restart is posted RESTART_MS later: due once that long has gone by, and run before
        // the main thread is idle (waitForIdleSync runs every message due)
        Thread.sleep(PhoneListener.RESTART_MS + 5)
        instrumentation.waitForIdleSync()
    }

    @Test
    fun fedTheAppsSoundInOneSession() {
        begin(fed = true)
        val (first) = service.sent
        val source = fed(first)
        assertTrue("given the app's sound", source != null)
        assertEquals(RecognizerIntent.EXTRA_AUDIO_SOURCE, first.getStringExtra(RecognizerIntent.EXTRA_SEGMENTED_SESSION))
        assertEquals(MicSound.RATE, first.getIntExtra(RecognizerIntent.EXTRA_AUDIO_SOURCE_SAMPLING_RATE, 0))
        assertEquals(1, first.getIntExtra(RecognizerIntent.EXTRA_AUDIO_SOURCE_CHANNEL_COUNT, 0))
        sound.say("douze")
        assertEquals("douze", read(source!!, 5))
        answer { onSegmentResults(said("douze cartes")) }
        assertEquals("douze cartes", heard.last())

        var done = false
        instrumentation.runOnMainSync { listener.stop { done = true } }
        instrumentation.waitForIdleSync()
        assertTrue("the microphone stopped", sound.stopped)
        assertEquals("its sound ends the session, not stopListening", 0, service.stopped)
        assertEquals("the pipe closed: the session ends", -1, FileInputStream(source.fileDescriptor).read())
        answer { onEndOfSegmentedSession() }
        assertTrue("done once the session ended", done)
        assertEquals(1, listener.starts)
        assertFalse(PhoneListener.feedRefused)
        assertTrue("$failed", failed.isEmpty())
    }

    @Test
    fun fedTheWordsSaidWhileTheServiceStartsAgainAreHeard() {
        // The service ends its session at a pause anyway (Google's, opening the microphone
        // itself, did at each one: the words said while it started again were lost)
        begin(fed = true)
        val first = fed(service.sent[0])!!
        sound.say("un deux ")
        assertEquals("un deux ", read(first, 8))
        first.close() // the service's end of the pipe closed: its session is over
        sound.say("cinq ") // said meanwhile
        answer { onResults(said("un deux")) }
        assertEquals("started again, fed", 2, service.sent.size)
        assertFalse("not a refusal", PhoneListener.feedRefused)
        val second = fed(service.sent[1])!!
        sound.say("six")
        assertEquals("cinq six", read(second, 8))
        assertEquals("un deux", heard.last())
        assertTrue("$failed", failed.isEmpty())
    }

    @Test
    fun fedADictationNeverStoppedStopsByItself() {
        // The page closed or reloaded while listening: no stop comes, the microphone stops
        // all the same once the longest dictation is over
        PhoneListener.feedRefused = false
        val forgotten = PhoneListener(instrumentation.targetContext, { service }, { sound }, longest = 500)
        forgotten.start("fr-FR", { heard += it }, { failed += it })
        instrumentation.waitForIdleSync()
        val source = fed(service.sent[0])!!
        val deadline = System.currentTimeMillis() + 10_000 // `longest` is 500 ms: a hang fails fast
        while (!sound.stopped && System.currentTimeMillis() < deadline) Thread.sleep(20)
        instrumentation.waitForIdleSync()
        assertTrue("the microphone stopped", sound.stopped)
        assertEquals("the pipe closed: the session ends", -1, FileInputStream(source.fileDescriptor).read())
        answer { onEndOfSegmentedSession() }
        assertEquals("not started again", 1, service.sent.size)
        assertTrue("$failed", failed.isEmpty())
    }

    @Test
    fun fedAnErrorBeforeAnyWordIsARefusalOfTheSound() {
        // A service that won't take the app's sound: it opens the microphone itself from then on
        begin(fed = true)
        answer { onError(SpeechRecognizer.ERROR_CLIENT) }
        assertTrue(PhoneListener.feedRefused)
        assertTrue("the app's microphone stopped", sound.stopped)
        assertEquals(2, service.sent.size)
        assertEquals("not fed", null, fed(service.sent[1]))
        assertTrue("segmented", segmented(service.sent[1]))
        assertTrue("$failed", failed.isEmpty())
    }

    @Test
    fun fedASilenceEndingTheSessionIsNoRefusal() {
        begin(fed = true)
        answer { onError(SpeechRecognizer.ERROR_SPEECH_TIMEOUT) }
        assertFalse(PhoneListener.feedRefused)
        assertEquals(2, service.sent.size)
        assertTrue("fed again", fed(service.sent[1]) != null)
    }

    @Test
    fun oneSegmentedSessionItsPartsKept() {
        begin()
        val (first) = service.sent
        assertTrue("asked segmented", segmented(first))
        // Its length an Int: Google's service reads a Long as 0, its session then ended at the first pause
        assertEquals(10 * 60 * 1000, first.getIntExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_MINIMUM_LENGTH_MILLIS, 0))
        assertFalse("no silence length asked: Google's service then loses the parts", first.hasExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_COMPLETE_SILENCE_LENGTH_MILLIS))
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
        begin()
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
        begin()
        answer { onError(SpeechRecognizer.ERROR_CLIENT) }
        assertTrue(PhoneListener.segmentsRefused)
        assertEquals(2, service.sent.size)
        assertFalse("started again, not segmented", segmented(service.sent[1]))
        assertTrue("$failed", failed.isEmpty())
    }

    @Test
    fun anErrorAfterWordsHeardIsNoRefusal() {
        begin()
        answer { onPartialResults(said("douze")) }
        answer { onError(SpeechRecognizer.ERROR_SERVER) }
        assertFalse(PhoneListener.segmentsRefused)
        assertEquals(listOf("dictation.recognizer"), failed)
    }
}
