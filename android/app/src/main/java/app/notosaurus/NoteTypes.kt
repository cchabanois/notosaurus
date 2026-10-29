package app.notosaurus

import kotlinx.serialization.Serializable
import java.security.MessageDigest

/**
 * The Anki note types, the computer's: static/note-types.json, written from app/anki.py by
 * tools/note_types.py (in the app's assets with the page). The same in AnkiDroid: same
 * names, fields in the same order, same signature; a lesson's notes sent from one device
 * are found again from the other (Anki.kt: by the lesson's tag and the key field's name).
 */
@Serializable
data class NoteTypes(@kotlinx.serialization.SerialName("note_types") val all: Map<String, NoteType>) {
    /** A note type by its family and options ("text+reverse+typing", "picture+back"). */
    operator fun get(variant: String): NoteType = all[variant] ?: error("No note type $variant")

    companion object {
        fun parse(text: String): NoteTypes = json.decodeFromString(serializer(), text)
    }
}

@Serializable
data class NoteType(
    val name: String,
    val family: String,
    val fields: List<String>,
    val key: String,
    val cloze: Boolean,
    val cards: List<CardTemplate>,
    val css: String,
    @kotlinx.serialization.SerialName("signature") val computerSignature: String = "", // the computer's (a test compares)
) {
    /** Its name in AnkiDroid as the app's test versions made it (the key first): their notes
     * found and updated in place still. */
    val legacyName: String get() = name.removeSuffix(" (audio)") + " (Android)"

    /** What it is made of (name, fields, card templates, style), in 12 characters, as the
     * computer's (note_types.common.NoteType.signature): written in its style (signedCss). */
    val signature: String
        get() {
            val templates = cards.map { "${it.name}\u001e${it.front}\u001e${it.back}" }
            val parts = listOf(name, if (cloze) "True" else "False") + fields + templates + css
            val digest = MessageDigest.getInstance("SHA-256").digest(parts.joinToString("\u001f").toByteArray())
            return digest.joinToString("") { "%02x".format(it) }.take(12)
        }

    /** Its style, signed (as the computer's full_css): a note type in AnkiDroid without
     * today's signature was made by an older app, and is brought up to date at the next send. */
    val signedCss: String get() = "$css\n/* Notosaurus note type, version $signature: updated by Notosaurus */\n"

    /** A note's values (by field name) in the order of `names` (its note type's fields in
     * AnkiDroid); a field not given keeps its value `there` (the Source the computer wrote). */
    fun values(names: List<String>, fields: Map<String, String>, there: Array<String>? = null): Array<String> =
        Array(names.size) { i -> fields[names[i]] ?: there?.getOrNull(i).orEmpty() }
}

@Serializable
data class CardTemplate(val name: String, val front: String, val back: String)
