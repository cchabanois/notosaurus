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
import re
import time
from typing import Literal
from urllib.parse import urlparse

import httpx
from PIL import Image as PILImage
from pydantic import BaseModel

from .errors import AppError
from .pictures import card_size

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


_cache: dict[tuple, tuple[float, object]] = {}


def _cached(key: tuple):
    hit = _cache.get(key)
    return hit[1] if hit and time.monotonic() - hit[0] < CACHE_S else None


def _keep(key: tuple, value):
    if len(_cache) > 2000:
        _cache.clear()
    _cache[key] = (time.monotonic(), value)
    return value


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=TIMEOUT, transport=_transport, headers={"User-Agent": AGENT})


async def search(subject: str, pixabay_key: str = "") -> list[Found]:
    """Up to MAX_RESULTS free pictures of `subject` (English), the sources taking turns.
    A source that fails or finds nothing leaves the others."""
    subject = " ".join(subject.split())[:200]
    if not subject:
        raise AppError("picture.no_subject")
    async with _client() as client:
        sources = [_pixabay(client, subject, pixabay_key)] if pixabay_key else []
        sources += [_openverse(client, subject), _commons(client, subject)]
        found = await asyncio.gather(*sources, return_exceptions=True)
        lists = [f for f in found if isinstance(f, list)]
        if not lists:
            raise AppError("picture.search_failed")
        mixed = [item for row in zip(*[lst + [None] * PER_SOURCE for lst in lists], strict=False) for item in row]
        chosen = [m for m in mixed if m][:MAX_RESULTS]
        previews = await asyncio.gather(*(_preview(client, source, url) for source, url, _ in chosen))
    return [
        Found(source=source, id=id_, title=title, preview=preview, licence=licence)
        for (source, _, (id_, title, licence)), preview in zip(chosen, previews, strict=True)
        if preview
    ]


async def fetch(source: str, id_: str, pixabay_key: str = "") -> bytes:
    """The picture chosen, card size (JPEG): looked up again by its source and id."""
    async with _client() as client:
        if source == "commons":
            url = await _commons_url(client, id_)
        elif source == "openverse":
            if not re.fullmatch(r"[0-9a-f-]{36}", id_):
                raise AppError("picture.not_found")
            url = f"{OPENVERSE}{id_}/thumb/?full_size=true"
        elif source == "pixabay" and pixabay_key:
            url = await _pixabay_url(client, id_, pixabay_key)
        else:
            raise AppError("picture.not_found")
        return card_size(await _download(client, source, url))


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
        ("commons", info["thumburl"], (page["title"], _title(page["title"]), licence))
        for page in pages
        if (info := (page.get("imageinfo") or [None])[0]) and (licence := _commons_licence(page["title"], info))
    ][:PER_SOURCE]


async def _commons_url(client: httpx.AsyncClient, title: str) -> str:
    data = await _json(client, COMMONS, _commons_params(titles=title, iiurlwidth=1024))
    for page in (data.get("query") or {}).get("pages", {}).values():
        info = (page.get("imageinfo") or [None])[0]
        same = page.get("title", "").replace("_", " ") == title.replace("_", " ")  # that file, no other
        if same and info and _commons_licence(title, info):
            return info["thumburl"]
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
            (r["id"], r.get("title") or "", "CC0" if r.get("license") == "cc0" else "Public domain"),
        )
        for r in data.get("results", [])
        if not r.get("mature") and not UNSUITABLE.search(r.get("title") or "")
    ][:PER_SOURCE]


async def _pixabay(client: httpx.AsyncClient, subject: str, key: str) -> list:
    data = await _json(client, PIXABAY, {"key": key, "q": subject[:100], "safesearch": "true", "per_page": 12})
    return [("pixabay", h["previewURL"], (str(h["id"]), h.get("tags", ""), "Pixabay")) for h in data.get("hits", [])][
        :PER_SOURCE
    ]


async def _pixabay_url(client: httpx.AsyncClient, id_: str, key: str) -> str:
    if not id_.isdigit():
        raise AppError("picture.not_found")
    hits = (await _json(client, PIXABAY, {"key": key, "id": id_})).get("hits", [])
    if not hits:
        raise AppError("picture.not_found")
    return hits[0]["webformatURL"]


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
        image = PILImage.open(io.BytesIO(await _download(client, source, url))).convert("RGB")
        image.thumbnail((PREVIEW, PREVIEW))
        out = io.BytesIO()
        image.save(out, "JPEG", quality=75)
    except (AppError, httpx.HTTPError, OSError, ValueError):
        return None
    return "data:image/jpeg;base64," + base64.b64encode(out.getvalue()).decode()
