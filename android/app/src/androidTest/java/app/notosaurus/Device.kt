package app.notosaurus

import android.app.Activity
import android.content.Context
import android.os.ParcelFileDescriptor
import android.view.View
import android.view.ViewGroup
import android.webkit.WebView
import androidx.core.content.edit
import androidx.test.core.app.ActivityScenario
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Assume.assumeTrue
import org.junit.rules.ExternalResource
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

/** What the tests on a device share: the app's context, a shell, AnkiDroid ready, the
 * app's WebView and JavaScript run in its page. */
object Device {
    val context get() = InstrumentationRegistry.getInstrumentation().targetContext

    /** A shell command, as `adb shell` runs it (e.g. granting a permission). */
    fun shell(command: String): String {
        val output = InstrumentationRegistry.getInstrumentation().uiAutomation.executeShellCommand(command)
        return ParcelFileDescriptor.AutoCloseInputStream(output).bufferedReader().use { it.readText() }
    }

    /** AnkiDroid installed (skipped otherwise: see README), the app allowed to use it. */
    fun ankiDroidReady() {
        assumeTrue("AnkiDroid isn't installed on this device", Anki(context).installed())
        shell("pm grant ${context.packageName} ${Anki.PERMISSION}")
    }

    /** The app's settings as they were before the test, put back after it: the device
     * (a phone in use) keeps its relay, key and mode. */
    class KeepSettings : ExternalResource() {
        private val prefs get() = context.getSharedPreferences("settings", Context.MODE_PRIVATE)
        private var saved: Map<String, *> = emptyMap<String, Any>()

        override fun before() {
            saved = prefs.all.toMap()
        }

        override fun after() = prefs.edit {
            clear()
            saved.forEach { (name, value) -> putString(name, value as String) }
        }
    }

    /** The app's settings, as the settings page would leave them. */
    fun settings(vararg values: Pair<String, String>) {
        val prefs = SharedPreferencesStore(context)
        values.forEach { (name, value) -> prefs[name] = value }
    }

    fun webView(scenario: ActivityScenario<out Activity>): WebView {
        var found: WebView? = null
        scenario.onActivity { found = find(it.window.decorView) }
        return found ?: error("no WebView")
    }

    private fun find(view: View): WebView? = when (view) {
        is WebView -> view
        is ViewGroup -> (0 until view.childCount).firstNotNullOfOrNull { find(view.getChildAt(it)) }
        else -> null
    }

    /** A JavaScript expression's value (as JSON) in the page shown. */
    fun js(scenario: ActivityScenario<out Activity>, expression: String): String {
        val web = webView(scenario)
        val latch = CountDownLatch(1)
        var result = "null"
        scenario.onActivity {
            web.evaluateJavascript(expression) { value ->
                result = value
                latch.countDown()
            }
        }
        latch.await(10, TimeUnit.SECONDS)
        return result
    }

    /** Waits (20 s at most) until the expression is true in the page. */
    fun waitFor(scenario: ActivityScenario<out Activity>, expression: String, what: String = expression) {
        val deadline = System.currentTimeMillis() + 20_000
        while (System.currentTimeMillis() < deadline) {
            if (runCatching { js(scenario, "Boolean($expression)") }.getOrNull() == "true") return
            Thread.sleep(300)
        }
        error("Timed out waiting for: $what (page: ${js(scenario, "location.href")})")
    }

    /** Runs async JavaScript in the page; returns what it puts in window.__result (as JSON). */
    fun run(scenario: ActivityScenario<out Activity>, script: String): String {
        js(scenario, "window.__result = undefined; (async () => { $script })().then(r => window.__result = JSON.stringify(r ?? null)).catch(e => window.__result = JSON.stringify({ error: e.message }))")
        waitFor(scenario, "window.__result !== undefined", "the script's result")
        return kotlinx.serialization.json.Json.parseToJsonElement(js(scenario, "window.__result")).toString()
            .let { kotlinx.serialization.json.Json.decodeFromString<String>(it) }
    }
}
