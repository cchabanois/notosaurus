package app.notosaurus

import app.notosaurus.LocalServer.Companion.CARD_HELPS
import app.notosaurus.LocalServer.Companion.COMPUTER
import app.notosaurus.LocalServer.Companion.COMPUTER_MODE
import app.notosaurus.LocalServer.Companion.COMPUTER_NAME
import app.notosaurus.LocalServer.Companion.INSTRUCTIONS
import app.notosaurus.LocalServer.Companion.KEY
import app.notosaurus.LocalServer.Companion.MODE
import app.notosaurus.LocalServer.Companion.PHONE_MODE
import app.notosaurus.LocalServer.Companion.PICTURE_FIND
import app.notosaurus.LocalServer.Companion.REAL_RELAY
import app.notosaurus.LocalServer.Companion.RELAY
import app.notosaurus.LocalServer.Companion.TEST_RELAY
import app.notosaurus.LocalServer.Companion.TTS_RATE
import app.notosaurus.LocalServer.Companion.keyOf
import io.ktor.server.routing.Route
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import java.net.URI

/** The page's configuration, the settings (assets/page/admin.html) and "With my computer". */
internal fun Route.settingsRoutes(server: LocalServer) {
    with(server) {
        api("GET", "/api/config") {
            buildJsonObject {
                put("version", version)
                put("diagram_warning", false)
                put("max_photos", 10)
                put("profiles", false) // AnkiDroid doesn't say its profile: no Anki profile badge
                put("card_helps", prefs[CARD_HELPS] == "true")
                put("configured", true)
                put("donations", false) // paid for by the subscription: no "Support Notosaurus" (Ko-fi)
                put("apkg", false) // the cards go to AnkiDroid: no .apkg to download
                put("review_in_anki", true) // a lesson sent: reviewed in AnkiDroid from here
                put("dictation", dictation != null) // the 🎤 of the instructions and the correction
            }
        }

        // --- The settings (assets/page/admin.html)
        api("GET", "/api/admin") { buildJsonObject { put("allowed", true) } }
        api("GET", "/api/admin/settings") { settings() }
        api("PUT", "/api/admin/settings") {
            val changes = body()
            changes.string(RELAY).trim().takeIf { it.isNotEmpty() }?.let { prefs[RELAY] = it.trimEnd('/') }
            (changes[KEY] as? JsonPrimitive)?.let { prefs[keyOf(relayUrl())] = it.content.trim() }
            (changes[INSTRUCTIONS] as? JsonPrimitive)?.let { prefs[INSTRUCTIONS] = it.content.take(4000) }
            (changes[CARD_HELPS] as? JsonPrimitive)?.let { prefs[CARD_HELPS] = it.content }
            (changes[PICTURE_FIND] as? JsonPrimitive)?.let { prefs[PICTURE_FIND] = it.content }
            (changes[TTS_RATE] as? JsonPrimitive)?.content?.takeIf { it in Speech.RATES }?.let { prefs[TTS_RATE] = it }
            settings()
        }
        api("GET", "/api/admin/account") { json.encodeToJsonElement(Account.serializer(), relay().account()) }
        api("GET", "/api/admin/anki") {
            buildJsonObject {
                put("installed", anki.installed())
                put("permitted", anki.installed() && anki.permitted())
            }
        }
        api("POST", "/api/admin/anki/permission") { buildJsonObject { put("permitted", requestAnkiPermission()) } }
        api("GET", "/api/admin/data") {
            buildJsonObject {
                put("lessons", lessons.list().size)
                put("bytes", lessons.bytes() + speech.bytes()) // with their sound
            }
        }
        api("DELETE", "/api/admin/lessons") {
            speech.deleteAll() // their sound too (AnkiDroid keeps its own copy)
            buildJsonObject { put("deleted", lessons.deleteAll()) }
        }

        // --- With my computer (the Anki add-on's Notosaurus)
        api("POST", "/api/admin/computer/scan") {
            val read = try {
                scan()
            } catch (e: Exception) {
                throw BadRequest("computer.scan_unavailable")
            } ?: return@api buildJsonObject { put("cancelled", true) }
            computer.connect(read)
        }
        api("PUT", "/api/admin/computer") { computer.connect(body().string("address")) }
        api("POST", "/api/admin/mode") {
            val mode = body().string("mode")
            if (mode == COMPUTER_MODE && prefs[COMPUTER].isNullOrEmpty()) throw BadRequest("computer.not_found")
            prefs[MODE] = if (mode == COMPUTER_MODE) COMPUTER_MODE else PHONE_MODE
            modeChanged()
            buildJsonObject { put("url", if (mode == COMPUTER_MODE) prefs[COMPUTER]!! else "/") }
        }
    }
}

private fun LocalServer.settings() = buildJsonObject {
    put(RELAY, relayUrl())
    // The relays to choose from in one tap: the test one in a debug build only
    put("relays", buildJsonObject {
        put("real", REAL_RELAY)
        if (TEST_RELAY.isNotEmpty()) put("test", TEST_RELAY)
    })
    put(KEY, masked(licence())) // shown, not given back whole
    put("has_key", licence().isNotEmpty())
    put(INSTRUCTIONS, prefs[INSTRUCTIONS].orEmpty())
    put(CARD_HELPS, prefs[CARD_HELPS] == "true")
    put(PICTURE_FIND, prefs[PICTURE_FIND] != "false") // on unless turned off
    put(TTS_RATE, prefs[TTS_RATE] ?: "-10%")
    put("version", version)
    put(MODE, prefs[MODE] ?: PHONE_MODE)
    prefs[COMPUTER]?.let {
        put(COMPUTER, it)
        put("computer_address", Computer.origin(URI(it))) // without its token
        put("computer_name", prefs[COMPUTER_NAME].orEmpty())
    }
}

private fun masked(key: String) = if (key.length <= 8) "•".repeat(key.length) else "${key.take(4)}…${key.takeLast(4)}"
