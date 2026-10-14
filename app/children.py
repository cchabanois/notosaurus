"""The children the parent makes lessons for, each its card: a first name (the parent's, to
tell them apart: never sent to the AI), a school class, the decks its lessons go in, and
standing instructions. The page says which child a lesson is for (Lesson.child).

A card may be linked to an Anki profile (a profile per child, on the computer): that
profile open, the lesson is for that child (`chosen`); the page chooses it, and offers no
child linked to another profile. Without links (a profile for all, one deck per child,
AnkiDroid), the child is chosen in the page.

data/children.json: {"format": 2, "children": [...]}. Before, the instructions per Anki
profile (Settings.profile_instructions) were the way to tell the children apart: the
first reading makes a card of each, named after its profile and linked to it.
"""

import re
import unicodedata

from pydantic import BaseModel, Field

from . import settings, storage

FORMAT = 2
# A class in the decks' path ("Jules::{classe}"): the child's class there, in any of the
# page's languages (its word in each)
CLASS_TOKEN = re.compile(r"\{(classe|class|klasse|curso|ano)\}", re.IGNORECASE)


class Child(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9-]{1,40}$")
    name: str = Field(min_length=1, max_length=40)  # the parent's: never sent to the AI
    grade: str = Field(default="", max_length=40)  # its school class ("5e"): told to the AI
    decks: str = Field(default="", max_length=200)  # the decks its lessons go in ("Jules::{classe}")
    instructions: str = Field(default="", max_length=4000)  # told to the AI, with every lesson
    anki_profile: str = Field(default="", max_length=100)  # its Anki profile (the computer), if one


def _path():
    return storage.data_dir() / "children.json"


def list_all() -> list[Child]:
    with storage.lock:
        data = storage.read_json(_path())
        if data is None:
            return _from_profiles()
        data = storage.migrate(data, "children", FORMAT, {1: _format_2})
        return [Child(**c) for c in data.get("children", [])]


def _format_2(data: dict) -> dict:
    """Format 1 → 2: the cards made from the instructions per Anki profile (named after it)
    linked to it."""
    profiles = set(settings.current().profile_instructions)
    cards = [
        {**c, "anki_profile": c["name"]} if c.get("name") in profiles and not c.get("anki_profile") else c
        for c in data.get("children", [])
    ]
    return {**data, "children": cards}


def save_all(children: list[Child]) -> list[Child]:
    with storage.lock:
        storage.write_json(_path(), {"format": FORMAT, "children": [c.model_dump() for c in children]})
    return children


def get(id: str | None) -> Child | None:
    return next((c for c in list_all() if c.id == id), None) if id else None


def _from_profiles() -> list[Child]:
    """The instructions per Anki profile, as they were: a child's card each."""
    s = settings.current()
    made, seen = [], set()
    for profile, text in s.profile_instructions.items():
        if not text.strip():
            continue
        base = slug(profile) or "child"
        id_, n = base, 2
        while id_ in seen:
            id_, n = f"{base}-{n}", n + 1
        seen.add(id_)
        made.append(Child(id=id_, name=profile[:40], instructions=text.strip()[:4000], anki_profile=profile[:100]))
    return made


def slug(text: str) -> str:
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", plain).strip("-")[:40]


def chosen(cards: list[Child], id: str | None, profile: str | None) -> Child | None:
    """The child a lesson is for: the one the page chose (`id`), else the one linked to the
    Anki profile it is made in (`profile`), else none."""
    if id:
        return next((c for c in cards if c.id == id), None)
    return next((c for c in cards if profile and c.anki_profile == profile), None)


def for_ai(child: Child | None) -> str:
    """What the AI is told of the child: its class and the parent's instructions; never its
    name (no pupil's data where it isn't needed)."""
    if child is None:
        return ""
    parts = []
    if child.grade.strip():
        parts.append(f"The pupil's school class: {child.grade.strip()} (word the cards and helps for that level).")
    if child.instructions.strip():
        parts.append(child.instructions.strip())
    return "\n".join(parts)


def deck_for(child: Child | None, deck: str) -> str:
    """The lesson's deck in the child's decks ("Jules::{classe}"): the class put in, and the
    levels the deck has already (the AI may have written "Anglais::5e") not twice."""
    if child is None or not child.decks.strip():
        return deck
    prefix = CLASS_TOKEN.sub(child.grade.strip(), child.decks)
    levels = [level.strip() for level in prefix.split("::") if level.strip()]
    seen = {_same(level) for level in levels}
    rest = [level.strip() for level in deck.split("::") if level.strip() and _same(level) not in seen]
    return "::".join(levels + rest)


def for_ai_deck(deck: str, cards: list[Child]) -> str:
    """A deck's name as the AI may see it: the children's levels it starts with (their decks'
    first names and classes, "Jules::5e::") left out, the name of none of them told."""
    return split_deck(deck, cards)[1]


def decks_for_ai(decks: list[str], cards: list[Child], child: Child | None) -> list[str]:
    """The decks the AI may reuse for a lesson of `child`: its own (its levels left out) and
    those of no child; never another child's (nothing of its lessons in this one's)."""
    mine = _levels(child) if child else set()
    kept = set()
    for deck in decks:
        private, rest = split_deck(deck, cards)
        if rest and all(_same(level) in mine for level in private.split("::") if level):
            kept.add(rest)
    return sorted(kept)


def _levels(child: Child) -> set[str]:
    """A child's own levels: its first name, its decks' levels (its class put in)."""
    prefix = CLASS_TOKEN.sub(child.grade.strip(), child.decks)
    return {_same(child.name)} | {_same(level) for level in prefix.split("::") if level.strip()}


def split_deck(deck: str, cards: list[Child]) -> tuple[str, str]:
    """A deck's name as the children's levels it starts with ("Jules::5e") and the rest
    ("Anglais::School subjects"): the rest is what the AI sees, the levels are put back."""
    private = set().union(*(_levels(c) for c in cards)) if cards else set()
    levels = [level.strip() for level in deck.split("::") if level.strip()]
    n = 0
    while n < len(levels) and _same(levels[n]) in private:
        n += 1
    return "::".join(levels[:n]), "::".join(levels[n:])


def _same(level: str) -> str:
    """A deck level as compared: no case, no accents, an ordinal's ending dropped ("5ème", "5e")."""
    plain = unicodedata.normalize("NFKD", level).encode("ascii", "ignore").decode().casefold().strip()
    return re.sub(r"^(\d+)\s*(e|eme|er|ere|re|de|nd|nde|st|rd|th|o|a|º|ª)$", r"\1", plain)
