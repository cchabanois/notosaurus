"""A card's exact figure drawn by the AI: its family picked, drawn in Typst with that
family's package (figures_typst.py), else as SVG (figures.py); looked at against its
description when the user asks ("🔍 Check")."""

import asyncio
import logging
from collections.abc import Callable
from typing import Any, Literal, NamedTuple

from . import ai
from .calls import ExtractionError, Image
from .config import AIConfig
from .errors import AppError, loggable
from .providers import demo as demo_ai

log = logging.getLogger("notosaurus")


# A light drawing that can't be used: drawn again with the model's thinking
_UNUSABLE = {"llm.invalid_answer", "llm.truncated", "llm.empty_answer", "figure.invalid"}


class MadeFigure(NamedTuple):
    """A figure drawn (made_figure): its SVG, cleaned, and how: "typst" (its family's
    packages) or "svg"; its family; with the model's thinking or not."""

    svg: str
    engine: Literal["typst", "svg"]
    family: str
    careful: bool
    typst: str = ""  # its Typst, what it was drawn with (figures_typst.made_with)


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
) -> MadeFigure:
    """A figure, its SVG cleaned (figures.clean) and how it was made, drawn by the cards' AI: in Typst
    (figures_typst.py: a curve computed from its function, marks from their points, angles
    by angle-mark), else as SVG (figures.py). Drawn quickly (light calls), not checked: the
    user checks it when in doubt (check_figure). A light drawing that can't be used: drawn
    again with the model's thinking. `problem`: what the check found in the last one, told
    to the AI: drawn quickly again (told the problem, it mostly gets it right: 9 times in 12,
    10 with thinking, four times slower), with the model's thinking when `careful` (the user
    asks it again after a quick one still wrong). `step`: told each step as it
    begins (relay_api.PictureStep). `kind`: its family, when the AI that described it said it
    (Card.figure_kind): not asked again. `front`: the card it goes on the front of, "question →
    answer": told, nothing written on it gives the answer away (its description, written once
    for cards that share it, may write it). Refused when figures are turned off (s.figures)."""
    from . import figures

    if not s.figures:
        raise AppError("relay.feature_off", 403, feature="figures.draw")
    tell = step or (lambda _: None)
    text = f"Figure to draw: {description.strip()}"
    if front.strip():
        text += (
            f"\n\nIt goes on the front of a card, with its question; the answer is on the back: {front.strip()}. "
            "Write nothing on the figure that gives this answer away (a name, a count, a measure), "
            "even where the description writes it."
        )
    family = await _figure_family(s, description, kind)
    if problem.strip():
        text += f"\n\nA first drawing had this problem: {problem.strip()} Draw it right."
        if careful:
            tell({"step": "redrawing", "problem": problem.strip()})
            return await _drawn(s, text, description, family, light=False)
    tell({"step": "drawing"})
    try:
        return await _drawn(s, text, description, family, light=True)
    except (ExtractionError, figures.FigureError) as e:
        if e.code not in _UNUSABLE:
            raise
        log.warning("Figure drawn again with thinking: %s", loggable(e))
    tell({"step": "redrawing", "problem": ""})
    return await _drawn(s, text, description, family, light=False)


async def check_figure(s: AIConfig, description: str, svg: str) -> str:
    """What is wrong in a figure, seen as a picture against its description (the user asked
    it: the "🔍 Check" button); "" when it looks right. figure.invalid: it can't be seen."""
    from . import figures

    png = figures.to_png(figures.clean(svg))
    if png is None:
        raise figures.FigureError("figure.invalid")
    checked = await ai._ask_provider(
        s,
        [Image(png, "image/png")],
        f"Description: {description.strip()}",
        figures.Checked,
        figures.CHECK_RULES,
        light=True,
        demo=lambda: figures.Checked(ok=True, problem=""),
    )
    return "" if checked.ok else (checked.problem.strip() or "It doesn't match its description.")


async def _figure_family(s: AIConfig, description: str, kind: str = "") -> str:
    """Which family of figures_typst draws it: `kind` when given (the AI that described it
    said it), else a light call; "other" (drawn as SVG): none of them, Typst not installed or
    not used (s.typst), the demo, or not told."""
    from . import figures_typst

    if s.llm == "fake" or not s.typst or not figures_typst.available():
        return "other"
    if kind in figures_typst.FAMILIES or kind == "other":
        return kind
    try:
        picked = await ai._ask_provider(
            s, [], f"Figure: {description.strip()}", figures_typst.Kind, figures_typst.FAMILY_RULES, light=True
        )
    except ExtractionError as e:
        if e.code not in _UNUSABLE:
            raise
        return "other"
    return picked.family


def _labelled(drawing, clamp: bool = False) -> str:
    """The AI's drawing cleaned, its labelled scheme's names set beside it (figures.labelled),
    grown to what it draws past its frame."""
    from . import figures

    return figures.fitted(figures.labelled(figures.clean(drawing.svg), drawing.labels, clamp))


async def _drawn(s: AIConfig, text: str, description: str, family: str, light: bool) -> MadeFigure:
    """A figure drawn once, cleaned: in Typst with its family's package and rule (asked again
    once, told what Typst said, when it doesn't compile), else as SVG (family "other", Typst
    refusing it twice; the demo), drawn once again when its labels touch (figures.touching_labels)."""
    from . import figures, figures_typst

    if family in figures_typst.FAMILIES:
        rules = figures_typst.FAMILIES[family].rules + figures_typst.COMMON
        asked = text
        for _ in range(2):
            try:
                body = (await ai._ask_provider(s, [], asked, figures_typst.Figure, rules, light=light)).typst
            except ExtractionError as e:
                if e.code not in _UNUSABLE:
                    raise
                break
            try:
                svg = figures.clean(await asyncio.to_thread(figures_typst.compile_svg, family, body))
                return MadeFigure(svg, "typst", family, not light, body)
            except (figures_typst.Unusable, figures.FigureError) as e:
                said = str(e) if isinstance(e, figures_typst.Unusable) else "its SVG was unusable"
                asked = (
                    f"{text}\n\nYour previous answer didn't compile:\n{body}\n\n"
                    f"Typst said: {said}\n\nAnswer it again, corrected."
                )
        log.warning("Figure drawn as SVG: Typst refused it")
    demo = lambda: demo_ai.figure(description)  # noqa: E731
    drawing = await ai._ask_provider(s, [], text, figures.Drawing, figures.RULES, light=light, demo=demo)
    try:
        svg = await asyncio.to_thread(_labelled, drawing)
    except figures.LabelError as e:
        # a label's point outside the drawing: drawn once again, told which; still so, brought to its edge
        log.warning("Figure drawn again: %s", e)
        asked = f"{text}\n\nIn your answer, {e}. Answer it again, corrected."
        try:
            again = await ai._ask_provider(s, [], asked, figures.Drawing, figures.RULES, light=light, demo=demo)
            svg = await asyncio.to_thread(_labelled, again)
        except (ExtractionError, figures.FigureError, figures.LabelError) as other:
            if isinstance(other, AppError) and other.code not in _UNUSABLE:
                raise
            svg = await asyncio.to_thread(_labelled, drawing, True)
    # Its labels written on one another (the AI places its words without measuring them: two
    # tubes' labels « soudeCl⁻ »): drawn once again, told which; kept if fewer touch and none
    # left out (told to make room, the AI dropped the tubes' labels, 3 drawings in 3)
    touching = await asyncio.to_thread(figures.touching_labels, svg)
    if touching:
        log.warning("Figure drawn again: %d of its labels touch", len(touching))
        extents = await asyncio.to_thread(figures.label_extents, svg)

        def told(label: str) -> str:
            left, right = extents.get(label, (0, 0))
            return f"« {label} » (drawn from x = {left} to x = {right}, {right - left} wide)"

        said = "; ".join(f"{told(a)} and {told(b)}" for a, b in touching[:4])
        asked = (
            f"{text}\n\nYour drawing wrote labels on one another, or with no room between them, "
            f"as measured in your SVG's units: {said}. "
            "Draw it again with every label it has, the same words, each clear of the others: more room "
            "between them, a smaller font, or a label on two lines; never a label left out."
        )
        try:
            again = await ai._ask_provider(s, [], asked, figures.Drawing, figures.RULES, light=light, demo=demo)
            other = await asyncio.to_thread(_labelled, again, True)
            kept = sorted(figures.label_words(svg)) == sorted(figures.label_words(other))
            if kept and len(await asyncio.to_thread(figures.touching_labels, other)) < len(touching):
                svg = other
        except (ExtractionError, figures.FigureError) as e:
            if e.code not in _UNUSABLE:
                raise
    return MadeFigure(svg, "svg", family, not light)
