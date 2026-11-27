"""Small helpers shared by the tests: a coroutine run in a thread of its own, a plain
image as bytes, a Gemini client that only hears and answers."""

import asyncio
import contextlib
import io
import struct
import time
import types as py_types
import zlib
from concurrent.futures import ThreadPoolExecutor

from google.genai import types
from PIL import Image

from app import sounds


def run(coroutine):
    """asyncio.run, in a thread of its own: after the page tests, Playwright's event loop
    runs in the main thread, where asyncio.run would refuse to start."""
    with ThreadPoolExecutor(1) as pool:
        return pool.submit(asyncio.run, coroutine).result()


def plain_image(width, height, color="white", fmt="JPEG") -> bytes:
    """A plain `width` × `height` image of one `color`, saved as `fmt` (JPEG, PNG…)."""
    out = io.BytesIO()
    Image.new("RGB", (width, height), color).save(out, fmt)
    return out.getvalue()


def bomb_png(side=20_000) -> bytes:
    """A PNG claiming `side` × `side` pixels in a few dozen bytes (a decompression bomb:
    decoded, 20,000² would take 1.2 GB). Its header is all Pillow reads before refusing it."""

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    header = struct.pack(">IIBBBBB", side, side, 8, 2, 0, 0, 0)  # 8-bit RGB
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(b"")) + chunk(b"IEND", b"")


class HearingGemini:
    """A Gemini answering `text`; it keeps what it was sent: (contents, config) per call."""

    def __init__(self, text):
        self.text, self.calls = text, []
        self.aio = py_types.SimpleNamespace(models=py_types.SimpleNamespace(generate_content=self.generate))

    async def generate(self, model, contents, config):
        self.calls.append((contents, config))
        candidate = py_types.SimpleNamespace(finish_reason=types.FinishReason.STOP)
        return py_types.SimpleNamespace(usage_metadata=None, candidates=[candidate], text=self.text)


def sounds_ahead_gone(timeout: float = 5.0) -> bool:
    """No sound made ahead left (app/sounds.py): each job cancelled on its own loop, its
    server's (another thread), and again until none is left, not once: a page's last save,
    arriving as it closes, starts one after the page's own cancelling (stop_sounds_ahead),
    whose 5 s of quiet (sounds.DELAY) outlasted a mere wait (2026-11-26, on main and #821)."""
    deadline = time.monotonic() + timeout
    while sounds._jobs and time.monotonic() < deadline:
        for task in list(sounds._jobs.values()):
            with contextlib.suppress(RuntimeError):  # a server stopped since: its loop closed, so is its job
                task.get_loop().call_soon_threadsafe(task.cancel)
        time.sleep(0.05)
    return not sounds._jobs
