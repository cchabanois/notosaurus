"""A saved lesson's notes in Anki: finding them, the decks they go to, and deleting the
lesson with them."""

from . import anki, ankiconnect, lessons
from .errors import AppError
from .models import ExportRequest, Lesson, LessonIn


def _export_request(lesson: Lesson) -> ExportRequest:
    return ExportRequest(**lesson.model_dump(include=set(LessonIn.model_fields)), lesson_id=lesson.id)


def decks(lesson: Lesson) -> list[str]:
    """The decks the lesson's cards go to: its own and its subdecks."""
    return sorted({lesson.deck.strip()} | {n.deck for n in anki.lesson_notes(_export_request(lesson))})


def _decks_meet(a: str, b: str) -> bool:
    """The same deck, or one inside the other ("Maths" and "Maths::Fractions"): their
    lessons' notes may share decks. Anki doesn't tell decks apart by case."""
    a, b = a.strip().casefold(), b.strip().casefold()
    return a == b or a.startswith(b + "::") or b.startswith(a + "::")


async def find(lesson: Lesson) -> dict:
    """The lesson's notes in the open Anki profile: {"available", "count", "ids"}.
    Only in its owner's profile (or any, for a lesson without owner): the others
    can't have them."""
    profile = await ankiconnect.active_profile()
    if profile is None or (lesson.owner and profile != lesson.owner):
        return {"available": False, "count": 0, "ids": []}
    # The other lessons: a note sent for one of them too isn't this lesson's alone. Their
    # tags need only their ids; their cards, only for those whose decks meet this one's
    # (the same deck, or one inside the other): the others' notes are elsewhere.
    summaries = [s for s in lessons.list_all() if s.id != lesson.id]
    other_tags = {anki.lesson_tag(s.id) for s in summaries}
    nearby = [o for s in summaries if _decks_meet(s.deck, lesson.deck) and (o := lessons.get(s.id))]
    others = {(n.deck, n.key) for o in nearby for n in anki.lesson_notes(_export_request(o))}
    try:
        ids = await ankiconnect.find_lesson_notes(
            lesson.id, anki.lesson_notes(_export_request(lesson)), others, other_tags
        )
    except ankiconnect.AnkiConnectError:
        return {"available": False, "count": 0, "ids": []}
    return {"available": True, "count": len(ids), "ids": ids}


async def delete_lesson(lesson: Lesson, in_anki: bool) -> dict:
    """Delete the lesson; with `in_anki`, its notes in Anki first (and its decks left
    empty), then sync."""
    result = {"anki_deleted": 0, "synced": False, "sync_error": None, "sync_skipped": False}
    if in_anki:
        found = await find(lesson)
        if not found["available"]:
            raise AppError("anki.unreachable", 502)
        sent = await ankiconnect.delete_notes(found["ids"], decks(lesson))
        result.update(
            anki_deleted=found["count"],
            synced=sent.synced,
            sync_error=sent.sync_error,
            sync_skipped=sent.sync_skipped,
        )
    lessons.delete(lesson.id)
    return result
