"""Free pictures for a card, found rather than drawn: Wikimedia Commons (real things:
paintings, places, people, species), Openverse, and Pixabay (everyday things) with a
key — the relay's own; the computer has none.

Only licences that ask for no credit: public domain, CC0, Pixabay's. Searched with the
card's subject (English, as the AI writes it). The previews come as data (nothing the
page loads from elsewhere, no hotlinking); the one chosen is fetched again by its
source and id, never by an address the client gives, and made card size.

For pupils: Openverse leaves mature images out, Pixabay is asked with SafeSearch, and
Commons, which has neither, loses any file whose name or categories say what pupils
shouldn't see; the user always picks the picture.
"""

import asyncio
import base64
import io
import logging
import re
import time
from collections.abc import AsyncIterator, Awaitable
from itertools import zip_longest
from typing import Any, Literal
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel

from . import images, llm, pictures
from .config import AIConfig
from .errors import AppError, loggable
from .models import PictureSource

log = logging.getLogger("notosaurus")
_transport: httpx.AsyncBaseTransport | None = None  # tests plug fake services here

AGENT = "Notosaurus (https://github.com/cchabanois/notosaurus)"  # Wikimedia asks for one
COMMONS = "https://commons.wikimedia.org/w/api.php"
OPENVERSE = "https://api.openverse.org/v1/images/"
PIXABAY = "https://pixabay.com/api/"
# Where the pictures themselves are fetched from: nowhere else
HOSTS = {
    "commons": ("upload.wikimedia.org", "thumb.wikimedia.org"),
    "openverse": ("api.openverse.org",),
    "pixabay": ("pixabay.com", "cdn.pixabay.com"),
}

PER_SOURCE = 4
MAX_RESULTS = 8
SORT_PER_SOURCE = 6  # more to choose from when the AI keeps only those that fit
MAX_SORTED = 12  # the pictures the AI kept, at most (all sources)
SOURCE_WAIT = 5  # s: a source slower than that (Openverse, at times 10 s) is left out of the search
PREVIEW = 200  # px: a choice in the grid
TIMEOUT = 10
CACHE_S = 24 * 3600  # Pixabay asks for its answers to be kept a day: the same for all
MAX_BYTES = 15 * 1024 * 1024

# A file on Commons whose name or categories hold one of these is left out
UNSUITABLE = re.compile(
    r"nud(e|ity)|naked|sex|porn|erotic|genital|penis|vagina|breast|topless|lingerie|corpse|dead body|"
    r"gore|wound|execution|lynch|torture|suicide|swastika|drug",
    re.IGNORECASE,
)

Source = Literal["commons", "openverse", "pixabay"]


class Found(BaseModel):
    source: Source
    id: str  # the source's own (a Commons file's title, an Openverse UUID, a Pixabay number)
    title: str
    preview: str  # data:image/jpeg;base64,…
    licence: str  # "Public domain", "CC0", "Pixabay"
    page: str = ""  # its page at its source


_cache: dict[tuple, tuple[float, Any]] = {}  # key → (when, a source's answer)


def _cached(key: tuple) -> Any:
    hit = _cache.get(key)
    return hit[1] if hit and time.monotonic() - hit[0] < CACHE_S else None


def _keep(key: tuple, value):
    if len(_cache) > 2000:
        _cache.clear()
    _cache[key] = (time.monotonic(), value)
    return value


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=TIMEOUT, transport=_transport, headers={"User-Agent": AGENT})


async def search(
    subject: str, pixabay_key: str = "", per_source: int = PER_SOURCE, most: int = MAX_RESULTS
) -> list[Found]:
    """Up to `most` free pictures of `subject` (English), `per_source` from each, the
    sources taking turns. A source that fails, finds nothing or is too slow (SOURCE_WAIT)
    leaves the others."""
    subject = _subject(subject)
    async with _client() as client:
        found = await asyncio.gather(*_sources(client, subject, pixabay_key, per_source), return_exceptions=True)
    lists = [f for f in found if isinstance(f, list)]
    if not lists:
        raise AppError("picture.search_failed")
    return [item for row in zip_longest(*lists) for item in row if item][:most]


async def sorted_as_found(
    s: AIConfig, subject: str, context: str = "", pixabay_key: str = ""
) -> AsyncIterator[list[Found]]:
    """Free pictures of `subject` (English) to choose from, each source's as soon as it
    answers (within SOURCE_WAIT), the cards' AI keeping those that show it, the best first
    (it sees their previews; as they came when it can't sort them): MAX_SORTED at most in
    all. picture.search_failed when every source failed. `context`: the card,
    "front → back"."""
    subject = _subject(subject)
    async with _client() as client:

        async def kept(source: Awaitable[list[Found]]) -> list[Found]:
            found = await source
            return await _sorted(s, found, subject, context) if found else []

        tasks = [asyncio.ensure_future(kept(f)) for f in _sources(client, subject, pixabay_key, SORT_PER_SOURCE)]
        failed, left = 0, MAX_SORTED
        try:
            for done in asyncio.as_completed(tasks):
                try:
                    batch = (await done)[:left]
                except Exception:  # a source that fails or is too slow leaves the others
                    failed += 1
                    continue
                if batch:
                    left -= len(batch)
                    yield batch
            if failed == len(tasks):
                raise AppError("picture.search_failed")
        finally:
            for task in tasks:
                task.cancel()  # the client went away: the sources and the AI stop


async def sorted_search(s: AIConfig, subject: str, context: str = "", pixabay_key: str = "") -> list[Found]:
    """sorted_as_found's pictures, all at once."""
    return [f async for batch in sorted_as_found(s, subject, context, pixabay_key) for f in batch]


def _subject(subject: str) -> str:
    subject = " ".join(subject.split())[:200]
    if not subject:
        raise AppError("picture.no_subject")
    return subject


def _sources(client: httpx.AsyncClient, subject: str, pixabay_key: str, per_source: int) -> list:
    """Each source's pictures (awaitables of list[Found])."""
    listed = [_pixabay(client, subject, pixabay_key)] if pixabay_key else []
    listed += [_openverse(client, subject), _commons(client, subject)]
    return [_with_previews(client, found, per_source) for found in listed]


async def _with_previews(client: httpx.AsyncClient, listed: Awaitable[list], per_source: int) -> list[Found]:
    """A source's first `per_source` pictures, with their previews (none: left out),
    within SOURCE_WAIT."""

    async def found() -> list[Found]:
        chosen = (await listed)[:per_source]
        previews = await asyncio.gather(*(_preview(client, source, url) for source, url, _ in chosen))
        return [
            Found(source=source, id=id_, title=title, preview=preview, licence=licence, page=page)
            for (source, _, (id_, title, licence, page)), preview in zip(chosen, previews, strict=True)
            if preview
        ]

    return await asyncio.wait_for(found(), SOURCE_WAIT)


async def _sorted(s: AIConfig, found: list[Found], subject: str, context: str) -> list[Found]:
    """The pictures the AI keeps, the best first; all, as they came, when it can't sort them."""
    try:
        order = await llm.sort_pictures(s, [_image(f) for f in found], subject, context)
    except AppError as e:  # no AI, or one that can't see pictures: unsorted
        log.warning("Pictures found not sorted: %s", loggable(e))  # never the query: no lesson in logs
        return found
    return [found[i] for i in order]


async def fetch(source: str, id_: str, pixabay_key: str = "") -> tuple[bytes, PictureSource]:
    """The picture chosen, card size (JPEG), and where it comes from: looked up again by
    its source and id."""
    async with _client() as client:
        if source == "commons":
            url, origin = await _commons_url(client, id_)
        elif source == "openverse":
            url, origin = await _openverse_url(client, id_)
        elif source == "pixabay" and pixabay_key:
            url, origin = await _pixabay_url(client, id_, pixabay_key)
        else:
            raise AppError("picture.not_found")
        return pictures.card_size(await _download(client, source, url)), origin


def _image(found: Found) -> llm.Image:
    return llm.Image(base64.b64decode(found.preview.split(",", 1)[1]), "image/jpeg")


async def find(s: AIConfig, query: str, context: str, pixabay_key: str = "") -> tuple[bytes, PictureSource] | None:
    """A free picture for a card, chosen by the cards' AI among those found (it sees their
    previews): card size, and where it comes from; None when none fits or nothing could be
    had (then it is drawn)."""
    try:
        found = await search(query, pixabay_key)
        if not found:
            return None
        choice = await llm.pick_picture(s, [_image(f) for f in found], query, context)
        return None if choice is None else await fetch(found[choice].source, found[choice].id, pixabay_key)
    except AppError as e:  # a source down, a model that can't see pictures…: drawn instead
        log.warning("No free picture, drawn instead: %s", loggable(e))  # never the query: no lesson in logs
        return None


# --- The sources: each gives (source, preview URL, (id, title, licence)) ------------


async def _json(client: httpx.AsyncClient, url: str, params: dict) -> dict:
    key = (url, tuple(sorted((k, v) for k, v in params.items() if k != "key")))
    if (hit := _cached(key)) is not None:
        return hit
    res = await client.get(url, params=params)
    res.raise_for_status()
    return _keep(key, res.json())


async def _commons(client: httpx.AsyncClient, subject: str) -> list:
    data = await _json(client, COMMONS, _commons_params(gsrsearch=f"{subject} filetype:bitmap", gsrlimit=12))
    pages = sorted((data.get("query") or {}).get("pages", {}).values(), key=lambda p: p.get("index", 0))
    return [
        ("commons", info["thumburl"], (page["title"], _title(page["title"]), licence, info.get("descriptionurl", "")))
        for page in pages
        if (info := (page.get("imageinfo") or [None])[0]) and (licence := _commons_licence(page["title"], info))
    ]


async def _commons_url(client: httpx.AsyncClient, title: str) -> tuple[str, PictureSource]:
    data = await _json(client, COMMONS, _commons_params(titles=title, iiurlwidth=1024))
    for page in (data.get("query") or {}).get("pages", {}).values():
        info = (page.get("imageinfo") or [None])[0]
        same = page.get("title", "").replace("_", " ") == title.replace("_", " ")  # that file, no other
        if same and info and (licence := _commons_licence(title, info)):
            origin = PictureSource(
                source="commons", licence=licence, page=info.get("descriptionurl", ""), title=_title(title)
            )
            return info["thumburl"], origin
    raise AppError("picture.not_found")


def _commons_params(**query) -> dict:
    params = {
        "action": "query",
        "format": "json",
        "prop": "imageinfo",
        "iiprop": "url|mime|extmetadata",
        "iiurlwidth": PREVIEW,
        "iiextmetadatafilter": "License|LicenseShortName|Categories",
    }
    if "gsrsearch" in query:
        params |= {"generator": "search", "gsrnamespace": 6}
    return params | query


def _commons_licence(title: str, info: dict) -> str | None:
    """ "Public domain" or "CC0" for a picture pupils may see; None otherwise."""
    meta = info.get("extmetadata") or {}
    licence = str((meta.get("License") or {}).get("value", "")).lower()
    categories = str((meta.get("Categories") or {}).get("value", ""))
    if info.get("mime") not in ("image/jpeg", "image/png", "image/webp") or UNSUITABLE.search(f"{title} {categories}"):
        return None
    if licence == "cc0":
        return "CC0"
    return "Public domain" if licence == "pd" or licence.startswith("pd-") else None


async def _openverse(client: httpx.AsyncClient, subject: str) -> list:
    data = await _json(client, OPENVERSE, {"q": subject, "license": "cc0,pdm", "page_size": 12})
    return [
        (
            "openverse",
            r["thumbnail"],
            (r["id"], r.get("title") or "", _openverse_licence(r), r.get("foreign_landing_url") or ""),
        )
        for r in data.get("results", [])
        if not r.get("mature") and not UNSUITABLE.search(r.get("title") or "")
    ]


def _openverse_licence(result: dict) -> str:
    return "CC0" if result.get("license") == "cc0" else "Public domain"


async def _openverse_url(client: httpx.AsyncClient, id_: str) -> tuple[str, PictureSource]:
    if not re.fullmatch(r"[0-9a-f-]{36}", id_):
        raise AppError("picture.not_found")
    found = await _json(client, f"{OPENVERSE}{id_}/", {})
    if found.get("license") not in ("cc0", "pdm") or found.get("mature"):
        raise AppError("picture.not_found")
    origin = PictureSource(
        source="openverse",
        licence=_openverse_licence(found),
        page=found.get("foreign_landing_url") or "",
        title=found.get("title") or "",
    )
    return f"{OPENVERSE}{id_}/thumb/?full_size=true", origin


async def _pixabay(client: httpx.AsyncClient, subject: str, key: str) -> list:
    data = await _json(client, PIXABAY, {"key": key, "q": subject[:100], "safesearch": "true", "per_page": 12})
    hits = data.get("hits", [])
    return [
        ("pixabay", h["previewURL"], (str(h["id"]), _tags(h.get("tags", "")), "Pixabay", h.get("pageURL", "")))
        for h in hits
    ]


async def _pixabay_url(client: httpx.AsyncClient, id_: str, key: str) -> tuple[str, PictureSource]:
    if not id_.isdigit():
        raise AppError("picture.not_found")
    hits = (await _json(client, PIXABAY, {"key": key, "id": id_})).get("hits", [])
    if not hits:
        raise AppError("picture.not_found")
    hit = hits[0]
    origin = PictureSource(
        source="pixabay", licence="Pixabay", page=hit.get("pageURL", ""), title=_tags(hit.get("tags", ""))
    )
    return hit["webformatURL"], origin


def _tags(tags: str) -> str:
    """Pixabay's tags, each once ("grandma, grandma, family" → "grandma, family")."""
    return ", ".join(dict.fromkeys(t.strip() for t in tags.split(",") if t.strip()))


def _title(file: str) -> str:
    return re.sub(r"\.\w+$", "", file.removeprefix("File:")).replace("_", " ")


# --- Fetching ----------------------------------------------------------------------


async def _download(client: httpx.AsyncClient, source: str, url: str) -> bytes:
    if urlparse(url).scheme != "https" or urlparse(url).hostname not in HOSTS[source]:
        raise AppError("picture.not_found")
    res = await client.get(url, follow_redirects=False)
    if res.status_code != 200 or len(res.content) > MAX_BYTES:
        raise AppError("picture.search_failed")
    return res.content


async def _preview(client: httpx.AsyncClient, source: str, url: str) -> str | None:
    """A small JPEG of the picture, as data the page shows; None if it can't be had."""
    try:
        image = images.upright(await _download(client, source, url))
        image.thumbnail((PREVIEW, PREVIEW))
        out = io.BytesIO()
        image.save(out, "JPEG", quality=75)
    except (AppError, httpx.HTTPError, OSError, ValueError):
        return None
    return "data:image/jpeg;base64," + base64.b64encode(out.getvalue()).decode()
