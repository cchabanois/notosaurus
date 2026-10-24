package app.notosaurus

import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Assert.assertEquals
import org.junit.Test
import org.junit.runner.RunWith

/** The shared cases' trickiest, with Android's own regex engine (ICU): the unit tests run on
 * the JVM's, which differs (its \w is ASCII; it knows (?U), Android doesn't: Speech failed to
 * load on a phone while every unit test passed). core/shared-cases.json holds them all. */
@RunWith(AndroidJUnit4::class)
class RegexOnDeviceTest {
    @Test
    fun aBackInAnyScriptHasItsSound() {
        assertEquals("кошка", Speech.spoken(Card("le chat", "кошка"), false))
        assertEquals("猫", Speech.spoken(Card("le chat", "猫"), false))
        assertEquals("bird\nword", Speech.spoken(Card("The sound in \"bird\" and «word»", "/ɜː/"), false))
        assertEquals("the tiger", Speech.speakable("the [ˈtaɪɡə] tiger"))
    }

    @Test
    fun aTestsTagWithANonBreakingSpace() {
        assertEquals("Interro_SVT", Exams.tagText("Interro SVT"))
        assertEquals("Straße", Exams.commonDeck(listOf("Straße::a", "STRASSE::b")))
    }
}
