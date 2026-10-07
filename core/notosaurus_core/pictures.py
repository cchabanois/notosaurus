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

from PIL import Image as PILImage
from PIL import ImageOps

from . import config, figures, files, llm, recommended
from .config import AIConfig
from .errors import AppError
from .models import Card

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
    images = (response.choices[0].message.model_extra or {}).get("images") or []
    if not images:
        raise PictureError("picture.empty")
    return base64.b64decode(images[0]["image_url"]["url"].split(",", 1)[1])


async def _gemini(s: AIConfig, name: str, prompt: str) -> bytes:
    from google import genai
    from google.genai import errors, types

    if not s.gemini_ready():
        raise PictureError("picture.missing_key", service="Gemini")
    client = genai.Client(**s.gemini_options())
    try:
        response = await client.aio.models.generate_content(
            model=name, contents=prompt, config=types.GenerateContentConfig(response_modalities=["IMAGE", "TEXT"])
        )
    except errors.APIError as e:
        if e.code == 429:
            raise PictureError("picture.quota", service="Gemini") from e
        raise PictureError("picture.failed", detail=f"{e.code} {e.message}"[:200]) from e
    usage = response.usage_metadata
    if usage:
        await llm.record(s, "gemini", name, usage.prompt_token_count, usage.candidates_token_count)
    for part in (response.candidates[0].content.parts if response.candidates else []) or []:
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
    return base64.b64decode(response.data[0].b64_json)


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
        ]
    import openai

    key = {"openai": s.openai_api_key, "openrouter": s.openrouter_api_key}[drawing]
    client = openai.AsyncOpenAI(api_key=key, **({"base_url": OPENROUTER} if drawing == "openrouter" else {}))
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
    image = ImageOps.exif_transpose(PILImage.open(io.BytesIO(data))).convert("RGB")
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


async def picture(s: AIConfig, subject: str, fresh: bool = False) -> bytes:
    """The card-size picture of a subject: from the cache, or drawn (then cached).
    `fresh`: draw it again (the user didn't like it); the new one replaces it in the cache."""
    path = _cache_path(s, subject)
    if not fresh and path.is_file():
        return path.read_bytes()
    jpeg = card_size(await draw(s, subject))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(jpeg)
    return jpeg


async def figure_or_picture(s: AIConfig, folder: Path, card: Card, fresh: bool = False) -> str:
    """The card's figure (SVG, drawn by the cards' AI) or picture (image model, from the
    cache unless `fresh`), saved in the lesson; returns its file name."""
    if card.figure.strip():
        return figures.save(folder, card, await llm.draw_figure(s, card.figure))
    return save(folder, card, await picture(s, card.picture_prompt, fresh=fresh))


async def draw_all(s: AIConfig, folder: Path, cards: list[Card]) -> tuple[int, dict | None]:
    """Draw the missing pictures (cards with a picture_prompt or a figure, and no picture),
    a few at a time. Returns how many failed and why the first did (an error's detail, for
    the page): a card without its picture is still a card."""
    todo = [c for c in cards if (c.picture_prompt.strip() or c.figure.strip()) and not c.picture]
    sem = asyncio.Semaphore(CONCURRENCY)
    failures: list[dict] = []

    async def one(card: Card) -> None:
        async with sem:
            try:
                card.picture = await figure_or_picture(s, folder, card)
            except AppError as e:
                failures.append(e.detail())
                log.warning("Picture for %r: %s", card.figure or card.picture_prompt, e)
            except (OSError, ValueError) as e:  # not an image
                failures.append(PictureError("picture.empty").detail())
                log.warning("Picture for %r: %s", card.figure or card.picture_prompt, e)

    await asyncio.gather(*(one(c) for c in todo))
    return len(failures), (failures[0] if failures else None)


def prune(folder: Path, cards: list[Card]) -> None:
    """Remove the pictures no card uses any more."""
    keep = {c.picture for c in cards if c.picture}
    if folder.is_dir():
        for path in folder.glob("picture-*.jpg"):
            if path.name not in keep:
                path.unlink(missing_ok=True)
