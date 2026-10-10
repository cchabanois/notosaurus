package app.notosaurus

import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.jsonObject

/** The page's languages and texts (static/i18n/<lang>.json, among the page's files). */
class PageTexts(
    private val web: (String) -> ByteArray?, // a file of the page, by its path
    private val languages: () -> List<String>, // the page's languages ("en", "fr"…)
) {
    fun codes(): List<String> = languages().sorted()

    fun file(lang: String): JsonObject =
        web("i18n/$lang.json")?.let { json.parseToJsonElement(it.decodeToString()).jsonObject } ?: JsonObject(emptyMap())

    /** A text in that language; null when it has none. */
    fun get(lang: String, vararg keys: String): String? {
        var value: JsonElement? = file(lang)
        for (key in keys) value = (value as? JsonObject)?.get(key)
        return (value as? JsonPrimitive)?.content
    }
}
