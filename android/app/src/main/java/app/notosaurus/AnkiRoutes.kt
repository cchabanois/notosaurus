package app.notosaurus

import io.ktor.http.ContentType
import io.ktor.http.HttpStatusCode
import io.ktor.server.response.respondBytes
import io.ktor.server.response.respondText
import io.ktor.server.routing.Route
import io.ktor.server.routing.get
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.longOrNull
import kotlinx.serialization.json.JsonObject
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
        // Told as it goes when the page asks (stepping): the sounds read, then the cards sent
        stepping("/api/anki/send") { req, step ->
            switches.check("anki.send")
            req.string("lesson_id").takeIf { it.isNotEmpty() }?.let { lessons.update(it, req, exported = true) }
            val deck = json.decodeFromJsonElement(Deck.serializer(), buildJsonObject {
                put("deck", req["deck"]!!)
                put("cards", req["cards"]!!)
            })
            readyAnki()
            fun on(option: String) = req[option]?.jsonPrimitive?.content == "true"
            val dictation = on("dictation") || on("dictation_only")
            val lessonId = req.string("lesson_id")
            soundsAhead.settle(lessonId) // the sounds being read ahead: read here instead
            val voice = req.string("voice").takeUnless { switches.off("speech.speak") }.orEmpty() // off: no sounds
            val (sounds, failures) = speech.sounds(deck, voice, dictation, req.string("rate"), lessonId) { done, total ->
                step(buildJsonObject { put("step", "sounds"); put("done", done); put("total", total) })
            }
            step(buildJsonObject { put("step", "cards") })
            val folder = lessons.images(lessonId)
            val pictures = deck.cards.mapNotNull { c -> folder?.resolve(c.picture)?.takeIf { c.picture.isNotEmpty() && it.isFile }?.let { c.picture to it } }.toMap()
            // The diagrams: the photos their labels are on
            val photos = deck.cards.mapNotNull { it.mask?.page }.distinct().mapNotNull { n -> lessons.photo(lessonId, n)?.let { n to it } }.toMap()
            // The diagram frames as the page has them (the user may have moved one), else the lesson's
            val frames = (req["frames"]?.takeIf { it is JsonArray } ?: lessons.get(lessonId)?.get("frames"))
                ?.jsonArray?.associate { it.jsonObject["page"]!!.jsonPrimitive.content.toInt() to it.jsonObject["box"]!!.jsonArray.map { v -> v.jsonPrimitive.content.toDouble() } }
                .orEmpty()
            // The lesson's notes from its last send, by card: a corrected front updates its own
            val sentBefore = (lessons.get(lessonId)?.get("anki_notes") as? JsonObject)
                ?.mapNotNull { (card, note) -> note.jsonPrimitive.longOrNull?.let { card to it } }?.toMap().orEmpty()
            // The tests the lesson is in: their tags on its cards' notes (Exams.kt)
            val extraTags = if (lessonId.isEmpty()) emptyMap() else exams.cardTags(lessonId, deck.cards.map { it.id })
            val media = Media(sounds, pictures, photos, lessonId, frames, sentBefore, extraTags)
            val options = Options(
                reverse = on("reverse"), typing = on("typing"), dictation = dictation, dictationOnly = on("dictation_only"),
                move = !switches.off("anki.move"),
            )
            val sent = try {
                withContext(Dispatchers.IO) { anki.send(deck, media, options) }
            } catch (e: Exception) { // e.g. AnkiDroid never opened: no collection yet
                throw BadRequest("anki.android_failed", buildJsonObject { put("detail", e.message ?: e.javaClass.simpleName) })
            }
            if (lessonId.isNotEmpty()) lessons.setAnkiNotes(lessonId, sent.notes)
            speech.prune(lessonId, sounds.values.toSet()) // the sounds no card says any more (AnkiDroid has its own copy)
            // Its notes no card updated (cards deleted, or remade): the page offers to delete them
            val leftovers = if (lessonId.isEmpty() || switches.off("anki.delete")) emptyList() else withContext(Dispatchers.IO) { anki.leftovers(lessonId, sent.notes.values.toSet()) }
            buildJsonObject {
                put("leftovers", JsonArray(leftovers.map { buildJsonObject { put("id", it.id); put("text", it.text); put("deck", it.deck) } }))
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
        // AnkiDroid's own icon, as installed (the page's "Open AnkiDroid"); none: 404, the page shows 🎓
        get("/api/anki/icon") {
            if (!allowed()) return@get
            val png = withContext(Dispatchers.IO) { runCatching { anki.icon() }.getOrNull() }
            if (png == null) call.respondText("", status = HttpStatusCode.NotFound)
            else call.respondBytes(png, ContentType.Image.PNG)
        }
        // AnkiDroid opened on its own screen (the page's "Open AnkiDroid"); missing: said, with Install
        api("POST", "/api/anki/open") {
            if (!anki.installed()) throw BadRequest("anki.android_missing")
            val opened = withContext(Dispatchers.IO) { runCatching { anki.open() }.getOrDefault(false) }
            if (!opened) throw BadRequest("anki.android_failed", buildJsonObject { put("detail", "open") })
            buildJsonObject { put("opened", true) }
        }
        // A lesson's deck reviewed in AnkiDroid ("Review" after sending it)
        api("POST", "/api/anki/review") {
            val deck = body().string("deck")
            val opened = withContext(Dispatchers.IO) { runCatching { anki.review(deck) }.getOrDefault(false) }
            if (!opened) throw BadRequest("anki.android_no_deck", buildJsonObject { put("deck", deck) })
            buildJsonObject { put("opened", true) }
        }
        // A test's cards in AnkiDroid's browser, where its menu makes their filtered deck
        api("POST", "/api/anki/browse") {
            val search = body().string("search")
            if (!anki.installed()) throw BadRequest("anki.android_missing")
            val opened = withContext(Dispatchers.IO) { runCatching { anki.browse(search) }.getOrDefault(false) }
            if (!opened) throw BadRequest("anki.android_browse_failed")
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
