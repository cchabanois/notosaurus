"""Pictures for cards ("front: the picture of the word"), drawn by an image model.

The AI that writes the cards says what to draw (Card.picture_prompt); an image
model draws it, by default through the cards' own service. Claude and local models
can't draw: then another service does (`picture_service`, see `service`), with its
own key.
"""

import asyncio
import base64
import hashlib
import io
import logging
import re
from pathlib import Path
from typing import Any, NamedTuple

from . import config, figures, files, images, llm, recommended, stock
from .cards import is_cloze
from .config import AIConfig
from .errors import AppError, loggable
from .models import Card, PictureSource
from .providers import gemini

log = logging.getLogger("notosaurus")

OPENROUTER = config.OPENROUTER_URL
NAME = re.compile(r"^picture-[a-z0-9]+-[a-f0-9]{8}\.(jpg|svg)$")  # files we write; blocks "../"
SIDE = 512  # on a card: clear enough, light to sync
QUALITY = 80
CONCURRENCY = 4
STYLE = (
    "A simple, clear picture for a child's vocabulary flashcard showing {subject}. Friendly flat "
    "illustration, bright colours, plain white background, the subject centred and filling the picture. "
    "No text, no letters, no numbers."
)


class PictureError(AppError):
    status = 502


# The services that can draw, and the model each uses by default (Gemini Flash Lite
# Image: fast and the cheapest; OpenAI's smaller image model).
DEFAULT_MODELS = {service: recommended.default(recommended.PICTURES, service) for service in recommended.PICTURES}
# When the cards' service can't draw (Claude, a local model…): the first with a key
FALLBACK = ("openrouter", "gemini", "openai")


def _ready(s: AIConfig, service: str) -> bool:
    """Whether the service can be called: its key (Gemini: or a Vertex AI project)."""
    if service == "gemini":
        return s.gemini_ready()
    return bool({"openai": s.openai_api_key, "openrouter": s.openrouter_api_key}[service])


def service(s: AIConfig) -> str:
    """The service drawing the pictures: the one chosen, else the cards' own when it can
    draw, else the first with a key. "" when none can (no key, or "no pictures")."""
    chosen = s.picture_service.strip()
    if chosen == "none":
        return ""
    if chosen:
        return chosen if _ready(s, chosen) else ""
    if s.llm in DEFAULT_MODELS:
        return s.llm if _ready(s, s.llm) else ""
    return next((name for name in FALLBACK if _ready(s, name)), "")


def model(s: AIConfig) -> str:
    """The image model, in the drawing service: the one set, else its default ("" when
    there is no service to draw)."""
    drawing = service(s)
    return (s.picture_model.strip() or DEFAULT_MODELS[drawing]) if drawing else ""


def drawing_usd(s: AIConfig) -> float | None:
    """About what one picture drawn by the image model costs, in US dollars (the
    recommended models' prices: told to the user before drawing); None when unknown."""
    drawing, name = service(s), model(s)
    found = next((m for m in recommended.PICTURES.get(drawing or "", []) if m.id == name), None)
    return found.cents / 100 if found else None


async def draw(s: AIConfig, subject: str) -> bytes:
    """One picture (PNG/JPEG bytes from the model), its cost recorded."""
    drawing, name = service(s), model(s)
    if not drawing:
        raise PictureError("picture.no_model")
    prompt = STYLE.format(subject=subject.strip())
    if drawing == "openrouter":
        return await _openrouter(s, name, prompt)
    if drawing == "gemini":
        return await _gemini(s, name, prompt)
    return await _openai(s, name, prompt)


async def _openrouter(s: AIConfig, name: str, prompt: str) -> bytes:
    import openai

    key = s.openrouter_api_key
    if not key:
        raise PictureError("picture.missing_key", service="OpenRouter")
    client = openai.AsyncOpenAI(base_url=OPENROUTER, api_key=key)
    try:
        response = await client.chat.completions.create(
            model=name,
            messages=[{"role": "user", "content": prompt}],
            extra_body={"modalities": ["image", "text"], "usage": {"include": True}},
        )
    except openai.RateLimitError as e:
        raise PictureError("picture.quota", service="OpenRouter") from e
    except openai.OpenAIError as e:
        raise PictureError("picture.failed", detail=str(e)[:200]) from e
    if response.usage:
        cost = (response.usage.model_extra or {}).get("cost")
        await llm.record(s, "openrouter.ai", name, response.usage.prompt_tokens, response.usage.completion_tokens, cost)
    # No choice, no image, or not as a data URL: nothing drawn (that card only, as below)
    message = response.choices[0].message if response.choices else None
    images = ((message.model_extra if message else None) or {}).get("images") or []
    url = str(((images[0] or {}).get("image_url") or {}).get("url") or "") if images else ""
    return _decoded(url.split(",", 1)[1] if url.startswith("data:") and "," in url else "")


async def _gemini(s: AIConfig, name: str, prompt: str) -> bytes:
    from google import genai
    from google.genai import errors, types

    if not s.gemini_ready():
        raise PictureError("picture.missing_key", service="Gemini")
    client = genai.Client(**s.gemini_options())
    try:
        response = await client.aio.models.generate_content(
            model=name,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"], safety_settings=gemini.gemini_safety()
            ),
        )
    except errors.APIError as e:
        if e.code == 429:
            raise PictureError("picture.quota", service="Gemini") from e
        raise PictureError("picture.failed", detail=f"{e.code} {e.message}"[:200]) from e
    usage = response.usage_metadata
    if usage:
        await llm.record(s, "gemini", name, usage.prompt_token_count, usage.candidates_token_count)
    # A picture refused for safety: its candidate comes without content
    content = response.candidates[0].content if response.candidates else None
    for part in (content.parts if content else None) or []:
        if part.inline_data and part.inline_data.data:
            return part.inline_data.data
    raise PictureError("picture.empty")


async def _openai(s: AIConfig, name: str, prompt: str) -> bytes:
    import openai

    key = s.openai_api_key
    if not key:
        raise PictureError("picture.missing_key", service="OpenAI")
    client = openai.AsyncOpenAI(api_key=key)
    try:
        response = await client.images.generate(model=name, prompt=prompt, size="1024x1024", quality="low")
    except openai.OpenAIError as e:
        raise PictureError("picture.failed", detail=str(e)[:200]) from e
    if response.usage:
        await llm.record(s, "openai", name, response.usage.input_tokens, response.usage.output_tokens)
    # No image, or a link instead of the image (an older model): nothing drawn
    return _decoded((response.data[0].b64_json or "") if response.data else "")


def _decoded(data: str) -> bytes:
    """An image sent as base64; none, or not base64: picture.empty."""
    try:
        image = base64.b64decode(data, validate=True)
    except ValueError:
        image = b""
    if not image:
        raise PictureError("picture.empty")
    return image


# --- The models that can draw, as each service lists them (listing is free) -----------


async def image_models(s: AIConfig) -> list[str]:
    """Every model of the drawing service that draws as Notosaurus asks it to (Gemini
    and OpenRouter: an image in the answer; OpenAI: its images API)."""
    drawing = service(s)
    if not drawing:
        raise PictureError("picture.no_model")
    try:
        found = await _fetch_models(s, drawing)
    except PictureError:
        raise
    except Exception as e:  # the service's own error (key refused, unreachable…)
        raise PictureError("picture.failed", detail=str(e)[:200]) from e
    return sorted(set(_drawing_models(drawing, found)))


async def _fetch_models(s: AIConfig, drawing: str) -> list[dict]:
    """The service's models: {"id", "outputs": modalities or None, "actions": or None}."""
    if drawing == "gemini":
        from google import genai

        options = s.gemini_options()
        client = genai.Client(**options)
        # Vertex AI names them "publishers/google/models/…" and doesn't say their actions
        vertex = ["generateContent"] if options.get("vertexai") else []
        return [
            {"id": m.name.rsplit("/", 1)[-1], "actions": m.supported_actions or vertex}
            async for m in await client.aio.models.list()
            if m.name
        ]
    import openai

    key = {"openai": s.openai_api_key, "openrouter": s.openrouter_api_key}[drawing]
    address: dict[str, Any] = {"base_url": OPENROUTER} if drawing == "openrouter" else {}  # else OpenAI's
    client = openai.AsyncOpenAI(api_key=key, **address)
    return [
        {"id": m.id, "outputs": ((m.model_extra or {}).get("architecture") or {}).get("output_modalities")}
        async for m in client.models.list()
    ]


def _drawing_models(drawing: str, models: list[dict]) -> list[str]:
    if drawing == "gemini":  # gemini-…-image: they answer with an image (not Imagen, another API)
        return [m["id"] for m in models if "image" in m["id"] and "generateContent" in (m.get("actions") or [])]
    if drawing == "openrouter":  # an image among its outputs; not its routers nor the slow ":batch"
        return [
            m["id"]
            for m in models
            if "image" in (m.get("outputs") or [])
            and not m["id"].startswith("openrouter/")
            and not m["id"].endswith(":batch")
        ]
    # OpenAI's images API: the gpt-image models (DALL·E doesn't take the "low" quality asked)
    return [m["id"] for m in models if m["id"].startswith(("gpt-image", "chatgpt-image"))]


def card_size(data: bytes) -> bytes:
    """A picture (from a model, or a photo) as a card shows it: upright, light JPEG."""
    image = images.upright(data)
    image.thumbnail((SIDE, SIDE))
    out = io.BytesIO()
    image.save(out, "JPEG", quality=QUALITY, optimize=True)
    return out.getvalue()


def save(folder: Path, card: Card, data: bytes) -> str:
    """The picture in the lesson's images/ folder (card size); returns its file name."""
    jpeg = card_size(data)
    folder.mkdir(parents=True, exist_ok=True)
    name = f"picture-{card.id}-{hashlib.sha1(jpeg).hexdigest()[:8]}.jpg"
    (folder / name).write_bytes(jpeg)
    return name


# --- Cache: a subject drawn once is reused by the next lessons, for free ----------


def _cache_path(s: AIConfig, subject: str) -> Path:
    key = hashlib.sha1(f"{model(s)}|{STYLE}|{subject.strip().lower()}".encode()).hexdigest()
    return files.cache_dir("pictures", f"{key}.jpg")


async def picture(
    s: AIConfig, subject: str, fresh: bool = False, search: str = "", context: str = "", pixabay_key: str = ""
) -> bytes:
    """The card-size picture of a subject (see sourced_picture, which also says where it
    comes from)."""
    return (await sourced_picture(s, subject, fresh, search, context, pixabay_key))[0]


async def sourced_picture(
    s: AIConfig,
    subject: str,
    fresh: bool = False,
    search: str = "",
    context: str = "",
    pixabay_key: str = "",
    draw_it: bool = True,
) -> tuple[bytes, PictureSource]:
    """The card-size picture of a subject, and where it comes from: from the cache, or
    found or drawn (then cached). `search`: what a free picture would show
    (Card.picture_search): one is looked for first (s.picture_find), the cards' AI
    choosing it (`context`: the card, "front → back"); drawn when none fits, if `draw_it`
    (the image model costs: the user said yes), else picture.needs_drawing. `fresh`: draw
    it again (the user didn't like it); the new one replaces it in the cache."""
    if search.strip() and s.picture_find and not fresh:
        key = hashlib.sha1(f"found|{search.strip().lower()}".encode()).hexdigest()
        found_path, origin_path = (files.cache_dir("pictures", f"{key}.{ext}") for ext in ("jpg", "json"))
        if found_path.is_file() and origin_path.is_file():
            return found_path.read_bytes(), PictureSource.model_validate_json(origin_path.read_text())
        if found := await stock.find(s, search, context, pixabay_key):
            found_path.parent.mkdir(parents=True, exist_ok=True)
            found_path.write_bytes(found[0])
            origin_path.write_text(found[1].model_dump_json())
            return found
    drawn = PictureSource(source="drawn", model=model(s))
    path = _cache_path(s, subject)
    if not fresh and path.is_file():
        return path.read_bytes(), drawn
    if not draw_it:
        raise AppError("picture.needs_drawing", 409)
    jpeg = card_size(await draw(s, subject))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(jpeg)
    return jpeg, drawn


class CardPicture(NamedTuple):
    card: Card  # its picture's fields as decided: figure or picture_prompt / picture_search, picture_source
    data: bytes  # the figure's SVG (cleaned), or the picture's JPEG, card size
    extension: str  # "svg" or "jpg"


async def card_picture(
    s: AIConfig,
    card: Card,
    asked: str | None = None,
    language: str = "English",
    fresh: bool = False,
    find: bool = True,
    pixabay_key: str = "",
    draw: bool = True,
) -> CardPicture:
    """A card's figure or picture: the one rule for the computer and the relay (the app).

    Its own description, unchanged (`asked` None or the same): drawn as it is. A figure's
    changed: that figure redrawn. Otherwise (nothing yet, or a picture's text changed, in
    any language): the cards' AI decides an exact figure or an image model's picture and
    describes it (llm.plan_picture). A figure is drawn by the cards' AI; a picture is a
    free one found first for a real thing (s.picture_find and `find`), else the image
    model's, if `draw` (it costs: the user said yes; else picture.needs_drawing); from the
    cache unless `fresh` (then drawn again). `language`: the cards', its English name."""
    card = await decided(s, card, asked, language)
    if card.figure.strip():
        svg = figures.clean(await llm.draw_figure(s, card.figure))
        card.picture_source = PictureSource(source="drawn", model=s.model_for_provider())
        return CardPicture(card, svg.encode(), "svg")
    context = f"{card.front.strip()} → {card.back.strip()}"
    search = card.picture_search if find else ""
    try:
        jpeg, card.picture_source = await sourced_picture(
            s, card.picture_prompt, fresh, search, context, pixabay_key, draw_it=draw
        )
    except AppError as e:
        if e.code != "picture.needs_drawing":
            raise
        # What was decided, for the client to look for free pictures itself or ask the user
        raise AppError("picture.needs_drawing", 409, description=card.picture_prompt, search=card.picture_search) from e
    return CardPicture(card, jpeg, "jpg")


async def decided(s: AIConfig, card: Card, asked: str | None = None, language: str = "English") -> Card:
    """What a card's picture should be, decided (card_picture's first step; the "✨ Image"
    button's, before free pictures are looked for): its own description, unchanged (`asked`
    None or the same); a figure's changed: that figure; otherwise (nothing yet, or a
    picture's text changed, in any language) the cards' AI decides an exact figure or a
    picture and describes it (llm.plan_picture). A copy of the card, its figure or its
    picture_prompt and picture_search set."""
    card = card.model_copy()
    current = (card.figure or card.picture_prompt).strip()
    written = (asked or "").strip()
    if card.figure.strip() and written:
        card.figure = written  # a figure stays one: drawn from what was written
    elif not current or (asked is not None and written != current):
        plan = await llm.plan_picture(s, card.front, card.back, written, language)
        if not plan.description:
            raise AppError("picture.no_subject")  # (a 400, as before: nothing to draw)
        figure = plan.kind == "figure"
        card.figure = plan.description if figure else ""
        card.picture_prompt, card.picture_search = ("", "") if figure else (plan.description, plan.search)
    return card


async def figure_or_picture(
    s: AIConfig,
    folder: Path,
    card: Card,
    fresh: bool = False,
    asked: str | None = None,
    language: str = "English",
    draw: bool = True,
    find: bool = True,
) -> str:
    """The card's figure or picture (card_picture), saved in the lesson, the card's picture
    fields updated in place (what it shows, where it comes from); returns its file name."""
    made = await card_picture(s, card, asked, language, fresh, find, draw=draw)
    for field in ("figure", "picture_prompt", "picture_search", "picture_source"):
        setattr(card, field, getattr(made.card, field))
    if made.extension == "svg":
        return figures.save(folder, card, made.data.decode())
    return save(folder, card, made.data)


class Drawn(NamedTuple):
    failures: int  # how many failed
    error: dict | None  # why the first did (an error's detail, for the page)
    to_draw: list[str]  # the cards whose picture no free one fits: drawn only if the user says yes


async def draw_all(s: AIConfig, folder: Path, cards: list[Card], draw: bool = False) -> Drawn:
    """The missing pictures (cards with a picture_prompt or a figure, and no picture), a few
    at a time: figures drawn, free pictures found; a picture none fits drawn by the image
    model only if `draw` (it costs: the user said yes), else its card in to_draw. A card
    without its picture is still a card."""
    # Not on a sentence with gaps: Anki shows no picture on it (not paid for, then)
    todo = [
        c for c in cards if (c.picture_prompt.strip() or c.figure.strip()) and not c.picture and not is_cloze(c.front)
    ]
    sem = asyncio.Semaphore(CONCURRENCY)
    failures: list[dict] = []
    to_draw: list[str] = []

    async def one(card: Card) -> None:
        async with sem:
            try:
                card.picture = await figure_or_picture(s, folder, card, draw=draw, find=not draw)
            except AppError as e:
                if e.code == "picture.needs_drawing":
                    to_draw.append(card.id)
                    return
                failures.append(e.detail())
                log.warning("Picture not drawn: %s", loggable(e))  # never the subject: no lesson in logs
            except (OSError, ValueError) as e:  # not an image
                failures.append(PictureError("picture.empty").detail())
                log.warning("Picture not an image: %s", loggable(e))

    await asyncio.gather(*(one(c) for c in todo))
    return Drawn(len(failures), failures[0] if failures else None, to_draw)


def prune(folder: Path, cards: list[Card]) -> None:
    """Remove the pictures no card uses any more."""
    keep = {c.picture for c in cards if c.picture}
    if folder.is_dir():
        for path in folder.glob("picture-*.jpg"):
            if path.name not in keep:
                path.unlink(missing_ok=True)
