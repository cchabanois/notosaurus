package app.notosaurus

import androidx.test.core.app.ActivityScenario
import androidx.test.ext.junit.runners.AndroidJUnit4
import mockwebserver3.Dispatcher
import mockwebserver3.MockResponse
import mockwebserver3.MockWebServer
import mockwebserver3.RecordedRequest
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/** "With my computer": the computer's page in the app, the page when it doesn't
 * answer, and back to the phone. The computer: a fake one, on the device. */
@RunWith(AndroidJUnit4::class)
class ModesTest {
    @get:Rule val keepSettings = Device.KeepSettings()

    private val computer = MockWebServer()

    @Before
    fun setUp() {
        computer.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest) = when (request.url.encodedPath) {
                "/api/lang" -> MockResponse.Builder().body("""{"lang": null, "available": ["en"]}""").build()
                else -> MockResponse.Builder().body("<html><body><h1 id=\"computer\">The computer's page</h1></body></html>")
                    .addHeader("Content-Type", "text/html").build()
            }
        }
        computer.start()
        Device.settings(
            LocalServer.MODE to LocalServer.COMPUTER_MODE,
            LocalServer.COMPUTER to computer.url("/?k=token").toString(),
        )
    }

    @After fun tearDown() = computer.close()

    @Test
    fun theComputerThenThePhone() {
        ActivityScenario.launch(MainActivity::class.java).use { app ->
            Device.waitFor(app, "document.getElementById('computer')", "the computer's page")
        }

        // The computer gone: the app's page saying so, then back to the phone's
        computer.close()
        ActivityScenario.launch(MainActivity::class.java).use { app ->
            Device.waitFor(app, "location.pathname === '/unreachable.html' && document.querySelectorAll('button').length >= 3", "the unreachable page")
            Device.js(app, "document.querySelector('[x-data]')._x_dataStack[0].usePhone()")
            Device.waitFor(app, "location.pathname === '/' && typeof api === 'function'", "the phone's page")
        }
        assertEquals(LocalServer.PHONE_MODE, SharedPreferencesStore(Device.context)[LocalServer.MODE])
    }
}
