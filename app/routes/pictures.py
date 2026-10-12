from fastapi import APIRouter, Depends, UploadFile
from fastapi.responses import FileResponse

from notosaurus_core import llm, pictures, stock
from notosaurus_core.models import Card, PictureSource

from .. import access, i18n, lessons, settings, usage
from ..errors import AppError
from ..models import FoundPicture, Lesson, PictureRequest, PictureSearch
from .common import IMAGE_TYPES, page_lang, read_photo

router = APIRouter()


@router.post("/api/lessons/{id}/pictures")
async def draw_pictures(id: str) -> dict:
    """Draw the pictures the cards ask for and don't have yet (after a generation or a
    correction). A picture that fails leaves its card without one: said, not fatal."""
    await access.editable(id)

    async def draw(draft: Lesson) -> tuple:
        with usage.metered("picture", id, draft.deck):
            return await pictures.draw_all(settings.current(), lessons.folder(id) / "images", draft.cards)

    lesson, (failures, error) = await lessons.edit(id, draw)
    return {"lesson": lesson, "failures": failures, "error": error}


async def _edit_card(id: str, card_id: str, change) -> dict:
    """Change one of the lesson's cards (`change` gets the lesson's working copy and the
    card in it), the pictures no card has any more pruned: the card and the lesson."""

    async def edit(draft: Lesson) -> Card:
        card = next((c for c in draft.cards if c.id == card_id), None)
        if card is None:
            raise AppError("card.not_found", 404)
        await change(draft, card)
        pictures.prune(lessons.folder(id) / "images", draft.cards)
        return card

    lesson, card = await lessons.edit(id, edit)
    return {"card": card, "lesson": lesson.model_dump()}


@router.post("/api/lessons/{id}/cards/{card_id}/picture/draw")
async def redraw_picture(id: str, card_id: str, req: PictureRequest, lang: str = Depends(page_lang)) -> dict:
    """Draw a card's picture (again), from what was written for it (pictures.card_picture:
    a figure or a picture, decided by the AI when needed). Never from the cache: this is
    asked when the picture didn't suit."""
    await access.editable(id)

    async def draw(draft: Lesson, card: Card) -> None:
        with usage.metered("picture", id, draft.deck):  # figures count as pictures in the costs
            card.picture = await pictures.figure_or_picture(
                settings.current(),
                lessons.folder(id) / "images",
                card,
                fresh=True,
                asked=req.subject,
                language=i18n.language_name(lang),
            )

    return await _edit_card(id, card_id, draw)


@router.post("/api/lessons/{id}/cards/{card_id}/picture", status_code=201)
async def upload_picture(id: str, card_id: str, photo: UploadFile) -> dict:
    """The user's own photo as the card's picture."""
    await access.editable(id)
    if photo.content_type not in IMAGE_TYPES:
        raise AppError("extract.bad_format", format=photo.content_type)
    data = await read_photo(photo)

    async def use(draft: Lesson, card: Card) -> None:
        try:
            card.picture = pictures.save(lessons.folder(id) / "images", card, data)
            card.picture_source = PictureSource(source="photo")
        except (OSError, ValueError) as e:
            raise AppError("extract.bad_format", format=photo.content_type) from e

    return await _edit_card(id, card_id, use)


@router.post("/api/pictures/search")
async def search_pictures(req: PictureSearch) -> dict:
    """Free pictures of what the user wrote (any language: turned into English search
    words by the cards' AI, a light call), to choose from (Commons, Openverse: no Pixabay
    on the computer, its key is the relay's)."""
    with usage.metered("picture"):
        try:
            words = await llm.search_words(settings.current(), req.subject, req.context)
        except AppError:  # no AI to ask: the words as they are
            words = req.subject
    return {"results": await stock.search(words), "words": words}


@router.post("/api/lessons/{id}/cards/{card_id}/picture/found", status_code=201)
async def found_picture(id: str, card_id: str, req: FoundPicture) -> dict:
    """One of the pictures found as the card's (fetched again by its source and id)."""
    await access.editable(id)

    async def use(draft: Lesson, card: Card) -> None:
        jpeg, card.picture_source = await stock.fetch(req.source, req.id)
        card.picture = pictures.save(lessons.folder(id) / "images", card, jpeg)

    return await _edit_card(id, card_id, use)


@router.delete("/api/lessons/{id}/cards/{card_id}/picture")
async def remove_picture(id: str, card_id: str) -> dict:
    """No picture on the card any more: it becomes a text card."""
    await access.editable(id)

    async def remove(draft: Lesson, card: Card) -> None:
        card.picture = card.picture_prompt = card.figure = ""
        card.picture_source = None

    return await _edit_card(id, card_id, remove)


@router.get("/api/lessons/{id}/pictures/{name}")
async def get_picture(id: str, name: str) -> FileResponse:
    await access.lesson(id)
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
