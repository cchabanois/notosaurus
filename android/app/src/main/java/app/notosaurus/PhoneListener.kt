package app.notosaurus

import android.content.Context
import android.content.Intent
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
 * The phone's own speech recognition (SpeechRecognizer), on the main thread as it asks. It
 * stops by itself after a pause: started again then, until the page says stop, each part's
 * text kept. Nothing reaches the relay: the recognition service hears it (on the phone, or
 * Google's servers, as the phone's settings say).
 */
class PhoneListener(private val context: Context) : Listener {
    private val main = Handler(Looper.getMainLooper())
    private var recognizer: SpeechRecognizer? = null
    private var finished = "" // the parts heard to their end
    private var listening = false
    private var restarts = 0 // in a row, nothing heard between: a service that can't listen gives up
    private var done: (() -> Unit)? = null

    override fun available() = SpeechRecognizer.isRecognitionAvailable(context)

    override fun start(language: String, heard: (String) -> Unit, failed: (String) -> Unit) {
        main.post {
            end()
            finished = ""
            listening = true
            restarts = 0
            val made = SpeechRecognizer.createSpeechRecognizer(context)
            recognizer = made
            made.setRecognitionListener(object : RecognitionListener {
                override fun onPartialResults(results: Bundle) {
                    best(results)?.let { restarts = 0; heard(joined(finished, it)) }
                }

                override fun onResults(results: Bundle) {
                    best(results)?.let { restarts = 0; finished = joined(finished, it) }
                    heard(finished)
                    if (listening) listen(made, language) else end()
                }

                override fun onError(error: Int) {
                    when {
                        !listening -> end()
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
        made.startListening(
            Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
                .putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                .putExtra(RecognizerIntent.EXTRA_LANGUAGE, language)
                .putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
                .putExtra(RecognizerIntent.EXTRA_CALLING_PACKAGE, context.packageName),
        )
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

        private fun best(results: Bundle) =
            results.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)?.firstOrNull()?.trim()?.takeIf { it.isNotEmpty() }

        /** Two parts of what was said, one after the other. */
        fun joined(before: String, part: String) = listOf(before, part).filter { it.isNotBlank() }.joinToString(" ")
    }
}
