import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Header, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse, StreamingResponse

from notosaurus_core import llm, pictures, stock
from notosaurus_core.models import Card, PictureSource

from .. import access, i18n, lessons, settings, usage
from ..errors import AppError
from ..models import DrawPictures, FoundPicture, Lesson, PictureRequest, PictureSearch, RedrawRequest
from .common import IMAGE_TYPES, Step, page_lang, read_photo, stepped
from .generation import NDJSON

router = APIRouter()


@router.post("/api/lessons/{id}/pictures")
async def draw_pictures(id: str, req: DrawPictures | None = None, accept: str | None = Header(None)):
    """The pictures the cards ask for and don't have yet (after a generation or a
    correction): figures drawn, free pictures found; those no free one fits drawn by the
    image model only when asked (`draw`: the user said yes), else listed in to_draw. A
    picture that fails leaves its card without one: said, not fatal. Asked as
    application/x-ndjson: each card's steps as they begin ({"card", "step", "problem",
    "first"}: what the page shows on it meanwhile), then the answer (common.stepped)."""
    await access.editable(id)
    allowed = bool(req and req.draw)
    not_from_lesson = req.not_from_lesson if req else []
    previous = {card: (was.source, was.kind) for card, was in req.previous.items()} if req else {}

    async def drawn(step: Step | None = None) -> dict:
        async def draw(draft: Lesson) -> pictures.Drawn:
            async with usage.metered("picture", id, draft.deck):
                folder = lessons.existing_folder(id) / "images"
                # The lesson's own drawings first: its photos (pictures.lesson_drawings)
                photos = [llm.Image(photo.read_bytes(), "image/jpeg") for photo in lessons.photos(id)]
                return await pictures.draw_all(
                    settings.current(),
                    folder,
                    draft.cards,
                    draw=allowed,
                    step=step,
                    photos=photos,
                    not_from_lesson=not_from_lesson,
                    previous=previous,
                )

        lesson, made = await lessons.edit(id, draw)
        return {"lesson": lesson, "failures": made.failures, "error": made.error, "to_draw": made.to_draw}

    if NDJSON in (accept or ""):
        return stepped(lambda step: _encoded(drawn(step)), "Drawing pictures")
    return await drawn()


def _nested(step: Step) -> Step:
    """A card's steps as lines of their own: {"step": {"step", "problem", "first"}}
    (relay_api.CardPictureLine's)."""
    return lambda said: step({"step": said})


async def _encoded(answer) -> dict:
    """An answer as JSON can write it (a lesson: its dates, its models)."""
    return jsonable_encoder(await answer)


async def _edit_card(id: str, card_id: str, change) -> dict:
    """Change one of the lesson's cards (`change` gets the lesson's working copy and the
    card in it): the card and the lesson. The picture it no longer has stays until
    prune_pictures: the page can undo the card's correction while the card is edited."""

    async def edit(draft: Lesson) -> Card:
        card = next((c for c in draft.cards if c.id == card_id), None)
        if card is None:
            raise AppError("card.not_found", 404)
        await change(draft, card)
        return card

    lesson, card = await lessons.edit(id, edit)
    return {"card": card, "lesson": lesson.model_dump()}


@router.post("/api/lessons/{id}/cards/{card_id}/picture/make")
async def make_picture(
    id: str, card_id: str, req: PictureRequest, lang: str = Depends(page_lang), accept: str | None = Header(None)
):
    """ "✨ Image", its first step (pictures.decided): from what was written for it (any
    language; none: the card), the AI decides a figure, then drawn (cheap), or a picture,
    its description and search words set: the page then looks for free ones (search) and
    asks the user before the image model draws one (draw). Asked as application/x-ndjson:
    its steps as they begin (relay_api.PictureStep), then the answer."""
    await access.editable(id)

    async def made(step: Step | None = None) -> dict:
        found: dict = {}

        async def make(draft: Lesson, card: Card) -> None:
            async with usage.metered("picture", id, draft.deck):  # figures count as pictures in the costs
                s = settings.current()
                folder = lessons.existing_folder(id) / "images"
                origin, kind = card.picture_source, card.figure_kind  # the figure it had, if any
                previous = pictures.kept_sources(folder, origin) if pictures.changed_figure(card, req.subject) else []
                decided = await pictures.decided(s, card, req.subject, i18n.language_name(lang), step)
                for field in pictures.PICTURE_FIELDS:
                    setattr(card, field, getattr(decided, field))
                if card.figure.strip():
                    card.picture = await pictures.figure_or_picture(
                        s,
                        folder,
                        card,
                        fresh=True,
                        step=step,
                        previous=previous,
                        previous_kind=kind,
                        previous_engine=origin.engine if origin else "",
                    )
                else:
                    found["search"] = card.picture_search or card.picture_prompt

        return {**await _edit_card(id, card_id, make), **found}

    if NDJSON in (accept or ""):
        return stepped(lambda step: _encoded(made(_nested(step))), "Making a picture")
    return await made()


@router.post("/api/lessons/{id}/cards/{card_id}/picture/draw")
async def draw_picture(id: str, card_id: str, req: RedrawRequest | None = None, accept: str | None = Header(None)):
    """The card's picture drawn by the image model, now: the user said yes (no free one
    fit). Its figure drawn again, for a figure: told what its check found (`problem`), when
    there is one, with the model's thinking when `careful`. Never from the cache: asked when it didn't
    suit. Asked as application/x-ndjson: its steps as they begin, then the answer."""
    await access.editable(id)
    problem, careful = (req.problem, req.careful) if req else ("", False)

    async def drawn(step: Step | None = None) -> dict:
        async def draw(draft: Lesson, card: Card) -> None:
            async with usage.metered("picture", id, draft.deck):
                folder = lessons.existing_folder(id) / "images"
                s = settings.current()
                # A figure drawn again from what it was drawn from: what is asked changed, the rest kept
                origin = card.picture_source
                previous = pictures.kept_sources(folder, origin) if card.figure else []
                card.picture = await pictures.figure_or_picture(
                    s,
                    folder,
                    card,
                    fresh=True,
                    find=False,
                    step=step,
                    problem=problem,
                    careful=careful,
                    previous=previous,
                    previous_kind=card.figure_kind,
                    previous_engine=origin.engine if origin else "",
                )

        return await _edit_card(id, card_id, draw)

    if NDJSON in (accept or ""):
        return stepped(lambda step: _encoded(drawn(_nested(step))), "Drawing a picture")
    return await drawn()


@router.post("/api/lessons/{id}/cards/{card_id}/picture/check")
async def check_picture(id: str, card_id: str) -> dict:
    """The card's picture looked at by the AI (the "🔍 Check" button): its figure as drawn
    against its description; any other picture (a photo found, drawn by the image model, the
    user's) against the card. {"ok", "problem"}, what is wrong in the cards' language. Nothing
    changed: the user then decides (a figure drawn again, with the problem; another picture)."""
    await access.editable(id)
    lesson, folder = lessons.get(id), lessons.folder(id)
    if lesson is None or folder is None:
        raise AppError("lesson.not_found", 404)
    card = next((c for c in lesson.cards if c.id == card_id), None)
    if card is None or not card.picture:
        raise AppError("card.not_found", 404)
    path = folder / "images" / card.picture
    if not pictures.NAME.match(card.picture) or not path.is_file():
        raise AppError("photo.not_found", 404)
    s = settings.current()
    async with usage.metered("picture", id, lesson.deck):
        if card.figure.strip() and card.picture.endswith(".svg"):
            problem = await llm.check_figure(s, card.figure, path.read_text(encoding="utf-8"))
        else:
            media = PICTURE_TYPES.get(path.suffix.lower())
            if media is None:
                raise AppError("photo.not_found", 404)
            meant = card.picture_prompt or card.figure
            problem = await llm.check_picture(s, f"{card.front} → {card.back}", meant, path.read_bytes(), media)
    return {"ok": not problem, "problem": problem}


# A card's picture's type, by its file's extension (pictures.NAME: a figure's SVG, else a JPEG)
PICTURE_TYPES = {".jpg": "image/jpeg"}


@router.post("/api/lessons/{id}/cards/{card_id}/picture", status_code=201)
async def upload_picture(id: str, card_id: str, photo: UploadFile) -> dict:
    """The user's own photo as the card's picture."""
    await access.editable(id)
    if photo.content_type not in IMAGE_TYPES:
        raise AppError("extract.bad_format", format=photo.content_type)
    data = await read_photo(photo)

    async def use(draft: Lesson, card: Card) -> None:
        try:
            card.picture = pictures.save(lessons.existing_folder(id) / "images", card, data)
            card.picture_source = PictureSource(source="photo")
        except (OSError, ValueError) as e:
            raise AppError("extract.bad_format", format=photo.content_type) from e

    return await _edit_card(id, card_id, use)


@router.post("/api/pictures/search")
async def search_pictures(req: PictureSearch, accept: str | None = Header(None)):
    """Free pictures of what the user wrote (any language: turned into English search
    words by the cards' AI, a light call, unless the card's are given), to choose from
    (Commons, Openverse: no Pixabay on the computer, its key is the relay's), the AI
    keeping only those that show it (stock.sorted_as_found). Asked as
    application/x-ndjson: each source's as it answers, {"found": [...]} lines, then
    {"done": {"words"}} or {"error"}."""
    if NDJSON not in (accept or ""):
        results, words = [], ""
        async for item in _found(req):
            results += item.get("found", [])
            words = item.get("done", {}).get("words", words)
        return {"results": results, "words": words}

    async def lines():
        try:
            async for item in _found(req):
                yield json.dumps(item, ensure_ascii=False) + "\n"
        except AppError as e:
            yield json.dumps({"error": e.detail()}) + "\n"

    return StreamingResponse(lines(), media_type=NDJSON)


async def _found(req: PictureSearch) -> AsyncIterator[dict]:
    s = settings.current()
    async with usage.metered("picture"):
        words = req.words.strip()
        if not words:
            try:
                words = await llm.search_words(s, req.subject, req.context)
            except AppError:  # no AI to ask: the words as they are
                words = req.subject
        async for batch in stock.sorted_as_found(s, words, req.context):
            yield {"found": jsonable_encoder(batch)}
        yield {"done": {"words": words}}


@router.post("/api/lessons/{id}/cards/{card_id}/picture/found", status_code=201)
async def found_picture(id: str, card_id: str, req: FoundPicture) -> dict:
    """One of the pictures found as the card's (fetched again by its source and id)."""
    await access.editable(id)

    async def use(draft: Lesson, card: Card) -> None:
        jpeg, card.picture_source = await stock.fetch(req.source, req.id)
        card.picture = pictures.save(lessons.existing_folder(id) / "images", card, jpeg)

    return await _edit_card(id, card_id, use)


@router.post("/api/lessons/{id}/pictures/prune")
async def prune_pictures(id: str) -> dict:
    """The pictures no card of the saved lesson uses any more removed (drawn again, replaced,
    removed: kept until then, so that the page can undo a card's correction while it is
    edited). Asked by the page once no card is edited, and when the lesson opens. None while
    the lesson is being changed (lessons.edit: a picture just drawn is in no saved card yet,
    another tab or a reload asking meanwhile): the next time. The lesson read again after that
    check, nothing awaited in between (access.editable awaits Anki: an edit ending meanwhile
    saved cards that one never had, its pictures removed)."""
    await access.editable(id)
    if lessons.being_edited(id):
        return {"removed": 0}
    folder, lesson = lessons.folder(id), lessons.get(id)
    return {"removed": pictures.prune(folder / "images", lesson.cards) if folder and lesson else 0}


@router.delete("/api/lessons/{id}/cards/{card_id}/picture")
async def remove_picture(id: str, card_id: str) -> dict:
    """No picture on the card any more: it becomes a text card."""
    await access.editable(id)

    async def remove(draft: Lesson, card: Card) -> None:
        for field in pictures.REMOVED:
            setattr(card, field, None if field == "picture_source" else "")

    return await _edit_card(id, card_id, remove)


@router.get("/api/lessons/{id}/pictures/{name}")
async def get_picture(id: str, name: str) -> FileResponse:
    await access.seen(id)
    folder = lessons.folder(id)
    path = folder / "images" / name if folder and pictures.NAME.match(name) else None
    if path is None or not path.is_file():
        raise AppError("photo.not_found", 404)
    if path.suffix == ".svg":
        # Cleaned already; and even opened on its own, nothing in it may run or load
        headers = {
            "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'",
            "X-Content-Type-Options": "nosniff",
        }
        return FileResponse(path, media_type="image/svg+xml", headers=headers)
    return FileResponse(path, media_type="image/jpeg")
