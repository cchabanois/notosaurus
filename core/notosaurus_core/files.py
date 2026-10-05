"""Files: where the caches go (model prices, pictures, voice previews), and the
small file helpers the modules share.

The caches are under a folder the caller chooses with `configure` (the Notosaurus
app: its data/cache/); by default, under the system's temporary folder.
"""

import json
import os
import re
import tempfile
import unicodedata
from collections.abc import Callable
from pathlib import Path

_cache_root: Callable[[], Path] = lambda: Path(tempfile.gettempdir()) / "notosaurus-cache"  # noqa: E731


def configure(cache_dir: Callable[[], Path]) -> None:
    """Where the caches go: a function, so that the folder may change while running
    (the tests use a fresh one each)."""
    global _cache_root
    _cache_root = cache_dir


def cache_dir(*parts: str) -> Path:
    """A folder of the cache ("tts", "pictures"…), or the cache itself; not created."""
    return _cache_root().joinpath(*parts)


def slugify(text: str, max_length: int = 40) -> str:
    """ "Espagnol::Leçon 5 - La famille" → "espagnol-lecon-5-la-famille"."""
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")
    return slug[:max_length].rstrip("-")


def read_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def write_json(path: Path, data) -> None:
    """Write through a temporary file then rename, so a crash never leaves half a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
