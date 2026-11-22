package app.notosaurus

import android.app.Activity
import android.content.Context
import android.net.Uri
import androidx.activity.result.ActivityResult
import androidx.activity.result.IntentSenderRequest
import com.google.android.gms.common.moduleinstall.ModuleInstall
import com.google.android.gms.common.moduleinstall.ModuleInstallRequest
import com.google.mlkit.vision.documentscanner.GmsDocumentScannerOptions
import com.google.mlkit.vision.documentscanner.GmsDocumentScanning
import com.google.mlkit.vision.documentscanner.GmsDocumentScanningResult
import kotlinx.coroutines.tasks.await
import kotlinx.coroutines.withTimeoutOrNull

/**
 * The page's camera (📷): a lesson's pages scanned, several at once, each found on the
 * photo, flattened and cropped. Google's document scanner by default (Google Play services
 * show its screens: the app needs no camera permission and never sees the camera's image);
 * the device tests give their own (AppTest). Its pages are copied into the app's cache by
 * MainActivity, like the camera's photos; when it can't be used, the camera itself.
 */
fun interface Scanner {
    /** The pages scanned, at most [limit]; null: the user went back. Throws when the scanner
     * can't be used (no Google Play services, a phone it doesn't run on, its module not
     * there): the camera then. [launch] starts its screens and gives their answer. */
    suspend fun scan(activity: Activity, limit: Int, launch: suspend (IntentSenderRequest) -> ActivityResult): List<Uri>?

    companion object {
        /** The scanner the app uses; another in the device tests. */
        @Volatile internal var current: Scanner = DocumentScanner

        /** The pages one scan may give: those the lesson has room for when the page's input
         * takes several ([free], from the page; unknown: a whole lesson's, the page saying
         * which ones didn't fit), one when it takes a single photo (a page served by an older
         * add-on). */
        fun pageLimit(multiple: Boolean, free: Int?): Int =
            if (!multiple) 1 else (free ?: LocalServer.MAX_PHOTOS).coerceIn(1, LocalServer.MAX_PHOTOS)

        /** The page's places left, as its script answers [FREE] (a number as JSON); null when
         * it couldn't say (another page, an older one). */
        fun free(answer: String?): Int? = answer?.trim()?.toDoubleOrNull()?.takeIf { it.isFinite() }?.toInt()

        /** Asked of the page: the lesson's places left (its maxPhotos less its photos). */
        const val FREE = "(() => { try { const d = Alpine.\$data(document.querySelector('[x-data]')); " +
            "return typeof d.maxPhotos === 'number' && Array.isArray(d.photos) ? d.maxPhotos - d.photos.length : null; } catch (e) { return null; } })()"

        /** What [wait] gives within [ms]; not by then, an ordinary error (the camera instead).
         * Not withTimeout: its TimeoutCancellationException is a CancellationException, which
         * MainActivity.capture rethrows as the activity's own end: no camera, the page's 📷
         * never answered. A real cancellation still goes through. */
        suspend fun <T : Any> within(ms: Long, wait: suspend () -> T): T =
            withTimeoutOrNull(ms) { wait() } ?: error("scanner: not ready within $ms ms")
    }
}

/** Google's document scanner (ML Kit, through Google Play services): its full mode (edges
 * found, cropped, cleaned of shadows and fingers), JPEG pages, no import from the gallery
 * (the page's 🖼️ is for that). */
object DocumentScanner : Scanner {
    /** Its screens not ready by then (Google Play services fetching it, offline): the camera. */
    private const val START_MS = 10_000L

    private fun client(limit: Int) = GmsDocumentScanning.getClient(
        GmsDocumentScannerOptions.Builder()
            .setScannerMode(GmsDocumentScannerOptions.SCANNER_MODE_FULL)
            .setResultFormats(GmsDocumentScannerOptions.RESULT_FORMAT_JPEG)
            .setGalleryImportAllowed(false)
            .setPageLimit(limit)
            .build(),
    )

    override suspend fun scan(activity: Activity, limit: Int, launch: suspend (IntentSenderRequest) -> ActivityResult): List<Uri>? {
        val client = client(limit)
        // Its module not on the phone yet (fetched in the background, or offline): the camera
        // now. Started without it, Google Play services' own screen says only "Something went
        // wrong", and its "Cancel" leaves the parent without a photo
        val installed = Scanner.within(START_MS) { ModuleInstall.getClient(activity).areModulesAvailable(client).await() }
        if (!installed.areModulesAvailable()) {
            preinstall(activity.applicationContext) {}
            error("scanner: its module isn't installed")
        }
        val start = Scanner.within(START_MS) { client.getStartScanIntent(activity).await() }
        val answer = launch(IntentSenderRequest.Builder(start).build())
        if (answer.resultCode == Activity.RESULT_CANCELED) return null
        check(answer.resultCode == Activity.RESULT_OK) { "scanner: ${answer.resultCode}" }
        val result = checkNotNull(GmsDocumentScanningResult.fromActivityResultIntent(answer.data)) { "scanner: no result" }
        return result.pages.orEmpty().map { it.imageUri }.ifEmpty { null }
    }

    /** Its module asked of Google Play services ahead (the app's first launch), so that the
     * first 📷 needn't wait for it: in the background, nothing shown, a failure ignored (the
     * scanner then fetches it itself, or the camera does). */
    fun preinstall(context: Context, done: () -> Unit) {
        runCatching {
            val request = ModuleInstallRequest.newBuilder().addApi(client(LocalServer.MAX_PHOTOS)).build()
            ModuleInstall.getClient(context).installModules(request).addOnSuccessListener { done() }
        }
    }
}
