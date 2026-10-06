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
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File

/**
 * Notosaurus's page (the same as on the computer) in a WebView, its /api answered
 * by LocalServer on the phone.
 */
class MainActivity : ComponentActivity() {
    private lateinit var web: WebView
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

    private val ankiPermission = registerForActivityResult(ActivityResultContracts.RequestPermission()) {}

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

        val anki = Anki(this)
        if (anki.installed() && !anki.permitted()) ankiPermission.launch(Anki.PERMISSION)

        val version = packageManager.getPackageInfo(packageName, 0).versionName.orEmpty()
        val server = LocalServer.forApp(applicationContext, version) {
            runOnUiThread { ankiPermission.launch(Anki.PERMISSION) } // the settings' "Allow"
        }
        lifecycleScope.launch {
            val port = withContext(Dispatchers.IO) { server.start() }
            val origin = "http://127.0.0.1:$port"
            CookieManager.getInstance().setCookie(origin, "${LocalServer.COOKIE}=${server.token}; path=/")
            web.loadUrl("$origin/")
        }
    }

    /** Links out of the app (help, Play Store): in the browser or the app they're for. */
    private inner class Links : WebViewClient() {
        override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
            if (request.url.host == "127.0.0.1") return false
            runCatching { startActivity(Intent(Intent.ACTION_VIEW, request.url)) }
            return true
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
