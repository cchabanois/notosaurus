package app.notosaurus

import android.speech.SpeechRecognizer
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/** The phone's dictation: from Android 13 the app's own sound in one session, else one
 * segmented session (its sounds once), else restarts at each pause (their sounds each time, as
 * before), a refusal kept for the app's run. */
class PhoneListenerTest {
    @Test
    fun theAppsSoundFromAndroid13ThenTheModesNotRefused() {
        fun mode(sdk: Int, feed: Boolean = false, segments: Boolean = false) = PhoneListener.mode(sdk, feed, segments)
        assertEquals(PhoneListener.Mode.FED, mode(33))
        assertEquals(PhoneListener.Mode.FED, mode(37))
        assertEquals(PhoneListener.Mode.FED, mode(36, segments = true)) // its own sessions refused: fed all the same
        assertEquals(PhoneListener.Mode.SEGMENTED, mode(36, feed = true)) // the service won't take the app's sound
        assertEquals(PhoneListener.Mode.RESTARTS, mode(36, feed = true, segments = true))
        assertEquals(PhoneListener.Mode.RESTARTS, mode(32)) // Android 12L: restarts, beeps and all
        assertEquals(PhoneListener.Mode.RESTARTS, mode(28))
    }

    @Test
    fun aSegmentedSessionsLengthIsAnInt() {
        // Google's service reads it with getIntExtra: a Long is taken as 0, the session then
        // ended at the first pause (a restart, the words said meanwhile lost)
        val length = PhoneListener.segmentedExtras()[android.speech.RecognizerIntent.EXTRA_SPEECH_INPUT_MINIMUM_LENGTH_MILLIS]
        assertTrue("$length", (length as Any) is Int)
        assertEquals(10 * 60 * 1000, length)
    }

    @Test
    fun aSegmentedSessionsErrorBeforeAnyWordIsARefusal() {
        // Stopped as at a pause, or the mode unknown: restarts instead, dictation goes on
        for (error in listOf(SpeechRecognizer.ERROR_SPEECH_TIMEOUT, SpeechRecognizer.ERROR_NO_MATCH, SpeechRecognizer.ERROR_CLIENT,
            SpeechRecognizer.ERROR_CANNOT_CHECK_SUPPORT, SpeechRecognizer.ERROR_LANGUAGE_NOT_SUPPORTED)) {
            assertTrue("$error", PhoneListener.refusesSegments(error, heardAny = false))
        }
        // Words heard: the session worked, its later error is no refusal
        assertFalse(PhoneListener.refusesSegments(SpeechRecognizer.ERROR_NO_MATCH, heardAny = true))
        // The microphone refused: a failure, not a mode to fall back from
        assertFalse(PhoneListener.refusesSegments(SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS, heardAny = false))
    }

    @Test
    fun segmentsJoinedAsTheRestartsParts() {
        var text = ""
        for (segment in listOf("La Révolution", "", "commence en 1789")) text = PhoneListener.joined(text, segment)
        assertEquals("La Révolution commence en 1789", text)
    }
}
