package app.notosaurus

import android.annotation.SuppressLint
import android.app.Activity
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.provider.MediaStore
import android.webkit.CookieManager
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.FrameLayout
import androidx.activity.ComponentActivity
import androidx.activity.OnBackPressedCallback
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.content.FileProvider
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.updatePadding
import androidx.lifecycle.lifecycleScope
import com.google.mlkit.vision.barcode.common.Barcode
import com.google.mlkit.vision.codescanner.GmsBarcodeScannerOptions
import com.google.mlkit.vision.codescanner.GmsBarcodeScanning
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.tasks.await
import kotlinx.coroutines.withContext
import java.io.File

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

    // The page's <input type="file">: the camera ("capture"), or photos and PDFs
    private val chooser = registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
        val data = result.data
        val uris = when {
            result.resultCode != Activity.RESULT_OK -> null
            data?.clipData != null -> Array(data.clipData!!.itemCount) { data.clipData!!.getItemAt(it).uri }
            data?.data != null -> arrayOf(data.data!!)
            else -> photo?.let { arrayOf(it) } // the camera wrote to our file
        }
        chosen?.onReceiveValue(uris)
        chosen = null
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
        WebView.setWebContentsDebuggingEnabled(true) // prototype: chrome://inspect
        web = WebView(this).apply {
            settings.javaScriptEnabled = true
            settings.domStorageEnabled = true // the page keeps a few choices in localStorage
            webChromeClient = Chooser()
            webViewClient = Links()
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
            override fun handleOnBackPressed() = if (web.canGoBack()) web.goBack() else finish()
        })

        val version = packageManager.getPackageInfo(packageName, 0).versionName.orEmpty()
        server = LocalServer.forApp(
            applicationContext,
            version,
            requestAnkiPermission = ::askAnkiPermission,
            installAnki = ::openAnkiDroidPage,
            scan = ::scanQrCode,
            modeChanged = { runOnUiThread { Shortcuts.update(this, server) } },
        )
        lifecycleScope.launch {
            val port = withContext(Dispatchers.IO) { server.start() }
            origin = "http://127.0.0.1:$port"
            CookieManager.getInstance().setCookie(origin, "${LocalServer.COOKIE}=${server.token}; path=/")
            useMode(intent)
            Shortcuts.update(this@MainActivity, server)
        }
    }

    // A shortcut of the app's icon, the app already open
    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        if (origin != null) useMode(intent)
    }

    /** The mode a shortcut asks for, else the last one: the page of the phone or of the computer. */
    private fun useMode(intent: Intent?) {
        when (intent?.action) {
            Shortcuts.PHONE -> prefs[LocalServer.MODE] = LocalServer.PHONE_MODE
            Shortcuts.COMPUTER -> if (prefs[LocalServer.COMPUTER] != null) prefs[LocalServer.MODE] = LocalServer.COMPUTER_MODE
        }
        val computer = prefs[LocalServer.COMPUTER]
        web.loadUrl(if (prefs[LocalServer.MODE] == LocalServer.COMPUTER_MODE && computer != null) computer else "$origin/")
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

    companion object {
        const val ANKIDROID = "com.ichi2.anki"
    }

    /** The page's links: ours and the computer's stay in the app; others (help, Play Store)
     * go to the browser or the app they're for. The computer not answering: our page saying so. */
    private inner class Links : WebViewClient() {
        override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
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
            val intent = if (params.isCaptureEnabled) {
                val file = File(cacheDir, "photos/photo-${System.currentTimeMillis()}.jpg").apply { parentFile!!.mkdirs() }
                photo = FileProvider.getUriForFile(this@MainActivity, "$packageName.photos", file)
                Intent(MediaStore.ACTION_IMAGE_CAPTURE).putExtra(MediaStore.EXTRA_OUTPUT, photo)
            } else {
                params.createIntent().putExtra(Intent.EXTRA_ALLOW_MULTIPLE, params.mode == FileChooserParams.MODE_OPEN_MULTIPLE)
            }
            chooser.launch(intent)
            return true
        }
    }
}
