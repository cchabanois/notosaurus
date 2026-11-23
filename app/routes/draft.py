"""The lesson in progress (app/draft.py): kept as the page changes it, found again when it opens."""

import asyncio

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import FileResponse

from .. import draft
from ..errors import AppError
from .common import MAX_PAGES

router = APIRouter()


@router.get("/api/draft")
async def get_draft() -> dict:
    return await asyncio.to_thread(draft.get)


@router.get("/api/draft/photos/{n}")
async def get_draft_photo(n: int) -> FileResponse:
    path = draft.photo(n)
    if path is None:
        raise AppError("photo.not_found", 404)
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@router.put("/api/draft")
async def save_draft(
    text: str = Form(alias="draft"),
    photos_sent: bool = Form(False),
    photos: list[UploadFile] = File([]),
) -> dict:
    """`photos`: all of them, when `photos_sent` (none: no photo); else those kept stay.
    Too many refused before any is read, each read only up to its cap (draft.save checks again)."""
    if photos_sent and len(photos) > MAX_PAGES:
        raise AppError("draft.too_large", 413)
    sent = [await _read(photo) for photo in photos] if photos_sent else None
    await asyncio.to_thread(draft.save, text, sent, MAX_PAGES)
    return {}


async def _read(photo: UploadFile) -> bytes:
    """A photo of the draft, read only up to its cap: anything heavier refused before filling memory."""
    data = await photo.read(draft.MAX_PHOTO_BYTES + 1)
    if len(data) > draft.MAX_PHOTO_BYTES:
        raise AppError("draft.too_large", 413)
    return data


@router.delete("/api/draft")
async def clear_draft() -> dict:
    await asyncio.to_thread(draft.clear)
    return {}
