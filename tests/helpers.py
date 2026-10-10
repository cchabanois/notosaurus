"""Small helpers shared by the tests: a coroutine run in a thread of its own, a plain
image as bytes, a Gemini client that only hears and answers."""

import asyncio
import io
import types as py_types
from concurrent.futures import ThreadPoolExecutor

from google.genai import types
from PIL import Image


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


class HearingGemini:
    """A Gemini answering `text`; it keeps what it was sent: (contents, config) per call."""

    def __init__(self, text):
        self.text, self.calls = text, []
        self.aio = py_types.SimpleNamespace(models=py_types.SimpleNamespace(generate_content=self.generate))

    async def generate(self, model, contents, config):
        self.calls.append((contents, config))
        candidate = py_types.SimpleNamespace(finish_reason=types.FinishReason.STOP)
        return py_types.SimpleNamespace(usage_metadata=None, candidates=[candidate], text=self.text)
