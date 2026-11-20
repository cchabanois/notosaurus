package app.notosaurus

import android.annotation.SuppressLint
import android.content.Context
import android.content.Intent
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.ParcelFileDescriptor
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import java.io.IOException
import kotlin.concurrent.thread

/** What hears the 🎤 as it is said, the text shown as it comes (the JVM tests use a fake). */
interface Listener {
    /** Whether this phone can listen (a speech recognition service: Google's app, mostly). */
    fun available(): Boolean

    /** Listens in `language` (a BCP 47 tag) until stopped, through the pauses: `heard` told the
     * whole text so far (the parts finished, then the one being said) whenever it changes,
     * `failed` an error code (relay_api's kind: "dictation.refused", "dictation.recognizer")
     * when it can't go on. */
    fun start(language: String, heard: (String) -> Unit, failed: (String) -> Unit)

    /** Stops: the last words told to `heard`, then `done` (at once when not listening). */
    fun stop(done: () -> Unit)
}

/**
 * The phone's own speech recognition (SpeechRecognizer), on the main thread as it asks.
 *
 * From Android 13, the app records the microphone itself, without a break, and gives the
 * service its sound (EXTRA_AUDIO_SOURCE, through a pipe: AudioRelay), in one session segmented
 * at the pauses (EXTRA_SEGMENTED_SESSION = EXTRA_AUDIO_SOURCE) that lasts as long as the sound:
 * the page's stop closes it. No start or stop sound at each pause, and should the service end
 * its session anyway, what is said while it starts again waits for the next one: never lost.
 * Left to open the microphone itself, Google's service (Samsung's A35, 2026-11) ends its
 * session at each pause whatever the extras ask: restarted, it missed the words said meanwhile.
 *
 * Before Android 13, or a service that won't take the sound (an error before anything heard),
 * the service opens the microphone: one segmented session by its length when it takes it, else
 * restarts at each pause (their sounds each time), each part's text kept; a refusal kept for
 * the app's run. Nothing reaches the relay: the recognition service hears it (on the phone, or
 * Google's servers, as the phone's settings say).
 */
class PhoneListener(
    private val context: Context,
    // The service, made for each dictation (a device test's fake: what it is sent, its answers)
    private val make: (Context) -> Recognizer = { SystemRecognizer(SpeechRecognizer.createSpeechRecognizer(it)) },
    // The microphone as the app records it (a device test's: a recording played)
    private val sound: () -> Sound = { MicSound() },
) : Listener {
    private val main = Handler(Looper.getMainLooper())
    private var recognizer: Recognizer? = null
    private var finished = "" // the parts heard to their end
    private var listening = false
    private var restarts = 0 // in a row, nothing heard between: a service that can't listen gives up
    private var mode = Mode.RESTARTS // this dictation's
    private var heardAny = false // since the session began: a refusal comes before any word
    private var recording: Sound? = null // fed: the microphone, recorded by the app
    private var relay: AudioRelay? = null // fed: its sound, to the session listening
    private var source: ParcelFileDescriptor? = null // fed: the session's end of the pipe, until the service has it
    internal var starts = 0 // the service started this dictation (the device test: once when fed or segmented)
        private set
    private var done: (() -> Unit)? = null

    /** How the service hears a dictation. */
    enum class Mode { FED, SEGMENTED, RESTARTS }

    override fun available() = SpeechRecognizer.isRecognitionAvailable(context)

    override fun start(language: String, heard: (String) -> Unit, failed: (String) -> Unit) {
        main.post {
            end()
            finished = ""
            listening = true
            restarts = 0
            mode = mode(Build.VERSION.SDK_INT, feedRefused, segmentsRefused)
            if (mode == Mode.FED && !record()) mode = mode(Build.VERSION.SDK_INT, feedRefused = true, segmentsRefused)
            heardAny = false
            starts = 0
            val made = make(context)
            recognizer = made
            made.setRecognitionListener(object : RecognitionListener {
                override fun onPartialResults(results: Bundle) {
                    best(results)?.let { restarts = 0; heardAny = true; heard(joined(finished, it)) }
                }

                // A part of the segmented session, its pause reached: kept, the session going on
                override fun onSegmentResults(segmentResults: Bundle) {
                    best(segmentResults)?.let { restarts = 0; heardAny = true; finished = joined(finished, it) }
                    heard(finished)
                }

                // The session's end: stopped by the page, or ended by the service (started again)
                override fun onEndOfSegmentedSession() {
                    heard(finished)
                    if (listening) listen(made, language) else end()
                }

                override fun onResults(results: Bundle) {
                    // A segmented session answered as a plain one: the service doesn't segment
                    // (fed, nothing is lost by starting again: the same mode)
                    if (mode == Mode.SEGMENTED && listening) refuse(Mode.SEGMENTED)
                    best(results)?.let { restarts = 0; finished = joined(finished, it) }
                    heard(finished)
                    if (listening) listen(made, language) else end()
                }

                override fun onError(error: Int) {
                    when {
                        !listening -> end()
                        mode == Mode.SEGMENTED && refusesSegments(error, heardAny) -> {
                            refuse(Mode.SEGMENTED)
                            main.postDelayed({ if (listening && recognizer === made) listen(made, language) }, RESTART_MS)
                        }
                        // A pause with nothing said, or the service still closing the last part
                        // (fed: its session ended on a silence, started again, nothing lost)
                        error in QUIET && ++restarts <= MAX_RESTARTS -> main.postDelayed({ if (listening && recognizer === made) listen(made, language) }, RESTART_MS)
                        // Fed, any other error before a word: the service won't take the sound
                        mode == Mode.FED && refusesSegments(error, heardAny) -> {
                            refuse(Mode.FED)
                            main.postDelayed({ if (listening && recognizer === made) listen(made, language) }, RESTART_MS)
                        }
                        else -> {
                            listening = false
                            failed(if (error == SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS) "dictation.refused" else "dictation.recognizer")
                            end()
                        }
                    }
                }

                // The service has the pipe's end: ours closed, so that it closing its own fails
                // the relay's writes (the session ended: the next one gets the sound)
                override fun onReadyForSpeech(params: Bundle?) = closeSource()
                override fun onBeginningOfSpeech() {}
                override fun onRmsChanged(rmsdB: Float) {}
                override fun onBufferReceived(buffer: ByteArray?) {}
                override fun onEndOfSpeech() {}
                override fun onEvent(eventType: Int, params: Bundle?) {}
            })
            listen(made, language)
        }
    }

    override fun stop(done: () -> Unit) {
        main.post {
            val going = recognizer
            if (going == null) return@post done()
            listening = false
            this.done = done
            // Its last words come in onResults or onEndOfSegmentedSession, then end(): fed, once
            // its sound ends
            if (mode == Mode.FED) stopRecording() else going.stopListening()
            main.postDelayed({ if (recognizer === going) end() }, LAST_WORDS_MS)
        }
    }

    private fun listen(made: Recognizer, language: String) {
        heardAny = false
        starts++
        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
            .putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            .putExtra(RecognizerIntent.EXTRA_LANGUAGE, language)
            .putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
            .putExtra(RecognizerIntent.EXTRA_CALLING_PACKAGE, context.packageName)
        val relay = relay
        if (mode == Mode.FED && relay != null && Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            val (read, write) = ParcelFileDescriptor.createPipe()
            closeSource()
            source = read
            relay.to(ParcelFileDescriptor.AutoCloseOutputStream(write))
            intent.putExtra(RecognizerIntent.EXTRA_AUDIO_SOURCE, read)
                .putExtra(RecognizerIntent.EXTRA_AUDIO_SOURCE_CHANNEL_COUNT, 1)
                .putExtra(RecognizerIntent.EXTRA_AUDIO_SOURCE_ENCODING, AudioFormat.ENCODING_PCM_16BIT)
                .putExtra(RecognizerIntent.EXTRA_AUDIO_SOURCE_SAMPLING_RATE, MicSound.RATE)
                .putExtra(RecognizerIntent.EXTRA_SEGMENTED_SESSION, RecognizerIntent.EXTRA_AUDIO_SOURCE)
        } else {
            // The service opening the microphone: its pauses long, so that it starts again
            // rarely (each restart misses what is said meanwhile)
            for ((key, value) in pauseExtras()) intent.putExtra(key, value)
            // Segmented for as long as a dictation lasts at most: the page's stop ends it before
            if (mode == Mode.SEGMENTED && Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                intent.putExtra(RecognizerIntent.EXTRA_SEGMENTED_SESSION, RecognizerIntent.EXTRA_SPEECH_INPUT_MINIMUM_LENGTH_MILLIS)
                for ((key, value) in segmentedExtras()) intent.putExtra(key, value)
            }
        }
        made.startListening(intent)
    }

    // The microphone recorded by the app, its sound to the relay: false when it can't be
    private fun record(): Boolean {
        val made = sound()
        val relay = AudioRelay()
        if (!made.start(relay::heard)) return false
        recording = made
        this.relay = relay
        return true
    }

    private fun stopRecording() {
        recording?.stop()
        recording = null
        relay?.end() // the pipe closed: the service's session ends, its last words then
        relay = null
    }

    private fun closeSource() {
        try {
            source?.close()
        } catch (_: IOException) {
        }
        source = null
    }

    // This service won't take `refused`: the next mode from now on, this dictation and the next
    private fun refuse(refused: Mode) {
        when (refused) {
            Mode.FED -> {
                feedRefused = true
                stopRecording()
                closeSource()
            }
            Mode.SEGMENTED -> segmentsRefused = true
            Mode.RESTARTS -> return
        }
        mode = mode(Build.VERSION.SDK_INT, feedRefused, segmentsRefused)
    }

    private fun end() {
        stopRecording()
        closeSource()
        recognizer?.destroy()
        recognizer = null
        done?.invoke()
        done = null
    }

    companion object {
        private val QUIET = setOf(SpeechRecognizer.ERROR_NO_MATCH, SpeechRecognizer.ERROR_SPEECH_TIMEOUT, SpeechRecognizer.ERROR_RECOGNIZER_BUSY)
        private const val RESTART_MS = 150L
        private const val MAX_RESTARTS = 40 // a quiet pause restarts it every few seconds: 2 minutes and more
        private const val LAST_WORDS_MS = 3000L // stopped: its last words waited for this long at most
        private const val SESSION_MS = 10 * 60 * 1000 // a segmented session's length, then started again
        private const val PAUSE_MS = 10_000 // a silence this long ends a part (the service opening the microphone)

        // The service refused the app's sound, or a segmented session, once: the next mode for
        // the rest of the app's run (set back by the device tests only)
        internal var feedRefused = false
        internal var segmentsRefused = false

        /** How the service hears a dictation: given the app's sound from Android 13 (API 33),
         * else one segmented session from Android 13, else restarts at each pause (their
         * sounds each time); a mode the service refused once skipped. */
        fun mode(sdk: Int, feedRefused: Boolean, segmentsRefused: Boolean) = when {
            sdk < Build.VERSION_CODES.TIRAMISU -> Mode.RESTARTS
            !feedRefused -> Mode.FED
            !segmentsRefused -> Mode.SEGMENTED
            else -> Mode.RESTARTS
        }

        /** A segmented session's extras, the service left to open the microphone. Its length
         * an Int: Google's service reads it with getIntExtra, a Long taken as 0 (its session
         * then ended at the first pause). */
        fun segmentedExtras(): Map<String, Int> = mapOf(RecognizerIntent.EXTRA_SPEECH_INPUT_MINIMUM_LENGTH_MILLIS to SESSION_MS)

        /** How long a silence ends what is said, the service left to open the microphone: a
         * parent's pause while thinking, not the end of the dictation. Ints, as above. */
        fun pauseExtras(): Map<String, Int> = mapOf(
            RecognizerIntent.EXTRA_SPEECH_INPUT_COMPLETE_SILENCE_LENGTH_MILLIS to PAUSE_MS,
            RecognizerIntent.EXTRA_SPEECH_INPUT_POSSIBLY_COMPLETE_SILENCE_LENGTH_MILLIS to PAUSE_MS,
        )

        /** An error of a segmented session before any word heard: the service can't segment
         * (it stopped as at a pause, or doesn't know the mode). The microphone refused stays a
         * failure: restarting wouldn't hear more. */
        fun refusesSegments(error: Int, heardAny: Boolean) =
            !heardAny && error != SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS

        private fun best(results: Bundle) =
            results.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)?.firstOrNull()?.trim()?.takeIf { it.isNotEmpty() }

        /** Two parts of what was said, one after the other. */
        fun joined(before: String, part: String) = listOf(before, part).filter { it.isNotBlank() }.joinToString(" ")
    }
}

/** The microphone's sound as the app records it for the service: 16 kHz 16-bit mono PCM. */
interface Sound {
    /** Starts recording, each chunk told to `heard` (on a thread of its own): false when it can't. */
    fun start(heard: (ByteArray) -> Unit): Boolean

    fun stop()
}

/** The phone's microphone, as speech recognition hears it (VOICE_RECOGNITION). */
class MicSound : Sound {
    @Volatile private var going = false
    private var record: AudioRecord? = null

    @SuppressLint("MissingPermission") // the 🎤 asks for it first (MainActivity); refused: false
    override fun start(heard: (ByteArray) -> Unit): Boolean {
        val made = try {
            val least = AudioRecord.getMinBufferSize(RATE, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT)
            AudioRecord(MediaRecorder.AudioSource.VOICE_RECOGNITION, RATE, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT, maxOf(least, CHUNK * 8))
        } catch (_: Exception) {
            return false
        }
        try {
            if (made.state != AudioRecord.STATE_INITIALIZED) return false.also { made.release() }
            made.startRecording()
            if (made.recordingState != AudioRecord.RECORDSTATE_RECORDING) return false.also { made.release() }
        } catch (_: Exception) {
            made.release()
            return false
        }
        record = made
        going = true
        thread(name = "dictation-mic") {
            val buffer = ByteArray(CHUNK)
            while (going) {
                val n = made.read(buffer, 0, buffer.size)
                if (n > 0) heard(buffer.copyOf(n)) else if (n < 0) break
            }
            made.release()
        }
        return true
    }

    override fun stop() {
        going = false
        record?.let { runCatching { it.stop() } } // its read returns: the thread releases it
        record = null
    }

    companion object {
        const val RATE = 16_000
        private const val CHUNK = RATE * 2 / 50 // 20 ms: the words shown as they come
    }
}

/** What PhoneListener asks of the speech recognition service: SpeechRecognizer's own calls. */
interface Recognizer {
    fun setRecognitionListener(listener: RecognitionListener)
    fun startListening(intent: Intent)
    fun stopListening()
    fun destroy()
}

/** The phone's own service. */
class SystemRecognizer(private val service: SpeechRecognizer) : Recognizer {
    override fun setRecognitionListener(listener: RecognitionListener) = service.setRecognitionListener(listener)
    override fun startListening(intent: Intent) = service.startListening(intent)
    override fun stopListening() = service.stopListening()
    override fun destroy() = service.destroy()
}
