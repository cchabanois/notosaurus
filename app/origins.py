"""Only Notosaurus's own page changes something: what other websites can't do.

A website open in the parent's browser can send a form, or a request without a body, to
http://127.0.0.1:8000: its Host is allowed (hosts.py) and the computer itself needs no
token, so it would spend the AI keys, import lessons or unpair the phones. A browser
says where such a request comes from: its Origin header (another site's) or
Sec-Fetch-Site (cross-site). Those are refused for anything but reading (GET, HEAD,
OPTIONS). A request without them (curl, the phone app's own calls) still passes: a
browser always sends Origin with a cross-site POST.

The page's files also carry a Content-Security-Policy: scripts from the page itself only.
"""

import json
from urllib.parse import urlsplit

from . import hosts
from .errors import AppError

READING = {"GET", "HEAD", "OPTIONS"}
DEFAULT_PORTS = {"http": 80, "https": 443}

# What the page needs: its own scripts (Alpine.js evaluates its attributes: unsafe-eval), styles
# inline too (MathJax's, Alpine's :style), pictures and sounds made in the page (data:, blob:),
# pdf.js's worker. No other site's script, no javascript: link, no plugin, no frame around it.
PAGE_POLICY = (
    "default-src 'self'; script-src 'self' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: blob:; media-src 'self' data: blob:; font-src 'self' data:; "
    "connect-src 'self' data: blob:; worker-src 'self' blob:; object-src 'none'; base-uri 'none'; "
    "form-action 'self'; frame-ancestors 'none'"
)


def _endpoint(netloc: str, scheme: str) -> tuple[str, int | None] | None:
    """(name, port) of `netloc`, the port `scheme`'s when none is given; None if it can't be one."""
    try:
        parts = urlsplit(f"//{netloc}")
        return (parts.hostname or "").lower(), parts.port or DEFAULT_PORTS.get(scheme)
    except ValueError:
        return None


def same_origin(origin: str, host: str) -> bool:
    """`origin` (the Origin header) is the page Notosaurus served at `host` (the Host
    header), or the NOTOSAURUS_PUBLIC_URL a proxy serves it at."""
    parts = urlsplit(origin)
    if parts.scheme not in DEFAULT_PORTS or not parts.netloc or parts.path not in ("", "/"):
        return False  # "null" (a sandboxed frame, a file), anything not an origin
    theirs = _endpoint(parts.netloc, parts.scheme)
    if theirs is None:
        return False
    if theirs == _endpoint(host, parts.scheme):
        return True
    public = urlsplit(hosts.public_url() or "")
    return public.scheme == parts.scheme and theirs == _endpoint(public.netloc, public.scheme)


def allowed(method: str, headers: dict[bytes, bytes]) -> bool:
    if method in READING:
        return True
    if headers.get(b"sec-fetch-site", b"").decode("latin-1").lower() == "cross-site":
        return False
    origin = headers.get(b"origin")
    return origin is None or same_origin(origin.decode("latin-1"), headers.get(b"host", b"").decode("latin-1"))


class SameOriginOnly:
    """ASGI middleware: a change asked by another site gets 403; every answer the page's policy."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        if not allowed(scope["method"], dict(scope["headers"])):
            body = json.dumps({"detail": AppError("origin.not_allowed").detail()}).encode()
            headers = [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]
            await send({"type": "http.response.start", "status": 403, "headers": headers})
            return await send({"type": "http.response.body", "body": body})

        async def with_policy(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                if not any(name.lower() == b"content-security-policy" for name, _ in headers):  # an SVG's own
                    headers.append((b"content-security-policy", PAGE_POLICY.encode()))
                message = {**message, "headers": headers}
            await send(message)

        return await self.app(scope, receive, with_policy)
