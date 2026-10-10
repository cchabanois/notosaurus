package app.notosaurus

import org.junit.Assert.assertEquals
import org.junit.Test

/** What doesn't need AnkiDroid: the diagrams' masks, as the computer writes them. */
class AnkiTest {
    @Test
    fun masksAsTheComputersMasks() {
        val masks = listOf(Mask(1, 2, listOf(0.5, 0.1, 0.75, 0.2)), Mask(1, 1, listOf(0.123456, 0.3, 0.25, 0.333333)))
        // diagrams.masks_html(masks, 1, reveal) on the computer, for the same masks
        assertEquals(
            """<div class="notosaurus-mask target" style="left:12.35%;top:30.0%;width:12.65%;height:3.33%">(1)</div>""" +
                """<div class="notosaurus-mask" style="left:50.0%;top:10.0%;width:25.0%;height:10.0%">(2)</div>""",
            Anki.masksHtml(masks, 1, reveal = false),
        )
        assertEquals(
            """<div class="notosaurus-mask revealed" style="left:12.35%;top:30.0%;width:12.65%;height:3.33%"></div>""" +
                """<div class="notosaurus-mask" style="left:50.0%;top:10.0%;width:25.0%;height:10.0%">(2)</div>""",
            Anki.masksHtml(masks, 1, reveal = true),
        )
    }

    @Test
    fun theDiagramCroppedAsOnTheComputer() {
        val masks = listOf(Mask(1, 2, listOf(0.5, 0.1, 0.75, 0.2)), Mask(1, 1, listOf(0.123456, 0.3, 0.25, 0.333333)))
        // diagrams.crop and masks_html(…, box) on the computer, for the same frame and masks
        val box = Anki.crop(listOf(0.2, 0.05, 0.7, 0.5), masks)
        assertEquals(listOf(0.0935, 0.05, 0.78, 0.5), box) // stretched to hold the labels, with a margin
        assertEquals(
            """<div class="notosaurus-mask" style="left:4.36%;top:55.56%;width:18.44%;height:7.4%">(1)</div>""" +
                """<div class="notosaurus-mask target" style="left:59.21%;top:11.11%;width:36.42%;height:22.22%">(2)</div>""",
            Anki.masksHtml(masks, 2, reveal = false, box),
        )
        assertEquals(null, Anki.crop(null, masks)) // no frame: the whole photo
        assertEquals(listOf(0.0, 0.0, 0.99, 0.99), Anki.crop(listOf(0.0, 0.0, 0.99, 0.99), masks))
    }
}
