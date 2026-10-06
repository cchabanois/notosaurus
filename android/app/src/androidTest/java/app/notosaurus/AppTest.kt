package app.notosaurus

import androidx.test.core.app.ActivityScenario
import androidx.test.ext.junit.runners.AndroidJUnit4
import mockwebserver3.MockResponse
import mockwebserver3.MockWebServer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/**
 * The whole app on the phone: the activity, its WebView showing the page, the page's
 * /api answered by LocalServer (its cookie, its storage), the relay (a fake one, on
 * the device) and AnkiDroid (the real one).
 */
@RunWith(AndroidJUnit4::class)
class AppTest {
    @get:Rule val keepSettings = Device.KeepSettings()

    private val relay = MockWebServer()
    private val run = System.currentTimeMillis()

    @Before
    fun setUp() {
        Device.ankiDroidReady()
        relay.start()
        Device.settings(
            LocalServer.MODE to LocalServer.PHONE_MODE,
            LocalServer.RELAY to relay.url("/").toString(),
            LocalServer.KEY to "nts_test",
        )
    }

    @After fun tearDown() = relay.close()

    @Test
    fun aLessonFromThePageIntoAnkiDroid() {
        relay.enqueue(
            MockResponse.Builder().body(
                """{"deck": {"deck": "Notosaurus app test $run", "cards": [
                    {"front": "la mère $run", "back": "la madre"}, {"front": "le père $run", "back": "el padre"}]},
                    "turns": [], "usage": {"credits": 1, "credits_left": 99}}""",
            ).build(),
        )
        ActivityScenario.launch(MainActivity::class.java).use { app ->
            // The page, from the app's assets, with Notosaurus's prompts from its server
            Device.waitFor(app, "typeof api === 'function' && document.querySelectorAll('.chip').length > 3", "the page and its prompts")

            // As the page does it: a lesson made (by the relay), then sent to AnkiDroid
            val sent = Device.run(
                app,
                """
                const form = new FormData();
                form.append("prompt", "FR → ES");
                const lesson = await (await api("/api/extract", { method: "POST", body: form })).json();
                const body = JSON.stringify({ deck: lesson.deck, cards: lesson.cards, voice: "", lesson_id: lesson.id });
                return await (await api("/api/anki/send", { method: "POST", headers: { "Content-Type": "application/json" }, body })).json();
                """,
            )
            assertTrue(sent, "\"added\":2" in sent)
        }
        val request = relay.takeRequest()
        assertEquals("/v1/extract", request.url.encodedPath)
        assertEquals("Bearer nts_test", request.headers["Authorization"])
        assertTrue(Anki(Device.context).deckNames().contains("Notosaurus app test $run"))
    }
}
