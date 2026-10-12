"""What a lesson's cards take with them to Anki (a package or a send): the backs'
audio, the cards' pictures and the diagrams' images."""

import shutil
import tempfile
from pathlib import Path

from fastapi import BackgroundTasks

from notosaurus_core import diagrams, pictures, tts

from . import lessons, settings
from .models import ExportRequest, Lesson


async def card_audio(req: ExportRequest, background: BackgroundTasks) -> tuple[dict[str, Path], int]:
    """mp3 of the cards for an edge-tts voice: {what it says (tts.spoken): mp3} and the number of failures."""
    if not req.voice or tts.is_anki_locale(req.voice):
        return {}, 0
    # Saved lesson: mp3s go to its audio/ folder; otherwise a throwaway folder.
    directory = lessons.audio_dir(req.lesson_id) if req.lesson_id else None
    if directory is None:
        directory = Path(tempfile.mkdtemp(prefix="notosaurus-audio-"))
        background.add_task(shutil.rmtree, directory, ignore_errors=True)
    said = tts.spoken_backs(req.cards, req.dictation or req.dictation_only)
    audio, failures = await tts.tts_many(said, req.voice, directory, settings.current().tts_rate)
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
