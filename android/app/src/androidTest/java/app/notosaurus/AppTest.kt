package app.notosaurus

import android.app.Activity
import android.app.Instrumentation
import android.content.Intent
import android.graphics.Bitmap
import android.graphics.Color
import androidx.core.content.FileProvider
import androidx.test.core.app.ActivityScenario
import androidx.test.espresso.intent.Intents
import androidx.test.espresso.intent.Intents.intending
import androidx.test.espresso.intent.matcher.IntentMatchers.isInternal
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import androidx.test.uiautomator.By
import androidx.test.uiautomator.UiDevice
import androidx.test.uiautomator.Until
import mockwebserver3.Dispatcher
import mockwebserver3.MockResponse
import mockwebserver3.MockWebServer
import mockwebserver3.RecordedRequest
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.hamcrest.Matchers.not
import java.io.File

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
    private val ui = UiDevice.getInstance(InstrumentationRegistry.getInstrumentation())

    @Before
    fun setUp() {
        Device.ankiDroidReady()
        relay.start()
        Device.settings(
            LocalServer.MODE to LocalServer.PHONE_MODE,
            LocalServer.RELAY to relay.url("/").toString(),
            LocalServer.KEY to "nts_test",
            LocalServer.WELCOME to LocalServer.WELCOME_VERSION.toString(), // accepted: its sheet not over the page
        )
    }

    @After fun tearDown() = relay.close()

    /** What the page keeps (the child chosen, the language…) still there when the app is opened
     * again: its page then on another port (another origin: its localStorage empty), kept by the
     * app's preferences (Saved), served as saved.js. */
    @Test
    fun whatThePageKeepsSurvivesAnotherLaunch() {
        ActivityScenario.launch(MainActivity::class.java).use { app ->
            Device.waitFor(app, "typeof keep === 'function' && window.SAVED", "the page and what the app keeps")
            Device.js(app, "keep('notosaurus.test', 'kept $run')")
            // Told the app meanwhile (nothing waits for it): there once it has it
            val told = "for (let i = 0; i < 40; i++) { if ((await (await fetch('/saved.js')).text()).includes('kept $run')) return true; " +
                "await new Promise((r) => setTimeout(r, 250)); } return false"
            assertEquals("true", Device.run(app, told))
        }
        ActivityScenario.launch(MainActivity::class.java).use { app ->
            Device.waitFor(app, "typeof kept === 'function' && kept('notosaurus.test') === 'kept $run'", "the value kept, read again")
        }
    }

    @Test
    fun aLessonFromThePageIntoAnkiDroid() {
        // The relay answers by route: the page also asks for its voices when it opens
        val lesson = """{"deck": {"deck": "Notosaurus app test $run", "cards": [
            {"front": "la mère $run", "back": "la madre"}, {"front": "le père $run", "back": "el padre"}]},
            "turns": [], "usage": {"credits": 1, "credits_left": 99}}"""
        val extracts = mutableListOf<RecordedRequest>()
        relay.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest) = when (request.url.encodedPath) {
                "/v1/extract" -> MockResponse.Builder().body(lesson).build().also { extracts += request }
                "/v1/voices" -> MockResponse.Builder().body("[]").build()
                else -> MockResponse.Builder().code(404).body("""{"code": "relay.invalid_request", "params": {}}""").build()
            }
        }
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
                const sent = await (await api("/api/anki/send", { method: "POST", headers: { "Content-Type": "application/json" }, body })).json();
                return { ...sent, lesson: lesson.id };
                """,
            )
            assertTrue(sent, "\"added\":2" in sent)
            // Its notes carry the lesson's tag: found again (its leftovers, the ✎ link)
            val lessonId = Regex("\"lesson\":\"([^\"]+)\"").find(sent)!!.groupValues[1]
            assertEquals(sent, 2, Anki(Device.context).leftovers(lessonId, emptySet()).size)
        }
        val request = extracts.single()
        assertEquals("Bearer nts_test", request.headers["Authorization"])
        assertTrue(Anki(Device.context).deckNames().contains("Notosaurus app test $run"))
    }

    /** The page's main road, as a parent goes it: a photo from the gallery (the photo picker
     * answered in the test's place), "Generate cards", the cards shown, "Add to Anki". */
    @Test
    fun aLessonFromAPhotoThroughThePage() {
        val extracts = answering()
        val photo = galleryPhoto()
        Intents.init()
        try {
            intending(not(isInternal())).respondWith(Instrumentation.ActivityResult(Activity.RESULT_OK, Intent().setData(photo)))
            ActivityScenario.launch(MainActivity::class.java).use { app ->
                Device.waitFor(app, "typeof api === 'function' && document.querySelectorAll('.chip').length > 3", "the page and its prompts")
                tap(app, "app.photos.gallery")
                runCatching { Device.waitFor(app, "Alpine.\$data(document.querySelector('[x-data]')).photos.length === 1", "the photo added") }
                    .onFailure { ui.executeShellCommand("screencap -p /data/local/tmp/fail-photo.png"); error("photo not added; intents: " + Intents.getIntents().map { it.action + " " + it.component }) }
                tap(app, "app.actions.generate")
                addedToAnki(app)
            }
        } finally {
            Intents.release()
        }
        val sent = extracts.single().body!!.utf8()
        assertTrue("the photo sent to the relay", "name=\"images\"" in sent)
    }

    /** Without a photo: "✏️ Free", a prompt typed, "Generate from the prompt alone", "Add to Anki". */
    @Test
    fun aLessonFromThePromptAloneThroughThePage() {
        val extracts = answering()
        ActivityScenario.launch(MainActivity::class.java).use { app ->
            Device.waitFor(app, "typeof api === 'function' && document.querySelectorAll('.chip').length > 3", "the page and its prompts")
            tap(app, "app.prompt.free")
            ui.wait(Until.findObject(By.clazz("android.widget.EditText")), 10_000)!!.text = "FR → ES : la mère, le père"
            ui.pressBack() // the keyboard closed: the page under it again
            tap(app, "app.prompt.fromPrompt")
            addedToAnki(app)
        }
        assertTrue(extracts.single().body!!.utf8().contains("la mère, le père"))
    }

    /** The fake relay: a lesson of two cards, the voices, the sounds; the extracts asked. */
    private fun answering(): MutableList<RecordedRequest> {
        val lesson = """{"deck": {"deck": "Notosaurus app test $run", "cards": [
            {"front": "la mère $run", "back": "la madre"}, {"front": "le père $run", "back": "el padre"}]},
            "turns": [0], "usage": {"credits": 1, "credits_left": 99}}"""
        val extracts = mutableListOf<RecordedRequest>()
        relay.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest) = when (request.url.encodedPath) {
                "/v1/extract" -> MockResponse.Builder().body(lesson).build().also { extracts += request }
                "/v1/voices" -> MockResponse.Builder().body("[]").build()
                "/v1/speak" -> MockResponse.Builder().addHeader("Content-Type", "audio/mpeg").body("ID3 a sound").build()
                else -> MockResponse.Builder().code(404).body("""{"code": "relay.invalid_request", "params": {}}""").build()
            }
        }
        return extracts
    }

    /** A photo in the gallery's place: a small JPEG the app's own provider hands out. */
    private fun galleryPhoto(): android.net.Uri {
        val file = File(Device.context.cacheDir, "photos/gallery-$run.jpg").apply { parentFile!!.mkdirs() }
        val picture = Bitmap.createBitmap(400, 300, Bitmap.Config.ARGB_8888).apply { eraseColor(Color.WHITE) }
        file.outputStream().use { picture.compress(Bitmap.CompressFormat.JPEG, 90, it) }
        return FileProvider.getUriForFile(Device.context, "${Device.context.packageName}.photos", file)
    }

    /** Taps what shows `key`'s text in the page's language, as a finger would (a real touch:
     * the photo picker opens only on one), where the page itself says it is: not found
     * through Android's accessibility tree of the WebView, which Chrome builds when it can
     * (on a slow CI emulator, after the 10 s this waited: "not shown"). */
    private fun tap(app: ActivityScenario<MainActivity>, key: String) {
        Device.waitFor(app, "t('$key') !== '$key'", "the page's texts") // its language file read (after its prompts)
        val label = kotlinx.serialization.json.Json.decodeFromString<String>(Device.js(app, "t('$key')"))
        val text = label.dropWhile { !it.isLetterOrDigit() }.trim() // the emoji before it read apart
        val quoted = kotlinx.serialization.json.Json.encodeToString(kotlinx.serialization.json.JsonPrimitive(text))
        val shown = "[...document.querySelectorAll('button, label, a')].find(e => e.offsetParent && e.textContent.includes($quoted))"
        Device.waitFor(app, shown, "shown: $label")
        // Brought into view first (below the screen, it isn't there to touch), as a finger scrolls
        Device.js(app, "$shown.scrollIntoView({ block: 'center' })")
        Thread.sleep(400) // (scrolled)
        val (x, y, ratio) = kotlinx.serialization.json.Json.decodeFromString<List<Double>>(
            Device.js(app, "(() => { const r = $shown.getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2, devicePixelRatio]; })()"),
        )
        val web = Device.webView(app)
        val origin = IntArray(2)
        app.onActivity { web.getLocationOnScreen(origin) }
        check(ui.click(origin[0] + (x * ratio).toInt(), origin[1] + (y * ratio).toInt())) { "not tapped: $label" }
    }

    /** The cards shown, "Add to Anki" tapped: the lesson's two notes in AnkiDroid. */
    private fun addedToAnki(app: ActivityScenario<MainActivity>) {
        Device.waitFor(app, "Alpine.\$data(document.querySelector('[x-data]')).cards.length === 2", "the lesson's cards")
        tap(app, "app.actions.addToAnki")
        val deadline = System.currentTimeMillis() + 30_000
        val anki = Anki(Device.context)
        while (System.currentTimeMillis() < deadline && "Notosaurus app test $run" !in anki.deckNames()) Thread.sleep(500)
        assertTrue("the deck in AnkiDroid", "Notosaurus app test $run" in anki.deckNames())
        val lessonId = kotlinx.serialization.json.Json.decodeFromString<String>(Device.js(app, "Alpine.\$data(document.querySelector('[x-data]')).lessonId"))
        while (System.currentTimeMillis() < deadline && anki.leftovers(lessonId, emptySet()).size < 2) Thread.sleep(500)
        assertEquals(2, anki.leftovers(lessonId, emptySet()).size)
    }
}
