"""What a lesson's cards take with them to Anki (a package or a send): the backs'
audio, the cards' pictures and the diagrams' images."""

import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path

from fastapi import BackgroundTasks

from notosaurus_core import diagrams, pictures, tts

from . import lessons, settings, sounds
from .models import ExportRequest, Lesson


async def card_audio(
    req: ExportRequest, background: BackgroundTasks, on_sound: Callable[[int, int], None] | None = None
) -> tuple[dict[str, Path], int]:
    """mp3 of the cards for an edge-tts voice: {what it says (tts.spoken): mp3} and the number of failures.
    `on_sound`: told (done, total) first then as each sound is done, for the page's progress."""
    if not sounds.wanted(req.voice):
        return {}, 0
    await sounds.settle(req.lesson_id)  # the sounds being made ahead: made here instead
    # Saved lesson: mp3s go to its audio/ folder; otherwise a throwaway folder.
    directory = lessons.audio_dir(req.lesson_id) if req.lesson_id else None
    if directory is None:
        directory = Path(tempfile.mkdtemp(prefix="notosaurus-audio-"))
        background.add_task(shutil.rmtree, directory, ignore_errors=True)
    rate = req.rate or settings.current().tts_rate
    voices = tts.spoken_voices(req.cards, req.voice, directory, rate, req.dictation or req.dictation_only)
    total, done = len(voices), 0

    def one_done() -> None:
        nonlocal done
        done += 1
        if on_sound:
            on_sound(done, total)

    if on_sound and total:
        on_sound(0, total)
    audio, failures = await tts.tts_voices(voices, directory, rate, on_done=one_done)
    tts.prune(directory, set(audio.values()))
    return audio, failures


def card_pictures(req: ExportRequest, lesson: Lesson | None) -> dict[int, Path]:
    """The picture of each picture card (index in req.cards → file), from the saved lesson."""
    folder = lessons.folder(lesson.id) if lesson else None
    if folder is None:
        return {}
    pictures.prune(folder / "images", req.cards)  # pictures of cards gone (removed, regenerated)
    found = {i: folder / "images" / card.picture for i, card in enumerate(req.cards) if card.picture}
    return {i: path for i, path in found.items() if pictures.NAME.match(path.name) and path.is_file()}


def diagram_images(req: ExportRequest, lesson: Lesson | None) -> dict[int, tuple[Path, list[float] | None]]:
    """The diagram image of each diagram card (index in req.cards → path and crop),
    from the saved lesson's photos. Without a saved lesson, there is no photo to show."""
    folder = lessons.folder(lesson.id) if lesson else None
    if lesson is None or folder is None:
        return {}
    frames = {f.page: f.box for f in (req.frames if req.frames is not None else lesson.frames)}
    images, used = {}, set()
    for i, card in enumerate(req.cards):
        if card.mask is None:
            continue
        page = card.mask.page
        photo = lessons.photo_path(lesson.id, page)
        if photo and photo.is_file():
            box = diagrams.crop(frames.get(page), [c.mask for c in req.cards if c.mask and c.mask.page == page])
            images[i] = (diagrams.page_image(folder / "images", photo, box), box)
            used.add(images[i][0])
    diagrams.prune(folder / "images", used)
    return images
