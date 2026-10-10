import shutil
import tempfile
from pathlib import Path

from fastapi import BackgroundTasks, Header, Request

from notosaurus_core import diagrams, pictures, tts

from .. import ankiconnect, i18n, lessons, settings
from ..errors import AppError
from ..models import ExportRequest, Lesson

STATIC_DIR = Path(__file__).parent.parent.parent / "static"
IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_IMAGES = 10


def page_lang(x_notosaurus_lang: str | None = Header(None)) -> str:
    """Language of the page making the request (sent by the page on every call)."""
    return i18n.resolve(x_notosaurus_lang) or i18n.DEFAULT


def pupil_lang(x_notosaurus_lang: str | None = Header(None)) -> str:
    """The pupil's language when the page says it ("" otherwise: no guess)."""
    return i18n.resolve(x_notosaurus_lang) or ""


async def _card_audio(req: ExportRequest, background: BackgroundTasks) -> tuple[dict[str, Path], int]:
    """mp3 of the card backs for an edge-tts voice: {back: mp3} and the number of failures."""
    if not req.voice or tts.is_anki_locale(req.voice):
        return {}, 0
    # Saved lesson: mp3s go to its audio/ folder; otherwise a throwaway folder.
    directory = lessons.audio_dir(req.lesson_id) if req.lesson_id else None
    if directory is None:
        directory = Path(tempfile.mkdtemp(prefix="notosaurus-audio-"))
        background.add_task(shutil.rmtree, directory, ignore_errors=True)
    audio, failures = await tts.tts_many(tts.spoken_backs(req.cards), req.voice, directory, settings.current().tts_rate)
    tts.prune(directory, set(audio.values()))
    return audio, failures


def _pictures(req: ExportRequest, lesson: Lesson | None) -> dict[int, Path]:
    """The picture of each picture card (index in req.cards → file), from the saved lesson."""
    folder = lessons.folder(lesson.id) if lesson else None
    if folder is None:
        return {}
    pictures.prune(folder / "images", req.cards)  # pictures of cards gone (removed, regenerated)
    found = {i: folder / "images" / card.picture for i, card in enumerate(req.cards) if card.picture}
    return {i: path for i, path in found.items() if pictures.NAME.match(path.name) and path.is_file()}


def _diagram_images(req: ExportRequest, lesson: Lesson | None) -> dict[int, tuple[Path, list[float] | None]]:
    """The diagram image of each diagram card (index in req.cards → path and crop),
    from the saved lesson's photos. Without a saved lesson, there is no photo to show."""
    folder = lessons.folder(lesson.id) if lesson else None
    if folder is None:
        return {}
    frames = {f.page: f.box for f in (req.frames if req.frames is not None else lesson.frames)}
    images, used = {}, set()
    for i, card in enumerate(req.cards):
        photo = lessons.photo_path(lesson.id, card.mask.page) if card.mask else None
        if photo and photo.is_file():
            page = card.mask.page
            box = diagrams.crop(frames.get(page), [c.mask for c in req.cards if c.mask and c.mask.page == page])
            images[i] = (diagrams.page_image(folder / "images", photo, box), box)
            used.add(images[i][0])
    diagrams.prune(folder / "images", used)
    return images


def _sees(profile: str | None, owner: str, shared: bool) -> bool:
    """A profile sees its own lessons, shared ones and lessons without owner; another
    profile's private lessons don't exist for it. Anki closed (no profile known): all."""
    return shared or not owner or profile is None or profile == owner


async def _visible(owner: str, shared: bool) -> bool:
    """Whether the open profile sees a lesson: Anki is asked only for a private one."""
    return shared or not owner or _sees(await ankiconnect.active_profile(), owner, shared)


async def _lesson(id: str | None) -> Lesson | None:
    """The lesson, if the open Anki profile may see it."""
    lesson = lessons.get(id) if id else None
    if lesson is None:
        if id:
            raise AppError("lesson.not_found", 404)
        return None
    if not await _visible(lesson.owner, lesson.shared):
        raise AppError("lesson.not_found", 404)
    return lesson


async def _is_owner(lesson: Lesson) -> bool:
    """Only the profile that created a lesson changes it; lessons without owner are everyone's."""
    return not lesson.owner or await ankiconnect.active_profile() == lesson.owner


async def _editable(id: str) -> Lesson:
    """The lesson, if the open Anki profile may change it: for the others, it's read-only
    (they can still read it, send it to their own Anki and export it)."""
    lesson = await _lesson(id)
    if not await _is_owner(lesson):
        raise AppError("lesson.read_only", 403, owner=lesson.owner)
    return lesson


def is_local(request: Request) -> bool:
    """Request made on this computer itself (not from a phone, not relayed by a proxy)."""
    host = request.client.host if request.client else ""
    relayed = "x-forwarded-for" in request.headers or "forwarded" in request.headers
    return host in ("127.0.0.1", "::1") and not relayed
