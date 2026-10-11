from fastapi import APIRouter, Depends, UploadFile
from fastapi.responses import FileResponse

from notosaurus_core import llm, pictures, stock
from notosaurus_core.models import PictureSource

from .. import i18n, lessons, settings, usage
from ..errors import AppError
from ..models import FoundPicture, Lesson, LessonIn, PictureRequest, PictureSearch
from .common import IMAGE_TYPES, _editable, _lesson, page_lang, read_photo

router = APIRouter()


@router.post("/api/lessons/{id}/pictures")
async def draw_pictures(id: str) -> dict:
    """Draw the pictures the cards ask for and don't have yet (after a generation or a
    correction). A picture that fails leaves its card without one: said, not fatal."""
    lesson = await _editable(id)
    cards = [card.model_copy(deep=True) for card in lesson.cards]
    folder = lessons.folder(id) / "images"
    with llm.recording("picture") as calls:
        try:
            failures, error = await pictures.draw_all(settings.current(), folder, cards)
        finally:
            lessons.add_ai_calls(id, calls)
            usage.add(calls, id, lesson.deck)
    content = LessonIn(**{**lesson.model_dump(include=set(LessonIn.model_fields)), "cards": cards})
    return {"lesson": lessons.update(id, content), "failures": failures, "error": error}


def _card(lesson: Lesson, card_id: str) -> int:
    index = next((i for i, c in enumerate(lesson.cards) if c.id == card_id), None)
    if index is None:
        raise AppError("card.not_found", 404)
    return index


def _save_card(lesson: Lesson, cards: list) -> dict:
    folder = lessons.folder(lesson.id) / "images"
    pictures.prune(folder, cards)
    content = LessonIn(**{**lesson.model_dump(include=set(LessonIn.model_fields)), "cards": cards})
    return lessons.update(lesson.id, content).model_dump()


@router.post("/api/lessons/{id}/cards/{card_id}/picture/draw")
async def redraw_picture(id: str, card_id: str, req: PictureRequest, lang: str = Depends(page_lang)) -> dict:
    """Draw a card's picture (again), from what was written for it (pictures.card_picture:
    a figure or a picture, decided by the AI when needed). Never from the cache: this is
    asked when the picture didn't suit."""
    lesson = await _editable(id)
    cards = [card.model_copy(deep=True) for card in lesson.cards]
    card = cards[_card(lesson, card_id)]
    s = settings.current()
    with llm.recording("picture") as calls:  # figures count as pictures in the costs
        try:
            card.picture = await pictures.figure_or_picture(
                s, lessons.folder(id) / "images", card, fresh=True, asked=req.subject, language=i18n.language_name(lang)
            )
        finally:
            lessons.add_ai_calls(id, calls)
            usage.add(calls, id, lesson.deck)
    return {"card": card, "lesson": _save_card(lessons.get(id), cards)}


@router.post("/api/lessons/{id}/cards/{card_id}/picture", status_code=201)
async def upload_picture(id: str, card_id: str, photo: UploadFile) -> dict:
    """The user's own photo as the card's picture."""
    lesson = await _editable(id)
    if photo.content_type not in IMAGE_TYPES:
        raise AppError("extract.bad_format", format=photo.content_type)
    data = await read_photo(photo)
    cards = [card.model_copy(deep=True) for card in lesson.cards]
    card = cards[_card(lesson, card_id)]
    try:
        card.picture = pictures.save(lessons.folder(id) / "images", card, data)
        card.picture_source = PictureSource(source="photo")
    except (OSError, ValueError) as e:
        raise AppError("extract.bad_format", format=photo.content_type) from e
    return {"card": card, "lesson": _save_card(lesson, cards)}


@router.post("/api/pictures/search")
async def search_pictures(req: PictureSearch) -> dict:
    """Free pictures of what the user wrote (any language: turned into English search
    words by the cards' AI, a light call), to choose from (Commons, Openverse: no Pixabay
    on the computer, its key is the relay's)."""
    s = settings.current()
    with llm.recording("picture") as calls:
        try:
            words = await llm.search_words(s, req.subject, req.context)
        except AppError:  # no AI to ask: the words as they are
            words = req.subject
        finally:
            usage.add(calls, None)
    return {"results": await stock.search(words), "words": words}


@router.post("/api/lessons/{id}/cards/{card_id}/picture/found", status_code=201)
async def found_picture(id: str, card_id: str, req: FoundPicture) -> dict:
    """One of the pictures found as the card's (fetched again by its source and id)."""
    lesson = await _editable(id)
    cards = [card.model_copy(deep=True) for card in lesson.cards]
    card = cards[_card(lesson, card_id)]
    jpeg, card.picture_source = await stock.fetch(req.source, req.id)
    card.picture = pictures.save(lessons.folder(id) / "images", card, jpeg)
    return {"card": card, "lesson": _save_card(lesson, cards)}


@router.delete("/api/lessons/{id}/cards/{card_id}/picture")
async def remove_picture(id: str, card_id: str) -> dict:
    """No picture on the card any more: it becomes a text card."""
    lesson = await _editable(id)
    cards = [card.model_copy(deep=True) for card in lesson.cards]
    card = cards[_card(lesson, card_id)]
    card.picture = card.picture_prompt = card.figure = ""
    card.picture_source = None
    return {"card": card, "lesson": _save_card(lesson, cards)}


@router.get("/api/lessons/{id}/pictures/{name}")
async def get_picture(id: str, name: str) -> FileResponse:
    await _lesson(id)
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
