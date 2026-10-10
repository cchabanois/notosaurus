"""The Notosaurus relay's API, version 1: what its client (the Notosaurus app with a
licence, later the Android app) and the relay itself both import, so that they
can't drift apart.

The relay is notosaurus_core behind a licence key: each route is the remote form
of a core function (/v1/extract → llm.extract_cards…), takes what that function
takes but the AI configuration (the relay's own), and keeps nothing.

- Authentication: "Authorization: Bearer <licence key>".
- The client says its version in CLIENT_HEADER ("1.1.0"); a client too old for
  the relay gets "relay.client_outdated".
- The routes with photos (extract, revise) take multipart/form-data: a "request"
  part holding the JSON request and one "images" part per photo (binary, as
  diagrams.prepare makes them: JPEG, at most 1568 px). The other routes take JSON.
- Errors: HTTP status of ERRORS, body {"code", "params"} (errors.AppError), the
  AI's own errors ("llm.*") passed on as they are.
- /v1/extract asked with "Accept: application/x-ndjson" (STREAM_TYPE) answers as the
  AI writes: one JSON object per line, each card as it comes, then the answer or
  the error (ExtractLine). A client going away stops the AI.
- /v1/transcribe turns a dictation (the app's 🎤) into the text its speaker meant to
  type: multipart/form-data, a "request" part (TranscribeRequest) and an "audio" part
  (AUDIO_TYPES, at most MAX_AUDIO_BYTES).
- /v1/pictures/search finds free pictures of a subject to choose from (stock.search: public
  domain, CC0, Pixabay), their previews as data; /v1/pictures/found gives the one chosen,
  card size (JPEG), looked up again by its source and id. Both free: no AI. Their pictures
  (and /v1/picture's) say where they come from in PICTURE_SOURCE_HEADER: kept with the card.
- /v1/speak reads a card's back aloud with one of /v1/voices (natural voices, the
  same on every device): an mp3, for the app that has no voices of its own.
- Each answer says the credits it used and those left (Usage; for /v1/picture and
  /v1/speak, the CREDITS_HEADER and CREDITS_LEFT_HEADER headers). A credit is a share of the
  call's real AI cost, at least 1 per call: the relay counts them, not the client.

The OpenAPI description (core/relay-api-v1.json) is generated from these models
by tools/relay_openapi.py. Apps already released keep calling the relay: within /v1 the
API only grows (new routes, optional request fields, answer fields more), checked against
the API each released app speaks (core/relay-api-releases/, tools/relay_compat.py).
"""

from typing import Literal

from pydantic import BaseModel, Field

from .llm import Extracted
from .models import Card, Deck, Dictated, Explanation, FollowUp, PicturePlan, Revision
from .stock import Found, Source

PREFIX = "/v1"
CLIENT_HEADER = "X-Notosaurus-Version"
CREDITS_HEADER = "X-Notosaurus-Credits"
CREDITS_LEFT_HEADER = "X-Notosaurus-Credits-Left"
# /v1/picture and /v1/pictures/found: where the picture comes from (models.PictureSource, JSON)
PICTURE_SOURCE_HEADER = "X-Notosaurus-Picture-Source"
STREAM_TYPE = "application/x-ndjson"

MAX_IMAGES = 10
MAX_IMAGE_BYTES = 4 * 1024 * 1024  # a prepared photo weighs a few hundred KB
MAX_PROMPT = 8000  # Notosaurus's own prompts are under 1,000 characters
MAX_INSTRUCTIONS = 10_000  # standing instructions, for everyone and for the pupil
MAX_PAGE_TEXT = 20_000  # per photo; the AI gets the first llm.PAGE_TEXT_MAX
MAX_NAME = 300  # a deck name
MAX_DECKS = 1000
MAX_INSTRUCTION = 2000  # a correction
MAX_SUBJECT = 1000  # a picture's subject, a figure's description
MAX_SPEECH = 500  # a back read aloud (the app reads the first 200 characters)
MAX_AUDIO_BYTES = 3 * 1024 * 1024  # a dictation: the app stops at 2 minutes (≈ 500 KB of AAC)

# Error code → HTTP status, besides the AI's own errors ("llm.*", passed on)
ERRORS = {
    "relay.invalid_key": 401,  # no licence key, unknown, or ended
    "relay.no_credits": 402,  # this period's credits are used up
    "relay.daily_limit": 429,  # too many credits used today: tomorrow, or wait
    "relay.too_large": 413,  # too many photos, or one too heavy
    "relay.bad_image": 415,  # a photo that isn't JPEG, PNG, WebP or GIF
    "relay.bad_audio": 415,  # a recording that isn't one of AUDIO_TYPES
    "relay.invalid_request": 422,  # a request that isn't the API's (params: "detail")
    "relay.client_outdated": 426,  # update Notosaurus
    "relay.unavailable": 503,  # the relay itself is down or overloaded
}

IMAGE_TYPES = ("image/jpeg", "image/png", "image/webp", "image/gif")
AUDIO_TYPES = ("audio/aac", "audio/ogg", "audio/mpeg", "audio/wav", "audio/flac")

Language = Field(default="English", max_length=50, description='English name of the language to answer in ("French").')
Instructions = Field(
    default="",
    max_length=MAX_INSTRUCTIONS,
    description="The user's standing instructions, put before the request (never replacing the rules).",
)
PageTexts = Field(
    default_factory=list,
    max_length=MAX_IMAGES,
    description='One per photo: the text of a PDF page, as the PDF holds it ("" for a photo).',
)


class Error(BaseModel):
    """Body of every error: a code the client translates, and its parameters."""

    code: str
    params: dict = Field(default_factory=dict)


class Usage(BaseModel):
    credits: int = Field(ge=0, description="Credits this call used.")
    credits_left: int = Field(ge=0, description="Credits left in this period.")


# --- Requests -----------------------------------------------------------------


class ExtractRequest(BaseModel):
    """Cards from the photos (the "images" parts, in order), or from the prompt alone."""

    prompt: str = Field(min_length=1, max_length=MAX_PROMPT, description="What to make of the lesson.")
    deck: str = Field(default="", max_length=MAX_NAME, description="Deck name template.")
    decks: list[str] = Field(
        default_factory=list, max_length=MAX_DECKS, description="Decks that exist already, to reuse their names."
    )
    fun_facts: bool = False
    helps: bool = False
    page_texts: list[str] = PageTexts
    instructions: str = Instructions
    quick: bool = Field(
        default=False, description="Made fast: the AI thinks little (2 to 4 times faster, a little less careful)."
    )


class ReviseRequest(BaseModel):
    """A natural-language correction of the cards, with the lesson's photos (the
    "images" parts, possibly none)."""

    prompt: str = Field(max_length=MAX_PROMPT, description="What the cards were made with.")
    deck: Deck
    instruction: str = Field(min_length=1, max_length=MAX_INSTRUCTION)
    language: str = Language
    instructions: str = Instructions


class ExplainRequest(BaseModel):
    """A card explained to the pupil (or an example, a way to remember it, why the
    answer is right). JSON."""

    card: Card
    kind: Literal["explain"] | FollowUp = "explain"
    prompt: str = Field(max_length=MAX_PROMPT)
    deck: str = Field(max_length=MAX_NAME)
    language: str = Language
    instructions: str = Instructions
    page_texts: list[str] = PageTexts


class FigureRequest(BaseModel):
    """An exact figure (geometry, a labelled drawing), drawn as SVG. JSON."""

    description: str = Field(min_length=1, max_length=MAX_SUBJECT, description="What to draw, every label exact.")


class SpeakRequest(BaseModel):
    """POST /v1/speak: a text read aloud. Answer: the mp3 (audio/mpeg), its credits in
    CREDITS_HEADER and CREDITS_LEFT_HEADER (a share of the characters' real cost, at
    least 1)."""

    text: str = Field(min_length=1, max_length=MAX_SPEECH)
    voice: str = Field(max_length=100, description='One of /v1/voices ("es-ES-Chirp3-HD-Aoede").')
    rate: float = Field(default=0.9, ge=0.25, le=2.0, description="The speed: 1 normal, 0.9 a little slower.")


class TranscribeRequest(BaseModel):
    """A dictation (the "audio" part) as the text its speaker meant to type: their words,
    hesitations out, their own corrections applied, a lesson's foreign words spelled right."""

    kind: Dictated = Field(description="What it is for: a lesson's instructions, or a correction of its cards.")
    language: str = Language


class RephraseRequest(BaseModel):
    """A lesson's instructions tidied up: clear and short, every intention kept, none added. JSON."""

    text: str = Field(min_length=1, max_length=MAX_PROMPT, description="The instructions as written (or dictated).")
    language: str = Language


class PictureSearchRequest(BaseModel):
    """Free pictures of a subject to choose from. JSON."""

    subject: str = Field(min_length=1, max_length=200, description="What to find (English, unless `translate`).")
    context: str = Field(default="", max_length=MAX_PROMPT, description='The card, "front → back".')
    translate: bool = Field(
        default=False, description="Written in any language: turned into English search words by the AI first."
    )


class FoundPictureRequest(BaseModel):
    """POST /v1/pictures/found: one of the pictures found, as the card's. Answer: the JPEG
    itself, card size."""

    source: Source
    id: str = Field(min_length=1, max_length=300, description="Found.id, as /v1/pictures/search gave it.")


class PictureRequest(BaseModel):
    """A picture for a card: a free one found when `search` is given and one fits (chosen
    by the AI), else drawn by an image model. JSON; the answer is the JPEG itself."""

    subject: str = Field(min_length=1, max_length=MAX_SUBJECT, description="What to draw, in English.")
    fresh: bool = Field(default=False, description="Draw it again rather than reuse the last drawing.")
    search: str = Field(
        default="", max_length=MAX_SUBJECT, description="Card.picture_search: a free picture looked for first."
    )
    context: str = Field(
        default="", max_length=MAX_PROMPT, description='The card, "front → back": to choose the picture found.'
    )


# --- Answers ------------------------------------------------------------------


class ExtractResponse(Extracted):
    usage: Usage


class ExtractLine(BaseModel):
    """A line of /v1/extract's answer as the AI writes it (STREAM_TYPE), one of:
    {"card"} as soon as a card is written; {"restart": true}: the cards sent so far
    are dropped (another model starts again); last, {"result"} or {"error"} (the
    HTTP status is 200 once a line is sent: an error comes as the last line). A
    client going away stops the AI: what it used is charged, at least 1 credit."""

    card: dict | None = Field(default=None, description="A card as the AI wrote it (Card's fields, some missing).")
    restart: bool | None = None
    result: ExtractResponse | None = None
    error: Error | None = None


class ReviseResponse(Revision):
    usage: Usage


class ExplainResponse(Explanation):
    usage: Usage


class TranscribeResponse(BaseModel):
    text: str = Field(description='What was said, as written text ("" when nothing was understood).')
    usage: Usage


class RephraseResponse(BaseModel):
    text: str = Field(description="The instructions, tidied up.")
    usage: Usage


class PictureSearchResponse(BaseModel):
    results: list[Found] = Field(description="The pictures found, at most 8, the sources taking turns.")
    words: str = Field(default="", description="What was searched for (the translation, when asked).")


class PlanPictureRequest(BaseModel):
    """What a card's picture should be ("🎨 Draw"): an exact figure or an image model's
    picture, described from the card and what the user wrote. JSON."""

    front: str = Field(max_length=MAX_PROMPT)
    back: str = Field(max_length=MAX_PROMPT)
    asked: str = Field(default="", max_length=MAX_SUBJECT, description="What the user wrote, any language.")
    language: str = Language


class PlanPictureResponse(PicturePlan):
    usage: Usage


class FigureResponse(BaseModel):
    svg: str = Field(description="The figure, cleaned: shapes and text only (figures.clean).")
    usage: Usage


class Voice(BaseModel):
    """GET /v1/voices gives a list of them: the voices /v1/speak reads with."""

    voice: str = Field(description='Its name, for /v1/speak ("es-ES-Chirp3-HD-Aoede").')
    locale: str = Field(description='The language it speaks ("es-ES").')
    gender: str = Field(description='"Female" or "Male".')


class Account(BaseModel):
    """GET /v1/account: what the licence gives; also the client's connection test."""

    plan: str = Field(description='The subscription ("monthly", "yearly"…).')
    credits_left: int = Field(ge=0, description="Credits left in this period.")
    daily_left: int = Field(ge=0, description="Credits that can still be used today.")
    renews_at: str | None = Field(default=None, description="When the credits are renewed (ISO 8601).")
