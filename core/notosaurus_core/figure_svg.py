"""A figure drawn as SVG by the AI (figure_making: no family of figures_typst draws it, Typst
refusing it twice, the demo): drawn with the drawing rules (RULES), its arrows and labelled
scheme's names set by the app (figure_labels.py), drawn once again when its text is too small to
read or its labels touch, cleaned (figures.clean).
"""

import asyncio
import contextvars
import logging
from collections.abc import Callable
from typing import Any

from . import ai, figure_labels, figures, figures_typst, text_size
from .calls import ExtractionError
from .config import AIConfig
from .errors import AppError
from .prompts import SVG_FIGURE_RULES
from .providers import demo as demo_ai

log = logging.getLogger("notosaurus")

RULES = SVG_FIGURE_RULES

# Each drawing in SVG the AI answered, its labels with their points, and what the app made of
# it, when someone keeps them (the figure bench: a change to how labels are placed judged again
# on the same drawings, without the AI)
answers: contextvars.ContextVar[list[dict] | None] = contextvars.ContextVar("answers", default=None)


def _labelled(drawing: figure_labels.Drawing, clamp: bool = False) -> str:
    """The AI's drawing cleaned, its arrows drawn with their words (figure_labels.arrows_set), its labelled
    scheme's names set beside it clear of them (figure_labels.labelled), grown to what it draws past its frame."""
    points = [(label.x, label.y) for label in drawing.labels]
    arrowed, marks = figure_labels.arrows_set(figures.clean(drawing.svg), drawing.arrows, points)
    svg = figures.fitted(figure_labels.labelled(arrowed, drawing.labels, clamp, marks))
    kept = answers.get()
    if kept is not None:
        kept.append({"drawing": drawing.model_dump(), "clamp": clamp, "svg": svg})
    return svg


async def _readable_svg(s: AIConfig, text: str, svg: str, light: bool, demo: Callable[[], Any]) -> str:
    """The AI's SVG whose text can't be read on a card (a viewBox of 1000 and text of 12: 4 px)
    drawn once again, told its size (text_size.svg_too_small); the more readable of the two kept."""
    said = await asyncio.to_thread(text_size.svg_too_small, svg, figures_typst.MIN_TEXT_PX)
    if not said:
        return svg
    log.warning("Figure drawn again: its text too small")
    asked = f"{text}\n\n{said}"
    try:
        again = await ai._ask_provider(s, [], asked, figure_labels.Drawing, RULES, light=light, demo=demo)
        other = await asyncio.to_thread(_labelled, again, True)
    except (ExtractionError, figures.FigureError) as e:
        if e.code not in figures.UNUSABLE:
            raise
        return svg
    before, after = await asyncio.gather(
        asyncio.to_thread(text_size.smallest_px, svg), asyncio.to_thread(text_size.smallest_px, other)
    )
    kept = len(figures.label_words(other)) >= len(figures.label_words(svg))
    return other if kept and (after or 0) > (before or 0) else svg


async def drawn(s: AIConfig, text: str, description: str, light: bool) -> str:
    """The figure drawn once as SVG, cleaned: a label's point outside the drawing, drawn once
    again (still so, brought to its edge); its text too small, drawn once again (_readable_svg);
    drawn once again when its labels touch (figures.touching_labels)."""
    demo = lambda: demo_ai.figure(description)  # noqa: E731
    drawing = await ai._ask_provider(s, [], text, figure_labels.Drawing, RULES, light=light, demo=demo)
    try:
        svg = await asyncio.to_thread(_labelled, drawing)
    except figure_labels.LabelError as e:
        # a label's point outside the drawing: drawn once again, told which; still so, brought to its edge
        log.warning("Figure drawn again: %s", e)
        asked = f"{text}\n\nIn your answer, {e}. Answer it again, corrected."
        try:
            again = await ai._ask_provider(s, [], asked, figure_labels.Drawing, RULES, light=light, demo=demo)
            svg = await asyncio.to_thread(_labelled, again)
        except (ExtractionError, figures.FigureError, figure_labels.LabelError) as other:
            if isinstance(other, AppError) and other.code not in figures.UNUSABLE:
                raise
            svg = await asyncio.to_thread(_labelled, drawing, True)
    svg = await _readable_svg(s, text, svg, light, demo)
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
            again = await ai._ask_provider(s, [], asked, figure_labels.Drawing, RULES, light=light, demo=demo)
            other = await asyncio.to_thread(_labelled, again, True)
            kept = sorted(figures.label_words(svg)) == sorted(figures.label_words(other))
            if kept and len(await asyncio.to_thread(figures.touching_labels, other)) < len(touching):
                svg = other
        except (ExtractionError, figures.FigureError) as e:
            if e.code not in figures.UNUSABLE:
                raise
    return svg
