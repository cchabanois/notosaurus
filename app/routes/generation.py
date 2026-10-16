import asyncio
import json
import logging
import os
import re
import traceback
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Header, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

from notosaurus_core import diagrams, llm, tts
from notosaurus_core.errors import loggable
from notosaurus_core.images import refuse_bomb
from notosaurus_core.llm import ExtractOptions, Image, extract_cards

from .. import access, ankiconnect, children, decks, exams, lessons, media, prompts, settings, usage
from ..anki import build_apkg
from ..errors import AppError
from ..models import ExportRequest, Generated, Lesson, LessonIn
from .common import IMAGE_TYPES, MAX_IMAGES, pupil_lang, read_photo

log = logging.getLogger("notosaurus")

router = APIRouter()


# --- Extraction & export ---------------------------------------------------


@dataclass
class Photo:
    """An uploaded photo, read at once: a streamed answer outlives the request's files."""

    data: bytes
    content_type: str | None

    async def read(self) -> bytes:
        return self.data


async def _photos(images: list[UploadFile]) -> list[Photo]:
    if len(images) > MAX_IMAGES:  # before reading any
        raise AppError("extract.too_many", max=MAX_IMAGES)
    return [Photo(await read_photo(img), img.content_type) for img in images]


def _page_texts(raw: str, count: int) -> list[str]:
    """The pages' texts sent by the page (JSON, one per photo); anything else: none."""
    try:
        texts = json.loads(raw) if raw.strip() else []
    except ValueError:
        return []
    if not isinstance(texts, list) or len(texts) != count or not all(isinstance(t, str) for t in texts):
        return []
    return texts


@dataclass
class GenerationForm:
    """What the page sends to make a lesson, new or again (multipart): its photos, the
    prompt and its options. A dependency of both routes: an option added here once."""

    images: list[UploadFile] = File([])
    prompt: str = Form(...)
    deck: str = Form("")
    voice: str = Form("")
    prompt_id: str | None = Form(None)
    typing: bool = Form(False)
    dictation: bool = Form(False)
    dictation_only: bool = Form(False)
    child: str = Form("")  # the child it is for (children.Child.id): its class, instructions, decks
    page_texts: str = Form("")  # the PDF pages' text, JSON (see _page_texts)
    quick: bool = Form(False)
    job: str = Form("")  # the page's id for it: what "Cancel" stops


async def _generate(
    form: GenerationForm,
    images: list[Photo],
    lang: str = "",
    lesson_id: str | None = None,
    on_card: llm.OnCard | None = None,
    existing: Sequence[str] = (),
) -> Generated:
    """Read the photos (or, without photos, work from the prompt alone): the lesson's
    new content, not saved yet. `images`: the form's, read already. Its AI calls go to
    the caller's usage.metered (paid for even if the lesson isn't saved)."""
    data, texts = await _inputs(form, images)
    profile = await ankiconnect.active_profile() or ""  # the lesson belongs to this Anki profile
    s = settings.current()
    child, known = await _child(form, profile)
    options = ExtractOptions(
        deck=form.deck,
        decks=known,
        fun_facts=s.fun_facts,
        helps=s.helps,
        pictures=s.pictures,
        page_texts=texts,
        instructions=settings.standing_instructions(s, children.for_ai(child)),
        quick=form.quick,
        existing=existing,
    )
    found = await extract_cards(s, data, form.prompt, options, on_card=on_card)
    if form.prompt_id is not None:
        await asyncio.to_thread(prompts.mark_used, form.prompt_id)
    # Photos taken sideways are saved upright (masks and diagram frames turn with them)
    photos = diagrams.straighten([i.data for i in data], found.deck.cards, found.turns, found.frames)
    content = await _content(form, found, s, lang, child)
    # In the child's decks ("Jules::{classe}"), its own: never one that exists already
    # (another lesson's, or the user's in Anki)
    content.deck = await decks.new_name(children.deck_for(child, content.deck), profile or None, but=lesson_id)
    return Generated(content, photos, form.prompt, profile, found.frames, found.choice, texts)


async def _inputs(form: GenerationForm, images: list[Photo]) -> tuple[list[Image], list[str]]:
    """The photos checked and read, and their pages' texts: refused before any AI call."""
    if not images and not form.prompt.strip():
        raise AppError("extract.no_input")
    if len(images) > MAX_IMAGES:
        raise AppError("extract.too_many", max=MAX_IMAGES)
    data = []
    for img in images:
        if img.content_type is None or img.content_type not in IMAGE_TYPES:
            raise AppError("extract.bad_format", format=img.content_type)
        data.append(Image(await img.read(), img.content_type))
    for img in data:  # a decompression bomb is refused before any AI call
        refuse_bomb(img.data)
    return data, _page_texts(form.page_texts, len(data))


async def _child(form: GenerationForm, profile: str) -> tuple[children.Child | None, list[str]]:
    """The child the lesson is for (chosen, else its Anki profile's), and the decks the AI
    may reuse: this child's and no child's, without the children's levels (no child's
    name to the AI, nothing of another child's lessons)."""
    known = await decks.known(profile)
    every = await asyncio.to_thread(children.list_all)
    child = children.chosen(every, form.child, profile)
    return child, children.decks_for_ai(known, every, child)


async def _content(
    form: GenerationForm, found: llm.Extracted, s: settings.Settings, lang: str, child: children.Child | None
) -> LessonIn:
    """The lesson made of what the AI found, with its options: Notosaurus's prompt's own,
    else what the AI read in the instructions (a typed answer, the reverse card, a
    dictation) or recognised (prompt "Automatic": a dictation)."""
    dictation_only = form.dictation_only or found.dictation
    typing = form.typing or found.typing
    dictation = form.dictation or found.dictation_card or dictation_only
    foreign = bool(_learned(found.back_language, lang, spelling=False))
    voice = form.voice
    if voice.strip().lower() == "auto":  # the voice of the language the backs are in
        heard = typing or dictation or found.read_aloud  # in the pupil's own language too
        voice = await tts.voice_for(_learned(found.back_language, lang, heard), s.voices)
    return LessonIn(
        **found.deck.model_dump(),
        voice=voice,
        rate=_rate(s.tts_rate, found.speed, foreign=foreign, dictation=dictation),
        reverse=found.reverse,
        typing=typing,
        dictation=dictation,
        dictation_only=dictation_only,
        child=child.id if child else "",
    )


def _rate(slowed: str, speed: str, foreign: bool, dictation: bool) -> str:
    """The backs' speed, kept with the lesson: the settings' slowdown (`slowed`) for a
    language being learned or a dictation (time to write), normal otherwise. What the
    instructions say comes first: "slow" slows even when the settings don't."""
    if speed == "slow":
        return slowed if slowed != tts.NORMAL else tts.RATE
    return slowed if speed != "normal" and (foreign or dictation) else tts.NORMAL


def _learned(back_language: str, lang: str, spelling: bool) -> str:
    """The backs' language when it is one being learned: not the pupil's own (the page's)
    for a lesson in their language ("Français" is no foreign language to a French pupil),
    unless the cards are for writing what is heard (a dictation): then theirs when the AI
    gave none (it doesn't for their own language)."""
    own = lang.split("-")[0].lower()
    if spelling:
        return back_language.strip() or own
    if own and back_language.strip().lower().split("-")[0] == own:
        return ""
    return back_language


NDJSON = "application/x-ndjson"
_streaming: set[asyncio.Task] = set()  # generations under way, kept until done
_generating: dict[str, asyncio.Task] = {}  # by the page's id for each one: what "Cancel" stops


def _streamed(work, job: str = "") -> StreamingResponse:
    """The cards sent to the page as soon as the AI writes them, one JSON per line:
    {"card": …} (or {"restart": true}: the ones sent so far are dropped), then
    {"lesson": …}, {"error": {"code", "params"}} as the page translates it, or
    {"cancelled": true}. The lesson is made and saved even if the page goes away
    meanwhile: only "Cancel" (`job`, see cancel_generation) stops it."""
    queue: asyncio.Queue = asyncio.Queue()

    async def card(found: dict | None) -> None:
        await queue.put({"card": found} if found is not None else {"restart": True})

    async def run() -> None:
        try:
            await queue.put({"lesson": jsonable_encoder(await work(card))})
        except AppError as e:
            await queue.put({"error": e.detail()})
        except asyncio.CancelledError:  # "Cancel": stopped here, nothing saved
            await queue.put({"cancelled": True})
        except Exception as e:
            # Where it failed (files, lines, functions), not what it said: the message,
            # like the traceback's source lines, may quote the lesson
            where = "\n".join(f"  {f.filename}:{f.lineno} in {f.name}" for f in traceback.extract_tb(e.__traceback__))
            log.error("Generating failed: %s\n%s", loggable(e), where)
            await queue.put({"error": {"code": "internal", "params": {}}})
        finally:
            await queue.put(None)

    task = asyncio.create_task(run())
    _streaming.add(task)
    task.add_done_callback(_streaming.discard)
    if job:
        _generating[job] = task
        task.add_done_callback(lambda _: _generating.pop(job, None))

    async def lines():
        while (item := await queue.get()) is not None:
            yield json.dumps(item, ensure_ascii=False) + "\n"

    return StreamingResponse(lines(), media_type=NDJSON)


@router.post("/api/generations/{job}/cancel")
async def cancel_generation(job: str) -> dict:
    """Stop a lesson being made ("Cancel" while waiting): the AI stops writing, no
    lesson is saved (generated again: the old one stays as it was). What the AI wrote
    already is paid for."""
    task = _generating.get(job)
    if task:
        task.cancel()
    return {"cancelled": task is not None}


def _wants_stream(accept: str | None) -> bool:
    return NDJSON in (accept or "")


@router.post("/api/extract", status_code=201)
async def extract(
    form: Annotated[GenerationForm, Depends()],
    lang: str = Depends(pupil_lang),
    accept: str | None = Header(None),
):
    """A new lesson (photos + cards), saved so it can be reopened. Asked for as
    application/x-ndjson: the cards as they come, then the lesson (see _streamed)."""
    photos = await _photos(form.images)

    async def work(on_card=None) -> Lesson:
        # Model, tokens and cost, kept with the lesson; answered but unusable: paid for, no lesson
        async with usage.metered("extract") as meter:
            g = await _generate(form, photos, lang, on_card=on_card)
            created = await asyncio.to_thread(lessons.create, g, meter.calls)
            meter.kept_by(created)
        return created

    if _wants_stream(accept):
        return _streamed(work, form.job)
    return JSONResponse(jsonable_encoder(await work()), status_code=201)


@router.post("/api/lessons/{id}/complete")
async def complete(
    id: str,
    form: Annotated[GenerationForm, Depends()],
    lang: str = Depends(pupil_lang),
    accept: str | None = Header(None),
):
    """The lesson's next pages (the form's photos: those only, a few days later): the AI
    reads them knowing the cards made already, and their cards come after the lesson's,
    which stay as they are (so do their notes in Anki). Only its owner's profile may.
    Streamed as /api/extract."""
    old = await access.editable(id)
    photos = await _photos(form.images)
    if not photos:
        raise AppError("extract.no_input")
    if old.photo_count + len(photos) > MAX_IMAGES:
        raise AppError("extract.too_many", max=MAX_IMAGES)
    existing = [c.front.strip() + (f" [{c.subdeck.strip()}]" if c.subdeck.strip() else "") for c in old.cards]
    # Its deck and voice are the lesson's: only the cards, photos and frames are taken
    form = replace(form, deck=old.deck, voice="")

    async def work(on_card=None) -> Lesson:
        async with usage.metered("extract") as meter:  # as /api/extract's
            g = await _generate(form, photos, lang, lesson_id=id, on_card=on_card, existing=existing)
            lesson = await asyncio.to_thread(lessons.completed, id, g, meter.calls)
            if lesson is None:  # deleted meanwhile
                raise AppError("lesson.not_found", 404)
            meter.kept_by(lesson)
        return lesson

    if _wants_stream(accept):
        return _streamed(work, form.job)
    return await work()


@router.post("/api/lessons/{id}/regenerate")
async def regenerate(
    id: str,
    form: Annotated[GenerationForm, Depends()],
    lang: str = Depends(pupil_lang),
    accept: str | None = Header(None),
):
    """Generate the lesson again (other prompt, other photos) in its place, instead of
    a second lesson. Only its owner's profile may. Streamed as /api/extract."""
    old = await access.editable(id)
    photos = await _photos(form.images)

    async def work(on_card=None) -> Lesson:
        async with usage.metered("extract") as meter:  # as /api/extract's
            g = await _generate(form, photos, lang, lesson_id=id, on_card=on_card)
            # The options set in the review stay (the prompt's are added): only the cards change
            g.content.reverse = g.content.reverse or old.reverse
            g.content.typing = g.content.typing or old.typing
            g.content.dictation = g.content.dictation or old.dictation
            g.content.dictation_only = g.content.dictation_only or old.dictation_only
            g.content.child = g.content.child or old.child  # still for its child
            lesson = await asyncio.to_thread(lessons.regenerated, id, g, meter.calls)
            if lesson is None:  # deleted meanwhile
                raise AppError("lesson.not_found", 404)
            meter.kept_by(lesson)
        return lesson

    if _wants_stream(accept):
        return _streamed(work, form.job)
    return await work()


APKG_TYPE = "application/apkg"  # the type AnkiDroid opens (not a generic download)


def _filename(deck: str) -> str:
    name = re.sub(r'[\\/:*?"<>|]+', " - ", deck).strip(" -") or "notosaurus"
    return f"{name}.apkg"


@router.post("/api/export")
async def export(req: ExportRequest, background: BackgroundTasks) -> FileResponse:
    lesson = await access.lesson(req.lesson_id)
    audio, failures = await media.card_audio(req, background)
    tags = await asyncio.to_thread(exams.card_tags, lesson.id, [c.id for c in req.cards]) if lesson else {}
    path = build_apkg(req, audio, media.diagram_images(req, lesson), media.card_pictures(req, lesson), tags)
    background.add_task(os.remove, path)
    if lesson and await access.is_owner(lesson):  # someone else's lesson: exported, not changed
        await asyncio.to_thread(lessons.update, lesson.id, req, exported=True)
    return FileResponse(
        path,
        media_type=APKG_TYPE,
        filename=_filename(req.deck),
        headers={"X-Notosaurus-Audio-Failures": str(failures)},
    )
