package app.notosaurus

import android.content.Context
import android.media.MediaRecorder
import android.os.Build
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeoutOrNull
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import java.io.File

/** What the 🎤 records with: AAC in ADTS frames (audio/aac), which the relay's AI hears.
 * ADTS frames stand on their own: a recording cut short is still readable. */
interface Recorder {
    fun start(file: File)

    /** The recording is in the file; may fail when it was too short to hold anything. */
    fun stop()
}

/**
 * The page's 🎤 (the instructions, a correction): heard by the phone's own speech
 * recognition (`listener`), its text shown as it comes ("✨ Tidy up" cleans it after); a phone
 * without one: recorded, then written by the relay's AI as the user meant to type it
 * (/v1/transcribe). One at a time.
 */
class Dictation(
    private val folder: File,
    private val recorder: Recorder,
    private val relay: () -> Relay,
    private val listener: Listener? = null,
) {
    private var recording: File? = null

    /** The phone hears it: the text as it comes, no relay. */
    val live: Boolean get() = listener?.available() == true

    @Volatile private var heard = ""
    @Volatile private var failure: String? = null
    @Volatile private var listening = false

    /** Started by listen(), until stopped (a failure too: said when stopped). */
    @Volatile var listeningLive = false
        private set

    /** Listens with the phone's recognition, in `language` (a BCP 47 tag). */
    @Synchronized
    fun listen(language: String) {
        val phone = listener ?: throw BadRequest("dictation.recognizer")
        cancel()
        heard = ""
        failure = null
        listening = true
        listeningLive = true
        phone.start(language, { heard = it }, { failure = it; listening = false })
    }

    /** What was heard so far, and the error that stopped it (null: none). */
    fun heard(): Pair<String, String?> = heard to failure

    /** Stopped: everything heard ("" when nothing). */
    suspend fun stopListening(): String {
        val phone = listener ?: return ""
        listeningLive = false
        if (listening) {
            listening = false
            val stopped = CompletableDeferred<Unit>()
            phone.stop { stopped.complete(Unit) }
            withTimeoutOrNull(STOP_MS) { stopped.await() }
        }
        failure?.let { throw BadRequest(it) }
        return heard.trim()
    }

    // Asked from Ktor's threads (two taps at once): one at a time, the recording with them
    @Synchronized
    fun start() {
        cancel() // one left listening (the page closed meanwhile): dropped
        val file = File(folder, "dictation.aac").apply { delete() }
        try {
            recorder.start(file)
        } catch (e: Exception) { // the microphone taken by another app, or none
            file.delete()
            throw BadRequest("dictation.failed", buildJsonObject { put("detail", e.message ?: e.javaClass.simpleName) })
        }
        recording = file
    }

    /** What was said, as text ("" when nothing was heard). `kind`: "prompt" or "correction";
     * `language`: the page's, its English name. */
    suspend fun stop(kind: String, language: String): String {
        val file = taken() ?: throw BadRequest("dictation.failed")
        val audio = withContext(Dispatchers.IO) { file.takeIf { it.isFile }?.readBytes().also { file.delete() } }
        if (audio == null || audio.size < MIN_BYTES) return ""
        return relay().transcribe(kind, language, audio)
    }

    @Synchronized
    fun cancel() {
        taken()?.delete()
        listeningLive = false
        if (listening) {
            listening = false
            listener?.stop {}
        }
    }

    /** The recording stopped and handed over, once (null: none going). */
    @Synchronized
    private fun taken(): File? {
        val file = recording ?: return null
        recording = null
        runCatching { recorder.stop() } // too short: nothing in it, said by stop
        return file
    }

    companion object {
        const val MIN_BYTES = 1000 // a quarter of a second at 32 kb/s: less is nothing said
        const val STOP_MS = 5000L // stopped: the recognition's last words waited for this long at most
        val KINDS = setOf("prompt", "correction")
    }
}

/** The phone's microphone: AAC, mono, 16 kHz (a voice), 32 kb/s: a minute weighs 240 KB. */
class MicRecorder(private val context: Context) : Recorder {
    private var recorder: MediaRecorder? = null

    override fun start(file: File) {
        val made = if (Build.VERSION.SDK_INT >= 31) MediaRecorder(context) else @Suppress("DEPRECATION") MediaRecorder()
        try {
            made.setAudioSource(MediaRecorder.AudioSource.VOICE_RECOGNITION)
            made.setOutputFormat(MediaRecorder.OutputFormat.AAC_ADTS)
            made.setAudioEncoder(MediaRecorder.AudioEncoder.AAC)
            made.setAudioChannels(1)
            made.setAudioSamplingRate(16_000)
            made.setAudioEncodingBitRate(32_000)
            made.setMaxDuration(MAX_MS) // the page stops at 2 minutes: this only if it didn't
            made.setOutputFile(file.path)
            made.prepare()
            made.start()
        } catch (e: Exception) {
            made.release()
            throw e
        }
        recorder = made
    }

    override fun stop() {
        val r = recorder ?: return
        recorder = null
        try {
            r.stop()
        } finally {
            r.release()
        }
    }

    companion object {
        const val MAX_MS = 150_000
    }
}
