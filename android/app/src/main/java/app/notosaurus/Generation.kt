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
) {
    private val running = ConcurrentHashMap<String, Job>() // by the page's id for each

    suspend fun make(form: GenerationForm, onCard: OnCard): Made {
        val fields = form.fields
        val texts = fields["page_texts"]?.let { json.parseToJsonElement(it) } ?: JsonArray(emptyList())
        val request = buildJsonObject {
            put("prompt", fields["prompt"] ?: "")
            put("deck", fields["deck"] ?: "")
            put("decks", JsonArray(lessons.list().map { JsonPrimitive(it.string("deck")) }.distinct()))
            put("fun_facts", form.on("fun_facts"))
            put("helps", form.on("helps"))
            put("page_texts", texts)
            put("instructions", instructions())
            put("quick", form.on("quick"))
        }
        val found = cancellable(fields["job"]) { relay().extract(request, form.images, onCard) }
        val voice = fields["voice"].orEmpty().let {
            if (!it.equals("auto", ignoreCase = true)) it
            else speech.voiceFor(Speech.learned(found.string("back_language"), form.lang, form.on("typing") || form.on("dictation")))
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
            "deck" to found["deck"]!!.jsonObject["deck"]!!,
            "cards" to JsonArray(cards),
            "prompt" to JsonPrimitive(fields["prompt"] ?: ""),
            "voice" to JsonPrimitive(voice),
            "typing" to JsonPrimitive(form.on("typing")),
            "dictation" to JsonPrimitive(form.on("dictation")),
            "choice" to (found["choice"] ?: JsonPrimitive("")),
            "page_texts" to texts,
            "frames" to JsonArray(frames), // each diagram's frame: what AnkiDroid shows
        )
        return Made(content, photos)
    }

    /** "Cancel": the lesson with that id stops being made; false when it isn't (done, unknown). */
    fun cancel(job: String): Boolean = running[job]?.also { it.cancel() } != null

    /** The settings' standing instructions, put before every request to the AI
     * (app/settings.py, standing_instructions). */
    fun instructions(): String {
        val text = prefs[LocalServer.INSTRUCTIONS].orEmpty().trim()
        if (text.isEmpty()) return ""
        return "Standing instructions, for every lesson:\n$text\n(The request below wins if it says otherwise.)\n\n"
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
