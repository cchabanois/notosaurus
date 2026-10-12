import asyncio
import json
import logging
import os
import re
import traceback
from dataclasses import dataclass, replace
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Header, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

from notosaurus_core import diagrams, llm, tts
from notosaurus_core.errors import loggable
from notosaurus_core.images import refuse_bomb
from notosaurus_core.llm import Image, extract_cards

from .. import access, ankiconnect, decks, lessons, media, prompts, settings, usage
from ..anki import build_apkg
from ..errors import AppError
from ..models import ExportRequest, Lesson, LessonIn
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


@dataclass
class Generated:
    content: LessonIn
    photos: list[bytes]  # upright
    found: llm.Extracted
    profile: str
    page_texts: list[str]  # one per photo: a PDF page's text, "" for a photo


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
    fun_facts: bool = Form(False)
    page_texts: str = Form("")  # the PDF pages' text, JSON (see _page_texts)
    helps: bool = Form(False)
    quick: bool = Form(False)
    job: str = Form("")  # the page's id for it: what "Cancel" stops


async def _generate(
    form: GenerationForm,
    images: list[Photo],
    lang: str = "",
    lesson_id: str | None = None,
    on_card: llm.OnCard | None = None,
    existing: list[str] = (),
) -> Generated:
    """Read the photos (or, without photos, work from the prompt alone): the lesson's
    new content, not saved yet. `images`: the form's, read already. Its AI calls go to
    the caller's usage.metered (paid for even if the lesson isn't saved)."""
    prompt, voice = form.prompt, form.voice
    if not images and not prompt.strip():
        raise AppError("extract.no_input")
    if len(images) > MAX_IMAGES:
        raise AppError("extract.too_many", max=MAX_IMAGES)
    for img in images:
        if img.content_type not in IMAGE_TYPES:
            raise AppError("extract.bad_format", format=img.content_type)

    data = [Image(await img.read(), img.content_type) for img in images]
    for img in data:  # a decompression bomb is refused before any AI call
        refuse_bomb(img.data)
    texts = _page_texts(form.page_texts, len(data))
    profile = await ankiconnect.active_profile() or ""  # the lesson belongs to this Anki profile
    known = await decks.known(profile)
    s = settings.current()
    found = await extract_cards(
        s,
        data,
        prompt,
        form.deck,
        known,
        fun_facts=form.fun_facts,
        page_texts=texts,
        helps=form.helps,
        instructions=settings.standing_instructions(s, profile),
        quick=form.quick,
        on_card=on_card,
        existing=existing,
    )
    if form.prompt_id is not None:
        prompts.mark_used(form.prompt_id)
    # Photos taken sideways are saved upright (masks and diagram frames turn with them)
    photos = diagrams.straighten([i.data for i in data], found.deck.cards, found.turns, found.frames)
    if voice.strip().lower() == "auto":  # the voice of the language the backs are in
        voice = await tts.voice_for(_learned(found.back_language, lang, form.typing or form.dictation))
    content = LessonIn(**found.deck.model_dump(), voice=voice, typing=form.typing, dictation=form.dictation)
    # Its own deck: never one that exists already (another lesson's, or the user's in Anki)
    content.deck = await decks.new_name(content.deck, profile or None, but=lesson_id)
    return Generated(content, photos, found, profile, texts)


def _learned(back_language: str, lang: str, spelling: bool) -> str:
    """The backs' language when it is one being learned: not the pupil's own (the page's)
    for a lesson in their language ("Français" is no foreign language to a French pupil),
    unless the cards are for writing what is heard (a dictation)."""
    own = lang.split("-")[0].lower()
    if own and back_language.strip().lower().split("-")[0] == own and not spelling:
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
        with usage.metered("extract") as meter:
            g = await _generate(form, photos, lang, on_card=on_card)
            created = lessons.create(
                g.content,
                form.prompt,
                g.photos,
                g.profile,
                g.found.frames,
                meter.calls,
                g.found.choice,
                page_texts=g.page_texts,
            )
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
        with usage.metered("extract") as meter:  # as /api/extract's
            g = await _generate(form, photos, lang, lesson_id=id, on_card=on_card, existing=existing)
            lesson = lessons.completed(id, g.found.deck.cards, g.photos, g.found.frames, meter.calls, g.page_texts)
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
        with usage.metered("extract") as meter:  # as /api/extract's
            g = await _generate(form, photos, lang, lesson_id=id, on_card=on_card)
            # The options set in the review stay (the prompt's are added): only the cards change
            g.content.reverse = old.reverse
            g.content.typing = g.content.typing or old.typing
            g.content.dictation = g.content.dictation or old.dictation
            lesson = lessons.regenerated(
                id, g.content, form.prompt, g.photos, g.found.frames, meter.calls, g.found.choice, g.page_texts
            )
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
    path = build_apkg(req, audio, media.diagram_images(req, lesson), media.card_pictures(req, lesson))
    background.add_task(os.remove, path)
    if lesson and await access.is_owner(lesson):  # someone else's lesson: exported, not changed
        lessons.update(lesson.id, req, exported=True)
    return FileResponse(
        path,
        media_type=APKG_TYPE,
        filename=_filename(req.deck),
        headers={"X-Notosaurus-Audio-Failures": str(failures)},
    )
