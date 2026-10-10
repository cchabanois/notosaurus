package app.notosaurus

import android.Manifest
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import androidx.test.rule.GrantPermissionRule
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File

/** The phone's microphone as the 🎤 records (the JVM tests use a fake): AAC in ADTS frames. */
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
}
