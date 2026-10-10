package app.notosaurus

import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import java.io.File

/** The prompts, as the computer's (app/prompts.py): Notosaurus's (from the page's
 * languages), then the user's (kept in `file`). */
class Prompts(private val file: File, private val texts: PageTexts) {
    fun all(lang: String): List<JsonElement> = builtin(lang) + mine()

    /** A prompt of the user's, new (`id` null) or changed. */
    fun save(id: Int?, prompt: JsonObject): JsonObject {
        val list = mine().toMutableList()
        val newId = id ?: ((list.maxOfOrNull { it.jsonObject["id"]!!.plain().toIntOrNull() ?: 0 } ?: 0) + 1)
        val saved = JsonObject(
            DEFAULTS + prompt.filterKeys { it in FIELDS } + mapOf("id" to JsonPrimitive(newId), "builtin" to JsonPrimitive(false)),
        )
        val at = list.indexOfFirst { it.jsonObject["id"]!!.plain() == newId.toString() }
        if (at >= 0) list[at] = saved else list += saved
        write(list)
        return saved
    }

    fun delete(id: String) = write(mine().filter { it.jsonObject["id"]!!.plain() != id })

    /** A copy of a prompt (Notosaurus's or the user's) of the user's own. */
    fun duplicate(lang: String, id: String): JsonObject = save(null, all(lang).first { it.jsonObject["id"]!!.plain() == id }.jsonObject)

    private fun builtin(lang: String): List<JsonElement> {
        val local = texts.file(lang)["builtinPrompts"] as? JsonObject ?: JsonObject(emptyMap())
        val english = texts.file("en")["builtinPrompts"] as? JsonObject ?: JsonObject(emptyMap())
        return BUILTIN.mapNotNull { key ->
            val prompt = (local[key] ?: english[key])?.jsonObject ?: return@mapNotNull null
            JsonObject(DEFAULTS + prompt + mapOf("id" to JsonPrimitive("notosaurus:$key"), "builtin" to JsonPrimitive(true)))
        }
    }

    private fun mine(): List<JsonElement> = if (file.isFile) json.parseToJsonElement(file.readText()).jsonArray else emptyList()

    private fun write(list: List<JsonElement>) = file.writeText(JsonArray(list).toString())

    companion object {
        // Notosaurus's prompts, in order (app/prompts.py, BUILTIN)
        private val BUILTIN = listOf(
            "auto", "vocabulary", "sentences", "questions", "cloze", "quiz", "true_false", "formulas",
            "geometry", "diagram", "pictures", "wordlist", "dictation",
        )
        private val FIELDS = setOf("name", "text", "deck", "voice", "typing", "dictation")
        private val DEFAULTS = mapOf(
            "deck" to JsonPrimitive(""), "voice" to JsonPrimitive(""), "typing" to JsonPrimitive(false),
            "dictation" to JsonPrimitive(false), "used_at" to JsonNull,
        )
    }
}
