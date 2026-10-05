"""Plain-file storage: everything lives under NOTOSAURUS_DATA (default ./data).

data/
  prompts.json
  lessons/<yyyy-mm-dd-deck-slug>/lesson.json, page-N.jpg, audio/*.mp3
  cache/                model prices, pictures, voice previews (notosaurus_core's), safe to delete
"""

import os
import threading
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from notosaurus_core import files
from notosaurus_core.files import read_json, slugify, write_json  # noqa: F401

from .errors import AppError

# Endpoints run in a thread pool: serialize read-modify-write cycles.
lock = threading.RLock()


def data_dir() -> Path:
    path = Path(os.environ.get("NOTOSAURUS_DATA", "data"))
    path.mkdir(parents=True, exist_ok=True)
    return path


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class DataTooNew(AppError):
    """Data written by a newer Notosaurus: not read, so this older one can't damage it."""

    status = 409

    def __init__(self, what: str, version: int, known: int):
        super().__init__("data.too_new", what=what)
        self.detail_text = f"{what}: format {version}, this Notosaurus knows up to {known}"


def migrate(data: dict, what: str, current: int, steps: dict[int, Callable[[dict], dict]]) -> dict:
    """Bring data read from a file up to the `current` format, one step at a time:
    steps[n] turns format n into n + 1. Files without "format" are format 0 (written
    before formats). Data from a newer format is refused (DataTooNew)."""
    version = data.get("format", 0)
    if not isinstance(version, int) or version > current:
        raise DataTooNew(what, version, current)
    while version < current:
        data = steps[version](data)
        version += 1
    return {**data, "format": current}


files.configure(lambda: data_dir() / "cache")  # notosaurus_core's caches go to data/cache/
