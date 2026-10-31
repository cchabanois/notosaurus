"""The lesson in progress, kept as the page changes it (static/app-draft.js): found again when
the page opens again, after leaving it (the settings, a link) or the browser closing it.

data/draft/
  draft.json   what the page said of it: its prompt, the open lesson, its photos' texts
  photo-N.jpg  its photos, in order (before the lesson is made)
"""

import json
import shutil
from pathlib import Path

from . import storage
from .errors import AppError

MAX_TEXT = 200_000  # the draft's JSON: a prompt and its photos' PDF texts
MAX_PHOTO_BYTES = 10 * 1024 * 1024  # a photo as the page prepared it weighs a few hundred KB


def _dir() -> Path:
    return storage.data_dir() / "draft"


def get() -> dict:
    """What the page said, and how many photos it has; {} when there is none."""
    path = _dir() / "draft.json"
    if not path.is_file():
        return {}
    try:
        draft = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return {}
    return {**draft, "photos": len(list(_dir().glob("photo-*.jpg")))} if isinstance(draft, dict) else {}


def photo(n: int) -> Path | None:
    path = _dir() / f"photo-{n}.jpg"
    return path if n >= 1 and path.is_file() else None


def save(text: str, photos: list[bytes] | None, max_photos: int) -> None:
    """`text`: the draft's JSON (an object); `photos`: all of them, replacing those kept
    (None: kept as they are)."""
    if len(text) > MAX_TEXT:
        raise AppError("draft.too_large", 413)
    try:
        draft = json.loads(text)
    except ValueError:
        raise AppError("draft.invalid", 400) from None
    if not isinstance(draft, dict):
        raise AppError("draft.invalid", 400)
    if photos is not None and (len(photos) > max_photos or any(len(p) > MAX_PHOTO_BYTES for p in photos)):
        raise AppError("draft.too_large", 413)
    with storage.lock:
        folder = _dir()
        folder.mkdir(parents=True, exist_ok=True)
        if photos is not None:
            for old in folder.glob("photo-*.jpg"):
                old.unlink()
            for n, data in enumerate(photos, 1):
                (folder / f"photo-{n}.jpg").write_bytes(data)
        storage.write_json(folder / "draft.json", draft)


def clear() -> None:
    with storage.lock:
        shutil.rmtree(_dir(), ignore_errors=True)
