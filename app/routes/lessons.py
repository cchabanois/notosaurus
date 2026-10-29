import asyncio

from fastapi import APIRouter, Depends, Header, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse
from pydantic import BaseModel

from notosaurus_core import diagrams, llm
from notosaurus_core.llm import Image, revise_cards
from notosaurus_core.models import switched
from notosaurus_core.relay_api import STREAM_TYPE

from .. import access, ankiconnect, children, i18n, lesson_notes, lessons, settings, sounds, usage
from ..errors import AppError
from ..models import (
    Deck,
    ExplainRequest,
    Explanation,
    FixCardRequest,
    Lesson,
    LessonIn,
    LessonSummary,
    RevisionRequest,
)
from .common import Step, page_lang, stepped

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
    sounds.soon(updated.id, updated.voice)  # the backs as edited: their sounds made meanwhile
    return updated


class CopyFor(BaseModel):
    child: str  # children.Child.id


@router.post("/api/lessons/{id}/copy")
async def copy_lesson(id: str, req: CopyFor) -> Lesson:
    """The lesson copied for another child: its decks ("Jules::5e::Anglais" →
    "Mathilde::3e::Anglais"), its Anki profile (on the computer); also from a lesson only
    read here (another profile's). Free: nothing asked of the AI."""
    lesson = await access.seen(id)
    every = await asyncio.to_thread(children.list_all)
    child = next((c for c in every if c.id == req.child), None)
    if child is None:
        raise AppError("children.not_found", 404)
    deck = children.deck_for(child, children.split_deck(lesson.deck, every)[1]) or lesson.deck
    owner = child.anki_profile or await ankiconnect.active_profile() or ""
    copied = await asyncio.to_thread(lessons.copy, id, deck, child.id, owner)
    sounds.soon(copied.id, copied.voice)
    return copied


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
async def revise_lesson(
    id: str, req: RevisionRequest, lang: str = Depends(page_lang), accept: str | None = Header(None)
):
    """Apply a natural-language correction to the cards, using the lesson photos. Asked as
    application/x-ndjson: what the AI is at ({"step": relay_api.AiStep}), then the answer."""
    if STREAM_TYPE in (accept or ""):

        async def told(step: Step) -> dict:
            with llm.telling(lambda said: step({"step": said})):
                return jsonable_encoder(await _revised(id, req, lang))

        return stepped(told, "Correcting")
    return await _revised(id, req, lang)


async def _revised(id: str, req: RevisionRequest, lang: str) -> dict:
    lesson = await access.editable(id)
    photos = [Image(lessons.photo(id, n), "image/jpeg") for n in range(1, lesson.photo_count + 1)]
    every = await asyncio.to_thread(children.list_all)
    child = children.chosen(every, lesson.child, lesson.owner)
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
            settings.standing_instructions(s, children.for_ai(child)),
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
            # How the cards are asked: as they were, unless the correction said otherwise
            reverse=switched(req.reverse, revision.reverse),
            typing=switched(req.typing, revision.typing),
            dictation=switched(req.dictation, revision.dictation),
            dictation_only=req.dictation_only and switched(req.dictation, revision.dictation),
        ),
    )
    if updated:
        sounds.soon(updated.id, updated.voice)
    return {"lesson": updated, "summary": revision.summary}


@router.post("/api/lessons/{id}/fix-card")
async def fix_card(id: str, req: FixCardRequest, lang: str = Depends(page_lang)) -> llm.FixedCard:
    """One card corrected by the AI as asked ("the answer is 1789"), seeing the lesson's
    photos; the lesson isn't saved here: the page puts the card in place (and can undo it)."""
    lesson = await access.editable(id)
    photos = [Image(lessons.photo(id, n), "image/jpeg") for n in range(1, lesson.photo_count + 1)]
    every = await asyncio.to_thread(children.list_all)
    child = children.chosen(every, lesson.child, lesson.owner)
    async with usage.metered("fix", id, lesson.deck):  # an answer that couldn't be used is paid for too
        s = settings.current()
        return await llm.fix_card(
            s,
            photos,
            lesson.prompt,
            children.for_ai_deck(lesson.deck, every),  # no child's name to the AI
            req.card,
            req.instruction,
            req.others,
            i18n.language_name(lang),
            settings.standing_instructions(s, children.for_ai(child)),
            demo=i18n.get(lang, "demo"),
        )


@router.post("/api/lessons/{id}/explain")
async def explain(id: str, req: ExplainRequest, lang: str = Depends(page_lang)) -> Explanation:
    """A card explained to the pupil (or an example, a way to remember it, why the answer
    is right), in the page's language. Also for a lesson only read here: nothing in it
    changes but its record of AI calls."""
    lesson = await access.seen(id)  # not found, or another profile's private one: 404
    every = await asyncio.to_thread(children.list_all)
    child = children.chosen(every, lesson.child, lesson.owner)
    async with usage.metered("explain", id, lesson.deck):  # paid for, kept with the lesson
        s = settings.current()
        return await llm.explain_card(
            s,
            req.card,
            req.kind,
            lesson.prompt,
            children.for_ai_deck(lesson.deck, every),  # no child's name to the AI
            i18n.language_name(lang),
            settings.standing_instructions(s, children.for_ai(child)),
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
