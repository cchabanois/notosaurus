"""Every AI call ever made, in data/ai-calls.json: what was spent, whatever became of
the lessons.

A lesson keeps its own calls, but deleting it must not make the money spent
disappear, and a generation that failed after the model answered (paid for, no
lesson) has nowhere else to go. Entries are only ever added.
"""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from pydantic import BaseModel

from notosaurus_core.calls import recording
from notosaurus_core.models import CallKind

from . import lessons, storage
from .models import AiCall, Lesson


class Entry(AiCall):
    lesson_id: str | None = None  # None: a generation that failed (no lesson), or a call for no lesson
    deck: str = ""  # the lesson's name at the time


def _path():
    return storage.data_dir() / "ai-calls.json"


# ai-calls.json's format; storage.migrate brings older files up to it
FORMAT = 1


def _load() -> list[Entry]:
    """The journal; the first time, filled with the calls the lessons already keep."""
    data = storage.read_json(_path())
    if data is not None:
        # Format 0 → 1: the bare list of calls, now under "calls"
        data = storage.migrate({"calls": data} if isinstance(data, list) else data, "ai-calls", FORMAT, {0: dict})
        return [Entry(**e) for e in data["calls"]]
    entries = []
    for summary in lessons.list_all():
        for call in summary.ai_calls:
            entries.append(Entry(**call.model_dump(), lesson_id=summary.id, deck=summary.deck))
    entries.sort(key=lambda e: e.at)
    _save(entries)
    return entries


def _save(entries: list[Entry]) -> None:
    storage.write_json(_path(), {"format": FORMAT, "calls": [e.model_dump() for e in entries]})


def _key(e: Entry) -> tuple:
    return e.lesson_id, e.at, e.kind, e.model, e.input_tokens, e.output_tokens


def add(calls: list[AiCall], lesson_id: str | None, deck: str = "") -> None:
    if not calls:
        return
    with storage.lock:
        entries = _load()
        known = {_key(e) for e in entries}
        new = [Entry(**c.model_dump(), lesson_id=lesson_id, deck=deck) for c in calls]
        _save([*entries, *(e for e in new if _key(e) not in known)])  # filled from the lessons just before


@dataclass
class Meter:
    """The AI calls made inside `metered`, and whom they are for."""

    calls: list[AiCall]
    lesson_id: str | None
    deck: str
    kept: bool = False  # the lesson keeps them already (saved with them)

    def kept_by(self, lesson: Lesson) -> None:
        """The calls were saved with this lesson (made, or made again, with them): counted
        for it, not added to it a second time."""
        self.lesson_id, self.deck, self.kept = lesson.id, lesson.deck, True


def _keep(meter: Meter) -> None:
    if meter.lesson_id and not meter.kept:
        lessons.add_ai_calls(meter.lesson_id, meter.calls)
    add(meter.calls, meter.lesson_id, meter.deck)


@asynccontextmanager
async def metered(kind: CallKind, lesson_id: str | None = None, deck: str = "") -> AsyncIterator[Meter]:
    """Record the AI calls made inside (llm.recording) and, on the way out, keep them
    with the lesson and in the costs: also when it failed after the AI answered (paid
    for). Without a lesson (or for a lesson not saved in the end), counted with none.
    Written in a worker thread, off the event loop."""
    with recording(kind) as calls:
        meter = Meter(calls, lesson_id, deck)
        try:
            yield meter
        finally:
            await asyncio.to_thread(_keep, meter)


class Totals(BaseModel):
    total: float  # US dollars, calls with a known cost
    deleted: float  # of it, for lessons deleted since
    failed: float  # of it, generations that failed
    estimated: bool  # some costs are estimates (not given by the service)
    unknown: int  # calls whose cost is unknown


def totals() -> Totals:
    with storage.lock:
        entries = _load()
    existing = {s.id for s in lessons.list_all()}
    known = [(e, e.cost) for e in entries if e.cost is not None]
    return Totals(
        total=round(sum(cost for _, cost in known), 6),
        deleted=round(sum(cost for e, cost in known if e.lesson_id and e.lesson_id not in existing), 6),
        failed=round(sum(cost for e, cost in known if e.lesson_id is None and e.kind == "extract"), 6),
        estimated=any(not e.exact and cost for e, cost in known),
        unknown=sum(1 for e in entries if e.cost is None),
    )
