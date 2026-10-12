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
        // Each line on its own, the mp3s joined (as the computer's tts.lines): a natural voice
        // given a lone word then a sentence in one text makes up words. 200 characters a line.
        val lines = text.lines().map { it.trim().take(200) }.filter { it.isNotEmpty() }.ifEmpty { listOf(text.trim().take(200)) }
        val said = lines.joinToString("\n")
        val rate = RATES[prefs[TTS_RATE]] ?: Relay.SPEECH_RATE
        val digest = MessageDigest.getInstance("SHA-1").digest("$voice|$rate|$said".toByteArray())
        val mp3 = File(folder, digest.joinToString("") { "%02x".format(it) }.take(16) + ".mp3")
        if (!mp3.isFile) {
            val bytes = lines.map { relay().speak(it, voice, rate) }.reduce { all, part -> all + part }
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
    suspend fun sounds(deck: Deck, voice: String, dictation: Boolean = false): Pair<Map<String, File>, Int> {
        if (!VOICE.matches(voice)) return emptyMap<String, File>() to 0
        val backs = deck.cards.map { spoken(it, dictation) }.filter { it.isNotEmpty() }.distinct()
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
        private val BLANK = Regex("""…|\.{3}|_{3,}""") // a sentence's blank for the word to write
        private val BRACKETS = Regex("""\s*\([^)]*\)""")

        /** What a card's sound says (as the core's tts.spoken): its back. A dictation's card
         * whose front is a sentence with a blank: the sentence with the word, then the word
         * (alone, "vers" could be "verre" or "vert"); each on its line, read on its own (read). */
        fun spoken(card: Card, dictation: Boolean): String {
            val back = card.back.trim()
            val sentence = card.front.replace(BRACKETS, "").trim()
            if (!dictation || '\n' in back || !BLANK.containsMatchIn(sentence)) return back
            val said = BLANK.replaceFirst(sentence, Regex.escapeReplacement(back))
            return "$said${if (said.last() in ".!?") "" else "."}\n$back"
        }

        // The voice chosen for a lesson whose voice is "auto" (Chirp 3 HD: the same name in
        // every language); a voice's name, as the page tells them from Anki locales
        const val DEFAULT_VOICE = "Aoede"
        const val TTS_RATE = "tts_rate" // the setting: the voice's speed, as the computer's
        val RATES = mapOf("-25%" to 0.75, "-10%" to Relay.SPEECH_RATE, "+0%" to 1.0)
        private val VOICE = Regex("""^[a-z]{2,3}-[A-Z]{2}-[\w-]+$""")

        /** The backs' language when it is one being learned: not the pupil's own (the page's)
         * unless the cards are for writing what is heard, as the computer (app/main.py). */
        /** The backs' language when it is one being learned: not the pupil's own, unless the cards
         * are for writing what is heard (a dictation): then theirs when the AI gave none (it
         * doesn't for their own language). As the computer's (generation._learned). */
        fun learned(language: String, pupil: String, spelling: Boolean): String = when {
            spelling -> language.trim().ifEmpty { pupil.substringBefore('-').lowercase() }
            language.lowercase().substringBefore('-') == pupil.substringBefore('-') -> ""
            else -> language
        }
    }
}
