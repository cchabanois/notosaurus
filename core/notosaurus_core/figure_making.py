"""A card's exact figure drawn by the AI: its family picked, drawn in Typst with that
family's package (figures_typst.py), else as SVG (figure_svg.py), cleaned (figures.py); looked
at against its description when the user asks ("🔍 Check")."""

import asyncio
import contextvars
import logging
from collections.abc import Callable
from typing import Any, Literal, NamedTuple

from pydantic import BaseModel, Field

from . import ai, figure_svg, figures, figures_typst
from .calls import ExtractionError, Image
from .config import AIConfig
from .errors import AppError, loggable
from .prompts import FIGURE_CHECK_RULES, PICTURE_CHECK_RULES

log = logging.getLogger("notosaurus")


# Each drawing in Typst refused on the way to a figure, when someone keeps them (the figure
# bench: why a figure ends drawn as SVG): its family, its Typst, what Typst said
refusals: contextvars.ContextVar[list[dict] | None] = contextvars.ContextVar("refusals", default=None)

# The figure seen as a picture, against its description: what a light drawing gets wrong
# is placing by eye what belongs to another element (a mark off its segment, an angle's
# arc on the other side of its line); looking at it tells, where its coordinates don't
CHECK_RULES = FIGURE_CHECK_RULES


class Checked(BaseModel):
    problem: str = Field(description="The problem, in one short sentence; empty when none.")
    ok: bool


def _unusable_svg(e: Exception) -> str:
    """What the AI is told of a Typst figure whose SVG was refused: why, when it is known (too
    large: told only "unusable", it wrote the same again, then the figure went to SVG)."""
    too_large = getattr(e, "too_large", None)
    if too_large:
        return (
            f"its drawing is too large ({too_large} characters, a figure is a few thousand): "
            "too many marks or shapes drawn (a mark at each point of a curve's samples)"
        )
    return "its SVG was unusable"


def _refused(family: str, body: str, said: str) -> None:
    kept = refusals.get()
    if kept is not None:
        kept.append({"family": family, "typst": body, "said": said})


class MadeFigure(NamedTuple):
    """A figure drawn (made_figure): its SVG, cleaned, and how: "typst" (its family's
    packages) or "svg"; its family; with the model's thinking or not."""

    svg: str
    engine: Literal["typst", "svg"]
    family: str
    careful: bool
    typst: str = ""  # its Typst, what it was drawn with (figures_typst.made_with)
    panels: tuple["MadeFigure", ...] = ()  # a figure in panels (family "panels"): each one drawn


def kept_source(made: MadeFigure) -> str:
    """What a figure was drawn from, to keep beside it (pictures.SourceFile) and draw it again
    from: its Typst, its family being the card's figure_kind; "" for one drawn as SVG or in
    panels (drawn again from its description)."""
    if made.engine != "typst" or made.panels or not made.typst.strip():
        return ""
    return made.typst.strip() + "\n"


def _from_previous(body: str) -> str:
    """Told to the AI drawing a figure again: its Typst as drawn before, to change rather than
    rewrite. Never compiled itself: on the relay it comes from the app, so it is only text for
    the AI, as a description is; what the AI writes is compiled, as always (a function renamed
    since: Typst's message given back to the AI, as for any figure)."""
    return (
        f"\n\nThis figure was drawn before with this Typst:\n{body}\n\n"
        "Start from it: change what the description and anything below ask for, and keep the rest "
        "as it is (its points, values, labels, sizes, colours and layout); write it anew only when "
        "the description asks for another figure. It may call functions the rules above no longer "
        "have: the rules hold."
    )


def credits(made: MadeFigure) -> list[str]:
    """What drew a figure, credited where it shows: Typst and the packages its Typst uses
    (figures_typst.made_with), its panels' together; none for a drawing in SVG."""
    if made.panels:
        return list(dict.fromkeys(name for panel in made.panels for name in credits(panel)))
    return figures_typst.made_with(made.family, made.typst) if made.engine == "typst" else []


async def draw_figure(
    s: AIConfig,
    description: str,
    step: Callable[[dict], Any] | None = None,
    kind: str = "",
    problem: str = "",
    careful: bool = False,
) -> str:
    """The SVG of a figure (made_figure's)."""
    return (await made_figure(s, description, step, kind, problem, careful)).svg


async def made_figure(
    s: AIConfig,
    description: str,
    step: Callable[[dict], Any] | None = None,
    kind: str = "",
    problem: str = "",
    careful: bool = False,
    front: str = "",
    previous: str = "",
    previous_kind: str = "",
    gaps: bool = False,
) -> MadeFigure:
    """A figure, its SVG cleaned (figures.clean) and how it was made, drawn by the cards' AI: in Typst
    (figures_typst.py: a curve computed from its function, marks from their points, angles
    by angle-mark), else as SVG (figure_svg.py). Drawn quickly (light calls), not checked: the
    user checks it when in doubt (check_figure). A light drawing that can't be used: drawn
    again with the model's thinking. `problem`: what the check found in the last one, told
    to the AI: drawn quickly again (told the problem, it mostly gets it right: 9 times in 12,
    10 with thinking, four times slower), with the model's thinking when `careful` (the user
    asks it again after a quick one still wrong). `step`: told each step as it
    begins (relay_api.PictureStep). `kind`: its family, when the AI that described it said it
    (Card.figure_kind): not asked again. `front`: the card it goes on the front of, "question →
    answer": told, nothing written on it gives the answer away (its description, written once
    for cards that share it, may write it); with `gaps`, a text with gaps as its question
    shows it (cards.cloze_question), its answers the words hidden in them. `previous`: its Typst when drawn before
    (kept_source), in the family `previous_kind`, drawn again after a correction: the AI
    starts from it, changing what is asked and keeping the rest (another family by now:
    drawn anew). Refused when figures are turned off (s.figures)."""
    if not s.figures:
        raise AppError("relay.feature_off", 403, feature="figures.draw")
    tell = step or (lambda _: None)
    text = f"Figure to draw: {description.strip()}"
    if front.strip() and gaps:
        text += (
            f"\n\nIt goes on the front of a card, a text with gaps, each shown hidden ([…], or its hint in "
            f"brackets): {front.strip()}. The words hidden in its gaps are the answers. Write nothing on the "
            "figure that fills a gap or gives its words away (a name, a date, a count, a measure), even where "
            "the description writes it."
        )
    elif front.strip():
        text += (
            f"\n\nIt goes on the front of a card, with its question; the answer is on the back: {front.strip()}. "
            "Write nothing on the figure that gives this answer away (a name, a count, a measure), "
            "even where the description writes it."
        )
    family = await _figure_family(s, description, kind, problem)
    if family == "panels":
        parts = await _panels(s, description)
        if parts:
            return await _in_panels(s, parts, step, problem, careful, front, gaps)
        family = "other"  # not split: drawn as one SVG
    if previous.strip() and previous_kind == family:
        text += _from_previous(previous.strip())
    if problem.strip():
        text += f"\n\nA first drawing had this problem: {problem.strip()} Draw it right."
        if careful:
            tell({"step": "redrawing", "problem": problem.strip()})
            return await _drawn(s, text, description, family, light=False)
    tell({"step": "drawing"})
    try:
        return await _drawn(s, text, description, family, light=True)
    except (ExtractionError, figures.FigureError) as e:
        if e.code not in figures.UNUSABLE:
            raise
        log.warning("Figure drawn again with thinking: %s", loggable(e))
    tell({"step": "redrawing", "problem": ""})
    return await _drawn(s, text, description, family, light=False)


async def _panels(s: AIConfig, description: str) -> list:
    """A figure in panels split into them (figures_typst.Panels), from left to right: [] when
    the AI's answer can't be used, or gives fewer than two."""
    try:
        split = await ai._ask_provider(
            s, [], f"Figure: {description.strip()}", figures_typst.Panels, figures_typst.PANELS_RULES, light=True
        )
    except ExtractionError as e:
        if e.code not in figures.UNUSABLE:
            raise
        return []
    parts = [p for p in split.panels if p.description.strip()][:3]
    return parts if len(parts) >= 2 else []


async def _in_panels(
    s: AIConfig,
    parts: list,
    step: Callable[[dict], Any] | None,
    problem: str,
    careful: bool,
    front: str,
    gaps: bool = False,
) -> MadeFigure:
    """Each panel drawn by its own kind, at once (what a check found told to each), then set
    side by side (figures.side_by_side): Typst's when one of them is."""
    made = await asyncio.gather(
        *(made_figure(s, p.description, step, p.family, problem, careful, front, gaps=gaps) for p in parts)
    )
    svg = await asyncio.to_thread(figures.side_by_side, [m.svg for m in made])
    engine = "typst" if any(m.engine == "typst" for m in made) else "svg"
    return MadeFigure(svg, engine, "panels", any(m.careful for m in made), panels=tuple(made))


async def check_figure(s: AIConfig, description: str, svg: str) -> str:
    """What is wrong in a figure, seen as a picture against its description (the user asked
    it: the "🔍 Check" button); "" when it looks right. figure.invalid: it can't be seen."""
    # off the event loop: a large figure takes a while to draw, and other requests wait meanwhile
    png = await asyncio.to_thread(lambda: figures.to_png(figures.clean(svg)))
    if png is None:
        raise figures.FigureError("figure.invalid")
    checked = await ai._ask_provider(
        s,
        [Image(png, "image/png")],
        f"Description: {description.strip()}",
        Checked,
        CHECK_RULES,
        light=True,
        demo=lambda: Checked(ok=True, problem=""),
    )
    return "" if checked.ok else (checked.problem.strip() or "It doesn't match its description.")


async def check_picture(s: AIConfig, card: str, meant: str, data: bytes, media_type: str) -> str:
    """What is wrong in a card's picture (a photo found, drawn by the image model, the user's),
    seen against the card (`card`: "question → answer"; `meant`: what it was to show, when said):
    the user asked it (the "🔍 Check" button); "" when it illustrates the card."""
    text = f"The card: {card.strip()}"
    if meant.strip():
        text += f"\nThe picture was meant to show: {meant.strip()}"
    checked = await ai._ask_provider(
        s,
        [Image(data, media_type)],
        text,
        Checked,
        PICTURE_CHECK_RULES,
        light=True,
        demo=lambda: Checked(ok=True, problem=""),
    )
    return "" if checked.ok else (checked.problem.strip() or "It doesn't illustrate the card.")


async def _figure_family(s: AIConfig, description: str, kind: str = "", problem: str = "") -> str:
    """Which family of figures_typst draws it: `kind` when given (the AI that described it
    said it), else a light call; "other" (drawn as SVG): none of them, Typst not installed or
    not used (s.typst), the demo, or not told. Drawn again told what is wrong (`problem`: a
    check's, a correction's): asked again, told the family it was drawn in, kept unless what
    is wrong is the kind of drawing itself, or another one is asked; one drawn as SVG ("other":
    no family drew it then, or one was asked) given a family that draws it now, families being
    added (a map before the atlas). Never on every drawing: a family picked again could differ
    for nothing, and a correction's figure is drawn again from its own, in its family."""
    if s.llm == "fake" or not s.typst or not figures_typst.available():
        return "other"
    known = kind in figures_typst.FAMILIES or kind == "other"
    if known and not problem.strip():
        return kind
    text = f"Figure: {description.strip()}"
    if known:
        text += (
            f"\n\nIt was drawn as {kind}, and is drawn again because: {problem.strip()}\n"
            f"Give {kind} again, unless what is wrong is the kind of drawing itself, or it asks for another "
            "kind: another family, or a drawing made freely, in SVG, not in a family's style (other: what "
            "it gives when it asks for SVG or a free drawing). Drawn as other, give the family that draws "
            "it, if one does now; other only when none does, or when it is asked."
        )
    try:
        picked = await ai._ask_provider(s, [], text, figures_typst.Kind, figures_typst.FAMILY_RULES, light=True)
    except ExtractionError as e:
        if e.code not in figures.UNUSABLE:
            raise
        return kind if known else "other"  # asked again for nothing usable: as it was
    return picked.family


async def _drawn(s: AIConfig, text: str, description: str, family: str, light: bool) -> MadeFigure:
    """A figure drawn once, cleaned: in Typst with its family's package and rule (asked again
    once, told what Typst said, when it doesn't compile), else as SVG (family "other", Typst
    refusing it twice; the demo: figure_svg.drawn)."""
    if family in figures_typst.FAMILIES:
        rules = figures_typst.FAMILIES[family].rules + figures_typst.COMMON
        asked = text
        small: figures_typst.TooSmall | None = None  # the most readable drawing too small, its body
        small_body = ""
        for _ in range(2):
            try:
                body = (await ai._ask_provider(s, [], asked, figures_typst.Figure, rules, light=light)).typst
            except ExtractionError as e:
                if e.code not in figures.UNUSABLE:
                    raise
                _refused(family, "", f"the AI's answer was unusable: {e.code}")
                break
            try:
                svg = figures.clean(await asyncio.to_thread(figures_typst.compile_svg, family, body))
                return MadeFigure(svg, "typst", family, not light, body)
            except (figures_typst.Unusable, figures.FigureError) as e:
                if isinstance(e, figures_typst.TooSmall) and (small is None or e.px > small.px):
                    small, small_body = e, body
                said = str(e) if isinstance(e, figures_typst.Unusable) else _unusable_svg(e)
                _refused(family, body, said)
                asked = (
                    f"{text}\n\nYour previous answer didn't compile:\n{body}\n\n"
                    f"Typst said: {said}\n\nAnswer it again, corrected."
                )
        # drawn again still too small to read (or refused): the most readable drawing, rather
        # than one drawn as SVG
        if small is not None:
            log.warning("Figure kept too small: %.1f px", small.px)
            try:
                return MadeFigure(figures.clean(small.svg), "typst", family, not light, small_body)
            except figures.FigureError as e:  # refused by the cleaning: drawn as SVG, as when Typst refuses it
                _refused(family, small_body, _unusable_svg(e))
        log.warning("Figure drawn as SVG: Typst refused it")
    svg = await figure_svg.drawn(s, text, description, light)
    return MadeFigure(svg, "svg", family, not light)
