"""The backs' sounds made ahead, in the background, as soon as a lesson's cards exist or
change: "Add to Anki" then finds them made (making them took most of a send's time).

The same sounds as the send makes (media.card_audio: same texts, voice, rate and folder),
only the missing ones, never pruned here (the send prunes). One job per lesson, started
after a few seconds of quiet: the page saves as the user types, a newer save replaces the
job waiting or running. Failures are silent: the send makes what's still missing and
says what it couldn't."""

import asyncio
import contextlib
import logging

from notosaurus_core import tts
from notosaurus_core.errors import loggable

from . import lessons, settings

log = logging.getLogger("notosaurus")

DELAY = 5.0  # seconds of quiet after a lesson's last save

_jobs: dict[str, asyncio.Task] = {}  # by lesson id: one at a time


def wanted(voice: str) -> bool:
    """A voice the app reads with itself (edge-tts): an Anki locale is read by Anki."""
    return bool(voice) and not tts.is_anki_locale(voice)


def soon(lesson_id: str | None, voice: str = "") -> None:
    """The lesson's missing sounds made in a few seconds, in place of a job started before.
    `voice`: the lesson's, when the caller has it (none: nothing to make, no job)."""
    if not lesson_id or not wanted(voice):
        return
    if old := _jobs.pop(lesson_id, None):
        _cancel(old)
    task = asyncio.create_task(_make(lesson_id))
    _jobs[lesson_id] = task
    task.add_done_callback(lambda done: _jobs.pop(lesson_id, None) if _jobs.get(lesson_id) is done else None)


async def settle(lesson_id: str | None) -> None:
    """The lesson's job stopped, before the send makes its sounds: never two at once on
    the same files."""
    if lesson_id and lesson_id in _jobs and _here(_jobs[lesson_id]):
        task = _jobs.pop(lesson_id)
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def stop() -> None:
    """Every job of this server stopped (it stops). Another's (the tests run several,
    each on its own event loop) is left to it."""
    tasks = [task for task in _jobs.values() if _here(task)]
    for id in [id for id, task in _jobs.items() if task in tasks]:
        del _jobs[id]
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)


def _here(task: asyncio.Task) -> bool:
    return task.get_loop() is asyncio.get_running_loop()


def _cancel(task: asyncio.Task) -> None:
    if _here(task):
        task.cancel()
        return
    with contextlib.suppress(RuntimeError):  # another server's (the tests'); its loop closed: so is the job
        task.get_loop().call_soon_threadsafe(task.cancel)


async def _make(lesson_id: str) -> None:
    await asyncio.sleep(DELAY)
    # The lesson as saved now (it may have changed, or gone, since)
    lesson = await asyncio.to_thread(lessons.get, lesson_id)
    directory = lessons.audio_dir(lesson_id)
    if lesson is None or directory is None or not wanted(lesson.voice):
        return
    rate = lesson.rate or settings.current().tts_rate
    voices = tts.spoken_voices(lesson.cards, lesson.voice, directory, rate, lesson.dictation or lesson.dictation_only)
    if not voices:
        return
    try:
        await tts.tts_voices(voices, directory, rate)
    except Exception as e:  # silent: the send tries again
        log.warning("Sounds ahead failed: %s", loggable(e))
