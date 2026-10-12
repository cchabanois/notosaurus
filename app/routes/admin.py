import base64
import os
import time

from fastapi import APIRouter, Depends, Header, Query, Request

from notosaurus_core import llm, pictures, recommended
from notosaurus_core.llm import check, list_models

from .. import ankiconnect, lesson_notes, lessons, settings, usage
from ..access import is_local
from ..attempts import Attempts
from ..errors import AppError
from ..models import AdminPassword, Lesson, LessonAccess, LessonSummary, SettingsUpdate
from . import devices

router = APIRouter()


# --- Admin -----------------------------------------------------------------


TEST_PICTURE = "a giraffe"  # the settings' picture test: a familiar animal, drawn as on a card


attempts = Attempts()  # wrong passwords, per address: guessing is slowed down


def _check_password(request: Request, password: str | None, code: str) -> None:
    """The admin password, or `code` (401); a locked-out address isn't even checked.
    On the computer itself, never locked out and failures don't count: a shared address
    (Docker NAT, Tailscale) or a neighbour guessing must not lock the parent out."""
    if is_local(request):
        if not settings.check_password(password):
            raise AppError(code, 401)
        return
    address = request.client.host if request.client else ""
    if wait := attempts.wait(address):
        raise AppError("admin.too_many_attempts", 429, seconds=wait)
    if not settings.check_password(password):
        if password:  # a page without the password yet (no header) isn't guessing
            attempts.failed(address)
        raise AppError(code, 401)
    attempts.succeeded(address)


def require_admin(request: Request, x_admin_password: str | None = Header(None)) -> None:
    # In the Anki add-on, settings are opened on the computer (Tools → Notosaurus →
    # Settings): API keys never cross the Wi-Fi and phones can't change anything.
    if settings.embedded():
        if not is_local(request):
            raise AppError("admin.local_only", 403)
        return
    _check_password(request, x_admin_password, "admin.password_required")


def _settings_view() -> dict:
    """Current settings for the admin page, API keys masked."""
    current = settings.current()
    s = current.model_dump()
    for field in settings.SECRET_FIELDS:
        s[field] = settings.masked(s[field])
    return {
        **s,
        "providers": settings.PROVIDERS,
        "default_models": settings.DEFAULT_MODELS,
        "recommended": recommended.view(),  # per service, in order: the first is the default
        "embedded": settings.embedded(),
        # The image model used when none is set: from the saved keys
        # Who draws the pictures now, and what "same as the cards" means here
        "pictures": {
            "service": pictures.service(current),
            "model": pictures.model(current),
            "cards_draw": current.llm in pictures.DEFAULT_MODELS,
            "default_models": pictures.DEFAULT_MODELS,
        },
    }


@router.get("/api/admin")
def admin_status(request: Request) -> dict:
    """What the admin page must do: ask for a password, or explain it only opens on the computer."""
    embedded = settings.embedded()
    return {
        "password_set": settings.password_is_set(),
        "password_needed": not embedded,
        "allowed": not embedded or is_local(request),
    }


@router.post("/api/admin/password", status_code=204)
def admin_password(body: AdminPassword, request: Request) -> None:
    """First visit: create the password. Afterwards: change it (current one required)."""
    if settings.embedded():  # no password in the add-on: the settings only open on the computer
        raise AppError("admin.local_only", 403)
    if settings.password_is_set():
        _check_password(request, body.current, "admin.wrong_password")
    settings.set_password(body.new)


@router.get("/api/admin/settings", dependencies=[Depends(require_admin)])
def admin_settings() -> dict:
    return _settings_view()


@router.put("/api/admin/settings", dependencies=[Depends(require_admin)])
def admin_save_settings(changes: SettingsUpdate) -> dict:
    settings.save(changes.model_dump())
    return _settings_view()


@router.post("/api/admin/models", dependencies=[Depends(require_admin)])
async def admin_models() -> dict:
    """Models of the saved OpenAI-compatible service, to fill the model suggestions."""
    return await list_models(settings.current())


@router.post("/api/admin/test", dependencies=[Depends(require_admin)])
async def admin_test() -> dict:
    """Check the saved provider, model and key: can it read an image and answer in JSON?"""
    s = settings.current()
    start = time.monotonic()
    result = await check(s)
    return {"llm": s.llm, "model": s.model_for_provider(), "seconds": round(time.monotonic() - start, 1), **result}


@router.post("/api/admin/pictures/models", dependencies=[Depends(require_admin)])
async def admin_picture_models() -> dict:
    """The drawing service's image models, listed by the service (free)."""
    return {"service": pictures.service(settings.current()), "models": await pictures.image_models(settings.current())}


@router.post("/api/admin/pictures/test", dependencies=[Depends(require_admin)])
async def admin_picture_test() -> dict:
    """Draw one picture with the saved service and model (a few cents): shown with its cost."""
    s = settings.current()
    start = time.monotonic()
    with llm.recording("picture") as calls:
        jpeg = pictures.card_size(await pictures.draw(s, TEST_PICTURE))
    known = [c.cost for c in calls if c.cost is not None]
    return {
        "service": pictures.service(s),
        "model": pictures.model(s),
        "seconds": round(time.monotonic() - start, 1),
        "cost": sum(known) if known else None,
        "image": "data:image/jpeg;base64," + base64.b64encode(jpeg).decode(),
    }


@router.get("/api/admin/lessons", dependencies=[Depends(require_admin)])
async def admin_lessons() -> dict:
    """Every lesson, whoever owns it, and Anki's profiles (None: Anki not reachable)."""
    return {"lessons": lessons.list_all(), "profiles": await ankiconnect.profiles(), "costs": usage.totals()}


@router.put("/api/admin/lessons/{id}", dependencies=[Depends(require_admin)])
def admin_lesson_access(id: str, access: LessonAccess) -> LessonSummary:
    """Give a lesson to another profile (or to nobody), share it or not."""
    lesson = lessons.set_access(id, access.owner, access.shared)
    if lesson is None:
        raise AppError("lesson.not_found", 404)
    return LessonSummary(card_count=len(lesson.cards), **lesson.model_dump(exclude={"cards"}))


def _any_lesson(id: str) -> Lesson:
    lesson = lessons.get(id)
    if lesson is None:
        raise AppError("lesson.not_found", 404)
    return lesson


@router.get("/api/admin/lessons/{id}/anki-notes", dependencies=[Depends(require_admin)])
async def admin_lesson_anki_notes(id: str) -> dict:
    found = await lesson_notes.find(_any_lesson(id))
    return {"available": found["available"], "count": found["count"]}


@router.delete("/api/admin/lessons/{id}", dependencies=[Depends(require_admin)])
async def admin_delete_lesson(id: str, in_anki: bool = Query(False, alias="anki")) -> dict:
    return await lesson_notes.delete_lesson(_any_lesson(id), in_anki)


def lan_address() -> str:
    """This computer's address on the local network, as phones reach it."""
    import socket

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))  # no packet is sent
            return s.getsockname()[0]
    except OSError:
        return "localhost"


@router.get("/api/admin/phone", dependencies=[Depends(require_admin)])
def admin_phone(request: Request) -> dict:
    """The link that pairs a phone (in the QR code): this computer's address and the token.
    NOTOSAURUS_PUBLIC_URL gives the address when Notosaurus can't see it (Docker, a proxy)."""
    base = os.environ.get("NOTOSAURUS_PUBLIC_URL", "").strip().rstrip("/")
    if not base:
        port = request.url.port or (443 if request.url.scheme == "https" else 80)
        host = lan_address() if is_local(request) else request.url.hostname
        base = f"{request.url.scheme}://{host}:{port}"
    return {"url": f"{base}/?k={settings.device_token()}", "paired_at": devices.last_paired}


@router.post("/api/admin/phone/unpair", dependencies=[Depends(require_admin)])
def admin_unpair(request: Request) -> dict:
    """A new token: every phone must scan the QR code again (one was lost, lent…)."""
    settings.new_device_token()
    return admin_phone(request)
