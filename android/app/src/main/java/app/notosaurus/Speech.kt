package app.notosaurus

import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.Semaphore
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.sync.withPermit
import kotlinx.coroutines.withContext
import kotlinx.serialization.builtins.ListSerializer
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.jsonObject
import java.io.File
import java.security.MessageDigest
import java.text.Normalizer

/**
 * The backs read aloud by the relay's voices (Google Chirp 3 HD). A lesson's sounds are in
 * its own folder, as the computer keeps them (core tts.py): audio/, each mp3 named after its
 * text and a hash of (voice, rate, text), the same names on both. A card may have a voice of
 * its own (Card.voice), else it is the lesson's: a lesson moved from the computer keeps its
 * sounds, made with edge-tts's voices (cardVoice). `folder`: the 🔊 previews outside a lesson;
 * it held every sound before (moveIntoLessons).
 */
class Speech(
    private val folder: File,
    private val prefs: Preferences,
    private val relay: () -> Relay,
    private val lessonAudio: (String) -> File? = { null }, // a lesson's audio/ folder (Lessons.audio)
) {
    private var voiceList: JsonArray? = null

    /** The relay's voices ({"voice", "locale", "gender"}, as the page lists them), asked once. */
    suspend fun voices(): JsonArray = voiceList ?: relay().voices().also { voiceList = it }

    /** A text read aloud: its mp3, at the lesson's `rate` ("-10%"; "": the settings'), in
     * the `lesson`'s folder (none: a preview, in `folder`). */
    suspend fun read(text: String, voice: String, rate: String = "", lesson: String = ""): File {
        val r = rateOf(rate)
        val dir = lesson.takeIf { it.isNotEmpty() }?.let(lessonAudio)
        val mp3 = File(dir ?: folder, fileName(text, voice, r))
        if (mp3.isFile) return mp3
        if (dir != null) {
            // Made before: the same sound previewed, or kept by an older version in `folder`
            val before = listOf(File(folder, mp3.name), File(folder, legacyName(text, voice, r))).firstOrNull { it.isFile }
            if (before != null) {
                withContext(Dispatchers.IO) { dir.mkdirs(); before.copyTo(mp3, overwrite = true) }
                return mp3
            }
        } else {
            File(folder, legacyName(text, voice, r)).takeIf { it.isFile }?.let { return it }
        }
        // Each line on its own, the mp3s joined (as the computer's tts.lines): a natural voice
        // given a lone word then a sentence in one text makes up words. 200 characters a line.
        val speed = RATES[r] ?: Relay.SPEECH_RATE
        val bytes = lines(text).map { relay().speak(it, voice, speed) }.reduce { all, part -> all + part }
        withContext(Dispatchers.IO) {
            mp3.parentFile?.mkdirs()
            val tmp = File(mp3.parentFile, mp3.name + ".tmp")
            tmp.writeBytes(bytes)
            tmp.renameTo(mp3)
        }
        return mp3
    }

    /** The rate a sound is read at: the lesson's, else the settings', else SLOWED. */
    private fun rateOf(rate: String): String = rate.ifEmpty { prefs[TTS_RATE].orEmpty() }.takeIf { it in RATES } ?: SLOWED

    /** A lesson's voice the relay reads with: the computer's (edge-tts's, a lesson imported
     * while the relay couldn't be asked) gives way to the relay's for that language. */
    suspend fun relayVoice(voice: String): String =
        if (voice.endsWith("Neural")) voiceFor(voice.split('-').take(2).joinToString("-")).ifEmpty { voice } else voice

    /** The voice of the card's sound: its own (Card.voice) when the relay reads with it or
     * its sound is in the lesson already (made on the computer), else the lesson's. */
    suspend fun cardVoice(card: Card, lessonVoice: String, text: String, rate: String = "", lesson: String = ""): String {
        val own = card.voice
        if (own.isEmpty() || own == lessonVoice) return lessonVoice
        val dir = lesson.takeIf { it.isNotEmpty() }?.let(lessonAudio)
        if (dir != null && File(dir, fileName(text, own, rateOf(rate))).isFile) return own
        val ours = runCatching { voices() }.getOrNull()?.map { it.jsonObject.string("voice") }.orEmpty()
        return if (own in ours) own else lessonVoice
    }

    /** The lesson's mp3s no card says any more (backs corrected, voice changed) deleted. */
    suspend fun prune(lesson: String, keep: Set<File>) {
        val dir = lesson.takeIf { it.isNotEmpty() }?.let(lessonAudio) ?: return
        withContext(Dispatchers.IO) {
            dir.listFiles { f -> f.name.endsWith(".mp3") && f !in keep }?.forEach { it.delete() }
        }
    }

    /** Every lesson's sounds, kept by an older version in `folder`, moved into its own folder
     * (no credit paid again); then `folder` holds only previews. Once (MOVED). */
    fun moveIntoLessons(lessons: List<JsonObject>) {
        if (prefs[MOVED] == "true") return
        for (lesson in lessons) {
            val dir = lessonAudio(lesson.string("id")) ?: continue
            val voice = lesson.string("voice")
            val r = rateOf(lesson.string("rate"))
            fun on(option: String) = (lesson[option] as? JsonPrimitive)?.content == "true"
            val cards = runCatching { json.decodeFromJsonElement(ListSerializer(Card.serializer()), lesson["cards"]!!) }.getOrDefault(emptyList())
            for (text in cards.map { spoken(it, on("dictation") || on("dictation_only")) }.filter { it.isNotEmpty() }.distinct()) {
                val old = File(folder, legacyName(text, voice, r)).takeIf { it.isFile } ?: continue
                dir.mkdirs()
                old.copyTo(File(dir, fileName(text, voice, r)), overwrite = true)
            }
        }
        folder.listFiles { f -> LEGACY.matches(f.name) }?.forEach { it.delete() }
        prefs[MOVED] = "true"
    }

    /** The backs' sound for AnkiDroid, with `voice` (none: no sound), and how many
     * couldn't be made. */
    suspend fun sounds(
        deck: Deck,
        voice: String,
        dictation: Boolean = false,
        rate: String = "",
        lesson: String = "", // its folder keeps them (none: previews')
        onSound: suspend (done: Int, total: Int) -> Unit = { _, _ -> }, // first (0, total), then as each is done
    ): Pair<Map<String, File>, Int> {
        if (!reads(voice)) return emptyMap<String, File>() to 0
        val voice = relayVoice(voice)
        // Each back in its card's voice (its own, else the lesson's: cardVoice)
        val voices = deck.cards.map { it to spoken(it, dictation) }.filter { it.second.isNotEmpty() }
            .associate { (card, back) -> back to cardVoice(card, voice, back, rate, lesson) }
        val backs = voices.keys.toList()
        if (backs.isNotEmpty()) onSound(0, backs.size)
        // PARALLEL at a time, as the computer's (tts.MAX_PARALLEL): one by one, a lesson's took minutes
        val gate = Semaphore(PARALLEL)
        val counting = Mutex() // told in order: the page shows the last one
        var done = 0
        val made = coroutineScope {
            backs.map { back ->
                async {
                    gate.withPermit {
                        val mp3 = try {
                            read(back, voices.getValue(back), rate, lesson)
                        } catch (e: CancellationException) {
                            throw e
                        } catch (e: Exception) { // the card goes without sound, counted
                            null
                        }
                        counting.withLock { onSound(++done, backs.size) }
                        back to mp3
                    }
                }
            }.awaitAll()
        }
        return made.mapNotNull { (back, mp3) -> mp3?.let { back to it } }.toMap() to made.count { it.second == null }
    }

    /** The voice for the backs' language ("es-ES", "en"…): DEFAULT_VOICE in that variety,
     * else in the language's usual one (VARIETY), else in another; "" when none (or no relay). */
    suspend fun voiceFor(language: String): String {
        val tag = language.trim().replace('_', '-').lowercase()
        if (tag.isEmpty()) return ""
        val all = runCatching { voices() }.getOrNull()?.map { it.jsonObject } ?: return ""
        val base = tag.substringBefore('-')
        // The one the user chose for that variety (for a language alone: for one of its varieties)
        val mine = chosen().mapKeys { it.key.lowercase() }.filterValues { it.isNotBlank() }
        mine[tag]?.let { return it }
        if (tag == base) mine.toSortedMap().entries.firstOrNull { it.key.substringBefore('-') == base }?.let { return it.value }
        val ranked = all.filter { it.string("locale").lowercase().substringBefore('-') == base }.sortedWith(
            compareBy(
                { it.string("locale").lowercase() != tag }, // the variety asked for
                { it.string("locale").lowercase() != (VARIETY[base] ?: "$base-$base") }, // else its usual one (en-GB, es-ES)
                { !it.string("voice").endsWith("-$DEFAULT_VOICE") },
            ),
        )
        return ranked.firstOrNull()?.string("voice") ?: ""
    }

    /** The voice chosen per language variety ("es-ES" → "es-ES-Chirp3-HD-Puck"), in the settings. */
    fun chosen(): Map<String, String> =
        runCatching { json.decodeFromString<Map<String, String>>(prefs[VOICES].orEmpty()) }.getOrDefault(emptyMap())

    fun choose(voices: Map<String, String>) {
        prefs[VOICES] = json.encodeToString(voices.filter { (locale, voice) -> locale.isNotBlank() && voice.isNotBlank() })
    }

    /** What the previews take on the phone (a lesson's sounds are in its folder: Lessons.bytes). */
    fun bytes(): Long = folder.walkTopDown().filter { it.isFile }.sumOf { it.length() }

    fun deleteAll() = folder.listFiles()?.forEach { it.delete() }

    companion object {
        // A language's usual variety, as the computer's (tts.PREFERRED): "en" alone isn't
        // en-AU, the first English voice by name ("en-en" isn't one)
        private val VARIETY = mapOf("en" to "en-gb", "pt" to "pt-pt")

        private val BLANK = Regex("""…|\.{3}|_{3,}""") // a sentence's blank for the word to write
        private val BRACKETS = Regex("""\s*\([^)]*\)""")
        // As the computer's tts.py: a phonetic transcription ("/ɜː/", "[ˈtaɪɡə]") isn't read; a part
        // singled out in brackets ("t[i]ger") is read as its word; the front's quoted examples
        private const val PHONETIC = "ɐ-ʯʰ-˿̀-ͯæøœθð"
        // Letters, digits and spaces of every script spelled out (\p{L}, \p{N}, \p{Z}), as Python's
        // \w, \d, \s: the JVM's are ASCII only ("кошка" no letters), Android's (ICU) aren't, and
        // Android knows no (?U): the same answer on both
        private val TRANSCRIPTION = Regex("""(?<![\p{L}\p{N}_/])/[^/\s\p{Z}\p{Nd}]{1,24}/(?![\p{L}\p{N}_/])|\[[^\[\]\s\p{Z}\p{Nd}]{0,24}[$PHONETIC][^\[\]\s\p{Z}\p{Nd}]{0,24}\]""")
        private val MARKED = Regex("""\[([^\[\]\n]{1,40})\]""")
        private val QUOTED = Regex("""[“"«]\s*([^”"»\n]{1,60}?)\s*[”"»]|‘([^’\n]{1,60}?)’""")
        private val LETTER = Regex("""[\p{L}\p{N}]""") // a letter or a digit, of any script: something a voice says

        /** The text as a voice can read it (the computer's tts.speakable). */
        fun speakable(text: String): String =
            text.replace(TRANSCRIPTION, " ").replace(MARKED) { it.groupValues[1] }.replace(Regex("[ \t]{2,}"), " ").trim()

        /** What a card's sound says (as the core's tts.spoken): its back. A dictation's card
         * whose front is a sentence with a blank: the sentence with the word, then the word
         * (alone, "vers" could be "verre" or "vert"); each on its line, read on its own (read). */
        fun spoken(card: Card, dictation: Boolean): String {
            val back = speakable(card.back.trim())
            if (!LETTER.containsMatchIn(back)) { // only a transcription: the front's quoted examples, each on its own
                return QUOTED.findAll(card.front).map { speakable(it.groupValues[1].ifEmpty { it.groupValues[2] }) }
                    .filter { LETTER.containsMatchIn(it) }.joinToString("\n")
            }
            val sentence = card.front.replace(BRACKETS, "").trim()
            if (!dictation || '\n' in back || !BLANK.containsMatchIn(sentence)) return back
            val said = BLANK.replaceFirst(sentence, Regex.escapeReplacement(back))
            return "$said${if (said.last() in ".!?") "" else "."}\n$back"
        }

        // The voice chosen for a lesson whose voice is "auto" (Chirp 3 HD: the same name in
        // every language); a voice's name, as the page tells them from Anki locales
        const val DEFAULT_VOICE = "Aoede"
        const val TTS_RATE = "tts_rate" // the setting: the voice's speed, as the computer's
        const val VOICES = "voices" // the setting: the voice chosen per language variety, as the computer's
        val RATES = mapOf("-25%" to 0.75, "-10%" to Relay.SPEECH_RATE, "+0%" to 1.0)
        private const val MOVED = "sounds_in_lessons" // the older shared sounds moved into their lessons
        private val LEGACY = Regex("^[0-9a-f]{16}\\.mp3$") // an older version's name: a hash of (voice, speed, text)

        /** A sound's file, as the computer names them (core tts.filename): "la-madre-3f2a1c9e.mp3",
         * the same name for the same sound (core/shared-cases.json, sound_file). */
        fun fileName(text: String, voice: String, rate: String): String =
            "${slug(text).ifEmpty { "audio" }}-${sha1("$voice|$rate|$text").take(8)}.mp3"

        /** As the core's files.slugify(text, 30): only what is ASCII once decomposed ("cœur" → "cur"). */
        private fun slug(text: String): String = Normalizer.normalize(text, Normalizer.Form.NFKD)
            .filter { it.code < 128 }.lowercase().replace(Regex("[^a-z0-9]+"), "-").trim('-').take(30).trimEnd('-')

        /** An older version's name for it (in `folder`): a hash of (voice, speed, the lines said). */
        private fun legacyName(text: String, voice: String, rate: String): String =
            sha1("$voice|${RATES[rate] ?: Relay.SPEECH_RATE}|${lines(text).joinToString("\n")}").take(16) + ".mp3"

        /** The lines read, each on its own (the computer's tts.lines): 200 characters a line. */
        private fun lines(text: String): List<String> =
            text.lines().map { it.trim().take(200) }.filter { it.isNotEmpty() }.ifEmpty { listOf(text.trim().take(200)) }

        private fun sha1(text: String): String =
            MessageDigest.getInstance("SHA-1").digest(text.toByteArray()).joinToString("") { "%02x".format(it) }
        const val SLOWED = "-10%" // the setting's default
        private const val NORMAL = "+0%"

        /** The backs' speed, kept with the lesson: the settings' slowdown (`slowed`) for a
         * language being learned or a dictation (time to write), normal otherwise. What the
         * instructions say ("slow", "normal") comes first: "slow" slows even when the settings
         * don't. As the computer's (generation._rate). */
        fun rate(slowed: String, speed: String, foreign: Boolean, dictation: Boolean): String = when {
            speed == "slow" -> if (slowed != NORMAL) slowed else SLOWED
            speed != "normal" && (foreign || dictation) -> slowed
            else -> NORMAL
        }
        private val VOICE = Regex("""^[a-z]{2,3}-[A-Z]{2}-[\w-]+$""")

        /** A voice the relay reads with (not an Anki locale, not none). */
        fun reads(voice: String) = VOICE.matches(voice)

        const val PARALLEL = 4 // sounds read at once

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
