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
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, NamedTuple

from . import config, figures, files, images, llm, recommended, stock
from .calls import MAX_IMAGES
from .cards import cloze_question, is_cloze, page_numbers
from .config import AIConfig
from .errors import AppError, loggable
from .models import Card, PictureSource, SourceFile
from .providers import gemini

log = logging.getLogger("notosaurus")
Step = Callable[[dict], Any]  # told each step of a card's picture as it begins (relay_api.PictureStep)

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
        # The picture's tokens at the image's price (20 times the text's); without the
        # detail, the whole output
        output = usage.candidates_token_count or 0
        details = usage.candidates_tokens_details
        image = (
            sum(d.token_count or 0 for d in details if d.modality == types.MediaModality.IMAGE) if details else output
        )
        await llm.record(s, "gemini", name, usage.prompt_token_count, output, image_tokens=image)
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
    step: Step | None = None,
) -> tuple[bytes, PictureSource]:
    """The card-size picture of a subject, and where it comes from: from the cache, or
    found or drawn (then cached). `search`: what a free picture would show
    (Card.picture_search): one is looked for first (s.picture_find), the cards' AI
    choosing it (`context`: the card, "front → back"); drawn when none fits, if `draw_it`
    (the image model costs: the user said yes), else picture.needs_drawing. `fresh`: draw
    it again (the user didn't like it); the new one replaces it in the cache. `step`: told
    each step as it begins (relay_api.PictureStep's fields)."""
    tell = step or (lambda _: None)
    if search.strip() and s.picture_find and not fresh:
        key = hashlib.sha1(f"found|{search.strip().lower()}".encode()).hexdigest()
        found_path, origin_path = (files.cache_dir("pictures", f"{key}.{ext}") for ext in ("jpg", "json"))
        if found_path.is_file() and origin_path.is_file():
            return found_path.read_bytes(), PictureSource.model_validate_json(origin_path.read_text())
        tell({"step": "searching"})
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
    tell({"step": "drawing"})
    jpeg = card_size(await draw(s, subject))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(jpeg)
    return jpeg, drawn


class CardPicture(NamedTuple):
    card: Card  # its picture's fields as decided: figure or picture_prompt / picture_search, picture_source
    data: bytes  # the figure's SVG (cleaned), or the picture's JPEG, card size
    extension: str  # "svg" or "jpg"
    kept: tuple[str, ...] = ()  # what a figure was drawn from (its Typst), to keep beside it (SourceFile)


async def card_picture(
    s: AIConfig,
    card: Card,
    asked: str | None = None,
    language: str = "English",
    fresh: bool = False,
    find: bool = True,
    pixabay_key: str = "",
    draw: bool = True,
    step: Step | None = None,
    problem: str = "",
    careful: bool = False,
    previous: Sequence[str] = (),
    previous_kind: str = "",
    previous_engine: str = "",
) -> CardPicture:
    """A card's figure or picture: the one rule for the computer and the relay (the app).

    Its own description, unchanged (`asked` None or the same): drawn as it is. A figure's
    changed: that figure redrawn. Otherwise (nothing yet, or a picture's text changed, in
    any language): the cards' AI decides an exact figure or an image model's picture and
    describes it (llm.plan_picture). A figure is drawn by the cards' AI; a picture is a
    free one found first for a real thing (s.picture_find and `find`), else the image
    model's, if `draw` (it costs: the user said yes; else picture.needs_drawing); from the
    cache unless `fresh` (then drawn again). `language`: the cards', its English name.
    `step`: told each step as it begins (relay_api.PictureStep's fields). `problem`: what the
    check found in its figure (the user asked it again): drawn again, told it; with the
    model's thinking when `careful`. `previous`: what its figure was drawn from before
    (CardPicture.kept, its sources' contents), in the language of `previous_engine` and the
    family `previous_kind` (its card's picture_source.engine and figure_kind then): drawn
    again from it when its engine is one a figure is drawn again from (Typst), else anew;
    nothing assumed of it. A figure's figure_kind becomes the family it was drawn in (not
    asked again)."""
    card = await planned(s, card, asked, language, step)
    if card.figure.strip():
        # A text with gaps: its question as shown, each gap hidden (its answers are in them, its
        # back only an extra); another card's, its question and its answer
        gaps = is_cloze(card.front)
        if card.picture_on_back:
            front = ""
        elif gaps:
            front = cloze_question(card.front.strip())
        else:
            front = f"{card.front.strip()} → {card.back.strip()}"
        first = next(iter(previous), "") if previous_engine in REDRAWN_FROM else ""
        made = await llm.made_figure(
            s, card.figure, step, card.figure_kind, problem, careful, front, first, previous_kind, gaps=gaps
        )
        if made.engine == "typst" and not made.panels:
            card = card.model_copy(update={"figure_kind": made.family})  # drawn again in it, not asked
        card.picture_source = PictureSource(
            source="drawn",
            model=s.model_for_provider(),
            engine=made.engine,
            made_with=llm.figure_credits(made),
            careful=made.careful,
        )
        kept = llm.kept_source(made)
        return CardPicture(card, figures.clean(made.svg).encode(), "svg", (kept,) if kept else ())
    context = f"{card.front.strip()} → {card.back.strip()}"
    search = card.picture_search if find else ""
    try:
        jpeg, card.picture_source = await sourced_picture(
            s, card.picture_prompt, fresh, search, context, pixabay_key, draw_it=draw, step=step
        )
    except AppError as e:
        if e.code != "picture.needs_drawing":
            raise
        # What was decided, for the client to look for free pictures itself or ask the user,
        # and the side it shows on (decided's: the computer's "✨ Image" sets it too)
        raise AppError(
            "picture.needs_drawing",
            409,
            description=card.picture_prompt,
            search=card.picture_search,
            on_back=card.picture_on_back,
        ) from e
    return CardPicture(card, jpeg, "jpg")


async def planned(
    s: AIConfig, card: Card, asked: str | None = None, language: str = "English", step: Step | None = None
) -> Card:
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
        if written != card.figure.strip():
            card.figure_kind = ""  # another figure written: its kind asked again
        card.figure = written  # a figure stays one: drawn from what was written
    elif not current or (asked is not None and written != current):
        if step:
            step({"step": "deciding"})
        plan = await llm.plan_picture(s, card.front, card.back, written, language)
        if not plan.description:
            raise AppError("picture.no_subject")  # (a 400, as before: nothing to draw)
        figure = plan.kind == "figure"
        card.figure = plan.description if figure else ""
        card.figure_kind = plan.figure_kind if figure else ""
        card.picture_prompt, card.picture_search = ("", "") if figure else (plan.description, plan.search)
        card.picture_on_back = plan.on_back  # showing the answer: with it, never giving it away
    return card


def changed_figure(card: Card, asked: str | None) -> bool:
    """A figure's description written anew (`asked`, the "✨ Image" button's): drawn again from
    what it was drawn from, what is asked changed and the rest kept. The same, or none: drawn
    anew (another drawing wanted); not a figure: decided anew (planned)."""
    written = (asked or "").strip()
    return bool(card.figure.strip() and written and written != card.figure.strip())


async def figure_or_picture(
    s: AIConfig,
    folder: Path,
    card: Card,
    fresh: bool = False,
    asked: str | None = None,
    language: str = "English",
    draw: bool = True,
    find: bool = True,
    step: Step | None = None,
    problem: str = "",
    careful: bool = False,
    previous: Sequence[str] = (),
    previous_kind: str = "",
    previous_engine: str = "",
) -> str:
    """The card's figure or picture (card_picture), saved in the lesson, the card's picture
    fields updated in place (what it shows, where it comes from); returns its file name. What
    a figure was drawn from kept beside it, named in its picture_source.sources, to draw it
    again from (`previous`, read with kept_sources)."""
    made = await card_picture(
        s,
        card,
        asked,
        language,
        fresh,
        find,
        draw=draw,
        step=step,
        problem=problem,
        careful=careful,
        previous=previous,
        previous_kind=previous_kind,
        previous_engine=previous_engine,
    )
    for field in PICTURE_FIELDS:
        setattr(card, field, getattr(made.card, field))
    if made.extension == "svg":
        name = figures.save(folder, card, made.data.decode())
        if card.picture_source is not None:
            card.picture_source.sources = keep_sources(folder, name, made.kept)
        return name
    return save(folder, card, made.data)


# What is decided of a card's picture (planned, card_picture): taken into the card with it
# (Pictures.PICTURE_FIELDS on the phone)
PICTURE_FIELDS = ("figure", "figure_kind", "picture_prompt", "picture_search", "picture_source", "picture_on_back")
# What a card's picture is drawn from (its description and its family): described anew while
# its picture was drawn, that picture is not the card's (app/lessons.py's merged_cards; the
# phone's Pictures.DESCRIBED, the page's describedAs)
DESCRIBED = ("figure", "figure_kind", "picture_prompt")
# What removing a card's picture clears ("" each, picture_source None): its search words and
# where it shows kept (Pictures.REMOVED on the phone)
REMOVED = ("picture", "picture_prompt", "figure", "figure_kind", "picture_source")

# The engines a figure is drawn again from, its sources given (figure_making.made_figure's
# previous): Typst's
REDRAWN_FROM = ("typst",)

# A figure's source files: named after its picture ("picture-c1-ab12cd34.typ", "-2.typ" for a
# second), so never on another card's; read back only by such a name (nothing else of the
# lesson's folder, nor outside it). Its group "picture": the picture's stem
SOURCE_NAME = re.compile(r"^(?P<picture>picture-[a-z0-9]+-[a-f0-9]{8})(-\d+)?\.typ$")


def keep_sources(folder: Path, picture: str, contents: Sequence[str]) -> list[SourceFile]:
    """What a figure was drawn from written beside its picture: the files, in order."""
    stem = Path(picture).stem
    files = []
    for n, content in enumerate(contents, 1):
        name = f"{stem}.typ" if n == 1 else f"{stem}-{n}.typ"
        (folder / name).write_text(content, encoding="utf-8")
        files.append(SourceFile(file=name))
    return files


def kept_sources(folder: Path, origin: PictureSource | None) -> list[str]:
    """What a figure was drawn from, as its picture_source names it: [] when it names none
    (drawn as SVG, before sources were kept), or one is missing or not one of ours."""
    files = origin.sources if origin else []
    paths = [folder / f.file for f in files if SOURCE_NAME.match(f.file)]
    if len(paths) != len(files) or not all(p.is_file() for p in paths):
        return []
    return [p.read_text(encoding="utf-8") for p in paths]


class RedrawFrom(NamedTuple):
    """An earlier figure a card's figure is drawn again from: what it was drawn from (its
    sources' contents, kept_sources), its family and its engine (card_picture's previous,
    previous_kind and previous_engine)."""

    sources: list[str]
    kind: str
    engine: str


def redraw_from(
    folder: Path,
    card: Card,
    replaced: tuple[PictureSource | None, str] | None = None,
    asked: str | None = None,
    again: bool = False,
) -> RedrawFrom | None:
    """Which earlier figure a card's figure is drawn again from, what is asked changed and the
    rest kept (the one rule for the missing pictures, "✨ Image" and its drawing, on the
    computer and the phone: Pictures.redrawFrom, core/shared-cases.json redraw_from).
    `replaced`: the figure a correction replaced, not drawn again since (where it came from,
    its family): that one, whatever is asked (its description always differs from what it was
    drawn from). Else the card's own figure, when it is drawn again (`again`: the drawing
    button, a check's problem) or its description written anew (`asked`, changed_figure).
    None: drawn anew (nothing to draw again from, or not in an engine figures are drawn
    again from, REDRAWN_FROM, or one of its sources missing)."""
    if replaced is not None:
        origin, kind = replaced
    elif card.figure.strip() and (again or changed_figure(card, asked)):
        origin, kind = card.picture_source, card.figure_kind
    else:
        return None
    if origin is None or origin.engine not in REDRAWN_FROM:
        return None
    sources = kept_sources(folder, origin)
    return RedrawFrom(sources, kind, origin.engine) if sources else None


def redrawn(redraw: RedrawFrom | None) -> dict[str, Any]:
    """figure_or_picture's (card_picture's) arguments for what a figure is drawn again from
    (redraw_from): none, drawn anew."""
    if redraw is None:
        return {}
    return {"previous": redraw.sources, "previous_kind": redraw.kind, "previous_engine": redraw.engine}


# --- The lesson's own drawings: a card's thing drawn on its pages, cut out ---------

DRAWING_MARGIN = 0.04  # of the drawing's width and height, each side: nothing of it cut off
PAPER_DARKEST = 128  # a darker edge isn't paper (a drawing to the edge): not lightened beyond twice


def whiter_paper(drawing):
    """The paper made white (a photo's is grey or yellow), the drawing's colours kept: each
    channel scaled so the paper's colour becomes white. The paper's colour: the median of
    the cut-out's edge (its margin, DRAWING_MARGIN, is paper). Not autocontrast: stretching
    each channel down to black turns a yellow sun orange, its rays brown."""
    from statistics import median

    width, height = drawing.size
    edge = [(x, y) for x in range(width) for y in (0, height - 1)] + [
        (x, y) for y in range(height) for x in (0, width - 1)
    ]
    pixels = [drawing.getpixel(point) for point in edge]
    paper = [max(PAPER_DARKEST, median(p[band] for p in pixels)) for band in range(3)]
    return drawing.point([min(255, round(v * 255 / paper[band])) for band in range(3) for v in range(256)])


def cut_out(photo: bytes, box: list[float]) -> bytes:
    """A drawing cut out of its page (`box`: fractions of the page, a margin added), its
    paper made white (whiter_paper), card size."""
    page = images.upright(photo)
    x0, y0, x1, y1 = box
    dx, dy = (x1 - x0) * DRAWING_MARGIN, (y1 - y0) * DRAWING_MARGIN
    width, height = page.size
    area = (
        max(0.0, x0 - dx) * width,
        max(0.0, y0 - dy) * height,
        min(1.0, x1 + dx) * width,
        min(1.0, y1 + dy) * height,
    )
    drawing = whiter_paper(page.crop((round(area[0]), round(area[1]), round(area[2]), round(area[3]))).convert("RGB"))
    drawing.thumbnail((SIDE, SIDE))
    out = io.BytesIO()
    drawing.save(out, "JPEG", quality=QUALITY, optimize=True)
    return out.getvalue()


class DrawingCall(NamedTuple):
    pages: list[int]  # the lesson's photos sent, their numbers (from 1)
    cards: list[int]  # the cards asked (their indexes), but those an earlier call found


def drawing_calls(pages: Sequence[int], photos: int | Sequence[int], per_call: int = MAX_IMAGES) -> list[DrawingCall]:
    """The calls looking for the lesson's own drawings of cards whose pages are `pages` (each
    card's, from 1; 0 unknown) among the lesson's `photos` (the numbers of its pages there,
    cards.page_numbers: a count, 1 to n). A card's drawing is looked for on its own page and its
    neighbours (the page before, the page after, those the lesson has): the cards taken by their
    page, each call sends the pages around as many as fit in `per_call` photos. The cards whose
    page is unknown (0, or not one of the lesson's: a page missing is never replaced by
    another): every page, at most `per_call` at a time, one call after another, each asked only
    for those still without a drawing. The same rule on the phone (Pictures.drawingCalls:
    core/shared-cases.json)."""
    present = page_numbers(photos)
    there = set(present)
    calls: list[DrawingCall] = []
    sent: set[int] = set()
    asked: list[int] = []
    for page, i in sorted((page, i) for i, page in enumerate(pages) if page in there):
        near = {page - 1, page, page + 1} & there
        if asked and len(sent | near) > per_call:
            calls.append(DrawingCall(sorted(sent), sorted(asked)))
            sent, asked = set(), []
        sent |= near
        asked.append(i)
    if asked:
        calls.append(DrawingCall(sorted(sent), sorted(asked)))
    unknown = [i for i, page in enumerate(pages) if page not in there]
    if unknown:
        for first in range(0, len(present), per_call):
            calls.append(DrawingCall(present[first : first + per_call], unknown))
    return calls


async def lesson_drawings(s: AIConfig, photos: list[llm.Image], cards: list[Card]) -> dict[int, bytes]:
    """The drawings of their own these photos (the lesson's, or some of them) show for these
    cards, cut out (one light call, llm.find_drawings): {card's index: its JPEG}. None, or the
    call failing: {} (the cards' pictures then looked for or drawn, as without)."""
    try:
        found = await llm.find_drawings(s, photos, [f"{c.front.strip()} → {c.back.strip()}" for c in cards])
    except AppError as e:
        log.warning("The lesson's drawings not looked for: %s", loggable(e))
        return {}
    drawings = {}
    for i, (page, box) in found.items():
        try:
            drawings[i] = await asyncio.to_thread(cut_out, photos[page].data, box)  # PIL's: off the loop
        except (OSError, ValueError) as e:
            log.warning("A lesson's drawing not cut out: %s", loggable(e))
    return drawings


class Drawn(NamedTuple):
    failures: int  # how many failed
    error: dict | None  # why the first did (an error's detail, for the page)
    to_draw: list[str]  # the cards whose picture no free one fits: drawn only if the user says yes


# A card's picture fields, told with "ready" (draw_all) the moment it has them
READY = {"picture", *PICTURE_FIELDS}


def needs_picture(card: Card) -> bool:
    """A card whose picture is still to be made: it says what to show (a picture_prompt or a
    figure) and has none. A sentence with gaps' too: its note type shows it (cloze v3), on its
    question or its answer. The one rule of the computer, the phone (Pictures.needsPicture) and
    the page (needsPicture): core/shared-cases.json's needs_picture."""
    return bool((card.picture_prompt.strip() or card.figure.strip()) and not card.picture)


async def draw_all(
    s: AIConfig,
    folder: Path,
    cards: list[Card],
    draw: bool = False,
    step: Step | None = None,
    photos: Mapping[int, llm.Image] | Sequence[llm.Image] | None = None,
    not_from_lesson: Sequence[str] = (),
    previous: Mapping[str, tuple[PictureSource, str]] | None = None,
) -> Drawn:
    """The missing pictures (cards with a picture_prompt or a figure, and no picture), a few
    at a time: figures drawn, free pictures found; a picture none fits drawn by the image
    model only if `draw` (it costs: the user said yes), else its card in to_draw. A card
    without its picture is still a card. `step`: told each card's steps as they begin,
    {"card": its id, …relay_api.PictureStep's fields}, then {"card", "step": "ready", its
    picture's fields (READY)} as soon as it has it. `photos`: the lesson's by their page
    number (a list: its pages 1 to n), its own drawings
    taken first for the cards whose thing they show (lesson_drawings: each card's on its page
    and its neighbours, drawing_calls; no search, the pupil's own pictures; {"card", "step":
    "lesson"} while they are looked at), but for the cards in `not_from_lesson` (their ids): a
    correction replaced their picture, the lesson's drawing would only come back; theirs
    looked for as any other. `previous`: by card
    id, the figure a correction replaced, where it came from (its sources, kept_sources) and
    its family: drawn again from it, what is asked changed and the rest kept."""
    todo = [c for c in cards if needs_picture(c)]
    if photos:
        by_page = photos if isinstance(photos, Mapping) else dict(enumerate(photos, 1))
        await _from_the_lesson(s, folder, [c for c in todo if c.id not in not_from_lesson], by_page, step)
        todo = [c for c in todo if not c.picture]
    sem = asyncio.Semaphore(CONCURRENCY)
    failures: list[dict] = []
    to_draw: list[str] = []

    async def one(card: Card) -> None:
        async with sem:
            try:
                told = None
                if step is not None:
                    tell = step  # (bound here: pyright sees it set)
                    told = lambda said, card=card: tell({"card": card.id, **said})  # noqa: E731
                replaced = (previous or {}).get(card.id)
                card.picture = await figure_or_picture(
                    s,
                    folder,
                    card,
                    draw=draw,
                    find=not draw,
                    step=told,
                    **redrawn(redraw_from(folder, card, replaced)),
                )
                if told is not None:  # shown at once, not when the others are done
                    told({"step": "ready", **card.model_dump(mode="json", include=READY)})
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


async def _from_the_lesson(
    s: AIConfig, folder: Path, cards: list[Card], photos: Mapping[int, llm.Image], step: Step | None
) -> None:
    """The pictures (not the figures: those are drawn exact) the lesson's own drawings
    give, saved and told at once (draw_all). Each card's looked for on its page and its
    neighbours, a page unknown on all of them (drawing_calls), one call after another.
    `photos`: by their page number (a page missing: none at its number)."""
    wanted = [c for c in cards if c.picture_prompt.strip() and not c.figure.strip()]
    if not wanted:
        return
    for card in wanted:
        if step:
            step({"card": card.id, "step": "lesson"})
    found: set[int] = set()
    for call in drawing_calls([c.page for c in wanted], list(photos)):
        asked = [i for i in call.cards if i not in found]  # the drawings' indexes: into these
        if not asked:
            continue
        sent = [photos[page] for page in call.pages]  # a drawing cut out of its own photo
        for j, jpeg in (await lesson_drawings(s, sent, [wanted[i] for i in asked])).items():
            found.add(asked[j])
            _from_its_page(folder, wanted[asked[j]], jpeg, step)


def _from_its_page(folder: Path, card: Card, jpeg: bytes, step: Step | None) -> None:
    """A card's picture cut out of the lesson's page, saved and told at once."""
    card.picture = save(folder, card, jpeg)
    card.picture_source = PictureSource(source="lesson")
    if step:
        step({"card": card.id, "step": "ready", **card.model_dump(mode="json", include=READY)})


def prune(folder: Path, cards: list[Card]) -> int:
    """Remove the pictures no card uses any more (pictures and figures), with the sources a
    figure was drawn from (keep_sources: named after it): how many pictures."""
    keep = {c.picture for c in cards if c.picture}
    stems = {Path(name).stem for name in keep}
    removed = 0
    if folder.is_dir():
        for path in folder.iterdir():
            if NAME.match(path.name) and path.name not in keep:
                path.unlink(missing_ok=True)
                removed += 1
            elif (source := SOURCE_NAME.match(path.name)) and source["picture"] not in stems:
                path.unlink(missing_ok=True)
    return removed
