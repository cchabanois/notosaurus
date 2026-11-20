package app.notosaurus

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.ByteArrayOutputStream
import java.io.IOException
import java.io.OutputStream

/** The app's sound to the recognition service: what is said while no session takes it (one
 * ended, the next not started) waits for the next, never lost. */
class AudioRelayTest {
    /** A session's pipe: what it was given, until the service closes it. */
    private class Session : OutputStream() {
        val got = ByteArrayOutputStream()
        var over = false
        var closed = false
        override fun write(b: Int) = write(byteArrayOf(b.toByte()))
        override fun write(b: ByteArray, off: Int, len: Int) {
            if (over || closed) throw IOException("Broken pipe")
            got.write(b, off, len)
        }
        override fun close() { closed = true }
        fun text() = got.toString(Charsets.UTF_8)
    }

    private fun AudioRelay.say(text: String) = heard(text.toByteArray())

    @Test
    fun theWordsSaidBetweenTwoSessionsReachTheNext() {
        val relay = AudioRelay()
        relay.say("avant ") // the first session not started yet
        val first = Session()
        relay.to(first)
        relay.say("un deux ")
        assertEquals("avant un deux ", first.text())
        first.over = true // the service ended it at a pause
        relay.say("cinq ")
        relay.say("six ")
        assertTrue("dropped, closed", first.closed)
        val second = Session()
        relay.to(second)
        relay.say("sept")
        assertEquals("cinq six sept", second.text())
        relay.end()
        assertTrue("the end closes the session", second.closed)
        relay.say("après")
        assertEquals("cinq six sept", second.text())
    }

    @Test
    fun aNewSessionClosesTheOneBefore() {
        val relay = AudioRelay()
        val first = Session()
        relay.to(first)
        relay.to(Session())
        assertTrue(first.closed)
    }

    @Test
    fun atMostThirtySecondsWait() {
        val relay = AudioRelay()
        val second = ByteArray(32_000)
        repeat(40) { relay.heard(second) }
        assertEquals(AudioRelay.MAX_WAITING, relay.waiting())
    }
}
