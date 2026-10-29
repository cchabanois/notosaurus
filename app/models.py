"""The app's own data: lessons, prompts, settings forms and requests. The cards
and what the AI answers are notosaurus_core's (re-exported here)."""

import re
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from notosaurus_core.models import (  # noqa: F401
    AiCall,
    Card,
    Deck,
    Explanation,
    Extraction,
    FollowUp,
    Frame,
    Mask,
    Revision,
    TextLine,
)

CARD_ID = re.compile(r"[a-z0-9]{0,40}")  # Notosaurus, the page and the Android app give 12 hex


class LessonOptions(Deck):
    """What a lesson sent by the page and a saved lesson both have, the same way."""

    # Voice for the back: "es-ES-ElviraNeural" → edge-tts mp3 embedded in the package;
    # "es_ES" → {{tts}} tag read by Anki itself; empty → no sound.
    voice: str = ""
    # The voice's speed, e.g. "-10%", chosen at generation (generation._rate); "" (lessons
    # made before): the settings' tts_rate
    rate: str = Field(default="", pattern=r"^([+-]\d{1,2}%)?$")
    reverse: bool = False  # adds the reverse card (back → front)
    typing: bool = False  # the answer is typed, Anki compares it letter by letter
    dictation: bool = False  # adds a dictation card: hear the back, type it (needs a voice)
    dictation_only: bool = False  # with dictation: that card alone (no front → back card)

    @field_validator("cards")
    @classmethod
    def _card_ids(cls, cards: list[Card]) -> list[Card]:
        # A card's id names its picture's file (picture-<id>-…): letters and digits only,
        # as pictures.NAME reads them back ("" = not given yet). Any other (in the AI's
        # answer, or from a page gone wrong) is blanked: the card gets a fresh one (with_ids)
        return [card if CARD_ID.fullmatch(card.id) else card.model_copy(update={"id": ""}) for card in cards]


class LessonIn(LessonOptions):
    """A lesson as the page sends it: None leaves a saved lesson's field unchanged."""

    # Whether every Anki profile sees the lesson. Only the owner's profile may change
    # it; the owner itself never changes.
    shared: bool | None = None
    frames: list[Frame] | None = None  # diagram frames: what Anki shows of each photo
    # The prompt it was generated with and what the AI chose, sent back when a
    # regeneration is undone
    prompt: str | None = None
    choice: str | None = None
    child: str | None = None  # the child it is for (children.Child.id)


class Lesson(LessonOptions):
    """A saved lesson (lesson.json); its fields in the order they always had."""

    shared: bool = False  # see LessonIn.shared
    frames: list[Frame] = []  # fractions of the photos: from the AI, then as the user set them
    prompt: str  # the prompt it was generated with
    choice: str = ""  # what the AI chose to make, when the prompt let it choose
    id: str  # folder name, e.g. "2026-09-28-spanish-lesson-5"
    owner: str = ""  # Anki profile open when the lesson was created ("" = none: shared)
    child: str = ""  # the child it is for (children.Child.id; "" none said)
    photo_count: int
    ai_calls: list[AiCall] = []  # generation, then corrections
    # One per photo: the text of a PDF page, as the PDF holds it ("" for a photo). Sent
    # to the AI with the pages; not in the lists (LessonSummary)
    page_texts: list[str] = []
    # Its notes in Anki, by profile then card id, from its last send: a card whose front
    # was corrected updates its own note (history kept)
    anki_notes: dict[str, dict[str, int]] = {}
    created_at: str
    updated_at: str
    exported_at: str | None = None


@dataclass
class Generated:
    """A lesson's content as the AI made it from the photos, not saved yet: what
    lessons.create, regenerated and completed save."""

    content: LessonIn
    photos: list[bytes]  # upright
    prompt: str = ""  # the prompt it was generated with
    profile: str = ""  # the Anki profile it belongs to ("" = none)
    frames: list[Frame] = field(default_factory=list)  # diagram frames, on the upright photos
    choice: str = ""  # what the AI chose to make (prompt "Automatic")
    page_texts: list[str] = field(default_factory=list)  # one per photo: a PDF page's text, "" for a photo


class LessonSummary(BaseModel):
    id: str
    deck: str
    owner: str = ""
    child: str = ""
    shared: bool = False
    card_count: int
    photo_count: int
    frames: list[Frame] = []  # fractions of the photos: from the AI, then as the user set them
    ai_calls: list[AiCall] = []  # generation, then corrections
    created_at: str
    updated_at: str
    exported_at: str | None = None


class RevisionRequest(LessonIn):
    """Current (possibly unsaved) state of the lesson + the correction to apply."""

    instruction: str = Field(min_length=1, max_length=2000)


class FixCardRequest(BaseModel):
    """A card as shown (possibly edited, not saved yet), the correction asked for it."""

    card: Card
    instruction: str = Field(min_length=1, max_length=2000)
    others: list[str] = Field(default_factory=list, max_length=500)  # the other cards' fronts


class ExportRequest(LessonIn):
    lesson_id: str | None = None  # saved lesson to update and mark as exported


class PromptIn(BaseModel):
    name: str
    text: str
    deck: str = ""
    voice: str = ""  # see LessonIn.voice
    typing: bool = False  # the lessons made with it start with these options (see LessonIn)
    dictation: bool = False
    dictation_only: bool = False


class RephraseRequest(BaseModel):
    text: str = Field(min_length=1, max_length=8000)  # the instructions as written (or dictated)


class Prompt(PromptIn):
    id: int | str  # the user's: a number; Notosaurus's: "notosaurus:<key>"
    builtin: bool = False  # Notosaurus's own: read-only, can be duplicated
    used_at: str | None = None  # last generation that used this prompt


class SettingsUpdate(BaseModel):
    """Admin page form: None leaves a field unchanged ("" clears an API key). Its fields
    are the settings.SPECS marked editable (tests/test_admin.py checks they agree)."""

    llm: Literal["gemini", "anthropic", "openai", "openrouter", "compatible", "fake"] | None = None
    model: str | None = None
    fallback_models: str | None = None
    gemini_api_key: str | None = None
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    openrouter_api_key: str | None = None
    compatible_base_url: str | None = Field(default=None, pattern=r"^(https?://.*)?$")
    compatible_api_key: str | None = None
    tts_rate: str | None = Field(default=None, pattern=r"^[+-]\d{1,2}%$")
    voices: dict[str, str] | None = None  # the voice chosen per language variety (replaces them all)
    ankiconnect_url: str | None = Field(default=None, pattern=r"^https?://")
    ankiconnect_key: str | None = None
    anki_sync: bool | None = None
    fun_facts: bool | None = None
    helps: bool | None = None
    pictures: bool | None = None
    instructions: str | None = Field(default=None, max_length=4000)
    picture_service: Literal["", "gemini", "openai", "openrouter", "none"] | None = None
    picture_model: str | None = None


class DrawPictures(BaseModel):
    draw: bool = False  # the pictures no free one fits drawn by the image model: the user said yes


class PictureSearch(BaseModel):
    """Free pictures of what the user wrote (any language): stock.search."""

    subject: str = Field(min_length=1, max_length=200)
    context: str = Field(default="", max_length=2000)  # the card, "front → back"
    words: str = Field(default="", max_length=200)  # its English search words when known (Card.picture_search)


class FoundPicture(BaseModel):
    """One of the pictures found, as the card's: stock.fetch."""

    source: Literal["commons", "openverse", "pixabay"]
    id: str = Field(min_length=1, max_length=300)


class RedrawRequest(BaseModel):
    """A card's picture drawn again now ("draw"): for a figure, what its check found wrong
    (the AI told it), drawn quickly or `careful`ly; empty: drawn as usual."""

    problem: str = Field(default="", max_length=1000)
    careful: bool = False  # with a problem: with the model's thinking (asked again after a quick one)


class PictureRequest(BaseModel):
    """Draw a card's picture again, with what to draw (None: the card's own): its subject,
    or a figure's description."""

    subject: str | None = Field(default=None, max_length=1000)


class LessonAccess(BaseModel):
    """Settings page: who a lesson belongs to. None leaves a field unchanged;
    owner "" = no owner (the lesson is everyone's)."""

    owner: str | None = Field(default=None, max_length=200)
    shared: bool | None = None


class AdminPassword(BaseModel):
    current: str | None = None
    new: str = Field(min_length=8)  # the settings hold the API keys, open to the network (standalone)


class ExplainRequest(BaseModel):
    card: Card  # as shown (possibly edited, not saved yet)
    kind: Literal["explain"] | FollowUp = "explain"
