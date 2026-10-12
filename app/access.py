"""Who may do what: the devices allowed to use Notosaurus, and which Anki profile sees
or changes which lesson."""

from fastapi import Request

from . import ankiconnect, lessons, settings
from .errors import AppError
from .models import Lesson

# The cookie a paired device keeps its token in (see routes/devices.py)
DEVICE_COOKIE = "notosaurus_key"


def is_local(request: Request) -> bool:
    """Request made on this computer itself (not from a phone, not relayed by a proxy)."""
    host = request.client.host if request.client else ""
    relayed = "x-forwarded-for" in request.headers or "forwarded" in request.headers
    return host in ("127.0.0.1", "::1") and not relayed


def paired(request: Request) -> bool:
    """Request from this computer or from a device given the token (cookie, or the QR
    code's ?k=)."""
    return (
        is_local(request)
        or settings.is_device_token(request.cookies.get(DEVICE_COOKIE))
        or settings.is_device_token(request.query_params.get("k"))
    )


def sees(profile: str | None, owner: str, shared: bool) -> bool:
    """A profile sees its own lessons, shared ones and lessons without owner; another
    profile's private lessons don't exist for it. Anki closed (no profile known): all."""
    return shared or not owner or profile is None or profile == owner


async def visible(owner: str, shared: bool) -> bool:
    """Whether the open profile sees a lesson: Anki is asked only for a private one."""
    return shared or not owner or sees(await ankiconnect.active_profile(), owner, shared)


async def lesson(id: str | None) -> Lesson | None:
    """The lesson, if the open Anki profile may see it (None without an id)."""
    found = lessons.get(id) if id else None
    if found is None:
        if id:
            raise AppError("lesson.not_found", 404)
        return None
    if not await visible(found.owner, found.shared):
        raise AppError("lesson.not_found", 404)
    return found


async def is_owner(lesson: Lesson) -> bool:
    """Only the profile that created a lesson changes it; lessons without owner are everyone's."""
    return not lesson.owner or await ankiconnect.active_profile() == lesson.owner


async def editable(id: str) -> Lesson:
    """The lesson, if the open Anki profile may change it: for the others, it's read-only
    (they can still read it, send it to their own Anki and export it)."""
    found = await lesson(id)
    if not await is_owner(found):
        raise AppError("lesson.read_only", 403, owner=found.owner)
    return found
