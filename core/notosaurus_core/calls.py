"""What every AI call shares: the photos sent (Image), the errors the page translates
(ExtractionError), each call recorded with its model, tokens and cost (recording,
record), and the cards read as the AI writes them (CardStream, OnCard)."""

import json
import re
from collections.abc import Awaitable, Callable, Iterator
from contextlib import contextmanager, suppress
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime

from . import prices
from .config import AIConfig
from .errors import AppError
from .models import AiCall

# The AI calls of the request being handled (kind, list), set by `recording`.
_recording: ContextVar[tuple[str, list[AiCall]] | None] = ContextVar("notosaurus_ai_calls", default=None)


@contextmanager
def recording(kind: str) -> Iterator[list[AiCall]]:
    """Collect the AI calls made inside, with their model, tokens and cost, to keep
    them with the lesson ("extract" or "revise"). Calls that failed after the model
    answered are kept too: they are paid for."""
    calls: list[AiCall] = []
    token = _recording.set((kind, calls))
    try:
        yield calls
    finally:
        _recording.reset(token)


async def record(
    s: AIConfig,
    provider: str,
    model: str,
    input_tokens: int | None,
    output_tokens: int | None,
    cost: float | None = None,
) -> None:
    """Note an answered call; without a cost from the service, estimate it."""
    current = _recording.get()
    if current is None:  # e.g. the settings page's connection test
        return
    kind, calls = current
    exact = cost is not None
    if cost is None and input_tokens is not None:
        cost = await prices.estimate(s.llm, model, input_tokens, output_tokens or 0)
    calls.append(
        AiCall(
            at=datetime.now().isoformat(timespec="seconds"),
            kind=kind,
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=cost,
            exact=exact,
        )
    )


@dataclass
class Image:
    data: bytes
    media_type: str  # image/jpeg, image/png, image/webp or image/gif; or a recording (transcribe)


# Told each card as soon as the AI has written it ({"front", "back"…} as the AI fills
# them), or None: the cards told so far are dropped (another model starts again)
OnCard = Callable[[dict | None], Awaitable[None]]


class ExtractionError(AppError):
    """The AI provider failed; `code` is translated by the page (errors.* keys)."""

    status = 502


class CardStream:
    """The cards of a JSON answer being written ({"cards": [{…}, {…}…], …}): fed the
    text as it comes, it gives each card once it is complete."""

    def __init__(self) -> None:
        self.text = ""
        self.at: int | None = None  # where the next card may start, once "cards": [ is read

    def feed(self, more: str) -> list[dict]:
        self.text += more
        if self.at is None:
            found = re.search(r'"cards"\s*:\s*\[', self.text)
            if not found:
                return []
            self.at = found.end()
        cards = []
        while (end := self._object_end()) is not None:
            start = self.text.index("{", self.at)
            with suppress(ValueError):  # not a card after all: skipped
                cards.append(json.loads(self.text[start : end + 1]))
            self.at = end + 1
        return cards

    def _object_end(self) -> int | None:
        """Where the next card's object closes; None when it isn't complete yet (or the
        list is over)."""
        i = self.at
        while i < len(self.text) and self.text[i] in " \t\r\n,":
            i += 1
        if i >= len(self.text) or self.text[i] != "{":
            return None
        depth, quoted, escaped = 0, False, False
        for j in range(i, len(self.text)):
            c = self.text[j]
            if quoted:
                if escaped:
                    escaped = False
                elif c == "\\":
                    escaped = True
                elif c == '"':
                    quoted = False
            elif c == '"':
                quoted = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return j
        return None
