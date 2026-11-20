package app.notosaurus

import java.io.IOException
import java.io.OutputStream

/**
 * The microphone's sound on its way to the speech recognition service (PhoneListener, from
 * Android 13): recorded without a break by the app, written to the session listening now.
 * A session the service ended (its pipe closed: a write fails) or not started yet (none):
 * what is said meanwhile waits for the next one, so the words said while the service starts
 * again are heard, not lost. At most MAX_WAITING bytes wait (the oldest dropped).
 */
class AudioRelay {
    private val waiting = ArrayDeque<ByteArray>()
    private var waitingBytes = 0
    private var sink: OutputStream? = null
    private var ended = false
    private val flushing = Any() // one writer at a time: the chunks in order

    /** A chunk of sound, as recorded (the recording's thread). */
    fun heard(chunk: ByteArray) {
        synchronized(this) {
            if (ended) return
            waiting.addLast(chunk)
            waitingBytes += chunk.size
            while (waitingBytes > MAX_WAITING) waitingBytes -= waiting.removeFirst().size
        }
        flush()
    }

    /** The session listening from now on: what waits is written to it first, with the next
     * chunk heard (on the recording's thread: the caller, the main thread, never blocked). */
    fun to(out: OutputStream) {
        val before = synchronized(this) {
            if (ended) return out.closeQuietly()
            sink.also { sink = out }
        }
        before?.closeQuietly()
    }

    /** No more sound: the session's pipe closed, which ends it (its last words then). */
    fun end() {
        val last = synchronized(this) {
            ended = true
            waiting.clear()
            waitingBytes = 0
            sink.also { sink = null }
        }
        last?.closeQuietly()
    }

    /** Bytes waiting for a session (the tests). */
    @Synchronized
    fun waiting(): Int = waitingBytes

    // Written in order, outside the lock (a pipe the service is slow to read blocks the
    // recording's thread, never the main thread); a failing sink is dropped, its chunk kept
    private fun flush() {
        synchronized(flushing) {
            while (true) {
                val (out, chunk) = synchronized(this) { (sink ?: return) to (waiting.firstOrNull() ?: return) }
                try {
                    out.write(chunk)
                    out.flush()
                } catch (_: IOException) {
                    synchronized(this) { if (sink === out) sink = null }
                    out.closeQuietly()
                    return
                }
                synchronized(this) {
                    if (waiting.firstOrNull() === chunk) {
                        waiting.removeFirst()
                        waitingBytes -= chunk.size
                    }
                }
            }
        }
    }

    private fun OutputStream.closeQuietly() {
        try {
            close()
        } catch (_: IOException) {
        }
    }

    companion object {
        const val MAX_WAITING = 32_000 * 30 // 30 s of 16 kHz 16-bit mono
    }
}
