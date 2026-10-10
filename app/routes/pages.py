import io
import json
import socket

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

from .. import i18n, settings
from ..version import VERSION
from .common import MAX_IMAGES, STATIC_DIR, is_local
from .devices import _paired

router = APIRouter()


@router.get("/api/lang")
def lang() -> dict:
    """In the Anki add-on: Anki's language (English if we don't have it).
    Otherwise None: the page uses the browser's language. A language picked on
    the page itself (kept in the browser) wins over both."""
    return {
        "lang": i18n.anki_language(),
        "available": i18n.available(),
        "names": {code: i18n.get(code, "meta.name", code) for code in i18n.available()},
    }


@router.get("/api/config")
def config() -> dict:
    """Settings the main page needs (no secrets, no password)."""
    s = settings.current()
    # Claude places diagram masks less precisely (too tight on handwriting): say so in the review.
    loose_boxes = s.llm == "anthropic" or "claude" in s.model_for_provider().lower()
    return {
        "version": VERSION,
        "diagram_warning": loose_boxes,
        "max_photos": MAX_IMAGES,
        "card_helps": s.card_helps,
        "configured": settings.configured(s),
        "computer_name": socket.gethostname(),  # the Android app names the computer it uses
    }


@router.get("/manifest.json")
def manifest(request: Request) -> JSONResponse:
    """The home screen icon opens the page with the token: on an iPhone, an icon doesn't
    share Safari's cookies."""
    data = json.loads((STATIC_DIR / "manifest.json").read_text(encoding="utf-8"))
    if _paired(request) and not is_local(request):
        data["start_url"] = f"/?k={settings.device_token()}"
    return JSONResponse(data, media_type="application/manifest+json", headers={"Cache-Control": "no-cache"})


@router.get("/api/qr")
def qr(text: str) -> Response:
    """QR code (PNG) of a text, e.g. the address to open on the phone."""
    import segno

    out = io.BytesIO()
    segno.make(text[:500], error="m").save(out, kind="png", scale=8, border=2)
    return Response(out.getvalue(), media_type="image/png")
