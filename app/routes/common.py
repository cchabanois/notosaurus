"""What the routers share: the page's files, the photos they accept and the language of
the page asking."""

from pathlib import Path

from fastapi import Header, UploadFile

from notosaurus_core.relay_api import MAX_IMAGE_BYTES

from .. import i18n
from ..errors import AppError

STATIC_DIR = Path(__file__).parent.parent.parent / "static"
IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_IMAGES = 10


async def read_photo(photo: UploadFile) -> bytes:
    """An uploaded photo, read whole only up to the relay's cap: the page sends them
    prepared (a few hundred KB), anything far heavier is refused before filling memory."""
    data = await photo.read(MAX_IMAGE_BYTES + 1)
    if len(data) > MAX_IMAGE_BYTES:
        raise AppError("extract.too_large", 413, max=MAX_IMAGE_BYTES // (1024 * 1024))
    return data


def page_lang(x_notosaurus_lang: str | None = Header(None)) -> str:
    """Language of the page making the request (sent by the page on every call)."""
    return i18n.resolve(x_notosaurus_lang) or i18n.DEFAULT


def pupil_lang(x_notosaurus_lang: str | None = Header(None)) -> str:
    """The pupil's language when the page says it ("" otherwise: no guess)."""
    return i18n.resolve(x_notosaurus_lang) or ""
