"""What the routers share: the page's files, the photos they accept, the language of
the page asking, the work told as it goes (streamed), and the AI's work "Cancel" stops
(jobs)."""

import asyncio
import json
import logging
import traceback
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from fastapi import Header, UploadFile
from fastapi.responses import StreamingResponse

from notosaurus_core.errors import loggable
from notosaurus_core.relay_api import MAX_IMAGE_BYTES, STREAM_TYPE

from .. import i18n
from ..errors import AppError

log = logging.getLogger("notosaurus")

STATIC_DIR = Path(__file__).parent.parent.parent / "static"
IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
# A lesson's pages (LocalServer.MAX_PHOTOS on the phone): more than one call to the AI reads
# (MAX_IMAGES, the relay's cap) are sent in several, its next ones completing it
MAX_PAGES = 30


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
_working: set[asyncio.Task] = set()  # streamed work under way, kept until done
# The AI's work under way, by the page's id for each ("job"): what "Cancel" stops (a
# lesson being made, corrected, a card corrected)
jobs: dict[str, asyncio.Task] = {}


def tracked(task: asyncio.Task, job: str) -> None:
    """`task` stopped by "Cancel" for `job` (none: not cancellable) until it is done."""
    if job:
        jobs[job] = task
        task.add_done_callback(lambda _: jobs.pop(job, None) if jobs.get(job) is task else None)


async def cancellable[T](job: str, work: Awaitable[T]) -> T:
    """`work`'s answer; stopped by "Cancel": AppError extract.cancelled (409), as the
    Android app answers. The request itself going away still cancels it as before."""
    task = asyncio.ensure_future(work)
    tracked(task, job)
    try:
        return await task
    except asyncio.CancelledError:
        current = asyncio.current_task()
        if task.cancelled() and not (current and current.cancelling()):
            raise AppError("extract.cancelled", 409) from None
        raise


async def finished[T](work: Awaitable[T]) -> T:
    """`work` (a lesson being saved) run to its end even when "Cancel" lands meanwhile, and its
    answer given: begun, it is done (a thread's work goes on whatever happens to the task
    waiting for it), so the page is told what is saved, never "cancelled" over it."""
    task = asyncio.ensure_future(work)
    while True:
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            if task.done() and task.cancelled():
                raise
            current = asyncio.current_task()
            if current:
                current.uncancel()  # the cancel taken: what follows the save isn't stopped by it


def wants_stream(accept: str | None) -> bool:
    """The page asked for the answer as the work goes (Accept: STREAM_TYPE, see streamed)."""
    return STREAM_TYPE in (accept or "")


def streamed(
    work: Callable[[Step], Awaitable[Any]], what: str, job: str = "", answer: str = "result"
) -> StreamingResponse:
    """Work told as it goes, one JSON per line (STREAM_TYPE): each step `work` tells (a
    send's {"step": "sounds", "done", "total"}, a picture's {"card", "step"…}, a lesson's
    cards), then {answer: …} (the answer without the stream: {"result": …}, a lesson's
    {"lesson": …}) or {"error": {"code", "params"}} as the page translates it. It goes on
    if the page goes away meanwhile; `job`: "Cancel" stops it, ending with
    {"cancelled": true}. `what`: the work, for the log ("Sending")."""
    queue: asyncio.Queue = asyncio.Queue()

    async def run() -> None:
        try:
            queue.put_nowait({answer: await work(queue.put_nowait)})
        except AppError as e:
            queue.put_nowait({"error": e.detail()})
        except asyncio.CancelledError:  # "Cancel": stopped here
            queue.put_nowait({"cancelled": True})
        except Exception as e:
            # Where it failed (files, lines, functions), not what it said: the message,
            # like the traceback's source lines, may quote the lesson
            where = "\n".join(f"  {f.filename}:{f.lineno} in {f.name}" for f in traceback.extract_tb(e.__traceback__))
            log.error("%s failed: %s\n%s", what, loggable(e), where)
            queue.put_nowait({"error": {"code": "internal", "params": {}}})
        finally:
            queue.put_nowait(None)

    task = asyncio.create_task(run())
    _working.add(task)
    task.add_done_callback(_working.discard)
    tracked(task, job)

    async def lines():
        while (item := await queue.get()) is not None:
            yield json.dumps(item, ensure_ascii=False) + "\n"

    return StreamingResponse(lines(), media_type=STREAM_TYPE)
