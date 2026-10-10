"""The app's own data: lessons, prompts, settings forms and requests. The cards
and what the AI answers are notosaurus_core's (re-exported here)."""

from typing import Literal

from pydantic import BaseModel, Field

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


class LessonIn(Deck):
    # Voice for the back: "es-ES-ElviraNeural" → edge-tts mp3 embedded in the package;
    # "es_ES" → {{tts}} tag read by Anki itself; empty → no sound.
    voice: str = ""
    reverse: bool = False  # adds the reverse card (back → front)
    typing: bool = False  # the answer is typed, Anki compares it letter by letter
    dictation: bool = False  # adds a dictation card: hear the back, type it (needs a voice)
    # Whether every Anki profile sees the lesson (None in an update = unchanged).
    # Only the owner's profile may change it; the owner itself never changes.
    shared: bool | None = None
    # Diagram frames: what Anki shows of each photo (None in an update = unchanged)
    frames: list[Frame] | None = None
    # The prompt it was generated with and what the AI chose, sent back when a
    # regeneration is undone (None in an update = unchanged)
    prompt: str | None = None
    choice: str | None = None


class Lesson(LessonIn):
    id: str  # folder name, e.g. "2026-09-28-spanish-lesson-5"
    prompt: str
    owner: str = ""  # Anki profile open when the lesson was created ("" = none: shared)
    shared: bool = False
    photo_count: int
    frames: list[Frame] = []  # fractions of the photos: from the AI, then as the user set them
    ai_calls: list[AiCall] = []  # generation, then corrections
    choice: str = ""  # what the AI chose to make, when the prompt let it choose
    # One per photo: the text of a PDF page, as the PDF holds it ("" for a photo). Sent
    # to the AI with the pages; not in the lists (LessonSummary)
    page_texts: list[str] = []
    created_at: str
    updated_at: str
    exported_at: str | None = None


class LessonSummary(BaseModel):
    id: str
    deck: str
    owner: str = ""
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


class ExportRequest(LessonIn):
    lesson_id: str | None = None  # saved lesson to update and mark as exported


class PromptIn(BaseModel):
    name: str
    text: str
    deck: str = ""
    voice: str = ""  # see LessonIn.voice
    typing: bool = False  # the lessons made with it start with these options (see LessonIn)
    dictation: bool = False


class RephraseRequest(BaseModel):
    text: str = Field(min_length=1, max_length=8000)  # the instructions as written (or dictated)


class Prompt(PromptIn):
    id: int | str  # the user's: a number; Notosaurus's: "notosaurus:<key>"
    builtin: bool = False  # Notosaurus's own: read-only, can be duplicated
    used_at: str | None = None  # last generation that used this prompt


class SettingsUpdate(BaseModel):
    """Admin page form: None leaves a field unchanged ("" clears an API key)."""

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
    ankiconnect_url: str | None = Field(default=None, pattern=r"^https?://")
    ankiconnect_key: str | None = None
    anki_sync: bool | None = None
    card_helps: bool | None = None
    instructions: str | None = Field(default=None, max_length=4000)
    profile_instructions: dict[str, str] | None = None  # replaces them all ("" removes one)
    picture_service: Literal["", "gemini", "openai", "openrouter", "none"] | None = None
    picture_model: str | None = None
    picture_find: bool | None = None


class PictureSearch(BaseModel):
    """Free pictures of what the user wrote (any language): stock.search."""

    subject: str = Field(min_length=1, max_length=200)
    context: str = Field(default="", max_length=2000)  # the card, "front → back"


class FoundPicture(BaseModel):
    """One of the pictures found, as the card's: stock.fetch."""

    source: Literal["commons", "openverse", "pixabay"]
    id: str = Field(min_length=1, max_length=300)


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
    new: str = Field(min_length=4)


class ExplainRequest(BaseModel):
    card: Card  # as shown (possibly edited, not saved yet)
    kind: Literal["explain"] | FollowUp = "explain"
