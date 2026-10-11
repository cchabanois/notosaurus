"""The names Notosaurus answers to: an IP address, localhost, or NOTOSAURUS_PUBLIC_URL's.

A website open in the parent's browser can point its own name at 127.0.0.1 (DNS
rebinding): its scripts then reach Notosaurus as the computer itself, which needs
no token and, in the add-on, opens the settings. Such a request always carries the
site's name in its Host header: refusing every other name stops it. Phones reach
the computer by its IP address; Docker or a proxy give theirs in NOTOSAURUS_PUBLIC_URL.
"""

import ipaddress
import json
import logging
import os
import re
from urllib.parse import urlsplit

from .errors import AppError

log = logging.getLogger("notosaurus")

HOST_HEADER = re.compile(r"^[A-Za-z0-9.\-]+(:\d{1,5})?$|^\[[0-9A-Fa-f:.]+\](:\d{1,5})?$")


def public_host() -> str | None:
    url = os.environ.get("NOTOSAURUS_PUBLIC_URL", "").strip()
    return urlsplit(url).hostname if url else None


def allowed(host: str) -> bool:
    """`host`: the Host header, its port included."""
    if not HOST_HEADER.match(host):
        return False
    try:  # ValueError: brackets around no IPv6 address ("[1.2.3.4]"), a port over 65535
        parts = urlsplit(f"//{host}")
        name, port = parts.hostname or "", parts.port
    except ValueError:
        return False
    if port == 0:
        return False
    if name == "localhost" or name == public_host():
        return True
    try:
        ipaddress.ip_address(name)
    except ValueError:
        return False
    return True


class KnownHostsOnly:
    """ASGI middleware: every request (API, page files) with another Host gets 421."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket"):
            return await self.app(scope, receive, send)
        host = dict(scope["headers"]).get(b"host", b"").decode("latin-1")
        if allowed(host):
            return await self.app(scope, receive, send)
        log.warning("Request for %r refused: open Notosaurus by an IP address, or set NOTOSAURUS_PUBLIC_URL", host)
        if scope["type"] == "websocket":
            return await send({"type": "websocket.close", "code": 1008})
        body = json.dumps({"detail": AppError("host.not_allowed", host=host).detail()}).encode()
        headers = [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]
        await send({"type": "http.response.start", "status": 421, "headers": headers})
        await send({"type": "http.response.body", "body": body})
