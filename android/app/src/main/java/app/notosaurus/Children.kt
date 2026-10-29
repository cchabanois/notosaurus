package app.notosaurus

import kotlinx.serialization.Serializable
import kotlinx.serialization.builtins.ListSerializer
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import java.text.Normalizer

/** A child's card (as the computer's app/children.py): its first name (the parent's: never
 * sent to the AI), school class, the decks its lessons go in, standing instructions. */
@Serializable
data class Child(
    val id: String,
    val name: String,
    val grade: String = "",
    val decks: String = "",
    val instructions: String = "",
)

/** The children the parent makes lessons for, kept on the phone (the page's "For: …" sheet
 * edits them, the page says which one a lesson is for). */
class Children(private val prefs: Preferences) {
    fun list(): List<Child> =
        runCatching { json.decodeFromString(ListSerializer(Child.serializer()), prefs[KEY].orEmpty()) }.getOrDefault(emptyList())

    /** The whole list, as the sheet has it; refused when it isn't one (BadRequest). */
    fun save(children: List<Child>): List<Child> {
        if (children.size > MAX) throw BadRequest("children.too_many", buildJsonObject { put("max", MAX) })
        if (children.map { it.id }.toSet().size != children.size) throw BadRequest("children.same_id")
        if (children.any { !ID.matches(it.id) || it.name.isBlank() || it.name.length > 40 || it.grade.length > 40 || it.decks.length > 200 || it.instructions.length > 4000 }) {
            throw BadRequest("children.invalid")
        }
        prefs[KEY] = json.encodeToString(ListSerializer(Child.serializer()), children)
        return children
    }

    fun get(id: String?): Child? = id?.takeIf { it.isNotEmpty() }?.let { wanted -> list().firstOrNull { it.id == wanted } }

    companion object {
        private const val KEY = "children"
        private const val MAX = 20
        private val ID = Regex("^[a-z0-9-]{1,40}$")
        // A class in the decks' path ("Jules::{classe}"), in any of the page's languages
        private val CLASS_TOKEN = Regex("""\{(classe|class|klasse|curso|ano)\}""", RegexOption.IGNORE_CASE)
        private val ORDINAL = Regex("""^(\d+)\s*(e|eme|er|ere|re|de|nd|nde|st|rd|th|o|a|º|ª)$""")

        /** What the AI is told of the child: its class and the parent's instructions; never its name. */
        fun forAi(child: Child?): String {
            if (child == null) return ""
            val parts = mutableListOf<String>()
            if (child.grade.isNotBlank()) parts += "The pupil's school class: ${child.grade.trim()} (word the cards and helps for that level)."
            if (child.instructions.isNotBlank()) parts += child.instructions.trim()
            return parts.joinToString("\n")
        }

        /** The lesson's deck in the child's decks ("Jules::{classe}"): the class put in, the
         * levels the deck has already not twice. */
        fun deckFor(child: Child?, deck: String): String {
            if (child == null || child.decks.isBlank()) return deck
            val levels = CLASS_TOKEN.replace(child.decks, child.grade.trim()).split("::").map { it.trim() }.filter { it.isNotEmpty() }
            val seen = levels.map(::same).toSet()
            val rest = deck.split("::").map { it.trim() }.filter { it.isNotEmpty() && same(it) !in seen }
            return (levels + rest).joinToString("::")
        }

        /** The decks the AI may reuse for a lesson of `child`: its own (its levels left out) and
         * those of no child; never another child's (as the computer's children.decks_for_ai). */
        fun decksForAi(decks: List<String>, children: List<Child>, child: Child?): List<String> {
            val mine = child?.let(::levels).orEmpty()
            return decks.mapNotNull { deck ->
                val (private, rest) = splitDeck(deck, children)
                rest.takeIf { it.isNotEmpty() && private.split("::").filter { l -> l.isNotEmpty() }.all { same(it) in mine } }
            }.distinct().sorted()
        }

        /** A child's own levels: its first name, its decks' levels (its class put in). */
        private fun levels(child: Child): Set<String> =
            (listOf(same(child.name)) + CLASS_TOKEN.replace(child.decks, child.grade.trim()).split("::").filter { it.isNotBlank() }.map(::same)).toSet()

        /** A deck's name as the children's levels it starts with ("Jules::5e") and the rest:
         * the rest is what the AI sees (no child's name), the levels are put back. */
        fun splitDeck(deck: String, children: List<Child>): Pair<String, String> {
            val private = children.flatMap(::levels).toSet()
            val levels = deck.split("::").map { it.trim() }.filter { it.isNotEmpty() }
            val n = levels.takeWhile { same(it) in private }.size
            return levels.take(n).joinToString("::") to levels.drop(n).joinToString("::")
        }

        /** A deck level as compared: no case, no accents, an ordinal's ending dropped ("5ème", "5e"). */
        private fun same(level: String): String {
            val plain = Normalizer.normalize(level, Normalizer.Form.NFKD).replace(Regex("\\p{M}"), "").lowercase().trim()
            return ORDINAL.replace(plain, "$1")
        }
    }
}
