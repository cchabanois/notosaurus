package app.notosaurus

import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.isActive
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.booleanOrNull
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
 * learned, photos taken sideways saved upright. "Cancel" (the page's job id) stops it.
 */
class Generation(
    private val lessons: Lessons,
    private val prefs: Preferences,
    private val relay: () -> Relay,
    private val speech: Speech,
    private val turnPhoto: (ByteArray, Int) -> ByteArray,
    private val children: Children = Children(prefs),
) {
    private val running = ConcurrentHashMap<String, Job>() // by the page's id for each

    /** `existing`: the lesson's cards made already ("front [part]"), when the photos are its
     * next pages (/v1/extract's "existing"): not made again. */
    suspend fun make(form: GenerationForm, onCard: OnCard, existing: List<String> = emptyList()): Made {
        val fields = form.fields
        val texts = pageTexts(fields["page_texts"], form.images.size)
        val every = children.list()
        val child = every.firstOrNull { it.id == fields["child"] } // the child it is for: its class, instructions, decks
        // The decks the AI may reuse: this child's and no child's, without the children's levels
        // (no child's name to the AI, nothing of another child's lessons)
        val decks = Children.decksForAi(lessons.list().map { it.string("deck") }, every, child)
        val request = buildJsonObject {
            put("prompt", fields["prompt"] ?: "")
            put("deck", fields["deck"] ?: "")
            put("decks", JsonArray(decks.map(::JsonPrimitive)))
            put("fun_facts", form.on("fun_facts"))
            put("helps", form.on("helps"))
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
            else speech.voiceFor(Speech.learned(found.string("back_language"), form.lang, typing || dictation))
        }
        // Photos taken sideways saved upright: their masks and frames turn with them
        val turns = found["turns"]?.jsonArray?.map { it.jsonPrimitive.content.toInt() }.orEmpty()
        var cards = found["deck"]!!.jsonObject["cards"]!!.jsonArray.map { it.jsonObject }
        var frames = (found["frames"] as? JsonArray)?.map { it.jsonObject }.orEmpty()
        val photos = form.images.mapIndexed { i, data ->
            val degrees = turns.getOrElse(i) { 0 }
            if (degrees == 0) return@mapIndexed data
            cards = cards.map { Diagrams.turnedMask(it, i + 1, degrees) }
            frames = frames.map { Diagrams.turnedFrame(it, i + 1, degrees) }
            turnPhoto(data, degrees)
        }
        val content = mapOf(
            "deck" to JsonPrimitive(Children.deckFor(child, found["deck"]!!.jsonObject.string("deck"))), // in the child's decks
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

    /** "Cancel": the lesson with that id stops being made; false when it isn't (done, unknown). */
    fun cancel(job: String): Boolean = running[job]?.also { it.cancel() } != null

    /** The settings' standing instructions and the child's (its class, instructions: never its
     * name), put before every request to the AI (app/settings.py, standing_instructions). */
    fun instructions(child: Child? = null): String {
        val parts = mutableListOf<String>()
        val text = prefs[LocalServer.INSTRUCTIONS].orEmpty().trim()
        if (text.isNotEmpty()) parts += "Standing instructions, for every lesson:\n$text"
        val own = Children.forAi(child)
        if (own.isNotEmpty()) parts += "Standing instructions for this pupil:\n$own"
        if (parts.isEmpty()) return ""
        return parts.joinToString("\n\n") + "\n(The request below wins if it says otherwise.)\n\n"
    }

    /** `work`, stopped by "Cancel" (`job`: the page's id for it): Cancelled then. */
    private suspend fun <T> cancellable(job: String?, work: suspend () -> T): T = coroutineScope {
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
