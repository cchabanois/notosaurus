package app.notosaurus

import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.isActive
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.intOrNull
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put
import java.util.concurrent.ConcurrentHashMap

/** The page's form for making a lesson: its fields, its photos, the page's language. */
class GenerationForm(val fields: Map<String, String>, val images: List<ByteArray>, val lang: String) {
    fun on(name: String) = fields[name] == "true"
}

/** What making a lesson gives: its new content (lesson fields) and its photos (upright). */
class Made(val content: Map<String, JsonElement>, val photos: List<ByteArray>)

/**
 * A lesson made by the relay from the page's form, as the computer makes it (app/main.py,
 * _generate): the cards (each told as it is written), an "auto" voice in the language
 * learned, the photos as taken (↻ turns one). "Cancel" (the page's job id) stops it.
 */
class Generation(
    private val lessons: Lessons,
    private val prefs: Preferences,
    private val relay: () -> Relay,
    private val speech: Speech,
    private val children: Children = Children(prefs),
    private val ankiDecks: () -> List<String> = { emptyList() }, // AnkiDroid's decks (none when it can't tell)
) {
    private val running = ConcurrentHashMap<String, Job>() // by the page's id for each

    /** `existing`: the lesson's cards made already ("front [part]"), when the photos are its
     * next pages (/v1/extract's "existing"): not made again. `but`: the lesson itself, made
     * again or completed (its deck is its own, not another's). */
    suspend fun make(form: GenerationForm, onCard: OnCard, existing: List<String> = emptyList(), but: String? = null): Made {
        // The pages of one call: more refused at once, not after sending them (the relay's limit)
        if (form.images.size > LocalServer.MAX_PER_CALL) throw BadRequest("extract.too_many", buildJsonObject { put("max", LocalServer.MAX_PER_CALL) })
        val fields = form.fields
        val texts = pageTexts(fields["page_texts"], form.images.size)
        val every = children.list()
        val child = every.firstOrNull { it.id == fields["child"] } // the child it is for: its class, instructions, decks
        // The decks the AI may reuse: this child's and no child's, without the children's levels
        // (no child's name to the AI, nothing of another child's lessons)
        val saved = lessons.list()
        val decks = Children.decksForAi(saved.map { it.string("deck") }, every, child)
        val request = buildJsonObject {
            put("prompt", fields["prompt"] ?: "")
            put("deck", fields["deck"] ?: "")
            put("decks", JsonArray(decks.map(::JsonPrimitive)))
            // The settings' (a prompt may say otherwise: "no fun facts")
            put("fun_facts", prefs[LocalServer.FUN_FACTS] != "false")
            put("helps", prefs[LocalServer.HELPS] != "false")
            put("pictures", prefs[LocalServer.PICTURES] != "false")
            put("page_texts", texts)
            put("instructions", instructions(child))
            put("quick", form.on("quick"))
            if (existing.isNotEmpty()) put("existing", JsonArray(existing.map(::JsonPrimitive)))
        }
        val found = cancellable(fields["job"]) { relay().extract(request, form.images, onCard) }
        // The options: Notosaurus's prompt's own, else what the AI read in the instructions (a
        // typed answer, the reverse card, a dictation) or recognised (prompt "Automatic": a dictation)
        fun said(key: String) = found[key]?.jsonPrimitive?.booleanOrNull == true
        val dictationOnly = form.on("dictation_only") || said("dictation")
        val typing = form.on("typing") || said("typing")
        val dictation = form.on("dictation") || said("dictation_card") || dictationOnly
        val voice = fields["voice"].orEmpty().let {
            if (!it.equals("auto", ignoreCase = true)) it
            else speech.voiceFor(Speech.learned(found.string("back_language"), form.lang, typing || dictation || said("read_aloud"))) // heard in their own language too
        }
        // The photos as taken: one sideways is turned with ↻ (no turn guessed: the AI named a
        // line's direction wrongly, a photo turned upside down)
        // Each card's page among this call's photos (0 unknown: from an older relay too); a lesson
        // completed numbers them from its own (Lessons.completed)
        val cards = found["deck"]!!.jsonObject["cards"]!!.jsonArray.map { pageWithin(it.jsonObject, form.images.size) }
        val frames = (found["frames"] as? JsonArray)?.map { it.jsonObject }.orEmpty()
        val photos = form.images
        // In the child's decks ("Jules::{classe}"), its own: never one that exists already
        // (another lesson's, or the user's in AnkiDroid), as the computer's (decks.new_name)
        val own = saved.firstOrNull { but != null && it.string("id") == but }?.string("deck").orEmpty()
        val inAnki = withContext(Dispatchers.IO) { runCatching(ankiDecks).getOrDefault(emptyList()) }
        val taken = existing(inAnki, saved.filter { it.string("id") != but }.map { it.string("deck") }, own)
        val content = mapOf(
            "deck" to JsonPrimitive(freeName(Children.deckFor(child, found["deck"]!!.jsonObject.string("deck")), taken)),
            "child" to JsonPrimitive(child?.id ?: ""),
            "cards" to JsonArray(cards),
            "prompt" to JsonPrimitive(fields["prompt"] ?: ""),
            "voice" to JsonPrimitive(voice),
            "rate" to JsonPrimitive(
                Speech.rate(
                    prefs[Speech.TTS_RATE] ?: Speech.SLOWED, found.string("speed"),
                    foreign = Speech.learned(found.string("back_language"), form.lang, false).isNotEmpty(), dictation = dictation,
                ),
            ),
            "reverse" to JsonPrimitive(said("reverse")),
            "typing" to JsonPrimitive(typing),
            "dictation" to JsonPrimitive(dictation),
            "dictation_only" to JsonPrimitive(dictationOnly),
            "choice" to (found["choice"] ?: JsonPrimitive("")),
            "page_texts" to texts,
            "frames" to JsonArray(frames), // each diagram's frame: what AnkiDroid shows
        )
        return Made(content, photos)
    }

    companion object {
        /** The card's page (the photo it was made from, counted from 1) as the AI gave it, kept
         * only when it is one of the call's `photos`: 0 (unknown) otherwise (cards.pages_within). */
        fun pageWithin(card: JsonObject, photos: Int): JsonObject {
            val page = (card["page"] as? JsonPrimitive)?.intOrNull ?: 0
            return card.with("page" to JsonPrimitive(if (page in 1..photos) page else 0))
        }

        /** The lesson's photos sent to correct one card (their numbers, from 1), and what they are,
         * as the computer (correction.fix_photos, core/shared-cases.json): the card's own page when
         * known ("card"); else all, when one call takes them ("all"); else none ("none": an older
         * card, a lesson longer than the relay takes at once, relay.too_large otherwise). */
        fun fixPhotos(page: Int, photos: Int): Pair<List<Int>, String> = when {
            page in 1..photos -> listOf(page) to "card"
            photos <= LocalServer.MAX_PER_CALL -> (1..photos).toList() to "all"
            else -> emptyList<Int>() to "none"
        }

        /** The lesson's photos sent to correct the whole lesson (their numbers, from 1), and what
         * they are, as the computer (correction.revise_photos, core/shared-cases.json): all, when one
         * call takes them ("all"); else none ("none": corrected from its cards, the AI told its pages
         * aren't shown; relay.too_large otherwise). */
        fun revisePhotos(photos: Int): Pair<List<Int>, String> =
            if (photos <= LocalServer.MAX_PER_CALL) (1..photos).toList() to "all" else emptyList<Int>() to "none"

        /** The decks that exist: AnkiDroid's (but its own, `own`: the deck of the lesson made
         * again, and its subdecks: they are its own, not another's), the lessons' with their
         * parents. As the computer's decks.existing (core/shared-cases.json). */
        fun existing(anki: List<String>, lessonDecks: List<String>, own: String = ""): Set<String> {
            val mine = own.trim().casefold()
            val names = anki.filter { n ->
                n != "Default" && !(mine.isNotEmpty() && (n.casefold() == mine || n.casefold().startsWith("$mine::")))
            }.toMutableSet()
            for (deck in lessonDecks) {
                val levels = deck.split("::").map { it.trim() }.filter { it.isNotEmpty() }
                for (n in levels.indices) names += levels.take(n + 1).joinToString("::")
            }
            return names
        }

        /** `deck`, or the first of "deck (2)", "deck (3)"… none of `taken` is: two lessons never
         * write into the same deck. AnkiDroid doesn't tell decks apart by case: neither does this.
         * As the computer's decks.free_name (core/shared-cases.json). */
        fun freeName(deck: String, taken: Set<String>): String {
            val name = deck.trim()
            val names = taken.map { it.casefold() }.toSet()
            if (name.isEmpty() || name.casefold() !in names) return name
            var n = 2
            while ("$name ($n)".casefold() in names) n++
            return "$name ($n)"
        }

        /** What the parent set, for everyone (`text`) and for this child (`child`: what the AI is
         * told of it, Children.forAi), put before the request to the AI: as the computer's
         * settings.standing_instructions (core/shared-cases.json). */
        fun standingInstructions(text: String, child: String): String {
            val parts = mutableListOf<String>()
            if (text.isNotBlank()) parts += "Standing instructions, for every lesson:\n${text.trim()}"
            if (child.isNotBlank()) parts += "Standing instructions for this pupil:\n${child.trim()}"
            if (parts.isEmpty()) return ""
            return parts.joinToString("\n\n") + "\n(The request below wins if it says otherwise.)\n\n"
        }

        /** The pages' texts sent by the page (JSON, one string per photo: a PDF page's text, "" for
         * a photo); anything else (not JSON, not strings, not one per photo): none, as the computer
         * (app/routes/generation.py, _page_texts). A list of the wrong length would give a page's
         * text to another photo. */
        fun pageTexts(raw: String?, photos: Int): JsonArray {
            val none = JsonArray(emptyList())
            val texts = runCatching { json.parseToJsonElement(raw.orEmpty().ifBlank { "[]" }) }.getOrNull() as? JsonArray ?: return none
            val strings = texts.all { it is JsonPrimitive && it.isString }
            return if (strings && texts.size == photos) texts else none
        }
    }

    /** "Cancel": the AI's work with that id (a lesson being made, corrected, a card corrected)
     * stops; false when it isn't running (done, unknown). */
    fun cancel(job: String): Boolean = running[job]?.also { it.cancel() } != null

    /** The settings' standing instructions and the child's (its class, instructions: never its
     * name), put before every request to the AI (app/settings.py, standing_instructions). */
    fun instructions(child: Child? = null): String = standingInstructions(prefs[LocalServer.INSTRUCTIONS].orEmpty(), Children.forAi(child))

    /** `work`, stopped by "Cancel" (`job`: the page's id for it): Cancelled then. */
    internal suspend fun <T> cancellable(job: String?, work: suspend () -> T): T = coroutineScope {
        val task = async { work() }
        if (!job.isNullOrBlank()) running[job] = task
        try {
            task.await()
        } catch (e: CancellationException) {
            if (task.isCancelled && isActive) throw Cancelled() else throw e
        } finally {
            if (!job.isNullOrBlank()) running.remove(job, task)
        }
    }
}
