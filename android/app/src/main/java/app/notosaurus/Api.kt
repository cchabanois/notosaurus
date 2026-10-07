package app.notosaurus

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject

// The relay's API, version 1 (notosaurus_core.relay_api in core/,
// described by core/relay-api-v1.json): the part this app uses.

val json = Json {
    ignoreUnknownKeys = true // the relay may add fields
    explicitNulls = false
    encodeDefaults = true
}

@Serializable
data class ExtractRequest(
    val prompt: String,
    val deck: String = "",
    val decks: List<String> = emptyList(),
    @SerialName("fun_facts") val funFacts: Boolean = false,
    val helps: Boolean = false,
    @SerialName("page_texts") val pageTexts: List<String> = emptyList(),
    val instructions: String = "",
    val quick: Boolean = false,
)

@Serializable
data class Mask(val page: Int, val n: Int, val box: List<Double>)

@Serializable
data class Card(
    val front: String,
    val back: String,
    val choices: List<String> = emptyList(),
    val info: String = "",
    val subdeck: String = "",
    val tags: List<String> = emptyList(),
    val mask: Mask? = null,
    @SerialName("picture_prompt") val picturePrompt: String = "",
    val figure: String = "",
)

@Serializable
data class Deck(val deck: String, val cards: List<Card>)

@Serializable
data class Usage(val credits: Int, @SerialName("credits_left") val creditsLeft: Int)

@Serializable
data class ExtractResponse(
    val deck: Deck,
    val turns: List<Int> = emptyList(),
    @SerialName("back_language") val backLanguage: String = "",
    val choice: String = "",
    val usage: Usage,
)

@Serializable
data class Account(
    val plan: String,
    @SerialName("credits_left") val creditsLeft: Int,
    @SerialName("daily_left") val dailyLeft: Int,
    @SerialName("renews_at") val renewsAt: String? = null,
)

/** Every error of the relay: a code (relay.*, llm.*) and its parameters. */
@Serializable
data class ApiError(val code: String, val params: JsonObject = JsonObject(emptyMap()))

class RelayException(val code: String, val params: JsonObject = JsonObject(emptyMap())) :
    Exception(if (params.isEmpty()) code else "$code $params")
