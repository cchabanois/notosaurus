package app.notosaurus

import mockwebserver3.MockResponse
import mockwebserver3.MockWebServer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/** Where the relays are: the published file read, a relay that moved followed. */
class RelayDirectoryTest {
    private val server = MockWebServer()
    private val prefs = MemoryPreferences()

    @Before fun start() = server.start()

    @After fun stop() = server.close()

    private fun directory(test: String = TEST) = RelayDirectory(prefs, server.url("/relay.json").toString(), REAL, test)

    private fun listed(body: String, code: Int = 200) = server.enqueue(MockResponse.Builder().code(code).body(body).build())

    @Test
    fun aRelayThatMovedIsFollowedWithItsLicenceKey() {
        prefs[LocalServer.keyOf(REAL)] = "nts_real"
        prefs[LocalServer.RELAY] = REAL // chosen in the settings
        listed("""{"real": "$MOVED/", "test": "$TEST"}""")
        val relays = directory()
        relays.refresh()
        assertEquals(MOVED, relays.real())
        assertEquals("nts_real", prefs[LocalServer.keyOf(MOVED)])
        assertEquals(MOVED, prefs[LocalServer.RELAY])
        assertEquals(TEST, relays.test())

        // Known from now on, the file unreachable
        listed("", code = 503)
        directory().refresh()
        assertEquals(MOVED, directory().real())
    }

    @Test
    fun anotherRelayChosenStaysAndAKeyThereIsKept() {
        prefs[LocalServer.RELAY] = TEST
        prefs[LocalServer.keyOf(REAL)] = "nts_old"
        prefs[LocalServer.keyOf(MOVED)] = "nts_new"
        listed("""{"real": "$MOVED"}""")
        directory().refresh()
        assertEquals(TEST, prefs[LocalServer.RELAY])
        assertEquals("nts_new", prefs[LocalServer.keyOf(MOVED)])
    }

    @Test
    fun onlyHttpsCloudRunAddressesAreTaken() {
        for (wrong in listOf("http://x-1.europe-west1.run.app", "https://evil.example.com", "https://x.run.app.evil.com",
                "https://x-1.europe-west1.run.app:8443", "https://x-1.europe-west1.run.app/v1", "https://u@x-1.europe-west1.run.app", "")) {
            assertFalse(wrong, RelayDirectory.accepted(wrong))
        }
        assertTrue(RelayDirectory.accepted(MOVED))
        listed("""{"real": "https://evil.example.com"}""")
        directory().refresh()
        assertEquals(REAL, directory().real())
        listed("not json")
        directory().refresh()
        assertEquals(REAL, directory().real())
    }

    @Test
    fun noTestRelayInARelease() {
        listed("""{"real": "$REAL", "test": "$MOVED"}""")
        val relays = directory(test = "")
        relays.refresh()
        assertEquals("", relays.test())
    }

    private companion object {
        const val REAL = "https://notosaurus-relay-1.europe-west1.run.app"
        const val TEST = "https://notosaurus-relay-dev-1.europe-west1.run.app"
        const val MOVED = "https://notosaurus-relay-2.europe-west9.run.app"
    }
}
