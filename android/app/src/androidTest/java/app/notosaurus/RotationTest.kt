package app.notosaurus

import android.app.Activity
import android.content.pm.ActivityInfo
import android.content.res.Configuration
import androidx.test.core.app.ActivityScenario
import androidx.test.ext.junit.runners.AndroidJUnit4
import mockwebserver3.Dispatcher
import mockwebserver3.MockResponse
import mockwebserver3.MockWebServer
import mockwebserver3.RecordedRequest
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertSame
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/**
 * The phone turned while a lesson is being made: the same activity, the same page (not
 * reloaded), with what it holds and nothing saves (the prompt typed, a photo taken).
 * Before, the activity was made again: a new LocalServer, the page reloaded, all lost.
 */
@RunWith(AndroidJUnit4::class)
class RotationTest {
    @get:Rule val keepSettings = Device.KeepSettings()

    private val relay = MockWebServer()

    @Before
    fun setUp() {
        // The page asks the relay for its voices when it opens
        relay.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest) = when (request.url.encodedPath) {
                "/v1/voices" -> MockResponse.Builder().body("[]").build()
                else -> MockResponse.Builder().code(404).body("""{"code": "relay.invalid_request", "params": {}}""").build()
            }
        }
        relay.start()
        Device.settings(
            LocalServer.MODE to LocalServer.PHONE_MODE,
            LocalServer.RELAY to relay.url("/").toString(),
            LocalServer.KEY to "nts_test",
        )
    }

    @After fun tearDown() = relay.close()

    @Test
    fun theLessonKeptWhenThePhoneIsTurned() {
        ActivityScenario.launch(MainActivity::class.java).use { app ->
            Device.waitFor(app, "typeof api === 'function' && document.querySelectorAll('.chip').length > 3", "the page and its prompts")

            // What only the page holds: a prompt typed, a photo added (as the camera's are),
            // and a mark gone if the page is loaded again
            Device.run(
                app,
                """
                const page = Alpine.${'$'}data(document.querySelector('.app'));
                const canvas = document.createElement('canvas');
                canvas.width = 40;
                canvas.height = 30;
                canvas.getContext('2d').fillRect(0, 0, 20, 15);
                const blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/jpeg'));
                await page.addFiles([new File([blob], 'page.jpg', { type: 'image/jpeg' })]);
                const prompt = document.querySelector('textarea[x-ref=promptText]');
                prompt.value = 'Turned, still here';
                prompt.dispatchEvent(new Event('input'));
                window.notReloaded = true;
                """,
            )
            Device.waitFor(app, "document.querySelectorAll('.thumb img').length === 1", "the photo's thumbnail")
            val before = activity(app)

            try {
                turn(app, ActivityInfo.SCREEN_ORIENTATION_LANDSCAPE, Configuration.ORIENTATION_LANDSCAPE)
                Device.waitFor(app, "innerWidth > innerHeight", "the page turned")

                assertSame("the activity was made again", before, activity(app))
                assertFalse(before.isDestroyed)
                assertEquals("true", Device.js(app, "window.notReloaded === true"))
                assertEquals("\"Turned, still here\"", Device.js(app, "Alpine.\$data(document.querySelector('.app')).form.text"))
                assertEquals("\"Turned, still here\"", Device.js(app, "document.querySelector('textarea[x-ref=promptText]').value"))
                assertEquals("1", Device.js(app, "Alpine.\$data(document.querySelector('.app')).photos.length"))
            } finally {
                turn(app, ActivityInfo.SCREEN_ORIENTATION_PORTRAIT, Configuration.ORIENTATION_PORTRAIT)
                app.onActivity { it.requestedOrientation = ActivityInfo.SCREEN_ORIENTATION_UNSPECIFIED }
            }
            // Turned back: still the same page
            assertSame(before, activity(app))
            assertEquals("true", Device.js(app, "window.notReloaded === true"))
        }
    }

    private fun activity(scenario: ActivityScenario<out Activity>): Activity {
        var found: Activity? = null
        scenario.onActivity { found = it }
        return found!!
    }

    /** The screen turned as the app asks it, waited for (10 s at most). */
    private fun turn(scenario: ActivityScenario<out Activity>, requested: Int, orientation: Int) {
        scenario.onActivity { it.requestedOrientation = requested }
        val deadline = System.currentTimeMillis() + 10_000
        while (System.currentTimeMillis() < deadline) {
            var now = 0
            scenario.onActivity { now = it.resources.configuration.orientation }
            if (now == orientation) return
            Thread.sleep(200)
        }
        error("the screen didn't turn")
    }
}
