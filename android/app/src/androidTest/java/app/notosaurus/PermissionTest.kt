package app.notosaurus

import androidx.test.core.app.ActivityScenario
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import androidx.test.uiautomator.By
import androidx.test.uiautomator.UiDevice
import androidx.test.uiautomator.Until
import mockwebserver3.MockWebServer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeFalse
import org.junit.Assume.assumeTrue
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import java.util.regex.Pattern

/**
 * AnkiDroid's permission never asked for: Android's dialog when the cards are first added,
 * refused (the page told why), asked again, refused for good (Android asks no more), then
 * granted. Needs the app freshly installed, never granted it: revoking a permission kills the
 * app's process, the tests' too. So on its own, after the others (see README):
 * `./gradlew connectedDebugAndroidTest -Pnotosaurus.freshInstall` (FreshInstall).
 */
@FreshInstall
@RunWith(AndroidJUnit4::class)
class PermissionTest {
    @get:Rule val keepSettings = Device.KeepSettings()

    private val relay = MockWebServer()
    private val run = System.currentTimeMillis()
    private val ui = UiDevice.getInstance(InstrumentationRegistry.getInstrumentation())
    private val anki = Anki(Device.context)

    @Before
    fun setUp() {
        assumeTrue("AnkiDroid isn't installed on this device", anki.installed())
        assumeFalse("AnkiDroid's permission granted already: needs the app freshly installed (FreshInstall)", anki.permitted())
        relay.start()
        Device.settings(
            LocalServer.MODE to LocalServer.PHONE_MODE,
            LocalServer.RELAY to relay.url("/").toString(),
            LocalServer.KEY to "nts_test",
        )
    }

    @After
    fun tearDown() {
        relay.close()
        Device.shell("pm grant ${Device.context.packageName} ${Anki.PERMISSION}") // granting doesn't kill
    }

    @Test
    fun refusedAskedAgainRefusedForGoodThenGranted() {
        ActivityScenario.launch(MainActivity::class.java).use { app ->
            Device.waitFor(app, "typeof api === 'function'", "the page")

            // Refused: the page told why
            send(app, "a")
            answer(DENY)
            assertTrue(refused(result(app)))

            // The cards added again: asked again, refused again
            send(app, "b")
            answer(DENY)
            assertTrue(refused(result(app)))

            // Twice refused, Android shows no dialog: refused at once, never left waiting
            send(app, "c")
            assertTrue(refused(result(app)))
            assertNull("a permission dialog", ui.findObject(By.res(DIALOG_BUTTON)))
            // The settings' "Allow" too: answered (not granted), not left waiting
            Device.js(app, "window.__sent = undefined; api('/api/admin/anki/permission', { method: 'POST' }).then(r => r.text()).then(t => window.__sent = t)")
            assertEquals("{\"permitted\":false}", result(app))

            // Android's choice forgotten (its settings' "Reset app preferences"): asked, granted, the cards in AnkiDroid
            Device.shell("pm clear-permission-flags ${Device.context.packageName} ${Anki.PERMISSION} user-set user-fixed")
            send(app, "d")
            answer(ALLOW)
            val sent = result(app)
            assertTrue(sent, "\"added\":1" in sent)
        }
        // Only the card sent once granted
        val decks = anki.deckNames().filter { it.startsWith("Notosaurus permission test $run") }
        assertEquals(listOf("Notosaurus permission test $run d"), decks)
    }

    /** The send refused for want of the permission, the page saying it in words (not its code). */
    private fun refused(answer: String): Boolean {
        val error = org.json.JSONObject(answer)
        return error.optInt("status") == 400 && error.optJSONObject("detail")?.optString("code") == "anki.android_refused" &&
            "AnkiDroid" in error.optString("message") && "anki." !in error.optString("message")
    }

    /** A card sent as the page sends it, the answer awaited apart (Android's dialog first): its
     * JSON, or the error the page would show ({status, detail, message}). */
    private fun send(app: ActivityScenario<MainActivity>, name: String) {
        val body = """{"deck": "Notosaurus permission test $run $name", "cards": [{"front": "le loup $run $name", "back": "el lobo"}], "voice": ""}"""
        Device.js(
            app,
            """window.__sent = undefined; api("/api/anki/send", { method: "POST", headers: { "Content-Type": "application/json" }, body: ${org.json.JSONObject.quote(body)} })
                .then(r => r.text(), e => JSON.stringify({ status: e.status, detail: e.detail, message: e.message })).then(t => window.__sent = t)""",
        )
    }

    /** What the last send (or request) answered, as text. */
    private fun result(app: ActivityScenario<MainActivity>): String {
        Device.waitFor(app, "window.__sent !== undefined", "the answer")
        return kotlinx.serialization.json.Json.decodeFromString<String>(Device.js(app, "window.__sent"))
    }

    /** Android's permission dialog answered (its button's id: "Allow" or "Don't allow"). */
    private fun answer(button: String) {
        val found = ui.wait(Until.findObject(By.res(Pattern.compile(".*:id/$button"))), 10_000)
            ?: error("no permission dialog (${ui.currentPackageName})")
        found.click()
        ui.wait(Until.gone(By.res(DIALOG_BUTTON)), 5_000)
    }

    private companion object {
        const val ALLOW = "permission_allow_button"
        const val DENY = "permission_deny(_and_dont_ask_again)?_button" // asked again: "Don't allow" asks no more
        val DIALOG_BUTTON: Pattern = Pattern.compile(".*:id/permission_(allow|deny)\\w*_button")
    }
}
