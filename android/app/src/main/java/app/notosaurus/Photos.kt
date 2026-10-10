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
}
