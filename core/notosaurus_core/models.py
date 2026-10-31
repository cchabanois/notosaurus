"""What the AI is asked for and answers: cards, decks, diagram masks and frames,
corrections, explanations, and the record of each call."""

from typing import Literal

from pydantic import BaseModel, Field

from .figures_typst import KINDS, FigureKind


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

    source: Literal["commons", "openverse", "pixabay", "drawn", "photo", "lesson"]  # lesson: its own pages' drawing
    licence: str = ""  # a free picture's: "Public domain", "CC0", "Pixabay"
    page: str = ""  # its page at its source
    title: str = ""
    model: str = ""  # a drawing's: the model that drew it
    # A figure's: drawn in Typst or as SVG; Typst's and its packages' names and versions
    # ("Typst 0.15.0", "ctz-euclide 0.3.0"), credited where it shows; with the model's thinking
    engine: Literal["", "typst", "svg"] = ""
    made_with: list[str] = []
    careful: bool = False


class Doubt(BaseModel):
    """A card whose lesson is clearly wrong (a pupil's notes, a copy mistake): the card says
    what the lesson says, this what is right; the parent chooses."""

    reason: str = Field(description="One short sentence: what the lesson says, and what is right.")
    front: str = Field(description="The card's front, corrected.")
    back: str = Field(description="The card's back, corrected.")


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
        description="When the card gets a picture, as the rules and the request say: what to draw, in English. "
        "Empty otherwise.",
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
    figure_kind: Literal["", FigureKind] = Field(
        default="", description=f"With a figure, which kind it is: {KINDS}. Empty otherwise."
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
    doubt: Doubt | None = Field(
        default=None,
        description="Only when the lesson itself is clearly wrong on this card (see the rules); otherwise null.",
    )
    # Set by Notosaurus, not by the AI:
    picture: str = Field(default="", description="Leave empty.")  # file in the lesson's images/ folder
    picture_source: PictureSource | None = Field(default=None, description="Leave empty.")
    id: str = Field(default="", description="Leave empty.")  # stable: tells Anki which note a card is
    # Its sound's voice when not the lesson's (a lesson moved from the other device: tts.card_voice)
    voice: str = Field(default="", description="Leave empty.")


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
    dictation: bool = Field(
        default=False,
        description="True when the instructions ask for dictation cards only (the pupil hears the back read "
        "aloud and writes it; no question → answer card), or, whenever they let you choose the kind of "
        "cards, when the page is a dictation to prepare (a text or a list of words to learn to write) and "
        "you made only dictation cards for it. Otherwise false.",
    )
    dictation_card: bool = Field(
        default=False,
        description="True when the instructions ask, besides the question → answer cards, for a dictation of "
        "each card too (hear the back read aloud, write it). Otherwise false.",
    )
    typing: bool = Field(
        default=False,
        description="True when the instructions ask for the answers to be typed (the pupil writes the answer, "
        "checked letter by letter: spelling, words with blanks). Otherwise false.",
    )
    read_aloud: bool = Field(
        default=False,
        description="True when the instructions ask for the backs to be heard, read aloud (a text to recite, "
        "a pronunciation to hear), even in the pupil's own language. Otherwise false.",
    )
    reverse: bool = Field(
        default=False,
        description="True when the instructions ask for the reverse card too (each card asked both ways: "
        "back → front as well). Anki makes that card from each card: never write the reverse cards yourself. "
        "Otherwise false.",
    )
    speed: Literal["", "slow", "normal"] = Field(
        default="",
        description='How fast the instructions ask for the backs to be read aloud: "slow" (e.g. "read slowly") '
        'or "normal" (e.g. "at normal speed"). Empty when they don\'t say.',
    )


class Revision(Deck):
    """Cards after a natural-language correction, with what changed."""

    summary: str = Field(description="One short sentence describing what changed, in the requested language.")
    # How the cards are asked, when the correction says to change it ("both ways", "without
    # typing"): "on", "off", or "" (unchanged). Anki makes these cards: never write them.
    reverse: Literal["", "on", "off"] = Field(
        default="",
        description='"on" when the correction asks for the reverse card too (each card asked both ways), "off" '
        "when it asks for one way only; otherwise empty. Anki makes that card: never write it yourself.",
    )
    typing: Literal["", "on", "off"] = Field(
        default="",
        description='"on" when the correction asks for the answers to be typed, "off" when it asks for them '
        "not to be; otherwise empty.",
    )
    dictation: Literal["", "on", "off"] = Field(
        default="",
        description='"on" when the correction asks for a dictation of each card (hear the back, write it), '
        '"off" when it asks for none; otherwise empty. Anki makes that card: never write it yourself.',
    )


class CardFix(BaseModel):
    """One card after a correction asked for it alone (as the AI fills it: ai_schema)."""

    cards: list[Card] = Field(description="The corrected card: exactly one.")
    summary: str = Field(description="One short sentence describing what changed, in the requested language.")


class FixedCard(BaseModel):
    """A card corrected on its own (llm.fix_card), with what changed."""

    card: Card
    summary: str


def switched(current: bool, said: str) -> bool:
    """A lesson's option after a correction's word on it (Revision: "on", "off", "")."""
    return {"on": True, "off": False}.get(said, current)


# What an AI call was for (transcribe: the relay only)
CallKind = Literal["extract", "revise", "fix", "picture", "explain", "transcribe", "rephrase"]


class AiCall(BaseModel):
    """One request to the AI for a lesson: what it used and cost."""

    at: str
    kind: CallKind
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


class Sorted(BaseModel):
    fitting: list[int] = Field(
        description="The numbers of the pictures that fit, the best first; empty when none does."
    )


class CardFigure(BaseModel):
    card: int = Field(description="The card's number, as listed.")
    figure: str = Field(description="What to draw, every label with its exact text; empty when no figure truly helps.")
    figure_kind: Literal["", FigureKind] = Field(default="", description=f"Which kind of figure it is: {KINDS}.")


class Figures(BaseModel):
    figures: list[CardFigure] = Field(default_factory=list)


class CardDrawing(BaseModel):
    card: int = Field(description="The card's number, as listed.")
    page: int = Field(description="The photo showing its drawing (1 = first).")
    box: list[float] = Field(
        description="The drawing's bounding box, in the format of the instructions: the whole drawing, nothing of "
        "its label nor of another drawing."
    )


class Drawings(BaseModel):
    drawings: list[CardDrawing] = Field(default_factory=list)


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
    figure_kind: Literal["", FigureKind] = Field(
        default="", description=f"A figure: which kind it is, {KINDS}. Empty for a picture."
    )
    search: str = Field(
        default="",
        description="A picture of a real, specific thing: a short English search for a free picture of it. "
        "Empty otherwise.",
    )
    on_back: bool = Field(
        default=False,
        description="True when it shows the card's answer (a label naming it, the answer drawn): it then goes "
        "with the answer, on the back, never giving it away. False when it is needed to answer or only shows "
        "what the question is about.",
    )


class SearchWords(BaseModel):
    words: str = Field(description="A few English words to search free pictures of it.")
