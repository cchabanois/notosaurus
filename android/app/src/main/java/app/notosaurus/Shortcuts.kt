package app.notosaurus

import android.content.Context
import android.content.Intent
import androidx.core.content.pm.ShortcutInfoCompat
import androidx.core.content.pm.ShortcutManagerCompat
import androidx.core.graphics.drawable.IconCompat
import java.util.Locale

/**
 * The shortcuts of the app's icon (a long press): "Without computer" and "With my
 * computer", only once a computer is connected (the others never see them). The way
 * back from the computer's page, whose settings the app doesn't control.
 */
object Shortcuts {
    const val PHONE = "app.notosaurus.action.PHONE"
    const val COMPUTER = "app.notosaurus.action.COMPUTER"

    fun update(context: Context, server: LocalServer) {
        if (SharedPreferencesStore(context)[LocalServer.COMPUTER] == null) {
            ShortcutManagerCompat.removeAllDynamicShortcuts(context)
            return
        }
        val lang = Locale.getDefault().language
        val shortcuts = listOf(PHONE to "phone", COMPUTER to "computer").map { (action, name) ->
            val label = server.text(lang, "android", "shortcuts", name) ?: name
            ShortcutInfoCompat.Builder(context, name)
                .setShortLabel(label)
                .setIcon(IconCompat.createWithResource(context, R.mipmap.ic_launcher))
                .setIntent(Intent(context, MainActivity::class.java).setAction(action))
                .build()
        }
        ShortcutManagerCompat.setDynamicShortcuts(context, shortcuts)
    }
}
