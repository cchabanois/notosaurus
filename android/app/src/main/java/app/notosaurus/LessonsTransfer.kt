package app.notosaurus

import kotlinx.serialization.builtins.ListSerializer
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.intOrNull
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put
import java.io.File
import java.io.OutputStream
import java.time.LocalDateTime
import java.util.UUID
import java.util.zip.ZipEntry
import java.util.zip.ZipFile
import java.util.zip.ZipOutputStream

/**
 * The lessons exported, to keep them or to move them to another device, and imported back:
 * a zip, the same from the computer (app/transfer.py: its docstring says the format) and from
 * the phone. Here the children and the tests are in the preferences and the prompts a list:
 * written and read in the computer's shapes.
 *
 * An import adds the lessons it doesn't have, replaces those it has when the export's is
 * newer, keeps the others; a lesson keeps its id (its notes' tag in AnkiDroid: found again,
 * not added twice). From another installation, its notes' ids (anki_notes) are another
 * collection's: cleared. Its voice one the relay doesn't have (the computer's): each card
 * keeps it as its own (Card.voice: its sound kept) and the lesson gets the relay's voice for
 * that language.
 */
class LessonsTransfer(
    private val root: File, // the lessons' folder (Lessons)
    private val lessons: Lessons,
    private val prefs: Preferences,
    private val children: Children,
    private val exams: Exams,
    private val prompts: Prompts,
    private val speech: Speech,
    private val version: String,
) {
    /** This installation's id, made once: an export says where it comes from. */
    fun installId(): String = prefs[INSTALL]?.takeIf { it.isNotEmpty() } ?: UUID.randomUUID().toString().replace("-", "").also { prefs[INSTALL] = it }

    /** Every lesson, the children, the tests and the user's prompts, as a zip into `out`;
     * how many lessons. */
    fun export(out: OutputStream): Int {
        val ids = lessons.list().map { it.string("id") }.sorted()
        ZipOutputStream(out.buffered()).use { z ->
            for (id in ids) {
                val folder = root.resolve(id)
                folder.walkTopDown().filter { it.isFile && LEFT_OUT.none { s -> it.name.endsWith(s) } }.sortedBy { it.path }.forEach { file ->
                    z.putNextEntry(ZipEntry("lessons/$id/" + file.relativeTo(folder).invariantSeparatorsPath))
                    file.inputStream().use { it.copyTo(z) }
                    z.closeEntry()
                }
            }
            fun entry(name: String, value: JsonElement) {
                z.putNextEntry(ZipEntry(name))
                z.write((value.toString() + "\n").toByteArray())
                z.closeEntry()
            }
            entry("children.json", buildJsonObject { put("children", json.encodeToJsonElement(ListSerializer(Child.serializer()), children.list())) })
            entry("exams.json", buildJsonObject { put("exams", json.encodeToJsonElement(ListSerializer(Exam.serializer()), exams.list())) })
            entry("prompts.json", buildJsonObject { put("user", JsonArray(prompts.mine())) })
            entry(
                MANIFEST,
                buildJsonObject {
                    put("format", FORMAT)
                    put("app", "notosaurus")
                    put("version", version)
                    put("device", "android")
                    put("install", installId())
                    put("exported_at", Lessons.now())
                    put("lessons", ids.size)
                },
            )
        }
        return ids.size
    }

    /** What an import did, as the computer's (transfer.Imported). */
    data class Imported(var added: Int = 0, var replaced: Int = 0, var kept: Int = 0, var children: Int = 0, var exams: Int = 0, var prompts: Int = 0) {
        fun json() = buildJsonObject {
            put("added", added); put("replaced", replaced); put("kept", kept)
            put("children", children); put("exams", exams); put("prompts", prompts)
        }
    }

    /** An export (the zip `file`) taken in (see the class's doc). */
    suspend fun import(file: File): Imported {
        val z = runCatching { ZipFile(file) }.getOrElse { throw BadRequest("transfer.not_an_export") }
        z.use {
            val manifest = read(z, MANIFEST)
            if (manifest.string("app") != "notosaurus" || manifest["format"]?.jsonPrimitive?.intOrNull == null) throw BadRequest("transfer.not_an_export")
            if (manifest["format"]!!.jsonPrimitive.intOrNull!! > FORMAT) throw BadRequest("transfer.too_new")
            if (z.entries().asSequence().sumOf { maxOf(0L, it.size) } > MAX_BYTES) throw BadRequest("transfer.too_large")
            val here = manifest.string("install") == installId()
            val result = Imported()
            for ((id, members) in members(z)) {
                when (lesson(z, id, members, here)) {
                    "added" -> result.added++
                    "replaced" -> result.replaced++
                    else -> result.kept++
                }
            }
            result.children = addChildren(read(z, "children.json")["children"] as? JsonArray)
            result.exams = addExams(read(z, "exams.json")["exams"] as? JsonArray)
            result.prompts = addPrompts(read(z, "prompts.json")["user"] as? JsonArray)
            return result
        }
    }

    private fun read(z: ZipFile, name: String): JsonObject =
        runCatching { json.parseToJsonElement(z.getInputStream(z.getEntry(name)!!).use { it.readBytes().decodeToString() }).jsonObject }
            .getOrDefault(JsonObject(emptyMap()))

    /** The export's lessons, by id: their entries, each with its path in the lesson's folder.
     * Only our own names: no "..", no absolute path, nothing outside a lesson's folder. */
    private fun members(z: ZipFile): Map<String, List<Pair<ZipEntry, List<String>>>> {
        val found = mutableMapOf<String, MutableList<Pair<ZipEntry, List<String>>>>()
        for (entry in z.entries()) {
            val parts = entry.name.split('/')
            if (entry.isDirectory || parts.size < 3 || parts[0] != "lessons" || '\\' in entry.name) continue
            val inside = parts.drop(2)
            if (!NAME.matches(parts[1]) || inside.any { it.isEmpty() || it == "." || it == ".." }) continue
            found.getOrPut(parts[1]) { mutableListOf() } += entry to inside
        }
        return found.filterValues { members -> members.any { it.second == listOf("lesson.json") } }
    }

    /** One lesson taken in: "added", "replaced" or "kept". */
    private suspend fun lesson(z: ZipFile, id: String, members: List<Pair<ZipEntry, List<String>>>, here: Boolean): String {
        root.mkdirs()
        val staging = root.resolve(".import-${UUID.randomUUID().toString().take(8)}") // not a lesson's name: never listed
        try {
            for ((entry, inside) in members) {
                val target = inside.fold(staging) { dir, part -> dir.resolve(part) }
                target.parentFile!!.mkdirs()
                z.getInputStream(entry).use { input -> target.outputStream().use { input.copyTo(it) } }
            }
            val incoming = json.parseToJsonElement(staging.resolve("lesson.json").readText()).jsonObject
            val existing = lessons.get(id)
            if (existing != null && !newer(incoming.string("updated_at"), existing.string("updated_at"))) return "kept"
            staging.resolve("lesson.json").writeText(arrived(incoming, id, here, staging).toString())
            val place = root.resolve(id)
            if (existing != null) {
                val old = root.resolve(".replaced-$id-${UUID.randomUUID().toString().take(6)}")
                place.renameTo(old)
                staging.renameTo(place)
                old.deleteRecursively()
                return "replaced"
            }
            staging.renameTo(place)
            return "added"
        } finally {
            staging.deleteRecursively() // gone already once in place
        }
    }

    private fun newer(incoming: String, existing: String): Boolean = runCatching {
        LocalDateTime.parse(incoming).isAfter(LocalDateTime.parse(existing))
    }.getOrElse { incoming > existing }

    /** The lesson as the phone keeps it: another collection's notes forgotten (the computer's
     * are by Anki profile, the phone's not); its voice the relay's (each card keeping the
     * computer's own: its sound). */
    private suspend fun arrived(lesson: JsonObject, id: String, here: Boolean, folder: File): JsonObject {
        // Its id and photos' count, as the phone keeps them in lesson.json (the computer's has neither)
        val photos = folder.listFiles { f -> PHOTO.matches(f.name) }?.size ?: 0
        val changes = mutableMapOf<String, JsonElement>("id" to JsonPrimitive(id), "photo_count" to JsonPrimitive(photos))
        if (!here) changes["anki_notes"] = JsonObject(emptyMap())
        val voice = lesson.string("voice")
        // The computer's voices are edge-tts's ("es-ES-ElviraNeural", as its tts.is_edge_voice): not the relay's
        if (Speech.reads(voice) && voice.endsWith("Neural")) {
            val mine = speech.voiceFor(voice.split('-').take(2).joinToString("-"))
            val cards = (lesson["cards"] as? JsonArray).orEmpty().map { c ->
                val card = c.jsonObject
                if (card.string("voice").isEmpty()) JsonObject(card + ("voice" to JsonPrimitive(voice))) else card
            }
            changes["cards"] = JsonArray(cards)
            if (mine.isNotEmpty()) changes["voice"] = JsonPrimitive(mine) // the relay unreachable: as it was, its cards' voice kept
        }
        return JsonObject(lesson + changes)
    }

    /** The export's children the phone doesn't have (by id) added. */
    private fun addChildren(incoming: JsonArray?): Int {
        val mine = children.list()
        val known = mine.map { it.id }.toMutableSet()
        val added = incoming.orEmpty().mapNotNull { runCatching { json.decodeFromJsonElement(Child.serializer(), it) }.getOrNull() }
            .filter { known.add(it.id) }
        if (added.isNotEmpty()) children.save(mine + added)
        return added.size
    }

    /** The export's tests the phone doesn't have (by id) added. */
    private fun addExams(incoming: JsonArray?): Int {
        val known = exams.list().map { it.id }.toSet()
        return incoming.orEmpty().mapNotNull { runCatching { json.decodeFromJsonElement(Exam.serializer(), it) }.getOrNull() }
            .filter { it.id !in known }
            .count { e -> runCatching { exams.save(e.id, e.name, e.date, e.lessons) }.isSuccess }
    }

    /** The export's prompts the phone doesn't have (the same name and text) added, with
     * numbers of their own. */
    private fun addPrompts(incoming: JsonArray?): Int {
        val known = prompts.mine().map { it.jsonObject.string("name") to it.jsonObject.string("text") }.toMutableSet()
        return incoming.orEmpty().mapNotNull { it as? JsonObject }
            .filter { it.string("name").isNotBlank() && known.add(it.string("name") to it.string("text")) }
            .onEach { prompts.save(null, it) }
            .size
    }

    companion object {
        const val FORMAT = 1
        const val MAX_FILE = 2L * 1024 * 1024 * 1024 // an export sent by the page: its photos, compressed
        const val MANIFEST = "manifest.json"
        private const val INSTALL = "install_id"
        private const val MAX_BYTES = 4L * 1024 * 1024 * 1024 // an export, unpacked: a few hundred lessons' photos
        private val LEFT_OUT = listOf(".tmp", ".part") // a file being written
        private val NAME = Regex("^[a-z0-9][a-z0-9-]*$") // Lessons' folder names: no "../"
        private val PHOTO = Regex("^page-\\d+\\.jpg$")
    }
}
