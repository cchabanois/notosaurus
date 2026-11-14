package app.notosaurus

import android.speech.SpeechRecognizer
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/** The phone's dictation: one segmented session from Android 13 (its sounds once), else
 * restarts at each pause (their sounds each time, as before), decided once per app's run. */
class PhoneListenerTest {
    @Test
    fun segmentedFromAndroid13UnlessRefused() {
        assertTrue(PhoneListener.segmentedSession(33, refused = false))
        assertTrue(PhoneListener.segmentedSession(36, refused = false))
        assertFalse(PhoneListener.segmentedSession(32, refused = false)) // Android 12L: restarts, beeps and all
        assertFalse(PhoneListener.segmentedSession(28, refused = false))
        assertFalse(PhoneListener.segmentedSession(36, refused = true)) // the service refused it once
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
