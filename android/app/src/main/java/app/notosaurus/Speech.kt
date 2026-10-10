package app.notosaurus

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.jsonObject
import java.io.File
import java.security.MessageDigest

/** The backs read aloud by the relay's voices (Google Chirp 3 HD), kept on the phone in
 * `folder`: the same text and voice aren't paid for twice (the 🔊 preview, then the cards). */
class Speech(private val folder: File, private val prefs: Preferences, private val relay: () -> Relay) {
    private var voiceList: JsonArray? = null

    /** The relay's voices ({"voice", "locale", "gender"}, as the page lists them), asked once. */
    suspend fun voices(): JsonArray = voiceList ?: relay().voices().also { voiceList = it }

    /** A text read aloud: its mp3, at the settings' speed. */
    suspend fun read(text: String, voice: String): File {
        val said = text.trim().take(200) // as the computer: a back's first 200 characters
        val rate = RATES[prefs[TTS_RATE]] ?: Relay.SPEECH_RATE
        val digest = MessageDigest.getInstance("SHA-1").digest("$voice|$rate|$said".toByteArray())
        val mp3 = File(folder, digest.joinToString("") { "%02x".format(it) }.take(16) + ".mp3")
        if (!mp3.isFile) {
            val bytes = relay().speak(said, voice, rate)
            withContext(Dispatchers.IO) {
                val tmp = File(folder, mp3.name + ".tmp")
                tmp.writeBytes(bytes)
                tmp.renameTo(mp3)
            }
        }
        return mp3
    }

    /** The backs' sound for AnkiDroid, with `voice` (none: no sound), and how many
     * couldn't be made. */
    suspend fun sounds(deck: Deck, voice: String): Pair<Map<String, File>, Int> {
        if (!VOICE.matches(voice)) return emptyMap<String, File>() to 0
        val backs = deck.cards.map { it.back.trim() }.filter { it.isNotEmpty() }.distinct()
        val made = backs.associateWith { runCatching { read(it, voice) }.getOrNull() }
        return made.filterValues { it != null }.mapValues { it.value!! } to made.count { it.value == null }
    }

    /** The voice for the backs' language ("es-ES", "en"…): DEFAULT_VOICE in that variety,
     * else in another of the language; "" when none (or no relay). */
    suspend fun voiceFor(language: String): String {
        val tag = language.trim().replace('_', '-').lowercase()
        if (tag.isEmpty()) return ""
        val all = runCatching { voices() }.getOrNull()?.map { it.jsonObject } ?: return ""
        val base = tag.substringBefore('-')
        val ranked = all.filter { it.string("locale").lowercase().substringBefore('-') == base }.sortedWith(
            compareBy(
                { it.string("locale").lowercase() != tag }, // the variety asked for
                { it.string("locale").lowercase() != "$base-$base" }, // else the language's own (es-ES, fr-FR)
                { !it.string("voice").endsWith("-$DEFAULT_VOICE") },
            ),
        )
        return ranked.firstOrNull()?.string("voice") ?: ""
    }

    /** What the kept sounds take on the phone. */
    fun bytes(): Long = folder.walkTopDown().filter { it.isFile }.sumOf { it.length() }

    fun deleteAll() = folder.listFiles()?.forEach { it.delete() }

    companion object {
        // The voice chosen for a lesson whose voice is "auto" (Chirp 3 HD: the same name in
        // every language); a voice's name, as the page tells them from Anki locales
        const val DEFAULT_VOICE = "Aoede"
        const val TTS_RATE = "tts_rate" // the setting: the voice's speed, as the computer's
        val RATES = mapOf("-25%" to 0.75, "-10%" to Relay.SPEECH_RATE, "+0%" to 1.0)
        private val VOICE = Regex("""^[a-z]{2,3}-[A-Z]{2}-[\w-]+$""")

        /** The backs' language when it is one being learned: not the pupil's own (the page's)
         * unless the cards are for writing what is heard, as the computer (app/main.py). */
        fun learned(language: String, pupil: String, spelling: Boolean): String =
            if (!spelling && language.lowercase().substringBefore('-') == pupil.substringBefore('-')) "" else language
    }
}
