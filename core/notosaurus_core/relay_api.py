"""The Notosaurus relay's API, version 1: what its client (the Notosaurus app with a
licence, later the Android app) and the relay itself both import, so that they
can't drift apart.

The relay is notosaurus_core behind a licence key: each route is the remote form
of a core function (/v1/extract → llm.extract_cards…), takes what that function
takes but the AI configuration (the relay's own), and keeps nothing.

- Authentication: "Authorization: Bearer <licence key>".
- The client says its version in CLIENT_HEADER ("1.1.0"); a client too old for
  the relay gets "relay.client_outdated".
- The routes with photos (extract, revise, fix-card) take multipart/form-data: a "request"
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
  card size (JPEG), looked up again by its source and id. Both free: no AI, unless the
  search is asked `sort`ed (the AI keeps the pictures that show the subject: 1 credit);
  asked so with "Accept: application/x-ndjson", each source's pictures come as it
  answers (PictureSearchLine). Their pictures (and /v1/picture's) say where they come
  from in PICTURE_SOURCE_HEADER: kept with the card.
- /v1/revise asked with "Accept: application/x-ndjson" says what the AI is at (slow, the
  fallback model), then the answer or the error (ReviseLine).
- /v1/fix-card: one card corrected by the user's request ("the answer is 1789"), seeing
  the lesson's photos: the AI writes that card alone (llm.fix_card).
- /v1/card-picture asked with "Accept: application/x-ndjson" says each step as it begins
  (deciding, drawing, checking, redrawing with the first figure, searching), then the
  answer or the error (CardPictureLine).
- /v1/report: content the AI made, reported by the user (shocking, wrong…: Google Play's
  policy on generated content). The only thing the relay keeps of a lesson: what the user
  saw and sent, for REPORT_DAYS, read by Notosaurus. Free, REPORTS_PER_DAY a licence.
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

from .llm import Extracted, ExtractOptions
from .models import Card, Deck, Dictated, Explanation, FixedCard, FollowUp, PicturePlan, Revision
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
MAX_EXISTING = 500  # a lesson's cards made already (the AI is sent the first 6,000 characters)
MAX_DECKS = 1000
MAX_INSTRUCTION = 2000  # a correction
MAX_SUBJECT = 1000  # a picture's subject, a figure's description
MAX_DRAWN_CARDS = 200  # a lesson's cards wanting a picture
MAX_FIGURE_SVG = 1_000_000  # a figure checked: Typst's, its letters as shapes, weighs tens of KB
MAX_SPEECH = 500  # a back read aloud (the app reads the first 200 characters)
MAX_AUDIO_BYTES = 3 * 1024 * 1024  # a dictation: the app stops at 2 minutes (≈ 500 KB of AAC)
MAX_REPORT = 6000  # a reported card, with its helps, or an explanation
MAX_REPORT_PICTURE = 700_000  # a reported picture, as a data URL (a card's: 512 px, ≈ 60 KB)
REPORT_DAYS = 180  # a report kept, then deleted
REPORTS_PER_DAY = 20  # a licence's

# Error code → HTTP status, besides the AI's own errors ("llm.*", passed on)
ERRORS = {
    "relay.invalid_key": 401,  # no licence key, unknown, or ended
    "relay.no_credits": 402,  # this period's credits are used up
    "relay.subscription_ended": 402,  # its subscription (Google Play) ended: subscribe again
    "relay.trial_ended": 402,  # the free trial's credits used up, or its days over: subscribe
    "relay.payment_pending": 402,  # its subscription on hold: a renewal's payment failed, to fix in Google Play
    "relay.invalid_purchase": 400,  # a purchase Google Play doesn't know, or not of this app
    "relay.trial_closed": 403,  # no new free trial for now (turned off, or today's all given): subscribe
    "relay.trial_refused": 403,  # no free trial: not the app from Google Play, or not a real phone (Play Integrity)
    "relay.daily_limit": 429,  # too many credits used today: tomorrow, or wait
    "relay.busy": 429,  # too many calls at once for this licence: retry in a moment
    "relay.too_large": 413,  # too many photos, or one too heavy
    "relay.bad_image": 415,  # a photo that isn't JPEG, PNG, WebP or GIF, or can't be read (images.py: a bomb)
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
    pictures: bool = Field(default=False, description="Pictures where they truly help, even unasked by the prompt.")
    page_texts: list[str] = PageTexts
    instructions: str = Instructions
    quick: bool = Field(
        default=False, description="Made fast: the AI thinks little (2 to 4 times faster, a little less careful)."
    )
    existing: list[str] = Field(
        default_factory=list,
        max_length=MAX_EXISTING,
        description='The photos are a lesson\'s next pages: its cards made already ("front [part]"), not made again.',
    )

    def options(self) -> ExtractOptions:
        """All but the prompt, as llm.extract_cards takes them."""
        return ExtractOptions(**self.model_dump(exclude={"prompt"}))


class ReviseRequest(BaseModel):
    """A natural-language correction of the cards, with the lesson's photos (the
    "images" parts, possibly none)."""

    prompt: str = Field(max_length=MAX_PROMPT, description="What the cards were made with.")
    deck: Deck
    instruction: str = Field(min_length=1, max_length=MAX_INSTRUCTION)
    language: str = Language
    instructions: str = Instructions


class FixCardRequest(BaseModel):
    """One card corrected by a natural-language request, with the lesson's photos (the
    "images" parts, possibly none)."""

    prompt: str = Field(max_length=MAX_PROMPT, description="What the cards were made with.")
    deck: str = Field(max_length=MAX_NAME)
    card: Card
    instruction: str = Field(min_length=1, max_length=MAX_INSTRUCTION)
    others: list[str] = Field(
        default_factory=list, max_length=MAX_EXISTING, description="The lesson's other cards' fronts."
    )
    language: str = Language
    instructions: str = Instructions


class LessonDrawingsRequest(BaseModel):
    """The drawings of their own the lesson's photos (the "images" parts) show for these
    cards, cut out (pictures.lesson_drawings): the cards' pictures, before any is looked
    for or drawn."""

    cards: list[Card] = Field(max_length=MAX_DRAWN_CARDS, description="The cards wanting a picture.")


class LessonDrawing(BaseModel):
    card: int = Field(description="The card's index in the request.")
    data: str = Field(description="The drawing, cut out of its page: a JPEG, card size, base64.")


class LessonDrawingsResponse(BaseModel):
    drawings: list[LessonDrawing] = Field(description="Those found; the other cards none (look for theirs).")
    usage: Usage


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


class CheckFigureRequest(BaseModel):
    """POST /v1/check-figure: a figure looked at against its description (the user asked it:
    the "🔍 Check" button), as llm.check_figure. JSON."""

    description: str = Field(min_length=1, max_length=MAX_SUBJECT, description="What it should show.")
    svg: str = Field(min_length=1, max_length=MAX_FIGURE_SVG, description="The figure, as drawn.")


class CheckFigureResponse(BaseModel):
    ok: bool = Field(description="It looks right.")
    problem: str = Field(description="What is wrong, in the cards' language; empty when it looks right.")
    usage: Usage


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
    sort: bool = Field(
        default=False,
        description="The AI keeps only the pictures that show the subject, the best first (it sees them): "
        "1 credit, unless it couldn't sort them. Else free. Asked as STREAM_TYPE: PictureSearchLine.",
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


class AiStep(BaseModel):
    """What the AI is at, for the user waiting (calls.tell)."""

    step: Literal["slow", "fallback", "figures"] = Field(
        description='"slow": no answer yet after a while (the model busy); "fallback": the model not '
        'answering, the fallback one asked; "figures": the cards written, their figures being described.'
    )


class ExtractLine(BaseModel):
    """A line of /v1/extract's answer as the AI writes it (STREAM_TYPE), one of:
    {"card"} as soon as a card is written; {"restart": true}: the cards sent so far
    are dropped (another model starts again); {"step"}: what the AI is at; last,
    {"result"} or {"error"} (the HTTP status is 200 once a line is sent: an error
    comes as the last line). A client going away stops the AI: what it used is
    charged, at least 1 credit."""

    card: dict | None = Field(default=None, description="A card as the AI wrote it (Card's fields, some missing).")
    restart: bool | None = None
    step: AiStep | None = None
    result: ExtractResponse | None = None
    error: Error | None = None


class ReviseResponse(Revision):
    usage: Usage


class FixCardResponse(FixedCard):
    usage: Usage


class ReviseLine(BaseModel):
    """A line of /v1/revise asked as STREAM_TYPE, one of: {"step"}, what the AI is at;
    last, {"result"} or {"error"} (the HTTP status is 200 once a line is sent)."""

    step: AiStep | None = None
    result: ReviseResponse | None = None
    error: Error | None = None


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
    usage: Usage | None = Field(default=None, description="The credits charged: sorted by the AI only.")


class PictureSearchLine(BaseModel):
    """A line of a sorted /v1/pictures/search asked as STREAM_TYPE, one of: {"found"},
    the pictures a source gave that the AI kept, the best first, as each source answers;
    last, {"done"} (its `results` empty: they came as "found") or {"error"} (the HTTP
    status is 200 once a line is sent)."""

    found: list[Found] | None = None
    done: PictureSearchResponse | None = None
    error: Error | None = None


class CardPictureRequest(BaseModel):
    """A card's figure or picture (pictures.card_picture): its own, drawn as it is; or
    what was written for it (any language), the AI deciding a figure or a picture. JSON."""

    card: Card
    asked: str | None = Field(default=None, max_length=MAX_SUBJECT, description="What the user wrote; null: none.")
    language: str = Language
    fresh: bool = Field(default=False, description="Draw it again rather than take it from the cache.")
    find: bool = Field(default=True, description="A free picture looked for first, for a real thing.")
    draw: bool = Field(
        default=True,
        description="A picture no free one fits drawn by the image model (it costs: the user said yes). False: "
        "409 picture.needs_drawing instead, its params what was decided (description, search).",
    )
    problem: str = Field(
        default="",
        max_length=MAX_SUBJECT,
        description="What /v1/check-figure found wrong in the card's figure: drawn again, told it (the user "
        "asked it). Empty: drawn as usual.",
    )
    careful: bool = Field(
        default=False, description="With a problem: drawn with the model's thinking (slower), not quickly."
    )


class CardPictureResponse(BaseModel):
    card: Card = Field(
        description="The card, its picture's fields as decided (figure, picture_prompt…, picture_source)."
    )
    data: str = Field(description="The figure's SVG or the picture's JPEG, base64.")
    media_type: Literal["image/svg+xml", "image/jpeg"]
    usage: Usage


class PictureStep(BaseModel):
    """What a card's picture is being made by, now (pictures.card_picture's steps)."""

    step: Literal["deciding", "drawing", "checking", "redrawing", "searching"] = Field(
        description='"deciding": a figure or a picture; "drawing": a figure drawn, or a picture by the image '
        'model; "checking": the figure looked at; "redrawing": it was wrong, drawn again with the model\'s '
        'thinking; "searching": a free picture looked for.'
    )
    problem: str = Field(default="", description='"redrawing": what was wrong.')
    first: str = Field(default="", description='"redrawing": the first figure, its SVG (never kept).')


class CardPictureLine(BaseModel):
    """A line of /v1/card-picture asked as STREAM_TYPE, one of: {"step"} as each begins;
    last, {"result"} or {"error"} (the HTTP status is 200 once a line is sent)."""

    step: PictureStep | None = None
    result: CardPictureResponse | None = None
    error: Error | None = None


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


class ReportRequest(BaseModel):
    """POST /v1/report: content the AI made, reported by the user. Only what they saw and
    sent: never the lesson's photos, nor the child's name. JSON."""

    kind: Literal["card", "explanation", "picture"] = Field(description="What is reported.")
    reason: Literal["offensive", "wrong", "other"] = Field(description="Shocking or inappropriate, wrong, other.")
    comment: str = Field(default="", max_length=1000, description="The user's words, if any.")
    content: str = Field(
        min_length=1,
        max_length=MAX_REPORT,
        description="The content, as text: the card, its explanation, its picture's subject.",
    )
    picture: str = Field(
        default="",
        max_length=MAX_REPORT_PICTURE,
        pattern=r"^(data:image/(jpeg|png|webp|svg\+xml);base64,[A-Za-z0-9+/=]+)?$",
        description="The card's picture, the AI's or a free one (never the user's photo): as a data URL; else empty.",
    )
    prompt: str = Field(default="", max_length=MAX_PROMPT, description="The instructions the lesson was made with.")
    language: str = Language


class ReportResponse(BaseModel):
    received: bool = True


class Voice(BaseModel):
    """GET /v1/voices gives a list of them: the voices /v1/speak reads with."""

    voice: str = Field(description='Its name, for /v1/speak ("es-ES-Chirp3-HD-Aoede").')
    locale: str = Field(description='The language it speaks ("es-ES").')
    gender: str = Field(description='"Female" or "Male".')


# What the app can be told to turn off (Account.disabled) while a fix of it waits for the
# store: the actions that change the user's data on the phone (AnkiDroid, the lessons),
# which the relay doesn't see, and the costly ones
FEATURES = (
    "anki.send",  # cards sent to AnkiDroid
    "anki.move",  # a lesson's cards moved to its new deck when sent
    "anki.delete",  # its notes deleted from AnkiDroid (after a send, or with the lesson)
    "lesson.complete",  # its next pages added
    "lesson.regenerate",  # made again in its place
    "pictures.search",  # free pictures found
    "pictures.draw",  # pictures drawn
    "trial",  # new free trials (a phone that has one keeps it)
)


class Notice(BaseModel):
    """A message for every user of the app, shown until closed (a problem being fixed…)."""

    id: str = Field(min_length=1, max_length=100, description="Another id: shown again, even once closed.")
    level: Literal["info", "warning"] = "info"
    texts: dict[str, str] = Field(
        min_length=1, description='By language ("fr", "en"…): the app shows its own, else English, else any.'
    )


class Account(BaseModel):
    """GET /v1/account: what the licence gives; also the client's connection test. And what
    the app is told for now (set on the relay, no app update): a notice, the FEATURES
    turned off, the latest version."""

    plan: str = Field(description='The subscription ("monthly", "yearly"…).')
    credits_left: int = Field(ge=0, description="Credits left in this period.")
    daily_left: int = Field(ge=0, description="Credits that can still be used today.")
    renews_at: str | None = Field(default=None, description="When the credits are renewed (ISO 8601).")
    ends_at: str | None = Field(
        default=None,
        description="A subscription: when it ends unless renewed (ISO 8601); none for a licence without end.",
    )
    on_hold: bool = Field(
        default=False,
        description="Past its end because a renewal's payment failed (Google Play's account hold): "
        "a payment to fix in Google Play, not a subscription ended.",
    )
    notice: Notice | None = Field(default=None, description="A message for every user, if any.")
    disabled: list[str] = Field(
        default_factory=list, description="FEATURES turned off for now: the app hides them and refuses them."
    )
    latest: str = Field(default="", description='The latest version of the app ("1.2.0"); "" when not said.')
    drawing_credits: int | None = Field(
        default=None, description="About what a picture drawn by the image model costs, in credits (told to the user)."
    )


class SubscribeRequest(BaseModel):
    """POST /v1/subscribe: a Google Play subscription bought (or restored, on another phone)
    in the app; the relay checks it with Google Play and answers its licence key. The same
    purchase always gives the same key: the phones of one subscription share its credits."""

    purchase_token: str = Field(
        min_length=1, max_length=1000, description="The purchase's token (Google Play Billing)."
    )
    product_id: str = Field(min_length=1, max_length=200, description="The subscription's product id.")


class TrialRequest(BaseModel):
    """POST /v1/trial: the free trial, without a card: a few credits for a while, once per
    phone. Play Integrity's token says it is the app from Google Play on a real phone; the
    same phone always gets the same key (reinstalled: the trial's credits left, not new ones)."""

    integrity_token: str = Field(
        min_length=1, max_length=10000, description="Play Integrity's token (its standard request)."
    )
    device: str = Field(
        pattern=r"^[0-9a-f]{64}$",
        description="The phone, as the app knows it (a SHA-256, in hex): the token's request hash is its own.",
    )


class SubscribeResponse(BaseModel):
    key: str = Field(description="The licence key, for the requests' Authorization header.")
    account: Account
