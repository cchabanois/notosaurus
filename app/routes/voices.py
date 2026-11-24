from typing import Annotated

from fastapi import APIRouter, Query, Request
from fastapi.responses import FileResponse

from notosaurus_core import tts
from notosaurus_core.models import Card

from .. import lessons, settings
from ..errors import AppError

router = APIRouter()


# --- Voices ----------------------------------------------------------------


@router.get("/api/voices")
async def list_voices() -> list[dict]:
    try:
        return await tts.voices()
    except Exception as e:
        raise AppError("tts.voices_unavailable", 502, detail=str(e)) from e


@router.get("/api/voices/for")
async def voice_for(language: str) -> dict:
    """The voice a lesson gets for a language ("es-ES", "cmn-CN"): as a lesson made with the
    "auto" voice gets it (tts.voice_for: the one chosen in the settings first); "" none."""
    return {"voice": await tts.voice_for(language, settings.current().voices)}


@router.get("/api/tts")
async def preview(
    request: Request,
    text: str,
    voice: str,
    lesson: str | None = None,
    rate: Annotated[str, Query(pattern=r"^([+-]\d{1,2}%)?$")] = "",
) -> FileResponse:
    """Listen to a text, at the lesson's `rate` (none: the settings'): stored in the lesson's
    audio/ folder when a lesson is given (so the export reuses it), in the preview cache otherwise.
    A GET that writes: never for another site (an <audio> of its page: Sec-Fetch-Site), as a
    change it asks is refused (origins.py); the page's own sounds are same-origin."""
    if request.headers.get("sec-fetch-site", "").lower() == "cross-site":
        raise AppError("origin.not_allowed", 403)
    if tts.is_anki_locale(voice):
        raise AppError("tts.no_preview_for_anki_locale")
    directory = lessons.audio_dir(lesson) if lesson else None
    said, rate = text[:600], rate or settings.current().tts_rate  # lines of 200 at most
    if lesson and not tts.is_edge_voice(voice) and (saved := lessons.get(lesson)):
        # A card's voice of the phone's: its sound kept in the lesson, else the lesson's voice
        voice = tts.card_voice(Card(front="", back="", voice=voice), saved.voice, said, directory, rate)
    try:
        path = await tts.tts(said, voice, directory, rate)
    except Exception as e:
        raise AppError("tts.failed", 502, detail=str(e)) from e
    return FileResponse(path, media_type="audio/mpeg")
