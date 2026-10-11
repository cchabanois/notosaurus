from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

from notosaurus_core import diagrams, llm
from notosaurus_core.llm import Image, revise_cards

from .. import anki, ankiconnect, i18n, lessons, settings, usage
from ..errors import AppError
from ..models import Deck, ExplainRequest, Explanation, ExportRequest, Lesson, LessonIn, LessonSummary, RevisionRequest
from .common import _editable, _lesson, _sees, page_lang

router = APIRouter()


# --- Saved lessons ---------------------------------------------------------


@router.get("/api/lessons")
async def list_lessons() -> list[LessonSummary]:
    found = lessons.list_all()
    # Anki asked once for all (not once per lesson), and only if some lesson is private
    private = any(s.owner and not s.shared for s in found)
    profile = await ankiconnect.active_profile() if private else None
    return [s for s in found if _sees(profile, s.owner, s.shared)]


@router.get("/api/lessons/{id}")
async def get_lesson(id: str) -> Lesson:
    return await _lesson(id)


@router.put("/api/lessons/{id}")
async def update_lesson(id: str, lesson: LessonIn) -> Lesson:
    current = await _editable(id)
    # Sharing only changes when asked, and only for a lesson that has an owner.
    share = lesson.shared if lesson.shared is not None and current.owner else None
    return lessons.update(id, lesson, share=share)


def _export_request(lesson: Lesson) -> ExportRequest:
    return ExportRequest(**lesson.model_dump(include=set(LessonIn.model_fields)), lesson_id=lesson.id)


def _lesson_decks(lesson: Lesson) -> list[str]:
    """The decks the lesson's cards go to: its own and its subdecks."""
    return sorted({lesson.deck.strip()} | {n.deck for n in anki.lesson_notes(_export_request(lesson))})


def _decks_meet(a: str, b: str) -> bool:
    """The same deck, or one inside the other ("Maths" and "Maths::Fractions"): their
    lessons' notes may share decks. Anki doesn't tell decks apart by case."""
    a, b = a.strip().casefold(), b.strip().casefold()
    return a == b or a.startswith(b + "::") or b.startswith(a + "::")


async def _anki_notes(lesson: Lesson) -> dict:
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


async def _delete(lesson: Lesson, in_anki: bool) -> dict:
    """Delete the lesson; with `in_anki`, its notes in Anki first (and its decks left
    empty), then sync."""
    result = {"anki_deleted": 0, "synced": False, "sync_error": None, "sync_skipped": False}
    if in_anki:
        found = await _anki_notes(lesson)
        if not found["available"]:
            raise AppError("anki.unreachable", 502)
        sent = await ankiconnect.delete_notes(found["ids"], _lesson_decks(lesson))
        result.update(
            anki_deleted=found["count"],
            synced=sent.synced,
            sync_error=sent.sync_error,
            sync_skipped=sent.sync_skipped,
        )
    lessons.delete(lesson.id)
    return result


@router.get("/api/lessons/{id}/anki-notes")
async def lesson_anki_notes(id: str) -> dict:
    """How many of the lesson's notes are in Anki: asked before deleting it."""
    found = await _anki_notes(await _editable(id))
    return {"available": found["available"], "count": found["count"]}


class NoteIds(BaseModel):
    ids: list[int]


@router.post("/api/lessons/{id}/anki-notes/delete")
async def delete_leftovers(id: str, req: NoteIds) -> dict:
    """The lesson's notes in Anki no card has any more, deleted (asked after a send, never
    by default; their review history is lost). Only notes of this lesson that none of its
    cards updated at its last send: never one a card has, nor another lesson's."""
    lesson = await _editable(id)
    profile = await ankiconnect.active_profile() or ""
    kept = set(lesson.anki_notes.get(profile, {}).values())
    allowed = {n["id"]: n["deck"] for n in await ankiconnect.leftovers(lesson.id, kept)}
    ids = [i for i in dict.fromkeys(req.ids) if i in allowed]
    decks = sorted({allowed[i] for i in ids if allowed[i]} | set(_lesson_decks(lesson)))
    sent = await ankiconnect.delete_notes(ids, decks)  # and the decks they leave empty
    return {"deleted": len(ids), "synced": sent.synced, "sync_error": sent.sync_error}


@router.delete("/api/lessons/{id}")
async def delete_lesson(id: str, in_anki: bool = Query(False, alias="anki")) -> dict:
    """Delete the lesson; `?anki=true`: its notes in Anki too (their review history is lost)."""
    return await _delete(await _editable(id), in_anki)


@router.post("/api/lessons/{id}/revise")
async def revise_lesson(id: str, req: RevisionRequest, lang: str = Depends(page_lang)) -> dict:
    """Apply a natural-language correction to the cards, using the lesson photos."""
    lesson = await _editable(id)
    photos = [Image(lessons.photo_path(id, n).read_bytes(), "image/jpeg") for n in range(1, lesson.photo_count + 1)]
    with llm.recording("revise") as calls:
        try:
            s = settings.current()
            revision = await revise_cards(
                s,
                photos,
                lesson.prompt,
                Deck(deck=req.deck, cards=req.cards),
                req.instruction,
                i18n.language_name(lang),
                settings.standing_instructions(s, lesson.owner),
                demo=i18n.get(lang, "demo"),
            )
        finally:
            lessons.add_ai_calls(id, calls)  # an answer that couldn't be used is paid for too
            usage.add(calls, id, req.deck)
    updated = lessons.update(
        id,
        LessonIn(
            deck=revision.deck,
            cards=revision.cards,
            voice=req.voice,
            reverse=req.reverse,
            typing=req.typing,
            dictation=req.dictation,
        ),
    )
    return {"lesson": updated, "summary": revision.summary}


@router.post("/api/lessons/{id}/explain")
async def explain(id: str, req: ExplainRequest, lang: str = Depends(page_lang)) -> Explanation:
    """A card explained to the pupil (or an example, a way to remember it, why the answer
    is right), in the page's language. Also for a lesson only read here: nothing in it
    changes but its record of AI calls."""
    lesson = await _lesson(id)  # not found, or another profile's private one: 404
    with llm.recording("explain") as calls:
        try:
            s = settings.current()
            return await llm.explain_card(
                s,
                req.card,
                req.kind,
                lesson.prompt,
                lesson.deck,
                i18n.language_name(lang),
                settings.standing_instructions(s, lesson.owner),
                lesson.page_texts,
            )
        finally:
            lessons.add_ai_calls(id, calls)  # paid for, kept with the lesson
            usage.add(calls, id, lesson.deck)


@router.post("/api/lessons/{id}/photos/{n}/rotate")
async def rotate_photo(id: str, n: int) -> Lesson:
    """Turn a photo a quarter turn clockwise (the AI got its direction wrong), with the
    diagram masks on it."""
    lesson = await _editable(id)
    path = lessons.photo_path(id, n)
    if path is None or not path.is_file():
        raise AppError("photo.not_found", 404)
    cards = [card.model_copy(deep=True) for card in lesson.cards]
    frames = [frame.model_copy(deep=True) for frame in lesson.frames]
    path.write_bytes(diagrams.turn(path.read_bytes(), diagrams.boxes_on(n, cards, frames), 90))
    content = LessonIn(**{**lesson.model_dump(include=set(LessonIn.model_fields)), "cards": cards, "frames": frames})
    return lessons.update(id, content)


@router.get("/api/lessons/{id}/photos/{n}")
async def get_photo(id: str, n: int) -> FileResponse:
    await _lesson(id)
    path = lessons.photo_path(id, n)
    if path is None or not path.is_file():
        raise AppError("photo.not_found", 404)
    return FileResponse(path, media_type="image/jpeg")
