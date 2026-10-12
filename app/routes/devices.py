import time

from fastapi import Request
from fastapi.responses import JSONResponse

from .. import settings
from ..access import DEVICE_COOKIE, is_local, paired
from ..errors import AppError

# --- Paired devices only -----------------------------------------------------
# On the Wi-Fi, anyone could otherwise use Notosaurus: spend the AI keys, delete lessons
# and their cards in Anki. The computer itself always may; other devices need the
# token, given once by the QR code (…/?k=<token>) and kept in a cookie. Without HTTPS
# this stops whoever finds the address and other websites' requests (the cookie is
# SameSite=Strict), not someone listening to the Wi-Fi.
UNPAIRED_ALLOWED = {"/api/lang", "/api/qr"}  # the page telling how to pair, the QR code
# The settings have their own protection (the computer only in the add-on, else the
# admin password, sent in a header other sites can't add): they give the QR code.
UNPAIRED_PREFIXES = ("/api/admin",)


# When a phone last scanned the QR code (this run only): the setup assistant sees it come
last_paired: float | None = None


async def paired_devices_only(request: Request, call_next):
    path = request.url.path
    allowed = path in UNPAIRED_ALLOWED or path.startswith(UNPAIRED_PREFIXES)
    try:
        is_paired = paired(request)
    except AppError as e:  # e.g. settings from a newer Notosaurus: said, as any error
        return JSONResponse(status_code=e.status, content={"detail": e.detail()})
    if path.startswith("/api/") and not allowed and not is_paired:
        return JSONResponse(status_code=401, content={"detail": AppError("device.not_paired").detail()})
    response = await call_next(request)
    given = request.query_params.get("k")
    if given and is_paired and request.cookies.get(DEVICE_COOKIE) != given and settings.is_device_token(given):
        if not is_local(request):
            global last_paired  # the setup assistant waits for the phone
            last_paired = time.time()
        response.set_cookie(
            DEVICE_COOKIE,
            given,
            max_age=400 * 24 * 3600,  # the longest browsers keep a cookie
            httponly=True,
            samesite="strict",
            secure=request.url.scheme == "https",
        )
    return response
