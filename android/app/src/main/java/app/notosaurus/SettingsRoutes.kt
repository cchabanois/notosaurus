package app.notosaurus

import app.notosaurus.LocalServer.Companion.WELCOME_VERSION
import app.notosaurus.LocalServer.Companion.WELCOME
import app.notosaurus.LocalServer.Companion.MAX_PHOTOS
import app.notosaurus.LocalServer.Companion.FUN_FACTS
import app.notosaurus.LocalServer.Companion.HELPS
import app.notosaurus.LocalServer.Companion.PICTURES
import app.notosaurus.LocalServer.Companion.COMPUTER
import app.notosaurus.LocalServer.Companion.COMPUTER_MODE
import app.notosaurus.LocalServer.Companion.COMPUTER_NAME
import app.notosaurus.LocalServer.Companion.INSTRUCTIONS
import app.notosaurus.LocalServer.Companion.KEY
import app.notosaurus.LocalServer.Companion.MODE
import app.notosaurus.LocalServer.Companion.PHONE_MODE
import app.notosaurus.LocalServer.Companion.RELAY
import app.notosaurus.LocalServer.Companion.TTS_RATE
import io.ktor.server.request.receiveText
import io.ktor.server.routing.Route
import kotlinx.serialization.builtins.ListSerializer
import kotlinx.coroutines.withTimeout
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import java.net.URI
import java.time.OffsetDateTime

private const val SWITCHES_WAIT_MS = 5_000L // the page shows meanwhile; the relay may be starting

/** The page's configuration, the settings (assets/page/admin.html) and "With my computer". */
internal fun Route.settingsRoutes(server: LocalServer) {
    with(server) {
        api("GET", "/api/config") {
            buildJsonObject {
                put("version", version)
                put("diagram_warning", false)
                put("max_photos", MAX_PHOTOS)
                put("profiles", false) // AnkiDroid doesn't say its profile: no Anki profile badge
                put("configured", true)
                put("donations", false) // paid for by the subscription: no "Support Notosaurus" (Ko-fi)
                put("apkg", false) // the cards go to AnkiDroid: no .apkg to download
                put("review_in_anki", true) // a lesson sent: reviewed in AnkiDroid from here
                put("report", true) // the AI's content reported to Notosaurus (the relay): ⚑ on the cards
                put("dictation", dictation != null) // the 🎤 of the instructions and the correction
                put("drawing_credits", switches.drawingCredits()?.let(::JsonPrimitive) ?: JsonNull) // told before drawing
                // The welcome (a parent's tool, Gemini, the privacy policy): until this version is accepted
                put("welcome", WELCOME_VERSION)
                put("welcome_accepted", (prefs[WELCOME]?.toIntOrNull() ?: 0) >= WELCOME_VERSION)
            }
        }
        // What the relay tells the app for now (Switches): read again, the last known when it can't be
        api("GET", "/api/switches") {
            runCatching { withTimeout(SWITCHES_WAIT_MS) { relay().account() } }.getOrNull()?.let(switches::keep)
            buildJsonObject {
                put("notice", switches.notice(lang()) ?: JsonNull)
                put("disabled", JsonArray(switches.disabled().map(::JsonPrimitive)))
                put("update", switches.updateAvailable())
                put("store", "https://play.google.com/store/apps/details?id=${BuildConfig.APPLICATION_ID}")
                // The free trial just started (the first lesson): its credits and end, told once
                put("trial", licensing.takeTrialStarted() ?: JsonNull)
            }
        }
        // The children's cards (Children): listed, saved by the page's "For: …" sheet
        api("GET", "/api/children") { json.encodeToJsonElement(ListSerializer(Child.serializer()), children.list()) }
        api("PUT", "/api/children") {
            val asked = json.decodeFromJsonElement(ListSerializer(Child.serializer()), json.parseToJsonElement(call.receiveText()))
            json.encodeToJsonElement(ListSerializer(Child.serializer()), children.save(asked))
        }
        api("POST", "/api/welcome") {
            prefs[WELCOME] = WELCOME_VERSION.toString()
            buildJsonObject { put("accepted", WELCOME_VERSION) }
        }

        // --- The settings (assets/page/admin.html)
        api("GET", "/api/admin") { buildJsonObject { put("allowed", true) } }
        api("GET", "/api/admin/settings") { settings() }
        api("PUT", "/api/admin/settings") {
            val changes = body()
            changes.string(RELAY).trim().takeIf { it.isNotEmpty() }?.let { prefs[RELAY] = it.trimEnd('/') }
            (changes[KEY] as? JsonPrimitive)?.let { licensing.setKey(it.content) }
            (changes[INSTRUCTIONS] as? JsonPrimitive)?.let { prefs[INSTRUCTIONS] = it.content.take(4000) }
            for (option in listOf(FUN_FACTS, HELPS, PICTURES)) (changes[option] as? JsonPrimitive)?.booleanOrNull?.let { prefs[option] = it.toString() }
            (changes[TTS_RATE] as? JsonPrimitive)?.content?.takeIf { it in Speech.RATES }?.let { prefs[TTS_RATE] = it }
            (changes[Speech.VOICES] as? JsonObject)?.let { voices -> speech.choose(voices.mapValues { it.value.plain() }) }
            settings()
        }
        api("GET", "/api/admin/account") {
            var account = relay().account()
            // Past its end (a renewal or a payment fixed the relay hasn't heard of): Google
            // Play's purchases checked again, the account then as it is
            if (licensing.store != null && account.endsAt?.let { runCatching { OffsetDateTime.parse(it) }.getOrNull() }?.isBefore(OffsetDateTime.now()) == true &&
                licensing.recheck()
            ) {
                account = relay().account()
            }
            json.encodeToJsonElement(Account.serializer(), account)
        }
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
        put("real", relays.real())
        relays.test().takeIf { it.isNotEmpty() }?.let { put("test", it) }
    })
    put(KEY, masked(licence())) // shown, not given back whole
    put("has_key", licence().isNotEmpty())
    put(INSTRUCTIONS, prefs[INSTRUCTIONS].orEmpty())
    put(FUN_FACTS, prefs[FUN_FACTS] != "false")
    put(HELPS, prefs[HELPS] != "false")
    put(PICTURES, prefs[PICTURES] != "false")
    put(TTS_RATE, prefs[TTS_RATE] ?: "-10%")
    put(Speech.VOICES, JsonObject(speech.chosen().mapValues { JsonPrimitive(it.value) }))
    put("version", version)
    put(MODE, prefs[MODE] ?: PHONE_MODE)
    prefs[COMPUTER]?.let {
        put(COMPUTER, it)
        put("computer_address", Computer.origin(URI(it))) // without its token
        put("computer_name", prefs[COMPUTER_NAME].orEmpty())
    }
}

private fun masked(key: String) = if (key.length <= 8) "•".repeat(key.length) else "${key.take(4)}…${key.takeLast(4)}"
