"""What the AI is asked for and answers: cards, decks, diagram masks and frames,
corrections, explanations, and the record of each call."""

from typing import Literal

from pydantic import BaseModel, Field


class Mask(BaseModel):
    """Where a diagram label is, to hide it on the photo (image occlusion).

    From the AI, `box` is in the format its instructions give (depends on the model);
    once saved, it is [x_min, y_min, x_max, y_max] as fractions of the photo's size."""

    page: int = Field(description="Number of the photo showing the label (1 = first photo).")
    n: int = Field(description="Number drawn in place of the label: 1, 2, 3… on each photo.")
    box: list[float] = Field(description="Bounding box of the label's text, in the format of the instructions.")


class PictureSource(BaseModel):
    """Where a card's picture comes from, kept with the card (and, on the computer, in its
    Anki note's hidden Source field): to check a free picture's page later, or find the
    cards using one that must go."""

    source: Literal["commons", "openverse", "pixabay", "drawn", "photo"]
    licence: str = ""  # a free picture's: "Public domain", "CC0", "Pixabay"
    page: str = ""  # its page at its source
    title: str = ""
    model: str = ""  # a drawing's: the model that drew it


class Card(BaseModel):
    front: str = Field(
        description="Front: what is shown first (e.g. the word in the pupil's language), "
        "or the text with its gaps for a cloze card (see the rules)."
    )
    back: str = Field(description="Back: the answer (e.g. the translation in the language being learned).")
    choices: list[str] = Field(
        default_factory=list,
        description="Only for a multiple-choice or true/false card (see the rules): the wrong options. "
        "Empty otherwise.",
    )
    info: str = Field(default="", description="Useful extra info: gender, plural, example… Empty if none.")
    subdeck: str = Field(
        default="", description='Sub-deck (e.g. "Vocabulary", "Conjugation"). Empty for a single deck.'
    )
    tags: list[str] = Field(default_factory=list)
    mask: Mask | None = Field(default=None, description="Only for a diagram label (see the rules); otherwise null.")
    picture_prompt: str = Field(
        default="",
        description="Only when the instructions ask for a picture on the card (see the rules): what to draw, "
        "in English. Empty otherwise.",
    )
    picture_search: str = Field(
        default="",
        description="Only with a picture_prompt, when the picture shows a real, specific thing that photos or "
        "paintings show (a person, a place, a monument, a work of art, an animal, an object, a food): a short "
        'search, in English, for a free picture of it ("Storming of the Bastille painting", "dog"). Empty '
        "when it must be drawn (an abstract word, an action, a scene made up for the card).",
    )
    figure: str = Field(
        default="",
        description="When an exact figure makes the card clearer (see the rules: geometry, or a notion the "
        "lesson's page shows a figure for): what to draw, every label with its exact text. Empty otherwise.",
    )
    fun_fact: str = Field(
        default="",
        description='Only when fun facts are asked for (see the request): one short "did you know" sentence. '
        "Empty otherwise.",
    )
    explanation: str = Field(
        default="",
        description="Only when helps are asked for (see the request): why the answer is the answer, "
        "when understanding helps remember it. Empty otherwise.",
    )
    mnemonic: str = Field(
        default="",
        description="Only when helps are asked for (see the request): a natural way to remember the "
        "answer. Empty otherwise.",
    )
    picture_on_back: bool = Field(
        default=False,
        description="True when the picture or figure belongs to the answer (see the rules); false when it is "
        "needed to answer.",
    )
    # Set by Notosaurus, not by the AI:
    picture: str = Field(default="", description="Leave empty.")  # file in the lesson's images/ folder
    picture_source: PictureSource | None = Field(default=None, description="Leave empty.")
    id: str = Field(default="", description="Leave empty.")  # stable: tells Anki which note a card is


class Deck(BaseModel):
    deck: str = Field(description='Anki deck name, with :: for hierarchy (e.g. "Spanish::Lesson 5 - Family").')
    cards: list[Card]


class TextLine(BaseModel):
    """A line of text on a photo, by its first and last words: its reading direction
    tells how the photo is turned (models place words well, but name directions badly)."""

    page: int = Field(description="Number of the photo (1 = first photo).")
    first_word: list[float] = Field(description="Box of the line's first word, in the format of the instructions.")
    last_word: list[float] = Field(description="Box of the line's last word, in the format of the instructions.")


class Frame(BaseModel):
    """Where a diagram is on a photo: the image Anki gets is cropped to it."""

    page: int = Field(description="Number of the photo (1 = first photo).")
    box: list[float] = Field(
        description="Box of the whole diagram (its drawing and all its labels), in the format of the instructions."
    )


class Extraction(Deck):
    """Cards read from the photos, a line of text on each photo (to save sideways
    photos upright) and the frame of each diagram."""

    text_lines: list[TextLine] = Field(
        default_factory=list,
        description="For each photo: its longest line of printed text (a title, a sentence).",
    )
    frames: list[Frame] = Field(
        default_factory=list, description="For each photo with diagram cards: the frame of the diagram."
    )
    back_language: str = Field(
        default="",
        description="Language of the card backs as a BCP 47 code, in the variety the lesson teaches "
        '(e.g. "es-ES", "en-GB", "de-DE"); empty when the backs aren\'t in a language being learned. '
        "The pupil's own language is not one being learned: a literature, grammar or history lesson "
        "in it gets empty.",
    )
    choice: str = Field(
        default="",
        description="Whenever the instructions let you choose the kind of cards: one short sentence, in the "
        'language of the instructions, saying what you made (e.g. "Spanish vocabulary: French → Spanish"). '
        "Otherwise empty.",
    )


class Revision(Deck):
    """Cards after a natural-language correction, with what changed."""

    summary: str = Field(description="One short sentence describing what changed, in the requested language.")


class AiCall(BaseModel):
    """One request to the AI for a lesson: what it used and cost."""

    at: str
    kind: Literal["extract", "revise", "picture", "explain", "transcribe", "rephrase"]  # transcribe: the relay only
    provider: str  # gemini, anthropic; the service's host for the OpenAI-like ones ("openrouter.ai")
    model: str  # the model that answered (a fallback, if the main one was overloaded)
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost: float | None = None  # US dollars; None: unknown
    exact: bool = False  # cost given by the service (OpenRouter), not estimated from public prices


# What can be asked about a card in the review ("💬"): an explanation, then, when the AI
# says they'd help, an example, a way to remember it, why the answer is right.
FollowUp = Literal["example", "mnemonic", "why"]

# What a dictation is for: the instructions a lesson is made with, or a correction of its cards
Dictated = Literal["prompt", "correction"]


class Explanation(BaseModel):
    text: str = Field(description="The answer to the request, as asked: plain text, short.")
    more: list[FollowUp] = Field(
        default_factory=list,
        description="The follow-ups that would truly help with this card, among "
        '"example", "mnemonic" and "why", not the one just given. Often one or none.',
    )


class Dictation(BaseModel):
    text: str = Field(description='What the user meant to type, as written text ("" when nothing was said).')


class Rephrased(BaseModel):
    text: str = Field(description="The instructions, rewritten: clear, every intention kept, nothing added.")


class Picked(BaseModel):
    choice: int = Field(description="The number of the picture that fits, -1 when none does.")


class CardFigure(BaseModel):
    card: int = Field(description="The card's number, as listed.")
    figure: str = Field(description="What to draw, every label with its exact text; empty when no figure truly helps.")


class Figures(BaseModel):
    figures: list[CardFigure] = Field(default_factory=list)


class PicturePlan(BaseModel):
    """What a card's picture should be, from the card and what the user asked for it."""

    kind: Literal["figure", "picture"] = Field(
        description='"figure": something exact a clean drawing shows (geometry, a diagram, sets, a graph, a '
        'table, labels); "picture": a thing, an animal, a place, a person, a scene.'
    )
    description: str = Field(
        description="A figure: what to draw, in the cards' language, every label with its exact text. A "
        "picture: what to draw, in English, one concrete subject a child recognises at once."
    )
    search: str = Field(
        default="",
        description="A picture of a real, specific thing: a short English search for a free picture of it. "
        "Empty otherwise.",
    )


class SearchWords(BaseModel):
    words: str = Field(description="A few English words to search free pictures of it.")
