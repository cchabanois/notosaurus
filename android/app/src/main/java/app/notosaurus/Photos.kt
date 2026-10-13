package app.notosaurus

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Matrix
import java.io.ByteArrayOutputStream

/** The photos of the lessons, as Android draws them. */
object Photos {
    /** A photo turned `degrees` clockwise (90, 180, 270), as the computer's
     * (diagrams.turn): JPEG. Not a right angle, or an unreadable photo: unchanged. */
    fun turn(data: ByteArray, degrees: Int): ByteArray {
        if (degrees !in setOf(90, 180, 270)) return data
        val photo = BitmapFactory.decodeByteArray(data, 0, data.size) ?: return data
        val turned = Bitmap.createBitmap(photo, 0, 0, photo.width, photo.height, Matrix().apply { postRotate(degrees.toFloat()) }, true)
        return ByteArrayOutputStream().also { turned.compress(Bitmap.CompressFormat.JPEG, 90, it) }.toByteArray()
    }

    /** A picture as a card shows it, as the computer's (pictures.card_size): at most CARD_SIDE,
     * a light JPEG. An unreadable one: unchanged. */
    fun cardSize(data: ByteArray): ByteArray {
        val photo = BitmapFactory.decodeByteArray(data, 0, data.size) ?: return data
        val scale = minOf(1f, CARD_SIDE.toFloat() / maxOf(photo.width, photo.height))
        val small = Bitmap.createScaledBitmap(photo, (photo.width * scale).toInt().coerceAtLeast(1), (photo.height * scale).toInt().coerceAtLeast(1), true)
        return ByteArrayOutputStream().also { small.compress(Bitmap.CompressFormat.JPEG, 80, it) }.toByteArray()
    }

    private const val CARD_SIDE = 512 // as the computer's pictures.SIDE: clear on a card, light to sync
}
