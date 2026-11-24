package app.notosaurus

/**
 * A card's formulas as they go to AnkiDroid (its notes, a package), as the computer's
 * (app/note_types/formulas.py: the reasons, core/shared-cases.json the cases): none of MathJax's
 * `html` commands, which AnkiDroid's MathJax runs. Inside a formula, `\style{color: X}{…}` (one
 * colour) becomes `{\color{X}{…}}`, every other of these commands its name written as text
 * (`\backslash\text{href}`). A text with gaps holding one once AnkiDroid draws it (its markup
 * out): every backslash written as "＼".
 */
object Formulas {
    // MathJax's html extension's commands
    val HTML_COMMANDS = listOf("href", "style", "class", "cssId", "data")

    private val START = Regex("""\\[(\[]""")
    private val CLOSE = mapOf("\\(" to "\\)", "\\[" to "\\]")

    // FindTeX's end pattern: the closing delimiter, a backslash and its next character (not a
    // line break: JavaScript's "."), a brace
    private val END = CLOSE.values.associateWith { Regex(Regex.escape(it) + """|\\(?:[a-zA-Z]|[^\n\r\u2028\u2029])|[\{\}]""") }
    private val COMMAND = Regex("""\\([a-zA-Z]+)?""")
    private val COLOUR = Regex(
        """\s*color\s*:\s*(#(?:[0-9a-f]{3,4}|[0-9a-f]{6}|[0-9a-f]{8})|[a-z]{1,30}""" +
            """|rgba?\(\s*[0-9.]+%?(?:\s*,\s*[0-9.]+%?){2,3}\s*\))\s*;?\s*""",
        RegexOption.IGNORE_CASE,
    )
    private val NAMED = Regex("""\\(?:""" + HTML_COMMANDS.joinToString("|") + """)(?![a-zA-Z])""")
    // Braces escaped: Android's regex engine (ICU) refuses a lone "}" the JVM's takes
    private val CLOZE = Regex("""\{\{c([0-9]+)::|\}\}""")

    /** `text` as it goes into an AnkiDroid field (before it is escaped): its formulas without
     * MathJax's html commands. */
    fun ankiText(text: String): String {
        val rewritten = formulas(text)
        if ("{{c" in rewritten && drawn(rewritten).any { NAMED.containsMatchIn(it) }) return rewritten.replace('\\', '＼')
        return rewritten
    }

    private fun formulas(text: String): String {
        val out = StringBuilder()
        var done = 0
        var at = 0
        while (true) {
            val start = START.find(text, at) ?: break
            val close = CLOSE.getValue(start.value)
            val end = end(text, start.range.last + 1, close)
            if (end == null) { // never closed: not a formula, the next one looked for after it
                at = start.range.last + 1
                continue
            }
            out.append(text, done, start.range.last + 1).append(math(text.substring(start.range.last + 1, end)))
            done = end
            at = end + close.length
        }
        return out.append(text, done, text.length).toString()
    }

    private fun end(text: String, at: Int, close: String): Int? {
        var braces = 0
        for (token in END.getValue(close).findAll(text, at)) {
            when {
                token.value == close && braces == 0 -> return token.range.first
                token.value == "{" -> braces++
                token.value == "}" && braces > 0 -> braces--
            }
        }
        return null
    }

    /** A formula's TeX without the html commands (`\\href`: a line break, then "href"). */
    private fun math(tex: String): String {
        val out = StringBuilder()
        var done = 0
        var at = 0
        while (at <= tex.length) {
            val command = COMMAND.find(tex, at) ?: break
            val name = command.groups[1]?.value
            if (name == null || name !in HTML_COMMANDS) {
                at = command.range.last + 1 + if (name == null) 1 else 0 // `\{`, `\\`: a symbol
                continue
            }
            out.append(tex, done, command.range.first)
            val css = if (name == "style") argument(tex, command.range.last + 1) else null
            val body = css?.let { argument(tex, it.second) }
            val colour = css?.let { COLOUR.matchEntire(it.first) }
            if (body != null && colour != null) {
                out.append("{\\color{").append(colour.groupValues[1].lowercase()).append("}{").append(math(body.first)).append("}}")
                done = body.second
            } else {
                out.append("\\backslash\\text{").append(name).append("}")
                done = command.range.last + 1
            }
            at = done
        }
        return out.append(tex, done, tex.length).toString()
    }

    /** The braced argument from `at` (spaces skipped), as MathJax reads it, and where it ends. */
    private fun argument(math: String, from: Int): Pair<String, Int>? {
        var at = from
        while (at < math.length && math[at].isWhitespace()) at++
        if (at >= math.length || math[at] != '{') return null
        val start = at + 1
        var depth = 1
        at = start
        while (at < math.length) {
            when (math[at++]) {
                '\\' -> at++
                '{' -> depth++
                '}' -> if (--depth == 0) return math.substring(start, at - 1) to at
            }
        }
        return null
    }

    /** What AnkiDroid draws of a text with gaps, its markup out (Anki's cloze.rs): the answer,
     * each gap's question; without line breaks (the HTML taken out of a formula). */
    private fun drawn(text: String): List<String> {
        val nodes = gaps(text)
        return (listOf<Int?>(null) + ordinals(nodes)).distinct().map { shown(nodes, it).replace("\n", "") }
    }

    private class Gap(val number: Int, val nodes: MutableList<Any> = mutableListOf(), var hint: String? = null)

    /** `text` parsed as Anki parses gaps: "{{cN::" opens one, "}}" closes the last open, the
     * text after "::" in a gap its hint; a gap never closed is left out. */
    private fun gaps(text: String): List<Any> {
        val output = mutableListOf<Any>()
        val open = ArrayDeque<Gap>()
        var at = 0
        while (at < text.length) {
            var token = CLOZE.find(text, at)
            while (token != null && token.groups[1] != null && (token.groupValues[1].toIntOrNull() ?: Int.MAX_VALUE) > 65535) {
                token = CLOZE.find(text, token.range.first + 1) // not a gap's number (u16)
            }
            val end = token?.range?.first ?: text.length
            if (end > at) {
                var plain = text.substring(at, end)
                val gap = open.lastOrNull()
                if (gap != null) {
                    val colons = plain.indexOf("::")
                    if (colons >= 0) {
                        gap.hint = plain.substring(colons + 2)
                        plain = plain.substring(0, colons)
                    }
                    gap.nodes.add(plain)
                } else {
                    output.add(plain)
                }
            }
            if (token == null) break
            at = token.range.last + 1
            if (token.groups[1] != null) {
                open.addLast(Gap(token.groupValues[1].toInt()))
            } else if (open.isNotEmpty()) {
                val gap = open.removeLast()
                (open.lastOrNull()?.nodes ?: output).add(gap)
            } else {
                output.add("}}")
            }
        }
        return output
    }

    private fun ordinals(nodes: List<Any>): List<Int> = nodes.filterIsInstance<Gap>().flatMap { listOf(it.number) + ordinals(it.nodes) }

    private fun shown(nodes: List<Any>, asked: Int?): String = nodes.joinToString("") { node ->
        when {
            node !is Gap -> node as String
            node.number == asked -> "[${node.hint ?: "..."}]"
            else -> shown(node.nodes, asked)
        }
    }
}
