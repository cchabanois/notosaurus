"""An exported .apkg, opened: what the export and send tests assert on — the real
package unzipped, its SQLite collection read (notes, note types, decks), its media."""

import html
import io
import json
import sqlite3
import zipfile
from pathlib import Path


class Apkg:
    """A package built by POST /api/export.

    notes: (guid, mid, flds) rows, by note id; models: id → note type; decks: id →
    deck; media_map: file in the package → media name; media: those names, sorted;
    cards: how many Anki cards (one per cloze gap number, one per template…).
    """

    def __init__(self, content: bytes, dest: Path):
        self._content = content
        with zipfile.ZipFile(io.BytesIO(content)) as z:
            (dest / "collection.anki2").write_bytes(z.read("collection.anki2"))
            self.media_map = json.loads(z.read("media"))
        conn = sqlite3.connect(dest / "collection.anki2")
        self.notes = conn.execute("SELECT guid, mid, flds FROM notes ORDER BY id").fetchall()
        self.models = {int(i): m for i, m in json.loads(conn.execute("SELECT models FROM col").fetchone()[0]).items()}
        self.decks = json.loads(conn.execute("SELECT decks FROM col").fetchone()[0])
        self.cards = conn.execute("SELECT count(*) FROM cards").fetchone()[0]
        conn.close()

    @property
    def media(self) -> list[str]:
        return sorted(self.media_map.values())

    @property
    def guids(self) -> list[str]:
        return [guid for guid, _, _ in self.notes]

    def fields(self, note) -> list[str]:
        """A note's fields, HTML-unescaped, in its note type's order."""
        return [html.unescape(f) for f in note[2].split("\x1f")]

    def fields_by_name(self, note) -> dict[str, str]:
        """The same, keyed by the note type's field names."""
        names = [f["name"] for f in self.models[note[1]]["flds"]]
        return dict(zip(names, self.fields(note), strict=True))

    def media_bytes(self, name: str) -> bytes:
        """A media file's content, by its name."""
        (index,) = [i for i, n in self.media_map.items() if n == name]
        with zipfile.ZipFile(io.BytesIO(self._content)) as z:
            return z.read(index)


def export(client, body: dict, dest: Path) -> Apkg:
    """POST /api/export and open the package it returns."""
    res = client.post("/api/export", json=body)
    assert res.status_code == 200, res.text
    return Apkg(res.content, dest)
