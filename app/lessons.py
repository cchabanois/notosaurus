"""Saved lessons: one folder per lesson under data/lessons/.

<yyyy-mm-dd-deck-slug>/
  lesson.json     deck, cards, prompt text, voice, dates
  page-1.jpg …    the photos, in order
  audio/          mp3 of the card backs, embedded in exported packages
"""

import asyncio
import hashlib
import logging
import re
import shutil
import uuid
from collections.abc import Awaitable, Callable, Sequence
from datetime import date
from pathlib import Path
from typing import cast

from notosaurus_core import pictures

from . import storage
from .errors import AppError
from .models import AiCall, Card, Generated, Lesson, LessonIn, LessonSummary

log = logging.getLogger("notosaurus")

ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")  # folder names we create; blocks "../"


def _root() -> Path:
    return storage.data_dir() / "lessons"


def folder(id: str) -> Path | None:
    """Folder of an existing lesson, or None (unknown or malformed id)."""
    if not ID_PATTERN.match(id):
        return None
    path = _root() / id
    return path if (path / "lesson.json").is_file() else None


def photo_path(id: str, n: int) -> Path | None:
    path = folder(id)
    return path / f"page-{n}.jpg" if path else None


def existing_folder(id: str) -> Path:
    """Folder of a lesson that must exist: lesson.not_found (404) otherwise (deleted meanwhile)."""
    path = folder(id)
    if path is None:
        raise AppError("lesson.not_found", 404)
    return path


def photo(id: str, n: int) -> bytes:
    """The lesson's photo n (from 1): photo.not_found (404) when there's none."""
    path = photo_path(id, n)
    if path is None or not path.is_file():
        raise AppError("photo.not_found", 404)
    return path.read_bytes()


def audio_dir(id: str) -> Path | None:
    path = folder(id)
    return path / "audio" if path else None


def photos(id: str) -> list[Path]:
    """The lesson's photos, in their order (page-1.jpg, page-2.jpg…); none: []."""
    path = folder(id)
    if path is None:
        return []
    return sorted(path.glob("page-*.jpg"), key=lambda photo: int(photo.stem.removeprefix("page-")))


def _count_photos(path: Path) -> int:
    return len(list(path.glob("page-*.jpg")))


# lesson.json's format; storage.migrate brings older files up to it
FORMAT = 1


def _read(path: Path) -> Lesson:
    raw = storage.read_json(path / "lesson.json")
    if raw is None:  # deleted meanwhile (another request, between a look and this reading)
        raise FileNotFoundError(path / "lesson.json")
    data = storage.migrate(raw, "lesson", FORMAT, {0: dict})
    lesson = Lesson(id=path.name, photo_count=_count_photos(path), **data)
    # Cards saved before cards had ids: the same id at every reading, until it's saved
    for n, card in enumerate(lesson.cards):
        if not card.id:
            card.id = hashlib.sha1(f"{path.name}|{n}|{card.front}".encode()).hexdigest()[:12]
    return lesson


def with_ids(cards: list[Card]) -> list[Card]:
    """New cards (from the AI, or added) get their stable id."""
    for card in cards:
        if not card.id:
            card.id = uuid.uuid4().hex[:12]
    return cards


def _write(path: Path, lesson: Lesson) -> None:
    with_ids(lesson.cards)
    storage.write_json(path / "lesson.json", {"format": FORMAT, **lesson.model_dump(exclude={"id", "photo_count"})})
    _summaries.pop(path, None)  # read again at the next listing, even within the same clock tick


# The lessons' summaries, kept between listings: a lesson is read again only when its
# file changed (written here, or by hand). Listing is then a look at the files' dates,
# not a reading of every card of every lesson; the first listing after a start reads
# them all once. Keyed by path: each data folder (tests) has its own.
_summaries: dict[Path, tuple[tuple[int, int, int], LessonSummary]] = {}


def _summary(path: Path) -> LessonSummary | None:
    try:
        stat = (path / "lesson.json").stat()
    except FileNotFoundError:
        return None
    version = (stat.st_mtime_ns, stat.st_size, stat.st_ino)  # the file replaced: a new inode
    cached = _summaries.get(path)
    if cached and cached[0] == version:
        return cached[1]
    try:
        lesson = _read(path)
    except FileNotFoundError:  # deleted between the look at its date and this reading
        _summaries.pop(path, None)
        return None
    except storage.DataTooNew as e:  # saved by a newer Notosaurus: left alone
        log.warning("Lesson %s not listed: %s", path.name, e.detail_text)
        return None
    summary = LessonSummary(card_count=len(lesson.cards), **lesson.model_dump(exclude={"cards"}))
    _summaries[path] = (version, summary)
    return summary


def _new_folder(deck: str) -> Path:
    base = f"{date.today().isoformat()}-{storage.slugify(deck) or 'lesson'}"
    path, n = _root() / base, 2
    while path.exists():
        path, n = _root() / f"{base}-{n}", n + 1
    return path


def create(g: Generated, ai_calls: Sequence[AiCall] = ()) -> Lesson:
    """A new lesson, saved: what the AI made (owned by its profile) and the calls it took."""
    with storage.lock:
        path = _new_folder(g.content.deck)
        tmp = path.with_name(f".{path.name}.tmp")
        tmp.mkdir(parents=True)
        try:
            for n, data in enumerate(g.photos, start=1):
                (tmp / f"page-{n}.jpg").write_bytes(data)
            now = storage.now()
            _write(
                tmp,
                Lesson(
                    **{
                        **g.content.model_dump(exclude={"prompt", "choice"}),
                        "child": g.content.child or "",
                        "owner": g.profile,
                        "shared": False,
                        "frames": list(g.frames),
                    },
                    ai_calls=list(ai_calls),
                    choice=g.choice,
                    page_texts=list(g.page_texts),
                    id=path.name,
                    prompt=g.prompt,
                    photo_count=len(g.photos),
                    created_at=now,
                    updated_at=now,
                ),
            )
            tmp.rename(path)  # the lesson appears complete, or not at all
        except BaseException:
            shutil.rmtree(tmp, ignore_errors=True)
            raise
    return _read(path)


def copy(id: str, deck: str, child: str, owner: str) -> Lesson:
    """A copy of lesson `id` for another child (its `deck`, its Anki profile `owner`): the
    photos, cards, pictures and sounds, the prompt and options. New card ids: in Anki, other
    notes with their own history, even in the same collection. Not sent yet; no AI calls
    (nothing asked of the AI: its costs stay the original's)."""
    with storage.lock:
        source = existing_folder(id)
        lesson = _read(source)
        path = _new_folder(deck)
        tmp = path.with_name(f".{path.name}.tmp")
        tmp.mkdir(parents=True)
        try:
            for photo in source.glob("page-*.jpg"):
                shutil.copy2(photo, tmp / photo.name)
            if (source / "audio").is_dir():  # read aloud: by what it says, whatever the card
                shutil.copytree(source / "audio", tmp / "audio")
            cards = []
            for card in lesson.cards:
                new_id = uuid.uuid4().hex[:12]
                picture = card.picture
                if picture and pictures.NAME.match(picture) and (source / "images" / picture).is_file():
                    picture = re.sub(r"^picture-[a-z0-9]+-", f"picture-{new_id}-", picture)  # named after its card
                    (tmp / "images").mkdir(exist_ok=True)
                    shutil.copy2(source / "images" / card.picture, tmp / "images" / picture)
                else:
                    picture = ""
                cards.append(card.model_copy(update={"id": new_id, "picture": picture}))
            now = storage.now()
            changes = {"id": path.name, "deck": deck, "child": child, "owner": owner, "shared": False, "cards": cards}
            reset = {"ai_calls": [], "anki_notes": {}, "created_at": now, "updated_at": now, "exported_at": None}
            _write(tmp, lesson.model_copy(update={**changes, **reset}))
            tmp.rename(path)
        except BaseException:
            shutil.rmtree(tmp, ignore_errors=True)
            raise
    return _read(path)


def get(id: str) -> Lesson | None:
    path = folder(id)
    try:
        return _read(path) if path else None
    except FileNotFoundError:  # deleted since folder() found it
        return None


def list_all() -> list[LessonSummary]:
    root = _root()
    if not root.is_dir():
        return []
    paths = [p for p in root.iterdir() if not p.name.startswith(".")]  # .…tmp: being created
    summaries = [s for p in paths if (s := _summary(p))]
    present = set(paths)
    for gone in [p for p in _summaries if p.parent == root and p not in present]:
        del _summaries[gone]  # deleted lessons
    return sorted(summaries, key=lambda s: (s.updated_at, s.id), reverse=True)


# What a content update may change: the lesson's content, never its sharing
CONTENT = set(LessonIn.model_fields) - {"shared"}


def update(id: str, changes: LessonIn, exported: bool = False, share: bool | None = None) -> Lesson | None:
    """Save the lesson's content. Sharing only changes through `share`, after the
    caller checked it's the owner's profile (content updates never touch it)."""
    return _save(id, changes.model_dump(include=CONTENT, exclude_none=True), exported, share)


def _save(id: str, content: dict, exported: bool = False, share: bool | None = None) -> Lesson | None:
    with storage.lock:
        path = folder(id)
        if not path:
            return None
        now = storage.now()
        # Validated again (not model_copy): the cards become Card objects, not dicts
        lesson = Lesson(
            **{
                **_read(path).model_dump(),
                **content,
                **({"shared": share} if share is not None else {}),
                "updated_at": now,
                **({"exported_at": now} if exported else {}),
            }
        )
        _write(path, lesson)
    return lesson


async def edit[T](id: str, change: Callable[[Lesson], T | Awaitable[T]]) -> tuple[Lesson, T]:
    """Change the lesson in place (a route's cards, pictures, frames…): `change` gets a
    working copy (cards and frames its own, deep copies) and may take its time (an AI
    call); what it changed in the content is then saved as `update` saves it (sharing
    never, the rest read again then: changed meanwhile elsewhere, it stays). If `change`
    fails, nothing is saved. The saved lesson and what `change` returned.

    The lesson is read outside the lock on purpose: `change` may wait seconds for the AI,
    and holding storage.lock that long would stall every other write. Not a race but a
    choice: `_save` merges field by field, writing only the fields `change` modified over
    the lesson as it is then, so a concurrent change to other fields is kept. The save
    runs in a worker thread, off the event loop (storage.lock serializes the threads)."""
    before = get(id)
    if before is None:
        raise AppError("lesson.not_found", 404)
    draft = before.model_copy(deep=True)
    outcome = change(draft)
    # cast: an awaitable `change` gives its T once awaited (pyright can't tell)
    result = cast("T", await outcome) if isinstance(outcome, Awaitable) else outcome
    changed = {f for f in CONTENT if getattr(draft, f) != getattr(before, f)}
    saved = await asyncio.to_thread(_save, id, draft.model_dump(include=changed))
    if saved is None:  # deleted meanwhile
        raise AppError("lesson.not_found", 404)
    return saved, result


def regenerated(id: str, g: Generated, calls: Sequence[AiCall] = ()) -> Lesson | None:
    """A new generation in place of the lesson's content: its cards, photos, frames and
    prompt replaced; its owner, sharing, dates and AI calls kept (the new ones added)."""
    with storage.lock:
        path = folder(id)
        if not path:
            return None
        old = _read(path)
        for photo in path.glob("page-*.jpg"):
            photo.unlink()
        for n, data in enumerate(g.photos, start=1):
            (path / f"page-{n}.jpg").write_bytes(data)
        # images/ is kept: "Undo" brings back the old cards with their pictures (pruned at export)
        lesson = Lesson(
            **{
                **old.model_dump(),
                **g.content.model_dump(include=CONTENT, exclude_none=True),
                "id": id,
                "prompt": g.prompt,
                "choice": g.choice,
                "page_texts": list(g.page_texts),
                "frames": list(g.frames),
                "photo_count": len(g.photos),
                "ai_calls": [*old.ai_calls, *calls],
                "updated_at": storage.now(),
            }
        )
        _write(path, lesson)
    return _read(path)


def completed(id: str, g: Generated, calls: Sequence[AiCall] = ()) -> Lesson | None:
    """The lesson's next pages added: their photos after its own, their cards after its
    cards (those untouched: their ids, so their notes in Anki, stay). `g`'s cards and frames
    count pages from the first new photo; numbered here from the lesson's own. Only its
    cards, photos, frames and page texts are taken (the deck, voice… stay the lesson's)."""
    cards = g.content.cards
    with storage.lock:
        path = folder(id)
        if not path:
            return None
        old = _read(path)
        before = old.photo_count
        for n, data in enumerate(g.photos, start=before + 1):
            (path / f"page-{n}.jpg").write_bytes(data)
        for card in cards:
            if card.mask:
                card.mask.page += before
        texts = old.page_texts
        if any(g.page_texts):  # one per photo: the earlier pages' ("" without a PDF), then these
            texts = [*old.page_texts, *[""] * (before - len(old.page_texts)), *g.page_texts]
        lesson = old.model_copy(
            update={
                "cards": [*old.cards, *cards],
                "frames": [*old.frames, *(f.model_copy(update={"page": f.page + before}) for f in g.frames)],
                "page_texts": texts,
                "ai_calls": [*old.ai_calls, *calls],
                "updated_at": storage.now(),
            }
        )
        _write(path, lesson)
    return _read(path)


def set_anki_notes(id: str, profile: str, notes: dict[str, int]) -> None:
    """The lesson's notes in that Anki profile after a send, by card id (not a content
    change: its place in the list stays)."""
    with storage.lock:
        path = folder(id)
        if path:
            lesson = _read(path)
            _write(path, lesson.model_copy(update={"anki_notes": {**lesson.anki_notes, profile: notes}}))


def add_ai_calls(id: str, calls: list[AiCall]) -> None:
    """Keep the AI calls of a correction with the lesson (not a content change)."""
    if not calls:
        return
    with storage.lock:
        path = folder(id)
        if path:
            lesson = _read(path)
            _write(path, lesson.model_copy(update={"ai_calls": [*lesson.ai_calls, *calls]}))


def set_access(id: str, owner: str | None = None, shared: bool | None = None) -> Lesson | None:
    """Change who a lesson belongs to (settings page). Not a content change: the
    lesson keeps its place in the list."""
    changes = {k: v for k, v in {"owner": owner, "shared": shared}.items() if v is not None}
    with storage.lock:
        path = folder(id)
        if not path:
            return None
        lesson = _read(path).model_copy(update=changes)
        _write(path, lesson)
    return lesson


def delete(id: str) -> bool:
    with storage.lock:
        path = folder(id)
        if not path:
            return False
        shutil.rmtree(path)
    return True
