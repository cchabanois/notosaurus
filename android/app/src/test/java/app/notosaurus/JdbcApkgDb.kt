package app.notosaurus

import java.io.File
import java.sql.DriverManager

/** A package's database on the JVM (sqlite-jdbc): the tests' ApkgDb, Android's SQLite being the app's. */
class JdbcApkgDb(file: File) : ApkgDb {
    private val db = DriverManager.getConnection("jdbc:sqlite:${file.path}")

    override fun exec(sql: String, vararg args: Any?) {
        db.prepareStatement(sql).use { statement ->
            args.forEachIndexed { i, arg -> statement.setObject(i + 1, arg) }
            statement.execute()
        }
    }

    override fun close() = db.close()
}

/** A package written by Apkg, opened: its collection's tables read with SQL, its media. */
class OpenedApkg(bytes: ByteArray, dir: File) {
    val entries: Map<String, ByteArray> = buildMap {
        java.util.zip.ZipInputStream(bytes.inputStream()).use { zip ->
            generateSequence { zip.nextEntry }.forEach { put(it.name, zip.readBytes()) }
        }
    }
    private val collection = dir.resolve("collection.anki2").apply { writeBytes(entries.getValue("collection.anki2")) }

    fun <T> query(sql: String, row: (java.sql.ResultSet) -> T): List<T> =
        DriverManager.getConnection("jdbc:sqlite:${collection.path}").use { db ->
            db.createStatement().use { s -> s.executeQuery(sql).use { r -> buildList { while (r.next()) add(row(r)) } } }
        }

    val media: Map<String, String>
        get() = (json.parseToJsonElement(entries.getValue("media").decodeToString()) as kotlinx.serialization.json.JsonObject)
            .mapValues { (it.value as kotlinx.serialization.json.JsonPrimitive).content }

    val deckNames: Set<String>
        get() = (json.parseToJsonElement(query("SELECT decks FROM col") { it.getString(1) }.single()) as kotlinx.serialization.json.JsonObject)
            .values.map { (it as kotlinx.serialization.json.JsonObject).string("name") }.toSet()
}
