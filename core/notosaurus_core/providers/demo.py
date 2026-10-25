"""The demo AI (provider "fake"): canned cards, explanations and corrections, to work on
the page without a key or any cost.

A provider like the others, behind llm._ask_provider: it gets the same request, and
answers what the entry point asking passes it (`answer`), built from what the request
was made of (the prompt, the card, the correction…). Its answers are in Notosaurus's own
terms: its models whole (ids and pictures kept on a correction), its boxes as fractions
of the photo (BOX_FORMAT)."""

from collections.abc import Callable

from pydantic import BaseModel

from ..calls import ExtractionError, Image, OnCard, record
from ..config import AIConfig
from ..figures import Drawing
from ..models import (
    Card,
    Deck,
    Dictation,
    Doubt,
    Explanation,
    Extraction,
    FollowUp,
    Mask,
    Picked,
    PicturePlan,
    Rephrased,
    Revision,
    SearchWords,
    Sorted,
)

# How the demo gives diagram boxes (diagrams.FORMATS): already as Notosaurus keeps them
BOX_FORMAT = "fractions"


async def _demo[T: BaseModel](s: AIConfig, answer: Callable[[], T] | None, on_card: OnCard | None = None) -> T:
    """The demo's `answer` to a request, recorded as a free call; its cards told one by
    one, as a real AI writes them. None: the demo has no answer for this request."""
    if answer is None:
        raise ExtractionError("llm.empty_answer", provider="demo")
    await record(s, "fake", "fake", 0, 0, cost=0.0)
    found = answer()
    if on_card:
        for card in getattr(found, "cards", ()):
            await on_card(card.model_dump(exclude_defaults=True))
    return found


def extraction(images: list[Image], prompt: str, fun_facts: bool = False, helps: bool = False) -> Extraction:
    """The demo's lesson (see _fake), with a fun fact and helps when asked for."""
    found = _fake(images, prompt)
    if fun_facts:  # the demo's "did you know" on its first card
        found.cards[0].fun_fact = "Le savais-tu ? Ce mot vient du latin."
    if helps:  # the demo's helps: an explanation on the first card, a mnemonic on the second
        found.cards[0].explanation = "(démo) Pourquoi c'est la réponse."
        found.cards[-1].mnemonic = "(démo) Une astuce pour retenir."
    choice = "Vocabulaire d'espagnol : français → espagnol" if _lets_choose(prompt) else ""
    return Extraction(deck=found.deck, cards=found.cards, back_language="es-ES", choice=choice)


def _lets_choose(prompt: str) -> bool:
    return "choisis" in prompt or "choose" in prompt


def _fake_vocabulary(images: list[Image], prompt: str) -> Deck:
    """Demo mode, by default: Spanish vocabulary."""
    return Deck(
        deck="Espagnol::Leçon 5 - La famille",
        cards=[
            Card(front="la mère", back="la madre", info="nom féminin", subdeck="Vocabulaire"),
            Card(front="le père", back="el padre", info="nom masculin", subdeck="Vocabulaire"),
            Card(front="les parents", back="los padres", info="masculin pluriel", subdeck="Vocabulaire"),
            Card(front="la sœur", back="la hermana", info="nom féminin", subdeck="Vocabulaire"),
            Card(front="Comment t'appelles-tu ?", back="¿Cómo te llamas?", subdeck="Phrases"),
            Card(
                front=f"({len(images)} photo(s) received)",
                back="demo mode (fake provider)",
                info=prompt[:80],
            ),
        ],
    )


def _fake(images: list[Image], prompt: str) -> Deck:
    """The demo's cards: the kind the prompt's words ask for (the first that matches),
    vocabulary otherwise and when the AI is let choose."""
    if _lets_choose(prompt):  # "Automatic": the demo always chooses vocabulary
        return _fake_vocabulary(images, prompt)
    kinds = (
        (("diagram", "schéma", "schema") if images else (), _fake_diagram),  # a diagram needs a photo
        (("picture", "image", "dessin"), _fake_pictures),
        (("cloze", "trous", "gaps"), _fake_cloze),
        (("qcm", "quiz", "vrai", "true"), _fake_choices),
        (("figure", "géométrie", "geometry", "triangle"), _fake_figures),
        (("dates", "histoire", "history"), _fake_dates),
    )
    words = prompt.lower()
    for keywords, make in kinds:
        if any(w in words for w in keywords):
            return make()
    return _fake_vocabulary(images, prompt)


def _fake_dates() -> Deck:
    """Demo mode, history dates: a pupil's notes, one of them wrong (its doubt)."""
    return Deck(
        deck="Histoire::Dates",
        cards=[
            Card(front="Première Guerre mondiale", back="1914 – 1918"),
            Card(
                front="Génocide des Juifs",
                back="1915",
                doubt=Doubt(
                    reason="La leçon dit 1915 : le génocide des Juifs (la Shoah) a eu lieu de 1941 à 1945 ; "
                    "1915 est l'année du génocide arménien.",
                    front="Génocide des Juifs (Shoah)",
                    back="1941 – 1945",
                ),
            ),
        ],
    )


def _fake_pictures() -> Deck:
    """Demo mode, picture prompt: three words to draw, one that can't be drawn."""
    words = [("an apple", "an apple"), ("a dog", "a dog"), ("an umbrella", "an umbrella"), ("", "tomorrow")]
    return Deck(
        deck="Anglais::Mots courants",
        cards=[
            Card(front="Comment dit-on en anglais ?" if subject else "demain", back=back, picture_prompt=subject)
            for subject, back in words
        ],
    )


def figure(description: str) -> Drawing:
    """Demo mode: a figure drawn."""
    return Drawing(svg=_fake_figure(description))


def _fake_figure(description: str) -> str:
    """Demo mode: a right triangle, its first label taken from the description."""
    label = (description.split("«")[1].split("»")[0].strip() if "«" in description else "hypoténuse")[:30]
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 300"><rect width="400" height="300" fill="white"/>'
        '<polygon points="80,240 320,240 80,60" fill="none" stroke="black" stroke-width="2"/>'
        '<rect x="80" y="225" width="15" height="15" fill="none" stroke="black"/>'
        f'<text x="215" y="140" font-family="sans-serif" font-size="16" transform="rotate(37 215 140)">{label}</text>'
        "</svg>"
    )


def _fake_figures() -> Deck:
    """Demo mode, figure prompt: geometry cards with figures to draw."""
    return Deck(
        deck="Maths::Le triangle rectangle",
        cards=[
            Card(
                front="Comment s'appelle le côté opposé à l'angle droit ?",
                back="l'hypoténuse",
                figure="Un triangle rectangle ABC, rectangle en C, l'angle droit marqué, sans autre étiquette.",
            ),
            Card(
                front="Quel théorème relie les côtés de ce triangle ?",
                back="le théorème de Pythagore",
                figure="Un triangle rectangle, l'hypoténuse étiquetée « c », les autres côtés « a » et « b ».",
            ),
            Card(
                front="Qu'est-ce qu'une tangente à un cercle ?",
                back="Une droite qui touche le cercle en un seul point, perpendiculaire au rayon en ce point.",
                figure="Un cercle de centre O, une droite étiquetée « tangente » qui le touche en T, "
                "le rayon [OT] et l'angle droit en T.",
                picture_on_back=True,
            ),
        ],
    )


def _fake_cloze() -> Deck:
    """Demo mode, cloze prompt: sentences with gaps."""
    return Deck(
        deck="Histoire::La Révolution française",
        cards=[
            Card(
                front="La Révolution française commence en {{c1::1789}} avec la prise de {{c2::la Bastille}}.", back=""
            ),
            Card(front="Le roi {{c1::Louis XVI}} est guillotiné en {{c2::1793}}.", back="place de la Révolution"),
            Card(
                front="La {{c1::Déclaration des droits de l'homme et du citoyen}} est adoptée en {{c1::août}} 1789.",
                back="",
            ),
        ],
    )


def _fake_choices() -> Deck:
    """Demo mode, multiple-choice prompt: two questions and two true/false statements."""
    return Deck(
        deck="Histoire::La Révolution française",
        cards=[
            Card(
                front="En quelle année commence la Révolution française ?",
                back="1789",
                choices=["1715", "1799", "1804"],
            ),
            Card(
                front="Quel roi est guillotiné en 1793 ?",
                back="Louis XVI",
                choices=["Louis XIV", "Louis XV", "Charles X"],
            ),
            Card(front="La Bastille est prise le 14 juillet 1789.", back="Vrai", choices=["Faux"]),
            Card(front="Napoléon est sacré empereur en 1789.", back="Faux", choices=["Vrai"], info="En 1804."),
        ],
    )


def explanation(card: Card, kind: str) -> Explanation:
    """Demo mode: a canned explanation; "why" offered for a multiple choice only."""
    text = f"(démo, {kind}) {card.front.strip()} → {card.back.strip()}."
    more: list[FollowUp] = [k for k in ("example", "mnemonic") if k != kind]
    if card.choices and kind != "why":
        more.append("why")
    return Explanation(text=text, more=more)


def _fake_diagram() -> Deck:
    """Demo mode, diagram prompt: three labels hidden on the first photo."""
    labels = [
        ("la bouche", [0.1, 0.1, 0.35, 0.2]),
        ("le cœur", [0.55, 0.4, 0.85, 0.5]),
        ("l'estomac", [0.2, 0.7, 0.5, 0.8]),
    ]
    return Deck(
        deck="Sciences::Le corps humain",
        cards=[
            Card(front=f"Qu'est-ce que ({n}) ?", back=text, mask=Mask(page=1, n=n, box=box))
            for n, (text, box) in enumerate(labels, 1)
        ],
    )


DEMO = {"removed": "Last card removed (demo).", "added": "One card added (demo).", "addedFront": "(demo addition)"}


def revision(deck: Deck, instruction: str, texts: dict[str, str]) -> Revision:
    """Demo mode: a request mentioning removal drops the last card, anything else adds one."""
    if any(w in instruction.lower() for w in ("supprime", "remove", "delete")) and deck.cards:
        return Revision(deck=deck.deck, cards=deck.cards[:-1], summary=texts["removed"])
    added = Card(front=texts["addedFront"], back=instruction[:60], subdeck="Demo")
    return Revision(deck=deck.deck, cards=[*deck.cards, added], summary=texts["added"])


def _fake_dictation(kind: str) -> str:
    """Demo mode: a canned dictation."""
    return f"(démo, {kind}) Fais dix cartes sur el abuelo et la abuela."


def _fake_rephrased(text: str) -> str:
    """Demo mode: the instructions as they were, marked."""
    return f"(démo) {text.strip()}"


def dictation(kind: str) -> Dictation:
    return Dictation(text=_fake_dictation(kind))


def rephrased(text: str) -> Rephrased:
    return Rephrased(text=_fake_rephrased(text))


def picked() -> Picked:
    """Demo mode: the first picture found (none found: none fits)."""
    return Picked(choice=0)


def sorted_pictures(count: int) -> Sorted:
    """Demo mode: the pictures found, as they came."""
    return Sorted(fitting=list(range(count)))


def picture_plan(back: str, asked: str) -> PicturePlan:
    """Demo mode: a picture of what was asked, else of the card's answer."""
    return PicturePlan(kind="picture", description=asked.strip() or back.strip(), search=asked.strip())


def search_words(asked: str) -> SearchWords:
    """Demo mode: what was asked, searched as it is."""
    return SearchWords(words=asked.strip())
