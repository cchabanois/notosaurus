"""The demo AI (provider "fake"): canned cards, explanations and corrections, to work on
the page without a key or any cost."""

from .calls import Image
from .models import Card, Deck, Explanation, Mask, Revision


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


def _fake(images: list[Image], prompt: str, deck: str) -> Deck:
    if _lets_choose(prompt):  # "Automatic": the demo always chooses vocabulary
        return _fake_vocabulary(images, prompt)
    if images and any(w in prompt.lower() for w in ("diagram", "schéma", "schema")):
        return _fake_diagram()
    if any(w in prompt.lower() for w in ("picture", "image", "dessin")):
        return _fake_pictures()
    if any(w in prompt.lower() for w in ("cloze", "trous", "gaps")):
        return _fake_cloze()
    if any(w in prompt.lower() for w in ("qcm", "quiz", "vrai", "true")):
        return _fake_choices()
    if any(w in prompt.lower() for w in ("figure", "géométrie", "geometry", "triangle")):
        return _fake_figures()
    return _fake_vocabulary(images, prompt)


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


def _fake_explanation(card: Card, kind: str) -> Explanation:
    """Demo mode: a canned explanation; "why" offered for a multiple choice only."""
    text = f"(démo, {kind}) {card.front.strip()} → {card.back.strip()}."
    more = [k for k in ("example", "mnemonic") if k != kind] + (["why"] if card.choices and kind != "why" else [])
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


def _fake_revision(deck: Deck, instruction: str, texts: dict[str, str]) -> Revision:
    """Demo mode: a request mentioning removal drops the last card, anything else adds one."""
    if any(w in instruction.lower() for w in ("supprime", "remove", "delete")) and deck.cards:
        return Revision(deck=deck.deck, cards=deck.cards[:-1], summary=texts["removed"])
    added = Card(front=texts["addedFront"], back=instruction[:60], subdeck="Demo")
    return Revision(deck=deck.deck, cards=[*deck.cards, added], summary=texts["added"])


def _fake_dictation(kind: str) -> str:
    """Demo mode: a canned dictation."""
    return f"(démo, {kind}) Fais dix cartes sur el abuelo et la abuela."
