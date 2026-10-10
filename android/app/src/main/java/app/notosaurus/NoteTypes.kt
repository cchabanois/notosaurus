package app.notosaurus

import kotlinx.serialization.Serializable

/**
 * The Anki note types, as the computer makes them: static/note-types.json, written from
 * app/anki.py by tools/note_types.py (in the app's assets with the page). AnkiDroid's
 * are made from these, with two changes of the app's own:
 * - the key first: AnkiDroid's duplicate check is on the first field;
 * - " (Android)" in the name instead of the computer's " (audio)": never one of the
 *   computer's (synced from Anki), whose fields are in another order.
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
) {
    /** Its name in AnkiDroid. */
    val androidName: String get() = name.removeSuffix(" (audio)") + " (Android)"

    /** Its fields in AnkiDroid: the key first. */
    val androidFields: List<String> get() = listOf(key) + fields.filter { it != key }

    /** The field the browser sorts by: the computer's first (the question, the text). */
    val sortField: Int get() = androidFields.indexOf(fields.first())

    /** A note's values (by field name) in AnkiDroid's order; missing ones empty. */
    fun values(fields: Map<String, String>): Array<String> = androidFields.map { fields[it].orEmpty() }.toTypedArray()
}

@Serializable
data class CardTemplate(val name: String, val front: String, val back: String)
