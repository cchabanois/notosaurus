"""The tests to prepare ("Contrôles"): a name, a date, and the lessons to revise for it,
each whole or some of its cards, from any decks.

Each test is a tag on its cards' notes in Anki, `Exam::<name>`: Anki's custom study
("study by card state or tag") then gathers them in one session, whatever their lessons,
and gives them back to their decks after. The tag is put on the notes the lessons have
in Anki already (Lesson.anki_notes) and on those sent later (anki.notes' extra tags).

data/exams.json: {"format": 1, "exams": [...]}.
"""

import re

from pydantic import BaseModel, Field

from . import lessons, storage
from .models import Lesson

FORMAT = 1
TAG_PREFIX = "Exam::"
MAX_EXAMS = 50
ID = r"^[a-z0-9-]{1,40}$"


class ExamLesson(BaseModel):
    lesson: str = Field(pattern=lessons.ID_PATTERN.pattern)
    cards: list[str] | None = Field(default=None, max_length=500)  # card ids; None: every card


class ExamIn(BaseModel):
    """What the page sends: the name, the date, the lessons."""

    name: str = Field(min_length=1, max_length=60)
    date: str = Field(default="", pattern=r"^(\d{4}-\d{2}-\d{2})?$")
    lessons: list[ExamLesson] = Field(default_factory=list, max_length=50)


class Exam(ExamIn):
    id: str = Field(pattern=ID)
    created_at: str = ""
    filtered_deck: str = ""  # the deck "Revise now" made in Anki (the computer), deleted with the test

    @property
    def tag(self) -> str:
        return TAG_PREFIX + tag_text(self.name)


def tag_text(name: str) -> str:
    """The name as an Anki tag's last part: no space (they separate tags), none of the
    characters Anki's search or hierarchy use."""
    text = re.sub(r"\s+", "_", re.sub(r'[:"*\\]', " ", name).strip())
    return text or "exam"


def _path():
    return storage.data_dir() / "exams.json"


def list_all() -> list[Exam]:
    with storage.lock:
        data = storage.read_json(_path())
        if data is None:
            return []
        data = storage.migrate(data, "exams", FORMAT, {})
        return [Exam(**e) for e in data.get("exams", [])]


def _write(exams: list[Exam]) -> None:
    storage.write_json(_path(), {"format": FORMAT, "exams": [e.model_dump() for e in exams]})


def get(id: str) -> Exam | None:
    return next((e for e in list_all() if e.id == id), None)


def save(id: str, content: ExamIn) -> Exam:
    """The test saved under `id` (made, or changed: its name, date, lessons)."""
    with storage.lock:
        exams = list_all()
        found = next((e for e in exams if e.id == id), None)
        kept = {"created_at": found.created_at, "filtered_deck": found.filtered_deck} if found else {}
        exam = Exam(id=id, **{"created_at": storage.now(), **kept}, **content.model_dump())
        exams = [exam if e.id == id else e for e in exams] if found else [*exams, exam]
        _write(exams)
    return exam


def set_filtered_deck(id: str, name: str) -> None:
    with storage.lock:
        exams = list_all()
        _write([e.model_copy(update={"filtered_deck": name}) if e.id == id else e for e in exams])


def delete(id: str) -> bool:
    with storage.lock:
        exams = list_all()
        kept = [e for e in exams if e.id != id]
        if len(kept) != len(exams):
            _write(kept)
    return len(kept) != len(exams)


def forget_lesson(lesson_id: str) -> None:
    """A lesson deleted: out of every test."""
    with storage.lock:
        exams = list_all()
        changed = [e.model_copy(update={"lessons": [x for x in e.lessons if x.lesson != lesson_id]}) for e in exams]
        if changed != exams:
            _write(changed)


# --- What a test tags -----------------------------------------------------------------


def card_tags(lesson_id: str, card_ids: list[str], exams: list[Exam] | None = None) -> dict[str, list[str]]:
    """The tests' tags of each of the lesson's cards (card id → tags; cards in no test
    left out): put on their notes when they are sent."""
    found: dict[str, list[str]] = {}
    for exam in list_all() if exams is None else exams:
        for part in exam.lessons:
            if part.lesson == lesson_id:
                for card in card_ids if part.cards is None else [c for c in part.cards if c in card_ids]:
                    found.setdefault(card, []).append(exam.tag)
    return found


def notes_of(exam: Exam | ExamIn, found: dict[str, Lesson], profile: str) -> set[int]:
    """The notes in Anki (`profile`'s) of the test's cards: those the lessons recorded
    when they were sent."""
    ids: set[int] = set()
    for part in exam.lessons:
        lesson = found.get(part.lesson)
        if lesson is None:
            continue
        notes = lesson.anki_notes.get(profile, {})
        cards = [c.id for c in lesson.cards] if part.cards is None else part.cards
        ids.update(notes[c] for c in cards if c in notes)
    return ids


def retagging(
    before: Exam | None, after: Exam | None, found: dict[str, Lesson], profile: str
) -> tuple[dict[str, set[int]], dict[str, set[int]]]:
    """The tags to add and to remove ({tag: notes}) so that Anki's notes follow a change
    of the test (`before` → `after`; None: made, or deleted)."""
    add: dict[str, set[int]] = {}
    remove: dict[str, set[int]] = {}
    old = notes_of(before, found, profile) if before else set()
    new = notes_of(after, found, profile) if after else set()
    if before and after and before.tag == after.tag:
        if new - old:
            add[after.tag] = new - old
        if old - new:
            remove[after.tag] = old - new
    else:
        if before and old:
            remove[before.tag] = old
        if after and new:
            add[after.tag] = new
    return add, remove


# --- What the page shows ---------------------------------------------------------------


def common_deck(decks: list[str]) -> str:
    """The deck holding every one of these (itself or a subdeck): where Anki's custom
    study finds all the test's cards; "" when they share none."""
    parts = [d.strip().split("::") for d in decks if d.strip()]
    if not parts:
        return ""
    common: list[str] = []
    for level in zip(*parts, strict=False):
        if len({p.casefold() for p in level}) != 1:
            break
        common.append(level[0])
    return "::".join(common)


def view(exam: Exam, found: dict[str, Lesson], profile: str) -> dict:
    """The test as the page shows it: its lessons that still exist, each with how many
    of its cards are in the test and how many of those are in Anki; the tag; where to
    find them in Anki."""
    parts = []
    for part in exam.lessons:
        lesson = found.get(part.lesson)
        if lesson is None:
            continue
        ids = [c.id for c in lesson.cards]
        chosen = ids if part.cards is None else [c for c in part.cards if c in ids]
        notes = lesson.anki_notes.get(profile, {})
        parts.append(
            {
                "lesson": part.lesson,
                "cards": part.cards,
                "deck": lesson.deck,
                "total": len(chosen),
                "in_anki": sum(c in notes for c in chosen),
            }
        )
    return {
        **exam.model_dump(exclude={"lessons"}),
        "lessons": parts,
        "tag": exam.tag,
        "deck": common_deck([p["deck"] for p in parts]),
        "search": f"tag:{exam.tag}",
    }
