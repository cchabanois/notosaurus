package app.notosaurus

import android.content.Context
import android.graphics.Bitmap
import android.graphics.ImageDecoder
import android.net.Uri
import java.io.ByteArrayOutputStream
import kotlin.math.max

object Photos {
    // As the relay's AI sees them (notosaurus_core.diagrams.MAX_SIDE): larger is only heavier
    private const val MAX_SIDE = 1568
    private const val QUALITY = 85

    /** A photo as sent to the relay: upright (its EXIF orientation applied), at most
     * MAX_SIDE, JPEG: a few hundred KB instead of 3–5 MB. */
    fun prepare(context: Context, uri: Uri): ByteArray {
        val source = ImageDecoder.createSource(context.contentResolver, uri)
        val bitmap = ImageDecoder.decodeBitmap(source) { decoder, info, _ ->
            val side = max(info.size.width, info.size.height)
            if (side > MAX_SIDE) {
                val scale = MAX_SIDE.toDouble() / side
                decoder.setTargetSize((info.size.width * scale).toInt(), (info.size.height * scale).toInt())
            }
            decoder.allocator = ImageDecoder.ALLOCATOR_SOFTWARE // compressible
        }
        return ByteArrayOutputStream().use { out ->
            bitmap.compress(Bitmap.CompressFormat.JPEG, QUALITY, out)
            out.toByteArray()
        }
    }
}
