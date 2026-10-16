package app.notosaurus

import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

/**
 * The backs' sounds made ahead, in the background, as soon as a lesson's cards exist or
 * change: "Add to Anki" then finds them on the phone (reading them took most of a send's
 * time). As the computer's app/sounds.py: `make` reads the lesson's missing sounds as the
 * send would; one job per lesson, started after `delayMs` of quiet (the page saves as the
 * user types), a newer save replacing the job waiting or running. Failures are silent: the
 * send reads what's still missing and says what it couldn't.
 */
class SoundsAhead(private val make: suspend (String) -> Unit, var delayMs: Long = DELAY_MS) {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val jobs = mutableMapOf<String, Job>() // by lesson id: one at a time

    /** The lesson's missing sounds made in a moment, in place of a job started before. */
    fun soon(lessonId: String) {
        if (lessonId.isEmpty()) return
        synchronized(jobs) {
            jobs.remove(lessonId)?.cancel()
            val job = scope.launch(start = CoroutineStart.LAZY) {
                delay(delayMs)
                try {
                    make(lessonId)
                } catch (e: CancellationException) {
                    throw e
                } catch (e: Exception) { // silent: the send tries again
                }
            }
            jobs[lessonId] = job
            job.invokeOnCompletion { synchronized(jobs) { if (jobs[lessonId] === job) jobs.remove(lessonId) } }
            job.start()
        }
    }

    /** The lesson's job stopped, before the send reads its sounds: never two at once on the same files. */
    suspend fun settle(lessonId: String) {
        synchronized(jobs) { jobs.remove(lessonId) }?.cancelAndJoin()
    }

    /** The lessons whose sounds are waiting or being made. */
    fun pending(): Set<String> = synchronized(jobs) { jobs.keys.toSet() }

    /** Every job stopped (the server stops). */
    fun stop() = scope.cancel()

    companion object {
        const val DELAY_MS = 5_000L // of quiet after a lesson's last save
    }
}
