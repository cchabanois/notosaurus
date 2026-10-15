"""The tests to prepare (app/exams.py): listed as the page shows them, saved, deleted;
the notes in Anki tagged to follow."""

import asyncio

from fastapi import APIRouter, Path
from pydantic import BaseModel, Field

from .. import ankiconnect, exams, lessons
from ..errors import AppError
from ..exams import Exam, ExamIn
from ..models import Lesson

router = APIRouter()


class ReviewIn(BaseModel):
    """What "Revise now" sends: the name of the filtered deck to make, in the page's language."""

    deck: str = Field(min_length=1, max_length=100)


async def _lessons(ids: set[str]) -> dict[str, Lesson]:
    """The lessons that still exist, by id."""
    found = await asyncio.gather(*(asyncio.to_thread(lessons.get, i) for i in sorted(ids)))
    return {lesson.id: lesson for lesson in found if lesson}


async def _retag(before: Exam | None, after: Exam | None, found: dict[str, Lesson], profile: str | None) -> bool:
    """Anki's notes made to follow the change; False when Anki can't be reached (`profile`
    None: closed; the tags of the notes sent later come with them anyway, anki.notes'
    extra tags, and a tag to take off waits for the next change)."""
    if profile is None:
        return False
    add, remove = exams.retagging(before, after, found, profile)
    if not add and not remove:
        return True
    try:
        await ankiconnect.tag_notes(add, remove)
    except ankiconnect.AnkiConnectError:
        return False
    return True


@router.get("/api/exams")
async def list_exams() -> list[dict]:
    every = await asyncio.to_thread(exams.list_all)
    profile = await ankiconnect.active_profile() or ""
    found = await _lessons({part.lesson for exam in every for part in exam.lessons})
    return [exams.view(exam, found, profile) for exam in every]


@router.put("/api/exams/{id}")
async def save_exam(content: ExamIn, id: str = Path(pattern=exams.ID)) -> dict:
    """A test made or changed (its name, date, lessons): saved, its tag put on its cards'
    notes in Anki and taken off those that left it."""
    before = await asyncio.to_thread(exams.get, id)
    if before is None and len(await asyncio.to_thread(exams.list_all)) >= exams.MAX_EXAMS:
        raise AppError("exams.too_many", 400, max=exams.MAX_EXAMS)
    wanted = {part.lesson for part in content.lessons} | ({part.lesson for part in before.lessons} if before else set())
    found = await _lessons(wanted)
    content = content.model_copy(update={"lessons": [p for p in content.lessons if p.lesson in found]})
    after = await asyncio.to_thread(exams.save, id, content)
    profile = await ankiconnect.active_profile()
    anki = await _retag(before, after, found, profile)
    return {**exams.view(after, found, profile or ""), "anki": anki}


@router.delete("/api/exams/{id}")
async def delete_exam(id: str = Path(pattern=exams.ID)) -> dict:
    """The test deleted, its tag taken off its notes in Anki (the notes themselves stay)."""
    before = await asyncio.to_thread(exams.get, id)
    if before is None:
        raise AppError("exams.not_found", 404)
    found = await _lessons({part.lesson for part in before.lessons})
    anki = await _retag(before, None, found, await ankiconnect.active_profile())
    if before.filtered_deck and anki:  # its filtered deck too: the cards go back to their decks
        try:
            await ankiconnect.drop_deck(before.filtered_deck)
        except ankiconnect.AnkiConnectError:
            anki = False
    await asyncio.to_thread(exams.delete, id)
    return {"deleted": True, "anki": anki}


@router.post("/api/exams/{id}/review")
async def review_exam(req: ReviewIn, id: str = Path(pattern=exams.ID)) -> dict:
    """The test revised now, on the computer: a filtered deck of its tagged cards, made
    (again) and shown in Anki; how many cards it holds."""
    exam = await asyncio.to_thread(exams.get, id)
    if exam is None:
        raise AppError("exams.not_found", 404)
    name = " ".join(req.deck.split()).replace("::", " ")  # one deck, not a hierarchy
    if exam.filtered_deck and exam.filtered_deck != name:  # named otherwise before (another language): one deck
        await ankiconnect.drop_deck(exam.filtered_deck)
    count = await ankiconnect.filtered_deck(name, exam.tag)
    await asyncio.to_thread(exams.set_filtered_deck, id, name)
    return {"deck": name, "count": count}
