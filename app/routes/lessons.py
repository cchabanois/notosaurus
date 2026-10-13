import asyncio

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

from notosaurus_core import diagrams, llm
from notosaurus_core.llm import Image, revise_cards

from .. import access, ankiconnect, children, i18n, lesson_notes, lessons, settings, usage
from ..errors import AppError
from ..models import Deck, ExplainRequest, Explanation, Lesson, LessonIn, LessonSummary, RevisionRequest
from .common import page_lang

router = APIRouter()


# --- Saved lessons ---------------------------------------------------------


@router.get("/api/lessons")
async def list_lessons() -> list[LessonSummary]:
    found = lessons.list_all()
    # Anki asked once for all (not once per lesson), and only if some lesson is private
    private = any(s.owner and not s.shared for s in found)
    profile = await ankiconnect.active_profile() if private else None
    return [s for s in found if access.sees(profile, s.owner, s.shared)]


@router.get("/api/lessons/{id}")
async def get_lesson(id: str) -> Lesson:
    return await access.seen(id)


@router.put("/api/lessons/{id}")
async def update_lesson(id: str, lesson: LessonIn) -> Lesson:
    current = await access.editable(id)
    # Sharing only changes when asked, and only for a lesson that has an owner.
    share = lesson.shared if lesson.shared is not None and current.owner else None
    updated = await asyncio.to_thread(lessons.update, id, lesson, share=share)
    if updated is None:  # deleted meanwhile
        raise AppError("lesson.not_found", 404)
    return updated


@router.get("/api/lessons/{id}/anki-notes")
async def lesson_anki_notes(id: str) -> dict:
    """How many of the lesson's notes are in Anki: asked before deleting it."""
    found = await lesson_notes.find(await access.editable(id))
    return {"available": found["available"], "count": found["count"]}


class NoteIds(BaseModel):
    ids: list[int]


@router.post("/api/lessons/{id}/anki-notes/delete")
async def delete_leftovers(id: str, req: NoteIds) -> dict:
    """The lesson's notes in Anki no card has any more, deleted (asked after a send, never
    by default; their review history is lost). Only notes of this lesson that none of its
    cards updated at its last send: never one a card has, nor another lesson's."""
    lesson = await access.editable(id)
    profile = await ankiconnect.active_profile() or ""
    kept = set(lesson.anki_notes.get(profile, {}).values())
    allowed = {n["id"]: n["deck"] for n in await ankiconnect.leftovers(lesson.id, kept)}
    ids = [i for i in dict.fromkeys(req.ids) if i in allowed]
    decks = sorted({allowed[i] for i in ids if allowed[i]} | set(lesson_notes.decks(lesson)))
    sent = await ankiconnect.delete_notes(ids, decks)  # and the decks they leave empty
    return {"deleted": len(ids), "synced": sent.synced, "sync_error": sent.sync_error}


@router.delete("/api/lessons/{id}")
async def delete_lesson(id: str, in_anki: bool = Query(False, alias="anki")) -> dict:
    """Delete the lesson; `?anki=true`: its notes in Anki too (their review history is lost)."""
    return await lesson_notes.delete_lesson(await access.editable(id), in_anki)


@router.post("/api/lessons/{id}/revise")
async def revise_lesson(id: str, req: RevisionRequest, lang: str = Depends(page_lang)) -> dict:
    """Apply a natural-language correction to the cards, using the lesson photos."""
    lesson = await access.editable(id)
    photos = [Image(lessons.photo(id, n), "image/jpeg") for n in range(1, lesson.photo_count + 1)]
    every = await asyncio.to_thread(children.list_all)
    child = next((c for c in every if c.id == lesson.child), None)
    # The deck without the children's levels: no child's name to the AI (put back after)
    private, deck = children.split_deck(req.deck, every)
    async with usage.metered("revise", id, req.deck):  # an answer that couldn't be used is paid for too
        s = settings.current()
        revision = await revise_cards(
            s,
            photos,
            lesson.prompt,
            Deck(deck=deck, cards=req.cards),
            req.instruction,
            i18n.language_name(lang),
            settings.standing_instructions(s, lesson.owner, children.for_ai(child)),
            demo=i18n.get(lang, "demo"),
        )
    revision.deck = "::".join(part for part in (private, revision.deck) if part)
    updated = await asyncio.to_thread(
        lessons.update,
        id,
        LessonIn(
            deck=revision.deck,
            cards=revision.cards,
            voice=req.voice,
            reverse=req.reverse,
            typing=req.typing,
            dictation=req.dictation,
            dictation_only=req.dictation_only,
        ),
    )
    return {"lesson": updated, "summary": revision.summary}


@router.post("/api/lessons/{id}/explain")
async def explain(id: str, req: ExplainRequest, lang: str = Depends(page_lang)) -> Explanation:
    """A card explained to the pupil (or an example, a way to remember it, why the answer
    is right), in the page's language. Also for a lesson only read here: nothing in it
    changes but its record of AI calls."""
    lesson = await access.seen(id)  # not found, or another profile's private one: 404
    every = await asyncio.to_thread(children.list_all)
    child = next((c for c in every if c.id == lesson.child), None)
    async with usage.metered("explain", id, lesson.deck):  # paid for, kept with the lesson
        s = settings.current()
        return await llm.explain_card(
            s,
            req.card,
            req.kind,
            lesson.prompt,
            children.for_ai_deck(lesson.deck, every),  # no child's name to the AI
            i18n.language_name(lang),
            settings.standing_instructions(s, lesson.owner, children.for_ai(child)),
            lesson.page_texts,
        )


@router.post("/api/lessons/{id}/photos/{n}/rotate")
async def rotate_photo(id: str, n: int) -> Lesson:
    """Turn a photo a quarter turn clockwise (the AI got its direction wrong), with the
    diagram masks on it."""
    await access.editable(id)
    path = lessons.photo_path(id, n)
    if path is None or not path.is_file():
        raise AppError("photo.not_found", 404)

    def turn(draft: Lesson) -> None:
        path.write_bytes(diagrams.turn(path.read_bytes(), diagrams.boxes_on(n, draft.cards, draft.frames), 90))

    return (await lessons.edit(id, turn))[0]


@router.get("/api/lessons/{id}/photos/{n}")
async def get_photo(id: str, n: int) -> FileResponse:
    await access.seen(id)
    path = lessons.photo_path(id, n)
    if path is None or not path.is_file():
        raise AppError("photo.not_found", 404)
    return FileResponse(path, media_type="image/jpeg")
