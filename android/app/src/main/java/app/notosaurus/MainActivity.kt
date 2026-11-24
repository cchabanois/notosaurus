package app.notosaurus

import android.Manifest
import android.annotation.SuppressLint
import android.app.Activity
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Bundle
import android.provider.MediaStore
import android.provider.OpenableColumns
import android.webkit.CookieManager
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import android.util.Log
import android.widget.Toast
import android.widget.FrameLayout
import androidx.activity.ComponentActivity
import androidx.activity.OnBackPressedCallback
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.ActivityResult
import androidx.activity.result.IntentSenderRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.content.ContextCompat
import androidx.core.content.FileProvider
import androidx.core.content.IntentCompat
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.updatePadding
import androidx.lifecycle.lifecycleScope
import androidx.webkit.WebViewCompat
import androidx.webkit.WebViewFeature
import com.google.mlkit.vision.barcode.common.Barcode
import com.google.mlkit.vision.codescanner.GmsBarcodeScannerOptions
import com.google.mlkit.vision.codescanner.GmsBarcodeScanning
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.tasks.await
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withContext
import java.io.File
import kotlin.coroutines.resume

/**
 * Notosaurus's page (the same as on the computer) in a WebView, its /api answered
 * by LocalServer on the phone; or, "With my computer", the Anki add-on's page itself
 * (the computer's address, from its QR code).
 */
class MainActivity : ComponentActivity() {
    private lateinit var web: WebView
    private lateinit var server: LocalServer
    private val prefs by lazy { SharedPreferencesStore(this) }
    private var origin: String? = null // LocalServer's, once started
    private var chosen: ValueCallback<Array<Uri>>? = null
    private var photo: Uri? = null
    private var photoFile: File? = null // the camera's photo, `photo`'s file
    private val photos by lazy { PhotoFolder(File(cacheDir, "photos")) }

    // The page's <input type="file">: the camera ("capture"), or photos and PDFs
    private val chooser = registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
        val data = result.data
        val uris = when {
            result.resultCode != Activity.RESULT_OK -> null
            data?.clipData != null -> Array(data.clipData!!.itemCount) { data.clipData!!.getItemAt(it).uri }
            data?.data != null -> arrayOf(data.data!!)
            else -> photo?.let { arrayOf(it) } // the camera wrote to our file
        }
        if (uris != null && photo != null && uris.singleOrNull() == photo) photoFile?.let { lifecycleScope.launch(Dispatchers.IO) { photos.handed(listOf(it)) } }
        chosen?.onReceiveValue(uris)
        chosen = null
    }

    // The document scanner's screens (Scanner), its pages for the camera's input
    private var scanAnswer: CompletableDeferred<ActivityResult>? = null
    private val scanner = registerForActivityResult(ActivityResultContracts.StartIntentSenderForResult()) { result ->
        scanAnswer?.complete(result)
    }

    private suspend fun launchScanner(request: IntentSenderRequest): ActivityResult = withContext(Dispatchers.Main) {
        val answer = CompletableDeferred<ActivityResult>().also { scanAnswer = it }
        scanner.launch(request)
        answer.await()
    }

    // AnkiDroid's permission, asked when the cards are first added (or from the settings)
    private var ankiAnswer: CompletableDeferred<Boolean>? = null
    private val ankiPermission = registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        ankiAnswer?.complete(granted)
    }

    private suspend fun askAnkiPermission(): Boolean = withContext(Dispatchers.Main) {
        val answer = CompletableDeferred<Boolean>().also { ankiAnswer = it }
        ankiPermission.launch(Anki.PERMISSION)
        answer.await()
    }

    // The microphone's permission, asked the first time the 🎤 is used
    private var micAnswer: CompletableDeferred<Boolean>? = null
    private val micPermission = registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        micAnswer?.complete(granted)
    }

    private suspend fun askMicPermission(): Boolean = withContext(Dispatchers.Main) {
        if (ContextCompat.checkSelfPermission(this@MainActivity, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) {
            return@withContext true
        }
        val answer = CompletableDeferred<Boolean>().also { micAnswer = it }
        micPermission.launch(Manifest.permission.RECORD_AUDIO)
        answer.await()
    }

    // A file to write where the user chooses (Drive, the SD card…): the lessons exported
    private var documentAnswer: CompletableDeferred<Uri?>? = null
    private var documentType = "application/zip"
    private val document = registerForActivityResult(object : ActivityResultContracts.CreateDocument("application/zip") {
        override fun createIntent(context: android.content.Context, input: String) = super.createIntent(context, input).setType(documentType)
    }) { uri -> documentAnswer?.complete(uri) }

    private suspend fun createDocument(name: String, mime: String): Document? {
        val uri = withContext(Dispatchers.Main) {
            documentType = mime
            val answer = CompletableDeferred<Uri?>().also { documentAnswer = it }
            document.launch(name)
            answer.await()
        } ?: return null
        val out = contentResolver.openOutputStream(uri) ?: return null
        // Its name as created: Android adds " (1)" when the folder has one of that name
        val created = runCatching {
            contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { if (it.moveToFirst()) it.getString(0) else null }
        }.getOrNull()
        return Document(created?.takeIf { it.isNotBlank() } ?: name, out)
    }

    /** AnkiDroid's page in Google Play (or in the browser, without Google Play). */
    private fun openAnkiDroidPage() = runOnUiThread {
        val store = Intent(Intent.ACTION_VIEW, Uri.parse("market://details?id=$ANKIDROID"))
        runCatching { startActivity(store) }.onFailure {
            runCatching { startActivity(Intent(Intent.ACTION_VIEW, Uri.parse("https://play.google.com/store/apps/details?id=$ANKIDROID"))) }
        }
    }

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        // chrome://inspect in a debug build only: a release's page (its token, the lessons) never open to it
        WebView.setWebContentsDebuggingEnabled(BuildConfig.DEBUG)
        web = WebView(this).apply {
            settings.javaScriptEnabled = true
            settings.domStorageEnabled = true // the page keeps a few choices in localStorage
            webChromeClient = Chooser()
            webViewClient = Links()
            // A file the page downloads (the computer's "⬇️ .apkg"): into the phone's Downloads
            addJavascriptInterface(downloads, PageDownloads.BRIDGE)
            setDownloadListener { url, _, _, mime, _ -> downloads.take(this, url, mime) }
            // The names its download links give, kept before the page's own scripts run (else as it loads)
            if (WebViewFeature.isFeatureSupported(WebViewFeature.DOCUMENT_START_SCRIPT)) {
                WebViewCompat.addDocumentStartJavaScript(this, PageDownloads.NAMES, setOf("*"))
            }
        }
        // The page below the status bar, above the navigation bar and the keyboard (a
        // WebView ignores its own padding: its frame takes it)
        val frame = FrameLayout(this).apply { addView(web) }
        ViewCompat.setOnApplyWindowInsetsListener(frame) { view, insets ->
            val bars = insets.getInsets(WindowInsetsCompat.Type.systemBars() or WindowInsetsCompat.Type.ime())
            view.updatePadding(top = bars.top, bottom = bars.bottom)
            WindowInsetsCompat.CONSUMED
        }
        setContentView(frame)
        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            // A sheet open in the page closed first (its typing kept), as Escape closes it
            override fun handleOnBackPressed() = web.evaluateJavascript("window.notosaurusBack?.() === true") { closed ->
                if (closed != "true") if (web.canGoBack()) web.goBack() else finish()
            }
        })

        val version = packageManager.getPackageInfo(packageName, 0).versionName.orEmpty()
        // Said to the pages: the computer's then links to the app's settings (its own stay on the computer)
        web.settings.userAgentString += " NotosaurusApp/$version"
        server = LocalServer.forApp(
            applicationContext,
            version,
            requestAnkiPermission = ::askAnkiPermission,
            installAnki = ::openAnkiDroidPage,
            scan = ::scanQrCode,
            createDocument = ::createDocument,
            modeChanged = { runOnUiThread { Shortcuts.update(this, server) } },
            requestMicPermission = ::askMicPermission,
            activity = { this.takeUnless { it.isFinishing || it.isDestroyed } },
        )
        // The document scanner's module fetched ahead, once (Scanner): never waited for. Not
        // while the relay has the scanner turned off (lesson.scan): the camera then
        if (prefs[SCANNER_READY] == null && !server.switches.off("lesson.scan")) DocumentScanner.preinstall(applicationContext) { prefs[SCANNER_READY] = "1" }
        // A share is taken once: the activity made again with the intent that brought it (a
        // change of theme, language or font size: its state saved; reopened from the recent
        // apps after Android ended the app) opens the page as without it, the share taken
        // already or still kept for the page (Shared), which takes it from ?shared=1. Taken
        // again, its files were copied and added to the lesson again
        val shareAgain = intent.action in SHARES &&
            (savedInstanceState != null || intent.flags and Intent.FLAG_ACTIVITY_LAUNCHED_FROM_HISTORY != 0)
        lifecycleScope.launch {
            val port = withContext(Dispatchers.IO) { server.start() }
            origin = "http://127.0.0.1:$port"
            CookieManager.getInstance().setCookie(origin, "${LocalServer.COOKIE}=${server.token}; path=/")
            useMode(intent.takeUnless { shareAgain }, shareWaits = shareAgain)
            Shortcuts.update(this@MainActivity, server)
            withContext(Dispatchers.IO) { server.relays.refresh() } // a relay moved: followed from now on
        }
    }

    override fun onDestroy() {
        Thread { server.stop() }.start() // off the main thread; another activity starts its own
        web.destroy()
        super.onDestroy()
    }

    // The app already open: a shortcut of its icon to the other mode, or a card's "✎" link,
    // opened; the icon itself (or a shortcut to the mode shown), the page as it was: a lesson
    // in progress (its photos, its prompt) never lost by coming back
    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        if (origin != null && asksAnotherPage(intent)) useMode(intent)
    }

    private fun asksAnotherPage(intent: Intent): Boolean {
        val mode = prefs[LocalServer.MODE] ?: LocalServer.PHONE_MODE
        return when (intent.action) {
            Shortcuts.PHONE -> mode != LocalServer.PHONE_MODE
            Shortcuts.COMPUTER -> mode != LocalServer.COMPUTER_MODE && prefs[LocalServer.COMPUTER] != null
            Intent.ACTION_VIEW -> intent.data?.let(::isFixLink) == true
            Intent.ACTION_SEND, Intent.ACTION_SEND_MULTIPLE -> true
            else -> false
        }
    }

    /** The mode a shortcut asks for, else the last one: the page of the phone or of the computer;
     * [shareWaits]: the phone's told to take a share that may wait for it. */
    private fun useMode(intent: Intent?, shareWaits: Boolean = false) {
        when (intent?.action) {
            Shortcuts.PHONE -> prefs[LocalServer.MODE] = LocalServer.PHONE_MODE
            Shortcuts.COMPUTER -> if (prefs[LocalServer.COMPUTER] != null) prefs[LocalServer.MODE] = LocalServer.COMPUTER_MODE
            // "✎ Notosaurus" on a card in AnkiDroid (notosaurus://fix?lesson=…&key=…): the phone's
            // page on that card (its query, nothing else: the page looks the lesson and card up)
            Intent.ACTION_VIEW -> intent.data?.takeIf { isFixLink(it) }?.let { link ->
                web.loadUrl("$origin/?${link.encodedQuery.orEmpty()}")
                return
            }
            Intent.ACTION_SEND, Intent.ACTION_SEND_MULTIPLE -> {
                shareReceived(intent)
                return
            }
        }
        val computer = prefs[LocalServer.COMPUTER]
        web.loadUrl(if (prefs[LocalServer.MODE] == LocalServer.COMPUTER_MODE && computer != null) computer else "$origin/" + if (shareWaits) "?shared=1" else "")
    }

    /** Something shared to Notosaurus ("Share" in another app): copied at once (reading it is
     * granted with this intent only), then the phone's page told to take it (Shared.kt,
     * app-photos.js takeShared). With my computer: its page can't read the phone's files, said;
     * its page shown as it was. */
    private fun shareReceived(intent: Intent) {
        val items = sharedUris(intent).map { uri -> sharedItem(uri, intent.type) }
        val text = intent.getCharSequenceExtra(Intent.EXTRA_TEXT)?.toString()
        lifecycleScope.launch {
            withContext(Dispatchers.IO) { server.shared.take(items, text) }
            if (prefs[LocalServer.MODE] == LocalServer.COMPUTER_MODE && prefs[LocalServer.COMPUTER] != null) {
                server.shared.clear()
                val lang = java.util.Locale.getDefault().language
                server.text(lang, "android", "share", "computer")?.let { Toast.makeText(this@MainActivity, it, Toast.LENGTH_LONG).show() }
                if (web.url == null) useMode(null) // opened by the share: the computer's page
                return@launch
            }
            // The page open and started: it takes them, as it is (a lesson in progress whose last
            // change isn't kept yet stays); else opened to take them
            web.evaluateJavascript("window.notosaurusShared?.() === true") { taken ->
                if (taken != "true") web.loadUrl("$origin/?shared=1")
            }
        }
    }

    /** The files shared: content:// only (a file:// one could name the app's own files). */
    private fun sharedUris(intent: Intent): List<Uri> {
        val extra = when (intent.action) {
            Intent.ACTION_SEND -> listOfNotNull(IntentCompat.getParcelableExtra(intent, Intent.EXTRA_STREAM, Uri::class.java))
            else -> IntentCompat.getParcelableArrayListExtra(intent, Intent.EXTRA_STREAM, Uri::class.java).orEmpty()
        }
        val clip = intent.clipData?.let { clip -> (0 until clip.itemCount).mapNotNull { clip.getItemAt(it).uri } }.orEmpty()
        return (extra.ifEmpty { clip }).filter { it.scheme == "content" }.distinct()
    }

    private fun sharedItem(uri: Uri, intentType: String?): Shared.Item {
        val name = runCatching {
            contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { if (it.moveToFirst()) it.getString(0) else null }
        }.getOrNull()?.takeIf { it.isNotBlank() } ?: uri.lastPathSegment.orEmpty()
        val type = runCatching { contentResolver.getType(uri) }.getOrNull() ?: intentType?.takeUnless { "*" in it }
        return Shared.Item(name, type) { contentResolver.openInputStream(uri) }
    }

    /** A QR code read by Google's scanner (no camera permission for the app); null: cancelled.
     * Fails when the scanner isn't there (Google Play services download it at first use). */
    private suspend fun scanQrCode(): String? = withContext(Dispatchers.Main) {
        val options = GmsBarcodeScannerOptions.Builder().setBarcodeFormats(Barcode.FORMAT_QR_CODE).build()
        try {
            GmsBarcodeScanning.getClient(this@MainActivity, options).startScan().await().rawValue
        } catch (e: CancellationException) {
            null // the user went back
        }
    }

    private fun computerHost(): String? = prefs[LocalServer.COMPUTER]?.let { Uri.parse(it).host }

    // Downloads only from our page or the computer's (the bridge is the WebView's, whatever it shows)
    private val downloads = PageDownloads(
        allowed = { url -> url?.let { Uri.parse(it).host }.let { it == "127.0.0.1" || (it != null && it == computerHost()) } },
        save = { name, mime, data -> lifecycleScope.launch { saveDownload(name, mime, data) } },
    )

    /** A file the page downloaded, in the phone's Downloads (Android 9: where the user chooses),
     * said in a toast. */
    private suspend fun saveDownload(name: String, mime: String, data: ByteArray) {
        // Our own page's package of cards: handed to the app the user shares it with (a message, a
        // mail, a drive), as a phone shares a file; the computer's page's: in Downloads, as before
        if (mime == APKG && Uri.parse(web.url.orEmpty()).host == "127.0.0.1") return sharePackage(name, data)
        val lang = java.util.Locale.getDefault().language
        val saved = runCatching {
            withContext(Dispatchers.IO) { PageDownloads.intoDownloads(this@MainActivity, name, mime, data) }
                ?: createDocument(name, mime)?.let { document -> withContext(Dispatchers.IO) { document.out.use { it.write(data) } }; document.name }
        }.getOrNull()
        val text = if (saved != null) server.text(lang, "android", "downloads", "saved")?.replace("{name}", saved)
        else server.text(lang, "android", "downloads", "failed")?.replace("{name}", name)
        Toast.makeText(this, text ?: saved ?: name, Toast.LENGTH_LONG).show()
    }

    /** The package in Android's share sheet: written where our FileProvider hands it out (the last
     * one only: a package is shared once), read by the app chosen. */
    private suspend fun sharePackage(name: String, data: ByteArray) {
        val file = withContext(Dispatchers.IO) {
            java.io.File(cacheDir, "outgoing").apply { deleteRecursively(); mkdirs() }.resolve(name).apply { writeBytes(data) }
        }
        val uri = FileProvider.getUriForFile(this, "$packageName.photos", file)
        val send = Intent(Intent.ACTION_SEND).setType(APKG).putExtra(Intent.EXTRA_STREAM, uri).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        startActivity(Intent.createChooser(send, null))
    }

    /** "✎ Notosaurus" on a card: notosaurus://fix?… (the documentation page's button), or that
     * page's own https address when Android gives it to the app. */
    private fun isFixLink(uri: Uri): Boolean =
        (uri.scheme == "notosaurus" && uri.host == "fix") ||
            (uri.scheme == "https" && uri.host == "cchabanois.github.io" && uri.path.orEmpty().startsWith("/notosaurus/fix"))

    companion object {
        const val ANKIDROID = "com.ichi2.anki"
        const val APKG = "application/apkg" // a package of cards (the page's ".apkg")
        const val APP_LINKS = "notosaurus-app" // links the pages make to the app itself
        const val SCANNER_READY = "scanner_module" // the document scanner's module installed (Scanner)
        private const val TAG = "Notosaurus"
        private val SHARES = setOf(Intent.ACTION_SEND, Intent.ACTION_SEND_MULTIPLE) // "Share" to Notosaurus
    }

    /** The page's camera (📷): its pages scanned (Scanner), as many as the lesson has room for
     * when its input takes several; the camera itself when the scanner can't be used, or is
     * turned off by the relay (lesson.scan: the switches last told, kept as each page loads;
     * none told yet, the scanner). */
    private fun capture(multiple: Boolean) = lifecycleScope.launch {
        // The pages before them (a notebook's pages, maybe a name on them: not kept on the phone
        // outside the lessons), the camera's as the scanner's; the last handed over kept (PhotoFolder)
        withContext(Dispatchers.IO) { photos.clear() }
        if (server.switches.off("lesson.scan")) return@launch chooser.launch(cameraIntent())
        val limit = Scanner.pageLimit(multiple, if (multiple) Scanner.free(pageAnswer(Scanner.FREE)) else null)
        val pages = try {
            Scanner.current.scan(this@MainActivity, limit, ::launchScanner)?.let { scanned ->
                withContext(Dispatchers.IO) { keep(scanned).also(photos::handed) }.map { FileProvider.getUriForFile(this@MainActivity, "$packageName.photos", it) }
            }
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            Log.i(TAG, "document scanner unavailable, the camera instead", e)
            return@launch chooser.launch(cameraIntent())
        }
        chosen?.onReceiveValue(pages?.takeIf { it.isNotEmpty() }?.toTypedArray())
        chosen = null
    }

    /** What the page's script gives (as JSON), null when it can't. */
    private suspend fun pageAnswer(script: String): String? = suspendCancellableCoroutine { done ->
        runCatching { web.evaluateJavascript(script) { done.resume(it) } }.onFailure { done.resume(null) }
    }

    /** The scanner's pages copied where the camera's photos go (cache/photos, emptied at the next
     * 📷), its own files deleted: no page of a notebook left behind. */
    private fun keep(scanned: List<Uri>): List<File> {
        val folder = photos.dir.apply { mkdirs() }
        val time = System.currentTimeMillis()
        return scanned.mapIndexed { i, uri ->
            val file = File(folder, "page-$time-${i + 1}.jpg")
            checkNotNull(contentResolver.openInputStream(uri)) { "page $i unreadable" }.use { input -> file.outputStream().use { input.copyTo(it) } }
            ownFile(uri)?.delete()
            file
        }
    }

    /** A file:// of the app's own (the scanner writes its pages in the app's cache), else null. */
    private fun ownFile(uri: Uri): File? {
        if (uri.scheme != "file") return null
        val file = File(uri.path ?: return null).canonicalFile
        val ours = listOf(cacheDir, filesDir).map { it.canonicalPath + File.separator }
        return file.takeIf { f -> ours.any { f.path.startsWith(it) } }
    }

    /** The phone's camera app, one photo into cache/photos (FileProvider). */
    private fun cameraIntent(): Intent {
        val file = File(photos.dir.apply { mkdirs() }, "photo-${System.currentTimeMillis()}.jpg")
        photoFile = file
        photo = FileProvider.getUriForFile(this, "$packageName.photos", file)
        return Intent(MediaStore.ACTION_IMAGE_CAPTURE).putExtra(MediaStore.EXTRA_OUTPUT, photo)
    }

    /** The page's links: ours and the computer's stay in the app; others (help, Play Store)
     * go to the browser or the app they're for. The computer not answering: our page saying so. */
    private inner class Links : WebViewClient() {
        override fun onPageStarted(view: WebView, url: String?, favicon: android.graphics.Bitmap?) {
            downloads.shown(url)
        }

        override fun onPageFinished(view: WebView, url: String?) {
            view.evaluateJavascript(PageDownloads.NAMES, null) // kept once (an older WebView: from now on)
        }

        override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
            if (request.url.scheme == APP_LINKS) { // from the computer's page: "notosaurus-app:settings"
                if (request.url.schemeSpecificPart == "settings") view.loadUrl("$origin/admin.html")
                return true
            }
            if (request.url.host == "127.0.0.1" || request.url.host == computerHost()) return false
            runCatching { startActivity(Intent(Intent.ACTION_VIEW, request.url)) }
            return true
        }

        override fun onReceivedError(view: WebView, request: WebResourceRequest, error: WebResourceError) {
            if (request.isForMainFrame && request.url.host == computerHost()) view.loadUrl("$origin/unreachable.html")
        }
    }

    private inner class Chooser : WebChromeClient() {
        override fun onShowFileChooser(
            view: WebView,
            callback: ValueCallback<Array<Uri>>,
            params: FileChooserParams,
        ): Boolean {
            chosen?.onReceiveValue(null)
            chosen = callback
            photo = null
            photoFile = null
            if (params.isCaptureEnabled) {
                capture(params.mode == FileChooserParams.MODE_OPEN_MULTIPLE)
                return true
            }
            chooser.launch(params.createIntent().putExtra(Intent.EXTRA_ALLOW_MULTIPLE, params.mode == FileChooserParams.MODE_OPEN_MULTIPLE))
            return true
        }
    }
}

/**
 * cache/photos: the pages handed to the page's 📷 (the scanner's, the camera's), read by the page
 * one by one after. A new 📷 empties it but for the last pages handed over, which the page may
 * still be reading (the computer's page, an older one, keeps its 📷 on meanwhile; a picture's 📷
 * taken while they are read); the new pages handed over, those last ones stay until the next
 * 📷: never more than two 📷's pages kept.
 */
internal class PhotoFolder(val dir: File) {
    private var last: Set<String> = emptySet()

    /** A new 📷: all but the last pages handed over deleted. */
    @Synchronized
    fun clear() {
        dir.listFiles()?.filter { it.name !in last }?.forEach { it.delete() }
    }

    /** `pages` handed to the page: every other file deleted, but the pages handed over before
     * them (the page may still be reading them: gone at the next 📷). */
    @Synchronized
    fun handed(pages: List<File>) {
        val kept = last + pages.map { it.name }
        last = pages.map { it.name }.toSet()
        dir.listFiles()?.filter { it.name !in kept }?.forEach { it.delete() }
    }
}
