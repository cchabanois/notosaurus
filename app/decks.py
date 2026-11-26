"""Decks that already exist: the open Anki profile's, and those of the lessons it
sees. Given to the AI so a lesson goes into the right deck ("Maths", not a new
"Mathématiques"), and offered when the deck name is edited."""

from collections.abc import Iterable

from . import ankiconnect, lessons

LIMIT = 150  # enough to recognise the subjects, light in the request
SKIPPED = {"Default"}  # Anki's own deck


def _with_parents(name: str) -> list[str]:
    parts = [p.strip() for p in name.split("::") if p.strip()]
    return ["::".join(parts[: n + 1]) for n in range(len(parts))]


async def _all(profile: str | None, but: str | None = None) -> set[str]:
    """Every deck name: Anki's (Anki closed: none) and the lessons' this profile sees,
    their parents included; `but`: a lesson left out (the one being generated again)."""
    left_out = lessons.get(but) if but else None
    seen = [
        lesson.deck
        for lesson in lessons.list_all()
        if lesson.id != but and (lesson.shared or not lesson.owner or not profile or lesson.owner == profile)
    ]
    return existing(await ankiconnect.deck_names() or [], seen, left_out.deck if left_out else "")


def existing(anki: Iterable[str], lesson_decks: Iterable[str], own: str = "") -> set[str]:
    """The decks that exist: Anki's (but its own, `own`: the deck of the lesson made again, and
    its subdecks: they are its own, not another's), the lessons' with their parents. The
    phone's Generation.existing the same (core/shared-cases.json)."""
    own = own.strip().casefold()
    names = {
        n
        for n in anki
        if n not in SKIPPED and not (own and (n.casefold() == own or n.casefold().startswith(own + "::")))
    }
    for deck in lesson_decks:
        names.update(_with_parents(deck))
    return names


async def known(profile: str | None, but: str | None = None) -> list[str]:
    """Sorted names; the top levels first kept when there are too many. Anki closed:
    the lessons' decks alone. `but`: the lesson being generated again, its deck left out
    (the AI makes a deck no other has: shown its own, it made another, "… (3)")."""
    kept = sorted(await _all(profile, but), key=lambda n: (n.count("::"), n.casefold()))[:LIMIT]
    return sorted(kept, key=str.casefold)


async def new_name(deck: str, profile: str | None, but: str | None = None) -> str:
    """The lesson's own deck, new: a deck that already exists (in Anki, or another
    lesson's) gets " (2)", " (3)"… so two lessons never write into the same deck. Its
    parents may exist ("Maths::Fractions" in "Maths"). `but`: the lesson itself, when
    generated again."""
    return free_name(deck, await _all(profile, but))


def free_name(deck: str, taken: Iterable[str]) -> str:
    """`deck`, or the first of "deck (2)", "deck (3)"… none of `taken` is. Anki doesn't tell
    decks apart by case: neither does this. The phone's Generation.freeName the same."""
    deck = deck.strip()
    names = {name.casefold() for name in taken}
    if not deck or deck.casefold() not in names:
        return deck
    n = 2
    while f"{deck} ({n})".casefold() in names:
        n += 1
    return f"{deck} ({n})"
