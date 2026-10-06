package app.notosaurus

import android.content.Context
import android.content.pm.PackageManager
import androidx.core.content.ContextCompat
import com.ichi2.anki.api.AddContentApi

/** What was done with the cards: added, already in AnkiDroid, left out by the prototype. */
data class Sent(val added: Int, val duplicates: Int, val skipped: Int, val deck: String)

/** Where the cards go (AnkiDroid; a fake in the tests). */
interface AnkiTarget {
    fun installed(): Boolean
    fun permitted(): Boolean
    fun deckNames(): List<String>
    fun send(deck: Deck): Sent
}

/**
 * Cards into AnkiDroid, through its API (the "Instant-Add" content provider): our
 * note type, the lesson's deck and sub-decks, the notes. Needs AnkiDroid installed
 * and its READ_WRITE_DATABASE permission granted.
 *
 * Prototype: text cards only (no diagram masks, pictures or gaps: they need the
 * Notosaurus note types of the PC app).
 */
class Anki(private val context: Context) : AnkiTarget {
    private val api = AddContentApi(context)

    override fun installed(): Boolean = AddContentApi.getAnkiDroidPackageName(context) != null

    override fun permitted(): Boolean =
        ContextCompat.checkSelfPermission(context, PERMISSION) == PackageManager.PERMISSION_GRANTED

    /** The decks in AnkiDroid ("" when it can't tell). */
    override fun deckNames(): List<String> =
        if (installed() && permitted()) firstUse { api.deckList?.values?.toList().orEmpty() } else emptyList()

    override fun send(deck: Deck): Sent = firstUse { add(deck) }

    /** AnkiDroid installed but never opened: its first request fails ("storage is not
     * configured") and sets it up; the next ones work. So: once more. */
    private fun <T> firstUse(request: () -> T): T = try {
        request()
    } catch (e: IllegalStateException) {
        if ("storage is not configured" !in e.message.orEmpty()) throw e
        Thread.sleep(1000)
        request()
    }

    private fun add(deck: Deck): Sent {
        val model = model() ?: error("AnkiDroid refused the note type")
        val cards = deck.cards.filter { it.front.isNotBlank() && !it.unsupported() }
        // Already there: same front in our note type (the API's duplicate check: first field)
        val known = api.findDuplicateNotes(model, cards.map { it.front })
        var added = 0
        var duplicates = 0
        cards.withIndex().groupBy { (_, card) -> deckName(deck.deck, card.subdeck) }.forEach { (name, group) ->
            val fresh = group.filter { (i, _) -> known?.get(i).isNullOrEmpty() }
            duplicates += group.size - fresh.size
            if (fresh.isEmpty()) return@forEach
            val did = deckId(name) ?: error("AnkiDroid refused the deck $name")
            val fields = fresh.map { (_, c) -> arrayOf(c.front, c.back, c.info) }
            val tags = fresh.map { (_, c) -> (c.tags.map { it.replace(' ', '_') } + "notosaurus").toSet() }
            added += maxOf(0, api.addNotes(model, did, fields, tags))
        }
        return Sent(added, duplicates, deck.cards.size - cards.size, deck.deck)
    }

    private fun model(): Long? =
        api.modelList?.entries?.firstOrNull { it.value == MODEL }?.key
            ?: api.addNewCustomModel(
                MODEL,
                arrayOf("Front", "Back", "Info"),
                arrayOf("Card 1"),
                arrayOf("{{Front}}"),
                arrayOf("{{FrontSide}}<hr id=answer>{{Back}}{{#Info}}<div class=info>{{Info}}</div>{{/Info}}"),
                CSS,
                null,
                null,
            )

    private fun deckId(name: String): Long? =
        api.deckList?.entries?.firstOrNull { it.value == name }?.key ?: api.addNewDeck(name)

    private fun deckName(deck: String, subdeck: String) =
        if (subdeck.isBlank()) deck.ifBlank { "Notosaurus" } else "${deck.ifBlank { "Notosaurus" }}::$subdeck"

    private fun Card.unsupported() = mask != null || picturePrompt.isNotBlank() || figure.isNotBlank() ||
        Regex("""\{\{c\d+::""").containsMatchIn(front)

    companion object {
        const val PERMISSION = AddContentApi.READ_WRITE_PERMISSION
        const val MODEL = "Notosaurus (prototype)"
        private const val CSS = """.card { font-family: sans-serif; font-size: 24px; text-align: center; }
.info { margin-top: 12px; font-size: 18px; color: #666; }"""
    }
}
