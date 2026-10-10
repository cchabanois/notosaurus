package app.notosaurus

import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonPrimitive
import java.math.BigDecimal
import java.math.RoundingMode

/** The diagrams' boxes (masks, frames) on the lessons' photos, as the computer's
 * (core/notosaurus_core/diagrams.py). */
object Diagrams {
    /** A box (fractions of the photo) once the photo is turned `degrees` clockwise
     * (diagrams.rotate_box). */
    fun rotateBox(box: List<Double>, degrees: Int): List<Double> {
        val (x0, y0, x1, y1) = box
        val turned = when (degrees) {
            90 -> listOf(1 - y1, x0, 1 - y0, x1)
            180 -> listOf(1 - x1, 1 - y1, 1 - x0, 1 - y0)
            270 -> listOf(y0, 1 - x1, y1, 1 - x0)
            else -> return box
        }
        return turned.map { BigDecimal(it.coerceIn(0.0, 1.0)).setScale(4, RoundingMode.HALF_EVEN).toDouble() }
    }

    /** A card with its mask turned, if it is on photo `page`. */
    fun turnedMask(card: JsonObject, page: Int, degrees: Int): JsonObject {
        val mask = card["mask"] as? JsonObject ?: return card
        if (mask["page"]?.jsonPrimitive?.content?.toIntOrNull() != page) return card
        return card.with("mask" to turnedBox(mask, degrees))
    }

    /** A diagram frame ({"page", "box"}) turned, if it is on photo `page`. */
    fun turnedFrame(frame: JsonObject, page: Int, degrees: Int): JsonObject =
        if (frame["page"]?.jsonPrimitive?.content?.toIntOrNull() == page) turnedBox(frame, degrees) else frame

    private fun turnedBox(item: JsonObject, degrees: Int): JsonObject {
        val box = item["box"]!!.jsonArray.map { it.jsonPrimitive.content.toDouble() }
        return item.with("box" to JsonArray(rotateBox(box, degrees).map(::JsonPrimitive)))
    }
}
