package app.notosaurus

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.util.Log
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import java.io.File

/**
 * The lessons exported or imported from adb, as the settings' buttons do (LessonsTransfer), in
 * the app's own folder adb can read (no document picker): a phone's lessons backed up, or put
 * back, from the computer, on any build. Only the shell (and the system) can send these: the
 * receiver asks for the DUMP permission (AndroidManifest.xml); adb needs USB debugging on and
 * this computer allowed.
 *
 *     adb shell am broadcast -a app.notosaurus.adb.EXPORT -n app.notosaurus/.AdbTransferReceiver
 *     adb pull /sdcard/Android/data/app.notosaurus/files/transfer/notosaurus-<date>.zip
 *
 *     adb push export.zip /sdcard/Android/data/app.notosaurus/files/transfer/
 *     adb shell am broadcast -a app.notosaurus.adb.IMPORT -n app.notosaurus/.AdbTransferReceiver --es file export.zip
 *
 * What was done is in the broadcast's result (and the log, tag Notosaurus).
 */
class AdbTransferReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val pending = goAsync()
        CoroutineScope(Dispatchers.IO).launch {
            val said = runCatching { run(context.applicationContext, intent) }.getOrElse { "failed: ${it.message ?: it.javaClass.simpleName}" }
            Log.i(TAG, "adb transfer: $said")
            pending.resultData = said
            pending.finish()
        }
    }

    private suspend fun run(context: Context, intent: Intent): String {
        val folder = File(context.getExternalFilesDir(null), "transfer").apply { mkdirs() }
        val version = context.packageManager.getPackageInfo(context.packageName, 0).versionName.orEmpty()
        // The app's own server, not started: the same lessons, preferences and relay as the app
        val server = LocalServer.forApp(
            context,
            version,
            requestAnkiPermission = { false },
            installAnki = {},
            scan = { null },
            createDocument = { _, _ -> null },
            modeChanged = {},
            requestMicPermission = { false },
            activity = { null },
        )
        return when (intent.action) {
            EXPORT -> {
                val file = File(folder, "notosaurus-${Lessons.now().take(10)}.zip")
                val count = file.outputStream().use { server.transfer.export(it) }
                "exported $count lesson(s) to ${file.absolutePath}"
            }
            IMPORT -> {
                val name = intent.getStringExtra("file") ?: return "no file: --es file <name in ${folder.absolutePath}>"
                val file = File(folder, File(name).name) // only that folder's
                if (!file.isFile) return "no such file: ${file.absolutePath}"
                "imported: ${server.transfer.import(file).json()}"
            }
            else -> "unknown action ${intent.action}"
        }
    }

    companion object {
        private const val TAG = "Notosaurus"
        const val EXPORT = "app.notosaurus.adb.EXPORT"
        const val IMPORT = "app.notosaurus.adb.IMPORT"
    }
}
