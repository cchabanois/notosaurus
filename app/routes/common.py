"""What the routers share: the page's files, the photos they accept, the language of
the page asking, and the work told as it goes (stepped)."""

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from pathlib import Path

from fastapi import Header, UploadFile
from fastapi.responses import StreamingResponse

from notosaurus_core.errors import loggable
from notosaurus_core.relay_api import MAX_IMAGE_BYTES, STREAM_TYPE

from .. import i18n
from ..errors import AppError

log = logging.getLogger("notosaurus")

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


Step = Callable[[dict], None]
_working: set[asyncio.Task] = set()  # stepped work under way, kept until done


def stepped(work: Callable[[Step], Awaitable[dict]], what: str) -> StreamingResponse:
    """Work told as it goes, one JSON per line: each step `work` tells (a send's
    {"step": "sounds", "done", "total"}, a picture's {"card", "step"…}), then {"result": …}
    (the answer without the stream) or {"error": {"code", "params"}}. It goes on if the
    page goes away meanwhile. `what`: the work, for the log ("Sending")."""
    queue: asyncio.Queue = asyncio.Queue()

    async def run() -> None:
        try:
            queue.put_nowait({"result": await work(queue.put_nowait)})
        except AppError as e:
            queue.put_nowait({"error": e.detail()})
        except Exception as e:
            log.error("%s failed: %s", what, loggable(e))
            queue.put_nowait({"error": {"code": "internal", "params": {}}})
        finally:
            queue.put_nowait(None)

    task = asyncio.create_task(run())
    _working.add(task)
    task.add_done_callback(_working.discard)

    async def lines():
        while (item := await queue.get()) is not None:
            yield json.dumps(item, ensure_ascii=False) + "\n"

    return StreamingResponse(lines(), media_type=STREAM_TYPE)
