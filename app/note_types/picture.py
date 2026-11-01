"""A card's picture (any card's: note_types/common.PICTURE): its fields, where it comes from."""

import html
from pathlib import Path

from .common import SOURCE_FIELD, field_html

SOURCE_NAMES = {"commons": "Wikimedia Commons", "openverse": "Openverse", "pixabay": "Pixabay"}


def picture_fields(card, picture: Path, card_id: str) -> dict[str, str]:
    """A card's picture, on its question ("Picture") or with its answer ("BackPicture":
    picture_on_back), where it comes from, its id (its note's key then: key_of)."""
    shown = f'<img src="{picture.name}">'
    on_back = card.picture_on_back
    return {
        "Picture": "" if on_back else shown,
        "BackPicture": shown if on_back else "",
        SOURCE_FIELD: source(card),
        "Id": card_id,
    }


def source(card) -> str:
    """Where the card's picture comes from, as its note's hidden Source field: "Wikimedia
    Commons · Public domain · Prise de la Bastille · <its page>", "Drawn by <model>" (a figure:
    "… with Typst 0.15.0, ctz-euclide 0.3.0"), "Own photo"."""
    origin = card.picture_source
    if origin is None:
        return ""
    if origin.source == "drawn":
        drawn = f"Drawn by {origin.model}" if origin.model else "Drawn"
        if origin.made_with:  # a figure: credited to what drew it (Typst, its packages)
            drawn += f" with {', '.join(origin.made_with)}"
        return field_html(drawn + (", carefully" if origin.careful else ""))
    if origin.source == "photo":
        return "Own photo"
    if origin.source == "lesson":
        return "Drawing from the lesson's pages"
    parts = [field_html(p) for p in (SOURCE_NAMES.get(origin.source, origin.source), origin.licence, origin.title) if p]
    if origin.page:
        page = html.escape(origin.page, quote=True)
        parts.append(f'<a href="{page}">{page}</a>')
    return " · ".join(parts)
