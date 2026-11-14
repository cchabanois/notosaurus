package app.notosaurus

import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer

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
 * The phone's own speech recognition (SpeechRecognizer), on the main thread as it asks. From
 * Android 13, one segmented session (EXTRA_SEGMENTED_SESSION): the service cuts what is said
 * at its pauses itself (onSegmentResults) and goes on listening, so that its start and stop
 * sounds come once, not at each pause. Before, or a service that refuses it (an error before
 * anything heard, or a plain onResults: it stopped at the pause), it stops by itself after a
 * pause: started again then, its sounds at each restart, until the page says stop, each
 * part's text kept; the refusal kept for the app's run. Nothing reaches the relay: the
 * recognition service hears it (on the phone, or Google's servers, as the phone's settings say).
 */
class PhoneListener(private val context: Context) : Listener {
    private val main = Handler(Looper.getMainLooper())
    private var recognizer: SpeechRecognizer? = null
    private var finished = "" // the parts heard to their end
    private var listening = false
    private var restarts = 0 // in a row, nothing heard between: a service that can't listen gives up
    private var segmented = false // this dictation's mode: one segmented session, or restarts
    private var heardAny = false // since the session began: a refusal comes before any word
    internal var starts = 0 // the service started this dictation (the device test: once when segmented)
        private set
    private var done: (() -> Unit)? = null

    override fun available() = SpeechRecognizer.isRecognitionAvailable(context)

    override fun start(language: String, heard: (String) -> Unit, failed: (String) -> Unit) {
        main.post {
            end()
            finished = ""
            listening = true
            restarts = 0
            segmented = segmentedSession(Build.VERSION.SDK_INT, segmentsRefused)
            heardAny = false
            starts = 0
            val made = SpeechRecognizer.createSpeechRecognizer(context)
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

                // The session's end: stopped by the page, or its whole length reached (started again)
                override fun onEndOfSegmentedSession() {
                    heard(finished)
                    if (listening) listen(made, language) else end()
                }

                override fun onResults(results: Bundle) {
                    // A segmented session answered as a plain one: the service doesn't segment
                    if (segmented && listening) refuseSegments()
                    best(results)?.let { restarts = 0; finished = joined(finished, it) }
                    heard(finished)
                    if (listening) listen(made, language) else end()
                }

                override fun onError(error: Int) {
                    when {
                        !listening -> end()
                        segmented && refusesSegments(error, heardAny) -> {
                            refuseSegments()
                            main.postDelayed({ if (listening && recognizer === made) listen(made, language) }, RESTART_MS)
                        }
                        // A pause with nothing said, or the service still closing the last part
                        error in QUIET && ++restarts <= MAX_RESTARTS -> main.postDelayed({ if (listening && recognizer === made) listen(made, language) }, RESTART_MS)
                        else -> {
                            listening = false
                            failed(if (error == SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS) "dictation.refused" else "dictation.recognizer")
                            end()
                        }
                    }
                }

                override fun onReadyForSpeech(params: Bundle?) {}
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
            going.stopListening() // its last words come in onResults, then end()
            main.postDelayed({ if (recognizer === going) end() }, LAST_WORDS_MS)
        }
    }

    private fun listen(made: SpeechRecognizer, language: String) {
        heardAny = false
        starts++
        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
            .putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            .putExtra(RecognizerIntent.EXTRA_LANGUAGE, language)
            .putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
            .putExtra(RecognizerIntent.EXTRA_CALLING_PACKAGE, context.packageName)
        if (segmented && Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            // Segmented for as long as a dictation lasts at most: the page's stop ends it before
            intent.putExtra(RecognizerIntent.EXTRA_SEGMENTED_SESSION, RecognizerIntent.EXTRA_SPEECH_INPUT_MINIMUM_LENGTH_MILLIS)
                .putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_MINIMUM_LENGTH_MILLIS, SESSION_MS)
        }
        made.startListening(intent)
    }

    // This service won't segment: restarts from now on, for this dictation and the next ones
    private fun refuseSegments() {
        segmented = false
        segmentsRefused = true
    }

    private fun end() {
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
        private const val SESSION_MS = 10 * 60 * 1000L // a segmented session's length, then started again

        // The service refused a segmented session once: restarts for the rest of the app's run
        internal var segmentsRefused = false
            private set

        /** One segmented session (its sounds once) or restarts at each pause (their sounds each
         * time): segmented from Android 13 (API 33), unless the service refused it already. */
        fun segmentedSession(sdk: Int, refused: Boolean) = sdk >= Build.VERSION_CODES.TIRAMISU && !refused

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
