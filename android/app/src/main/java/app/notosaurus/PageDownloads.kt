package app.notosaurus

import android.content.ContentValues
import android.os.Build
import android.provider.MediaStore
import android.webkit.JavascriptInterface
import android.webkit.URLUtil
import android.webkit.WebView
import java.io.ByteArrayOutputStream
import java.util.Base64
import java.util.concurrent.ConcurrentHashMap

/**
 * A file the page downloads (the computer's page: a lesson's "⬇️ .apkg", ORD-11), saved in the
 * phone's Downloads. The page makes it in a blob: link (`a.download`, app-anki.js exportApkg),
 * which Android's download manager can't fetch (it lives in the page) and the WebView drops
 * without a word: read by the page here, handed over in pieces (`window.NotosaurusDownloads`),
 * written by `save`. Works with whatever page the computer's add-on serves, an older one too.
 *
 * The link's file name (`a.download`) isn't told to the download listener: `NAMES`, run as each
 * page loads, keeps it by the link's address.
 */
class PageDownloads(
    private val allowed: (String?) -> Boolean, // the page's address: ours or the computer's
    private val save: (name: String, mime: String, data: ByteArray) -> Unit,
) {
    private val parts = ConcurrentHashMap<String, ByteArrayOutputStream>()
    @Volatile private var page: String? = null // the address of the page shown (set on the UI thread)

    /** The page shown now: only its downloads are taken (another page has nothing to hand over). */
    fun shown(url: String?) {
        page = url
    }

    @JavascriptInterface
    fun part(id: String, base64: String) {
        if (!allowed(page)) return
        val bytes = parts.getOrPut(id) { ByteArrayOutputStream() }
        if (bytes.size() <= MAX_BYTES) bytes.write(Base64.getDecoder().decode(base64)) // past it: refused at done
    }

    @JavascriptInterface
    fun done(id: String, name: String, mime: String) {
        val data = parts.remove(id) ?: return
        if (!allowed(page) || data.size() > MAX_BYTES) return
        save(fileName(name, mime), mime.ifBlank { "application/octet-stream" }, data.toByteArray())
    }

    /** The blob: link `url` read by the page and handed over (the listener's own call). */
    fun take(web: WebView, url: String, mime: String) {
        if (!url.startsWith("blob:") || !allowed(web.url)) return
        val quoted = kotlinx.serialization.json.JsonPrimitive(url).toString()
        val type = kotlinx.serialization.json.JsonPrimitive(mime).toString()
        web.evaluateJavascript(
            """
            (async () => {
              const url = $quoted;
              const name = (window.$KEPT || {})[url] || "";
              const blob = await (await fetch(url)).blob();
              const bytes = new Uint8Array(await blob.arrayBuffer());
              const id = url + ":" + Date.now();
              for (let i = 0; i < bytes.length; i += $PART) {
                let text = "";
                const piece = bytes.subarray(i, i + $PART);
                for (let j = 0; j < piece.length; j += 8192) text += String.fromCharCode(...piece.subarray(j, j + 8192));
                $BRIDGE.part(id, btoa(text));
              }
              $BRIDGE.done(id, name, blob.type || $type);
            })();
            """.trimIndent(),
            null,
        )
    }

    companion object {
        const val BRIDGE = "NotosaurusDownloads"
        private const val KEPT = "notosaurusDownloadNames"
        private const val PART = 393_216 // bytes per piece (512 KB of base64)
        private const val MAX_BYTES = 200 * 1024 * 1024 // a lesson's package with its pictures and sounds: far less

        /** Run as each page loads: the name a download link gives its file, kept by the link's
         * address (clicked in the page, or by its script: app-anki.js clicks a link it never adds). */
        val NAMES = """
            (() => {
              if (window.$KEPT) return;
              window.$KEPT = {};
              const keep = (a) => { if (a && a.download) window.$KEPT[a.href] = a.download; };
              const click = HTMLAnchorElement.prototype.click;
              HTMLAnchorElement.prototype.click = function () { keep(this); return click.call(this); };
              document.addEventListener("click", (e) => keep(e.target.closest && e.target.closest("a[download]")), true);
            })();
        """.trimIndent()

        /** The file's name: the page's, without folders; none, "Notosaurus" and its type's
         * extension ("application/apkg": .apkg, which Android's own guess doesn't know). */
        fun fileName(name: String, mime: String): String {
            val plain = name.substringAfterLast('/').substringAfterLast('\\').trim().trimStart('.')
            if (plain.isNotEmpty()) return plain
            val type = mime.substringAfter('/', "").takeIf { it.matches(Regex("[a-z0-9]+")) }
            return if (type != null) "Notosaurus.$type" else URLUtil.guessFileName(null, null, mime)
        }

        /** Written in the phone's Downloads (Android 10+: no permission); its name as created. */
        fun intoDownloads(context: android.content.Context, name: String, mime: String, data: ByteArray): String? {
            if (Build.VERSION.SDK_INT < Build.VERSION_CODES.Q) return null
            val resolver = context.contentResolver
            val values = ContentValues().apply {
                put(MediaStore.Downloads.DISPLAY_NAME, name)
                put(MediaStore.Downloads.MIME_TYPE, mime)
                put(MediaStore.Downloads.IS_PENDING, 1)
            }
            val uri = resolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, values) ?: return null
            resolver.openOutputStream(uri)?.use { it.write(data) } ?: return null
            resolver.update(uri, ContentValues().apply { put(MediaStore.Downloads.IS_PENDING, 0) }, null, null)
            return resolver.query(uri, arrayOf(MediaStore.Downloads.DISPLAY_NAME), null, null, null)
                ?.use { if (it.moveToFirst()) it.getString(0) else null } ?: name
        }
    }
}
