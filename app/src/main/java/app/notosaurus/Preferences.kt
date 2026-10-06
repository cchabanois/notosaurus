package app.notosaurus

import android.content.Context
import androidx.core.content.edit

/** The app's settings (the settings page's): a name, a text. */
interface Preferences {
    operator fun get(name: String): String?
    operator fun set(name: String, value: String)
}

class SharedPreferencesStore(context: Context) : Preferences {
    private val prefs = context.getSharedPreferences("settings", Context.MODE_PRIVATE)
    override fun get(name: String): String? = prefs.getString(name, null)
    override fun set(name: String, value: String) = prefs.edit { putString(name, value) }
}

/** For the tests. */
class MemoryPreferences : Preferences {
    val values = mutableMapOf<String, String>()
    override fun get(name: String) = values[name]
    override fun set(name: String, value: String) {
        values[name] = value
    }
}
