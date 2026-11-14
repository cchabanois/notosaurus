package app.notosaurus

import android.Manifest
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import androidx.test.rule.GrantPermissionRule
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File

/** The phone's microphone as the 🎤 records (the JVM tests use a fake): AAC in ADTS frames;
 * its speech recognition as the 🎤 listens. */
@RunWith(AndroidJUnit4::class)
class DictationTest {
    @get:Rule val mic: GrantPermissionRule = GrantPermissionRule.grant(Manifest.permission.RECORD_AUDIO)

    @Test
    fun aSecondRecorded() {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val file = File(context.cacheDir, "dictation-test.aac").apply { delete() }
        val recorder = MicRecorder(context)
        recorder.start(file)
        Thread.sleep(1500)
        recorder.stop()
        val audio = file.readBytes()
        file.delete()
        assertTrue("${audio.size} bytes", audio.size > Dictation.MIN_BYTES)
        // An ADTS frame starts with its sync word (12 bits set), then MPEG-4, layer 0
        assertEquals(0xFF, audio[0].toInt() and 0xFF)
        assertEquals(0xF0, audio[1].toInt() and 0xF6)
    }

    @Test
    fun thePhonesRecognitionListensThenStops() {
        // On the main thread as it asks, started again after its pauses, then stopped: done
        // told (nothing said on an emulator: no text, no failure)
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val listener = PhoneListener(context)
        assumeTrue("no speech recognition service on this device", listener.available())
        val failed = mutableListOf<String>()
        val done = java.util.concurrent.CountDownLatch(1)
        listener.start("fr-FR", {}, { failed += it })
        Thread.sleep(8000) // longer than a pause: started again meanwhile, unless one segmented session
        listener.stop { done.countDown() }
        assertTrue("stopped", done.await(6, java.util.concurrent.TimeUnit.SECONDS))
        assertTrue("$failed", failed.isEmpty() || failed == listOf("dictation.recognizer"))
        // From Android 13, the service takes the segmented session (EXTRA_SEGMENTED_SESSION and
        // its length) without refusing it: one start. (An emulator hears nothing, so its service
        // never reaches a pause: the restarts it saves aren't seen here, only that it's accepted)
        val mode = "starts ${listener.starts}, refused ${PhoneListener.segmentsRefused}"
        android.util.Log.i("DictationTest", mode)
        if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.TIRAMISU) {
            assertFalse(mode, PhoneListener.segmentsRefused)
            assertEquals(mode, 1, listener.starts)
        }
    }
}
