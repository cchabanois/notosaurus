package app.notosaurus

import io.ktor.server.routing.Route
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put

/** AnkiDroid: the cards sent, installed, a deck reviewed. */
internal fun Route.ankiRoutes(server: LocalServer) {
    with(server) {
        // --- AnkiDroid
        api("GET", "/api/anki/status") {
            buildJsonObject {
                // Always: "Add to Anki" asks for AnkiDroid (installed, allowed) when it's used
                put("available", true)
                put("version", 6)
                put("profile", JsonNull)
                put("sync", JsonNull)
            }
        }
        api("POST", "/api/anki/send") {
            val req = body()
            req.string("lesson_id").takeIf { it.isNotEmpty() }?.let { lessons.update(it, req, exported = true) }
            val deck = json.decodeFromJsonElement(Deck.serializer(), buildJsonObject {
                put("deck", req["deck"]!!)
                put("cards", req["cards"]!!)
            })
            readyAnki()
            val (sounds, failures) = speech.sounds(deck, req.string("voice"))
            val lessonId = req.string("lesson_id")
            val folder = lessons.images(lessonId)
            val pictures = deck.cards.mapNotNull { c -> folder?.resolve(c.picture)?.takeIf { c.picture.isNotEmpty() && it.isFile }?.let { c.picture to it } }.toMap()
            // The diagrams: the photos their labels are on
            val photos = deck.cards.mapNotNull { it.mask?.page }.distinct().mapNotNull { n -> lessons.photo(lessonId, n)?.let { n to it } }.toMap()
            // The diagram frames as the page has them (the user may have moved one), else the lesson's
            val frames = (req["frames"]?.takeIf { it is JsonArray } ?: lessons.get(lessonId)?.get("frames"))
                ?.jsonArray?.associate { it.jsonObject["page"]!!.jsonPrimitive.content.toInt() to it.jsonObject["box"]!!.jsonArray.map { v -> v.jsonPrimitive.content.toDouble() } }
                .orEmpty()
            val media = Media(sounds, pictures, photos, lessonId, frames)
            fun on(option: String) = req[option]?.jsonPrimitive?.content == "true"
            val options = Options(reverse = on("reverse"), typing = on("typing"), dictation = on("dictation"))
            val sent = try {
                withContext(Dispatchers.IO) { anki.send(deck, media, options) }
            } catch (e: Exception) { // e.g. AnkiDroid never opened: no collection yet
                throw BadRequest("anki.android_failed", buildJsonObject { put("detail", e.message ?: e.javaClass.simpleName) })
            }
            buildJsonObject {
                put("added", sent.added)
                put("updated", sent.updated) // the lesson's notes sent before, changed since
                put("moved", sent.moved) // and moved, the lesson's deck having changed
                put("synced", false)
                if (failures > 0) put("audio_failures", failures) // the page says some have no sound
            }
        }

        // AnkiDroid's Google Play page, asked from the message saying it's missing
        api("POST", "/api/anki/install") {
            installAnki()
            buildJsonObject { put("opened", true) }
        }
        // A lesson's deck reviewed in AnkiDroid ("Review" after sending it)
        api("POST", "/api/anki/review") {
            val deck = body().string("deck")
            val opened = withContext(Dispatchers.IO) { runCatching { anki.review(deck) }.getOrDefault(false) }
            if (!opened) throw BadRequest("anki.android_no_deck", buildJsonObject { put("deck", deck) })
            buildJsonObject { put("opened", true) }
        }
    }
}

/** AnkiDroid installed and allowed, asked for when the cards are first added: its Play
 * Store page when it's missing, its permission dialog when it isn't allowed yet. */
private suspend fun LocalServer.readyAnki() {
    // Not installed: said, with a button to install it (Google Play doesn't open by surprise)
    if (!anki.installed()) throw BadRequest("anki.android_missing")
    if (!anki.permitted() && !requestAnkiPermission()) throw BadRequest("anki.android_refused")
}
