"""Opening photos and pictures with Pillow, never a decompression bomb.

A file of a few kilobytes can claim 20,000 × 20,000 pixels: decoded, it would fill
gigabytes. Pillow refuses the worst (DecompressionBombError, neither OSError nor
ValueError) and only warns below twice its limit: any image over its limit is
refused here, as a photo Notosaurus can't read ("relay.bad_image", the relay's code
for it too), before anything is decoded.
"""

import contextlib
import io

from PIL import Image, ImageOps

from .errors import AppError

MAX_PIXELS = Image.MAX_IMAGE_PIXELS or 89_478_485  # Pillow's own limit (≈ 89 million)


def _too_big() -> AppError:
    return AppError("relay.bad_image", 415)


def _open(data: bytes) -> Image.Image:
    """The image, not decoded yet. A bomb: AppError; unreadable: OSError or ValueError."""
    try:
        image = Image.open(io.BytesIO(data))
    except Image.DecompressionBombError as e:
        raise _too_big() from e
    if image.width * image.height > MAX_PIXELS:
        raise _too_big()
    return image


def refuse_bomb(data: bytes) -> None:
    """Refuses a bomb (AppError). Anything else passes, even what Pillow can't read
    (the AI may)."""
    with contextlib.suppress(OSError, ValueError):
        _open(data).close()


def upright(data: bytes) -> Image.Image:
    """The image upright (its EXIF orientation applied), in RGB. A bomb: AppError;
    unreadable: OSError or ValueError."""
    return ImageOps.exif_transpose(_open(data)).convert("RGB")
