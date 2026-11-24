package app.notosaurus

import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Test

/** The voice an "auto" lesson gets (Speech.voiceFor), among the relay's voices (Chirp 3 HD). */
class VoicePickTest {
    private fun voice(locale: String, name: String = "Aoede") =
        JsonObject(mapOf("locale" to JsonPrimitive(locale), "voice" to JsonPrimitive("$locale-Chirp3-HD-$name")))

    private val all = listOf(
        voice("cmn-CN", "Puck"), voice("cmn-CN"), voice("cmn-TW"), voice("yue-HK"),
        voice("en-AU"), voice("en-GB"), voice("es-ES"), voice("es-US"),
    )

    @Test
    fun chineseFoundUnderTheSpokenLanguagesName() {
        // The AI says "zh-CN": the voices are Mandarin's (cmn-CN), Cantonese's (yue-HK)
        assertEquals("cmn-CN-Chirp3-HD-Aoede", Speech.pick("zh-CN", all, emptyMap()))
        assertEquals("cmn-CN-Chirp3-HD-Aoede", Speech.pick("zh", all, emptyMap()))
        assertEquals("cmn-CN-Chirp3-HD-Aoede", Speech.pick("zh-Hans", all, emptyMap()))
        assertEquals("cmn-TW-Chirp3-HD-Aoede", Speech.pick("zh-TW", all, emptyMap()))
        assertEquals("cmn-TW-Chirp3-HD-Aoede", Speech.pick("zh-Hant", all, emptyMap()))
        assertEquals("yue-HK-Chirp3-HD-Aoede", Speech.pick("zh-HK", all, emptyMap()))
        assertEquals("cmn-CN-Chirp3-HD-Puck", Speech.pick("zh-CN", all, mapOf("cmn-CN" to "cmn-CN-Chirp3-HD-Puck"))) // the one chosen
    }

    @Test
    fun otherLanguagesAsBefore() {
        assertEquals("en-GB-Chirp3-HD-Aoede", Speech.pick("en", all, emptyMap()))
        assertEquals("es-US-Chirp3-HD-Aoede", Speech.pick("es-US", all, emptyMap()))
        assertEquals("", Speech.pick("ja-JP", all, emptyMap()))
        assertEquals("", Speech.pick("", all, emptyMap()))
    }
}
