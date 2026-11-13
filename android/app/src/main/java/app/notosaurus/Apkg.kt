package app.notosaurus

import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.long
import kotlinx.serialization.json.put
import java.io.Closeable
import java.io.File
import java.io.OutputStream
import java.security.MessageDigest
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream

/** A package's database (SQLite): Android's in the app (AndroidApkgDb), another in the JVM tests. */
interface ApkgDb : Closeable {
    fun exec(sql: String, vararg args: Any?)
}

/**
 * An .apkg package of notes, as the computer writes one (genanki: app/anki.py build_apkg): the
 * legacy collection Anki and AnkiDroid import (collection.anki2: its note types, decks, notes and
 * cards, no review history), its media numbered beside it, zipped. The note types are the
 * computer's, ids and all (NoteType.model, from note-types.json): one who has them gets no second
 * copy; a note's GUID is the computer's (its deck and key): imported again, it is updated.
 */
object Apkg {
    /** The notes (their files shown as `files` named them) written to `out`; `work`: a scratch
     * file for the database. New cards: due as added, never reviewed. */
    internal fun write(notes: List<Built>, files: Collection<File>, out: OutputStream, work: File, db: (File) -> ApkgDb, now: Long = System.currentTimeMillis()) {
        work.delete()
        val seconds = now / 1000
        var next = now // the notes' and cards' ids: as genanki's, from the time, one each
        val decks = notes.map { it.deck }.distinct().associateWith { stableId("deck", it) }
        val types = notes.map { it.type }.distinctBy { it.name }
        db(work).use { sql ->
            SCHEMA.split(';').map { it.trim() }.filter { it.isNotEmpty() }.forEach { sql.exec(it) }
            val decksJson = buildJsonObject {
                put("1", deckJson(1, "Default"))
                decks.forEach { (name, id) -> put(id.toString(), deckJson(id, name)) }
            }
            val models = buildJsonObject {
                types.forEach { type ->
                    val model = type.model ?: error("No package model for ${type.name}")
                    val did = decks.getValue(notes.first { it.type.name == type.name }.deck)
                    put(model.getValue("id").jsonPrimitive.content, JsonObject(model + mapOf("mod" to JsonPrimitive(seconds), "did" to JsonPrimitive(did))))
                }
            }
            sql.exec(
                "INSERT INTO col VALUES(null,?,?,?,11,0,0,0,?,?,?,?,'{}')",
                1411124400, now, now, CONF, models.toString(), decksJson.toString(), DCONF,
            )
            for ((note, guid) in notes.zip(guids(notes))) {
                val model = note.type.model!!
                val values = note.type.values(note.type.fields, note.values)
                val id = next++
                val sort = values.getOrElse(model.getValue("sortf").jsonPrimitive.content.toInt()) { "" }
                sql.exec(
                    "INSERT INTO notes VALUES(?,?,?,?,-1,?,?,?,0,0,'')",
                    id, guid, model.getValue("id").jsonPrimitive.long, seconds,
                    " " + note.tags.joinToString(" ") + " ", values.joinToString("\u001f"), sort,
                )
                for (ord in cardOrds(note.type, values)) {
                    sql.exec(
                        "INSERT INTO cards VALUES(?,?,?,?,?,-1,0,0,0,0,0,0,0,0,0,0,0,'')",
                        next++, id, decks.getValue(note.deck), ord, seconds,
                    )
                }
            }
        }
        ZipOutputStream(out).use { zip ->
            zip.putNextEntry(ZipEntry("collection.anki2"))
            work.inputStream().use { it.copyTo(zip) }
            zip.closeEntry()
            val media = files.distinctBy { it.name }
            zip.putNextEntry(ZipEntry("media"))
            zip.write(buildJsonObject { media.forEachIndexed { i, f -> put(i.toString(), f.name) } }.toString().toByteArray())
            zip.closeEntry()
            media.forEachIndexed { i, f ->
                zip.putNextEntry(ZipEntry(i.toString()))
                f.inputStream().use { it.copyTo(zip) }
                zip.closeEntry()
            }
        }
        work.delete()
    }

    /** How a note's field shows a file in the package: by its name, as the computer's. */
    fun shown(file: File, kind: String): String = if (kind == "audio") "[sound:${file.name}]" else "<img src=\"${file.name}\">"

    /** The cards a note makes, by their template's number: a gap text one per gap number
     * ({{c2::…}}: the second), the others those whose fields the note type asks for ("req"). */
    internal fun cardOrds(type: NoteType, values: Array<String>): List<Int> {
        val model = type.model!!
        if (type.cloze) {
            val text = CLOZE_FIELD.find(type.cards.first().front)?.groupValues?.get(1)
            val value = values.getOrElse(type.fields.indexOf(text)) { "" }
            return CLOZE.findAll(value).map { it.groupValues[1].toInt() - 1 }.filter { it >= 0 }.distinct().sorted().toList().ifEmpty { listOf(0) }
        }
        return model.getValue("req").jsonArray.mapNotNull { req ->
            val (ord, how, fields) = req.jsonArray
            val filled = fields.jsonArray.map { values.getOrElse(it.jsonPrimitive.content.toInt()) { "" }.isNotEmpty() }
            val made = if (how.jsonPrimitive.content == "all") filled.all { it } else filled.any { it }
            ord.jsonPrimitive.content.toInt().takeIf { made }
        }
    }

    /** Each note's GUID, as the computer's (anki.guids): from its deck and key, the same key twice
     * in a deck numbered. */
    internal fun guids(notes: List<Built>): List<String> {
        val seen = mutableMapOf<Pair<String, String>, Int>()
        return notes.map { note ->
            val n = seen.merge(note.deck to note.key, 0) { a, _ -> a + 1 }!!
            guidFor(listOf(note.deck, note.key) + if (n > 0) listOf(n.toString()) else emptyList())
        }
    }

    /** genanki's guid_for: the first 8 bytes of the values' SHA-256, in Anki's base 91. */
    internal fun guidFor(values: List<String>): String {
        var n = java.math.BigInteger(1, MessageDigest.getInstance("SHA-256").digest(values.joinToString("__").toByteArray()).copyOf(8))
        val base = java.math.BigInteger.valueOf(BASE91.length.toLong())
        val out = StringBuilder()
        while (n.signum() > 0) {
            val (q, r) = n.divideAndRemainder(base)
            out.append(BASE91[r.toInt()])
            n = q
        }
        return out.reverse().toString()
    }

    /** A deck's id from its name, as the computer's (note_types.common.stable_id): 31 bits. */
    internal fun stableId(vararg parts: String): Long {
        val digest = MessageDigest.getInstance("SHA-256").digest(parts.joinToString("|").toByteArray())
        return ((digest[0].toLong() and 0xff shl 24) or (digest[1].toLong() and 0xff shl 16) or (digest[2].toLong() and 0xff shl 8) or (digest[3].toLong() and 0xff)) shr 1
    }

    private fun deckJson(id: Long, name: String) = buildJsonObject {
        put("collapsed", false); put("conf", 1); put("desc", ""); put("dyn", 0); put("extendNew", 0); put("extendRev", 50)
        put("id", id); put("mod", 1425278051); put("name", name); put("usn", -1)
        for (key in listOf("lrnToday", "newToday", "revToday", "timeToday")) put(key, kotlinx.serialization.json.JsonArray(listOf(JsonPrimitive(0), JsonPrimitive(0))))
    }

    // Every brace escaped: Android's regex engine (ICU) refuses a lone "}" the JVM's takes
    private val CLOZE_FIELD = Regex("""\{\{[^\}]*?cloze:(?:[^\}]?:)*(.+?)\}\}""")
    private val CLOZE = Regex("""\{\{c(\d+)::.+?\}\}""", RegexOption.DOT_MATCHES_ALL)
    private const val BASE91 = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!#$%&()*+,-./:;<=>?@[]^_`{|}~"

    // genanki's (apkg_schema.py, apkg_col.py): the collection as Anki 2.1's legacy package has it
    private val SCHEMA = """
        CREATE TABLE col (id integer primary key, crt integer not null, mod integer not null, scm integer not null,
            ver integer not null, dty integer not null, usn integer not null, ls integer not null, conf text not null,
            models text not null, decks text not null, dconf text not null, tags text not null);
        CREATE TABLE notes (id integer primary key, guid text not null, mid integer not null, mod integer not null,
            usn integer not null, tags text not null, flds text not null, sfld integer not null, csum integer not null,
            flags integer not null, data text not null);
        CREATE TABLE cards (id integer primary key, nid integer not null, did integer not null, ord integer not null,
            mod integer not null, usn integer not null, type integer not null, queue integer not null, due integer not null,
            ivl integer not null, factor integer not null, reps integer not null, lapses integer not null, left integer not null,
            odue integer not null, odid integer not null, flags integer not null, data text not null);
        CREATE TABLE revlog (id integer primary key, cid integer not null, usn integer not null, ease integer not null,
            ivl integer not null, lastIvl integer not null, factor integer not null, time integer not null, type integer not null);
        CREATE TABLE graves (usn integer not null, oid integer not null, type integer not null);
        CREATE INDEX ix_notes_usn on notes (usn);
        CREATE INDEX ix_cards_usn on cards (usn);
        CREATE INDEX ix_revlog_usn on revlog (usn);
        CREATE INDEX ix_cards_nid on cards (nid);
        CREATE INDEX ix_cards_sched on cards (did, queue, due);
        CREATE INDEX ix_revlog_cid on revlog (cid);
        CREATE INDEX ix_notes_csum on notes (csum)
    """.trimIndent()
    private const val CONF = """{"activeDecks":[1],"addToCur":true,"collapseTime":1200,"curDeck":1,"curModel":"1425279151691","dueCounts":true,"estTimes":true,"newBury":true,"newSpread":0,"nextPos":1,"sortBackwards":false,"sortType":"noteFld","timeLim":0}"""
    private const val DCONF = """{"1":{"autoplay":true,"id":1,"lapse":{"delays":[10],"leechAction":0,"leechFails":8,"minInt":1,"mult":0},"maxTaken":60,"mod":0,"name":"Default","new":{"bury":true,"delays":[1,10],"initialFactor":2500,"ints":[1,4,7],"order":1,"perDay":20,"separate":true},"replayq":true,"rev":{"bury":true,"ease4":1.3,"fuzz":0.05,"ivlFct":1,"maxIvl":36500,"minSpace":1,"perDay":100},"timer":0,"usn":0}}"""
}

/** Android's SQLite, for the app's packages. */
class AndroidApkgDb(file: File) : ApkgDb {
    private val db = android.database.sqlite.SQLiteDatabase.openOrCreateDatabase(file, null)

    override fun exec(sql: String, vararg args: Any?) = if (args.isEmpty()) db.execSQL(sql) else db.execSQL(sql, args)

    override fun close() = db.close()
}
