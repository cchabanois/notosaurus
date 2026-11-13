package app.notosaurus

import io.ktor.http.ContentDisposition
import io.ktor.http.ContentType
import io.ktor.http.HttpHeaders
import io.ktor.server.response.header
import io.ktor.server.response.respondBytes
import io.ktor.server.response.respondText
import io.ktor.server.routing.Route
import io.ktor.server.routing.RoutingContext
import io.ktor.server.routing.post
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put
import java.io.ByteArrayOutputStream
import java.io.File
import java.security.MessageDigest

/**
 * The cards as an .apkg package, made here as the computer makes one (app/anki.py): the open
 * lesson's ("📤 Partager": POST /api/export, as the page sends it), or the cards of lessons
 * ticked or of a test, for another family (POST /api/export/shared): a deck named as asked,
 * a subdeck per lesson without the child's levels, a test's chosen cards only, nothing of
 * this home (its tags, the lessons' ids). The page hands the file to Android's share sheet
 * (MainActivity). Turned off from the relay: "anki.share".
 */
internal fun Route.exportRoutes(server: LocalServer) {
    with(server) {
        packageRoute(server, "/api/export") {
            val req = body()
            val lessonId = req.string("lesson_id")
            if (lessonId.isNotEmpty() && lessons.get(lessonId) != null) lessons.update(lessonId, req) // saved, as the computer's
            val deck = json.decodeFromJsonElement(Deck.serializer(), buildJsonObject { put("deck", req["deck"]!!); put("cards", req["cards"]!!) })
            val part = packaged(deck, req, lessonId, lessonId)
            Packaged(listOf(part), deck.deck)
        }
        packageRoute(server, "/api/export/shared") {
            val req = body()
            val examId = req.string("exam")
            val wanted: List<Pair<String, List<String>?>> = if (examId.isNotEmpty()) {
                val exam = exams.get(examId) ?: throw BadRequest("exams.not_found")
                exam.lessons.map { it.lesson to it.cards }
            } else {
                (req["lessons"] as? JsonArray).orEmpty().map { it.jsonPrimitive.content }.distinct().map { it to null }
            }
            val found = wanted.mapNotNull { (id, cards) -> lessons.get(id)?.let { it to cards } }
            if (found.isEmpty()) throw BadRequest("export.no_cards")
            val every = children.list()
            val rests = found.associate { (lesson, _) -> lesson.string("id") to Children.splitDeck(lesson.string("deck"), every).second }
            val common = Exams.commonDeck(rests.values.toList())
            val default = if (examId.isNotEmpty()) exams.get(examId)!!.name else ""
            val top = req.string("name").ifBlank { default.ifBlank { common } }.replace("::", " - ").split(Regex("\\s+")).filter { it.isNotEmpty() }
                .joinToString(" ").ifBlank { "Notosaurus" }
            val parts = found.map { (lesson, cards) ->
                val id = lesson.string("id")
                val deck = json.decodeFromJsonElement(Deck.serializer(), buildJsonObject {
                    put("deck", sharedDeck(top, rests.getValue(id), common))
                    put("cards", lesson["cards"]!!)
                })
                val part = packaged(deck, lesson, id, sharedId(id))
                // A test's chosen cards only; this home's own tags left (a lesson's, a test's): another
                // Notosaurus would take them for its own lessons and tests
                part.copy(notes = part.notes.filter { cards == null || it.card in cards }.map {
                    Built(it.type, it.deck, it.values, it.tags.filterNot { t -> t.startsWith(Anki.TAG_PREFIX) || t.startsWith(Exams.TAG_PREFIX) }.toSet(), it.card)
                })
            }
            Packaged(parts, top)
        }
    }
}

/** A lesson's notes in a package, the files they show, how many sounds failed. */
internal data class Part(val notes: List<Built>, val files: Set<File>, val failures: Int)

internal data class Packaged(val parts: List<Part>, val name: String)

/** A route answering a package (application/apkg, its name, the sounds that failed): refused
 * while "anki.share" is turned off; errors as the other routes'. */
private fun Route.packageRoute(server: LocalServer, path: String, make: suspend RoutingContext.() -> Packaged) = with(server) {
    post(path) {
        if (!allowed()) return@post
        try {
            switches.check("anki.share")
            val packaged = make()
            val notes = packaged.parts.flatMap { it.notes }
            if (notes.isEmpty()) throw BadRequest("export.no_cards")
            val out = ByteArrayOutputStream()
            withContext(Dispatchers.IO) {
                val work = File.createTempFile("package", ".anki2", cacheDir.apply { mkdirs() })
                Apkg.write(notes, packaged.parts.flatMapTo(mutableSetOf()) { it.files }, out, work, apkgDb)
            }
            val name = ContentDisposition.Attachment.withParameter(ContentDisposition.Parameters.FileName, packageName(packaged.name))
            call.response.header(HttpHeaders.ContentDisposition, name.toString())
            call.response.header("X-Notosaurus-Audio-Failures", packaged.parts.sumOf { it.failures })
            call.respondBytes(out.toByteArray(), ContentType.parse("application/apkg"))
        } catch (e: Exception) {
            val (status, answer) = failure(e) ?: throw e
            call.respondText(answer.toString(), ContentType.Application.Json, status)
        }
    }
}

/** The lesson's notes as `deck` gives its cards, with the media they show: its sounds (made
 * for its voice), pictures, diagrams; `key`: the lesson's id the notes carry (a shared package:
 * one of its own). */
internal suspend fun LocalServer.packaged(deck: Deck, req: JsonObject, lessonId: String, key: String): Part {
    fun on(option: String) = req[option]?.jsonPrimitive?.content == "true"
    val dictation = on("dictation") || on("dictation_only")
    soundsAhead.settle(lessonId)
    val voice = req.string("voice").takeUnless { switches.off("speech.speak") }.orEmpty()
    val (sounds, failures) = speech.sounds(deck, voice, dictation, req.string("rate"), lessonId) { _, _ -> }
    val folder = lessons.images(lessonId)
    val pictures = deck.cards.mapNotNull { c -> folder?.resolve(c.picture)?.takeIf { c.picture.isNotEmpty() && it.isFile }?.let { c.picture to it } }.toMap()
    val photos = deck.cards.mapNotNull { it.mask?.page }.distinct().mapNotNull { n -> lessons.photo(lessonId, n)?.let { n to it } }.toMap()
    val frames = (req["frames"]?.takeIf { it is JsonArray } ?: lessons.get(lessonId)?.get("frames"))
        ?.jsonArray?.associate { it.jsonObject["page"]!!.jsonPrimitive.content.toInt() to it.jsonObject["box"]!!.jsonArray.map { v -> v.jsonPrimitive.content.toDouble() } }
        .orEmpty()
    val media = Media(sounds, pictures, photos, key, frames)
    val options = Options(reverse = on("reverse"), typing = on("typing"), dictation = dictation, dictationOnly = on("dictation_only"))
    val files = mutableSetOf<File>()
    fun shown(file: File, kind: String) = Apkg.shown(file.also { files += it }, kind)
    val notes = withContext(Dispatchers.IO) {
        Anki.buildNotes(noteTypes, deck, media, options, ::shown, { f, kind, _ -> shown(f, kind) }) { _, photo, box -> Anki.diagramImage(photo, box) }
    }
    return Part(notes, files, failures)
}

/** A lesson's deck in a shared package: under the package's own deck, the levels it has after
 * those every lesson shares; the same deck as every other: the package's deck (as the computer's). */
internal fun sharedDeck(top: String, rest: String, common: String): String {
    val levels = rest.split("::").map { it.trim() }.filter { it.isNotEmpty() }
    val shared = common.split("::").map { it.trim() }.filter { it.isNotEmpty() }
    val inside = levels.size >= shared.size && levels.take(shared.size).map { it.lowercase() } == shared.map { it.lowercase() }
    return (listOf(top) + if (inside) levels.drop(shared.size) else levels).joinToString("::")
}

/** A lesson's id in a shared package (its diagrams' and cards' keys): not its own, made from its
 * deck, which may name the child (as the computer's _shared_id). */
internal fun sharedId(lessonId: String): String =
    "shared-" + MessageDigest.getInstance("SHA-1").digest(lessonId.toByteArray()).joinToString("") { "%02x".format(it) }.take(12)

/** The package's file name: its deck's, without the characters a file name can't have. */
internal fun packageName(deck: String): String =
    (deck.replace(Regex("""[\\/:*?"<>|]+"""), " - ").trim(' ', '-').ifEmpty { "notosaurus" }) + ".apkg"
