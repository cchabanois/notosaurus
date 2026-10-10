package app.notosaurus

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Test
import org.junit.runner.RunWith
import java.io.ByteArrayOutputStream

/** Photos turned as Android draws them (the JVM tests use a fake). */
@RunWith(AndroidJUnit4::class)
class PhotosTest {
    @Test
    fun aQuarterTurn() {
        val wide = Bitmap.createBitmap(40, 30, Bitmap.Config.ARGB_8888)
        val jpeg = ByteArrayOutputStream().also { wide.compress(Bitmap.CompressFormat.JPEG, 90, it) }.toByteArray()
        val bytes = Photos.turn(jpeg, 90)
        val turned = BitmapFactory.decodeByteArray(bytes, 0, bytes.size)
        assertEquals(listOf(30, 40), listOf(turned.width, turned.height))
        assertArrayEquals(jpeg, Photos.turn(jpeg, 45)) // not a right angle: unchanged
        assertArrayEquals("not a photo".toByteArray(), Photos.turn("not a photo".toByteArray(), 90))
    }
}
