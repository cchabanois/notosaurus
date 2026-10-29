"""The lessons exported, to keep them or to move them to another device, and imported
back: a zip, the same from the computer and from the phone (Android: LessonsTransfer.kt).

    manifest.json   {"format", "app", "version", "device", "install", "exported_at", "lessons"}
    lessons/<id>/   each lesson's folder as it is: lesson.json, its photos, images/, audio/
    children.json   the children, as the computer keeps them ({"children": [...]})
    exams.json      the tests to prepare ({"exams": [...]})
    prompts.json    the user's prompts ({"user": [...]})

Nothing else: no settings (API keys, passwords), no paired phone, no AI costs' journal.

An import adds the lessons it doesn't have, replaces those it has when the export's is
newer, keeps the others. A lesson keeps its id (its notes' tag in Anki: found again by it,
not added twice). From another installation, its notes' ids (anki_notes) are another
collection's: cleared, the next send finds them by their tag. Its voice one this computer
can't read with (the phone's): each card keeps it as its own (Card.voice: its sound kept
while it says the same) and the lesson gets this computer's voice for that language.
"""

import json
import shutil
import tempfile
import uuid
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath

from notosaurus_core import tts

from . import children, exams, lessons, prompts, settings, storage
from .errors import AppError
from .version import VERSION

FORMAT = 1
MANIFEST = "manifest.json"
MAX_BYTES = 4 * 1024**3  # an export, unpacked: a few hundred lessons' photos
LEFT_OUT = (".part", ".tmp", ".joined")  # a file being written


def install_id() -> str:
    """This installation's id (data/install.json), made once: an export says where it comes from."""
    path = storage.data_dir() / "install.json"
    with storage.lock:
        found = storage.read_json(path, {}) or {}
        if not found.get("id"):
            found = {"id": uuid.uuid4().hex}
            storage.write_json(path, found)
    return found["id"]


def export(path: Path) -> int:
    """Every lesson, the children, the tests and the user's prompts into the zip `path`;
    returns how many lessons."""
    root = storage.data_dir() / "lessons"
    ids = sorted(p.name for p in root.iterdir() if lessons.folder(p.name)) if root.is_dir() else []
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for id in ids:
            folder = root / id
            for file in sorted(f for f in folder.rglob("*") if f.is_file() and not f.name.endswith(LEFT_OUT)):
                # Photos and mp3s are compressed already: stored as they are, quicker
                compress = zipfile.ZIP_STORED if file.suffix in (".jpg", ".mp3", ".png", ".webp") else None
                z.write(file, f"lessons/{id}/{file.relative_to(folder).as_posix()}", compress_type=compress)
        z.writestr("children.json", _json({"children": [c.model_dump() for c in children.list_all()]}))
        z.writestr("exams.json", _json({"exams": [e.model_dump() for e in exams.list_all()]}))
        user, _ = prompts._read()
        z.writestr("prompts.json", _json({"user": [p.model_dump() for p in user]}))
        manifest = {
            "format": FORMAT,
            "app": "notosaurus",
            "version": VERSION,
            "device": "computer",
            "install": install_id(),
            "exported_at": storage.now(),
            "lessons": len(ids),
        }
        z.writestr(MANIFEST, _json(manifest))
    return len(ids)


@dataclass
class Imported:
    added: int = 0  # lessons this computer didn't have
    replaced: int = 0  # the export's newer
    kept: int = 0  # this computer's as recent, kept
    children: int = 0
    exams: int = 0
    prompts: int = 0

    def dict(self) -> dict:
        return asdict(self)


async def import_(path: Path) -> Imported:
    """An export (the zip `path`) taken in (see the module's docstring)."""
    try:
        z = zipfile.ZipFile(path)
    except zipfile.BadZipFile as e:
        raise AppError("transfer.not_an_export") from e
    with z:
        manifest = _manifest(z)
        if sum(i.file_size for i in z.infolist()) > MAX_BYTES:
            raise AppError("transfer.too_large")
        here = manifest.get("install") == install_id()
        result = Imported()
        for id, members in _lessons(z).items():
            done = await _lesson(z, id, members, here)
            setattr(result, done, getattr(result, done) + 1)
        result.children = _children(_read(z, "children.json").get("children", []))
        result.exams = _exams(_read(z, "exams.json").get("exams", []))
        result.prompts = _prompts(_read(z, "prompts.json").get("user", []))
    return result


def _json(data) -> str:
    return json.dumps(data, ensure_ascii=False, indent=1) + "\n"


def _manifest(z: zipfile.ZipFile) -> dict:
    found = _read(z, MANIFEST)
    if found.get("app") != "notosaurus" or not isinstance(found.get("format"), int):
        raise AppError("transfer.not_an_export")
    if found["format"] > FORMAT:
        raise AppError("transfer.too_new")  # a newer Notosaurus's: update this one
    return found


def _read(z: zipfile.ZipFile, name: str) -> dict:
    try:
        found = json.loads(z.read(name))
    except (KeyError, ValueError):
        return {}
    return found if isinstance(found, dict) else {}


def _lessons(z: zipfile.ZipFile) -> dict[str, list[tuple[zipfile.ZipInfo, PurePosixPath]]]:
    """The export's lessons, by id: their files, each with its path in the lesson's folder.
    Only our own names: no "..", no absolute path, nothing outside a lesson's folder."""
    found: dict[str, list[tuple[zipfile.ZipInfo, PurePosixPath]]] = {}
    for info in z.infolist():
        parts = PurePosixPath(info.filename).parts
        if info.is_dir() or len(parts) < 3 or parts[0] != "lessons" or "\\" in info.filename:
            continue
        id, inside = parts[1], parts[2:]
        if not lessons.ID_PATTERN.match(id) or any(p in ("", ".", "..") or p.startswith("/") for p in inside):
            continue
        found.setdefault(id, []).append((info, PurePosixPath(*inside)))
    return {
        id: members for id, members in found.items() if any(rel == PurePosixPath("lesson.json") for _, rel in members)
    }


async def _lesson(z: zipfile.ZipFile, id: str, members: list, here: bool) -> str:
    """One lesson taken in: "added", "replaced" or "kept"."""
    root = storage.data_dir() / "lessons"
    root.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".import-", dir=root))  # not a lesson's name: never listed
    try:
        for info, rel in members:
            target = staging.joinpath(*rel.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with z.open(info) as source, target.open("wb") as out:
                shutil.copyfileobj(source, out)
        incoming = lessons._read(staging)
        with storage.lock:
            existing = lessons.folder(id)
            if existing and not _newer(incoming.updated_at, lessons._read(existing).updated_at):
                return "kept"
        await _arrived(staging, incoming, here)
        with storage.lock:
            existing = lessons.folder(id)
            if existing:
                old = existing.with_name(f".replaced-{id}-{uuid.uuid4().hex[:6]}")
                existing.rename(old)
                staging.rename(root / id)
                shutil.rmtree(old, ignore_errors=True)
                return "replaced"
            staging.rename(root / id)
            return "added"
    finally:
        shutil.rmtree(staging, ignore_errors=True)  # gone already once in place


def _newer(incoming: str, existing: str) -> bool:
    try:
        return datetime.fromisoformat(incoming) > datetime.fromisoformat(existing)
    except ValueError:
        return incoming > existing


async def _arrived(folder: Path, lesson: lessons.Lesson, here: bool) -> None:
    """The lesson as this computer keeps it: another collection's notes forgotten, its
    voice one of this computer's (each card keeping the phone's own: its sound)."""
    changes: dict = {}
    if not here:
        changes["anki_notes"] = {}
    voice = lesson.voice
    if voice and not tts.is_edge_voice(voice) and not tts.is_anki_locale(voice):
        locale = "-".join(voice.split("-")[:2])
        mine = await tts.voice_for(locale, settings.current().voices) if locale else ""
        cards = [c.model_copy(update={"voice": c.voice or voice}) for c in lesson.cards]
        changes |= {"voice": mine, "cards": cards}
    if changes:
        lessons._write(folder, lesson.model_copy(update=changes))


def _children(incoming: list) -> int:
    """The export's children this computer doesn't have (by id) added."""
    mine = children.list_all()
    known = {c.id for c in mine}
    added = []
    for raw in incoming:
        try:
            child = children.Child(**{**raw, "anki_profile": raw.get("anki_profile", "")})
        except (TypeError, ValueError):
            continue
        if child.id not in known:
            added.append(child)
            known.add(child.id)
    if added:
        children.save_all([*mine, *added])
    return len(added)


def _exams(incoming: list) -> int:
    """The export's tests this computer doesn't have (by id) added."""
    mine = exams.list_all()
    known = {e.id for e in mine}
    added = []
    for raw in incoming:
        try:
            exam = exams.Exam(**raw)
        except (TypeError, ValueError):
            continue
        if exam.id not in known:
            added.append(exam)
            known.add(exam.id)
    if added:
        with storage.lock:
            exams._write([*mine, *added])
    return len(added)


def _prompts(incoming: list) -> int:
    """The export's prompts this computer doesn't have (the same name and text) added, with
    numbers of their own."""
    with storage.lock:
        mine, used = prompts._read()
        known = {(p.name, p.text) for p in mine}
        next_id = max((p.id for p in mine if isinstance(p.id, int)), default=0) + 1
        added = []
        for raw in incoming:
            try:
                prompt = prompts.Prompt(**{**raw, "id": next_id, "builtin": False})
            except (TypeError, ValueError):
                continue
            if (prompt.name, prompt.text) not in known:
                added.append(prompt)
                known.add((prompt.name, prompt.text))
                next_id += 1
        if added:
            prompts._write([*mine, *added], used)
    return len(added)
