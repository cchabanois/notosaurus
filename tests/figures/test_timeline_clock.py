"""The timeline and clock families (our timeline and clock functions)."""

import re

import pytest

from notosaurus_core import figures, figures_typst


def test_a_timelines_texts_never_on_one_another():
    """Events a year apart, long texts: each on its own row, the figure taller for it."""
    one = figures_typst.compile_svg(
        "timeline", '#timeline(start: 1780, end: 1800, step: 5, events: ((1789, "Prise de la Bastille"),))'
    )
    crowded = figures_typst.compile_svg(
        "timeline",
        '#timeline(start: 1780, end: 1800, step: 5, events: ((1789, "Prise de la Bastille"), '
        '(1790, "Fête de la Fédération"), (1791, "Fuite à Varennes")), periods: ((1793, 1794, "La Terreur"),))',
    )
    height = lambda svg: float(re.search(r'height="([\d.]+)', svg).group(1))  # noqa: E731
    assert height(crowded) > height(one) * 1.5


def test_a_line_of_moments_writes_no_number():
    """A verb's tenses placed by their order (-1, 0 the present): `step: none` writes no number
    under the line (it wrote "−3", "−2"…), only the texts' letters; `now` marks the present
    across the line, its text under it, `past` and `future` written at the line's ends."""
    texts = '((-1, "Passé"), (0, "Présent"))'
    tenses = f"#timeline(start: -2, end: 2, step: none, events: {texts})"
    svg = figures_typst.compile_svg("timeline", tenses)
    assert svg.count("<use") == len("PasséPrésent")  # a glyph each, no number's
    numbered = figures_typst.compile_svg("timeline", tenses.replace("step: none", "step: 1"))
    assert numbered.count("<use") > svg.count("<use")
    now = figures_typst.compile_svg("timeline", tenses.replace("step: none", 'step: none, now: "Nu"'))
    drawn = lambda svg: svg.split("<defs")[0].count("<path")  # noqa: E731 (the glyphs' are in defs)
    assert drawn(now) > drawn(svg) and now.count("<use") == svg.count("<use") + 2
    ends = figures_typst.compile_svg("timeline", tenses.replace("step: none", 'step: none, past: "P", future: "F"'))
    assert ends.count("<use") == svg.count("<use") + 2


def hand_angle(png: bytes, colour: tuple[int, int, int]) -> float:
    """Where a clock's hand of that colour points: degrees from twelve o'clock, clockwise."""
    import io
    import math

    from PIL import Image

    image = Image.open(io.BytesIO(png)).convert("RGB")
    near = lambda p: sum(abs(a - b) for a, b in zip(p, colour, strict=True)) < 120  # noqa: E731
    points = [(x, y) for y in range(image.height) for x in range(image.width) if near(image.getpixel((x, y)))]
    dx = sum(x for x, _ in points) / len(points) - image.width / 2
    dy = sum(y for _, y in points) / len(points) - image.height / 2
    return math.degrees(math.atan2(dx, -dy)) % 360


@pytest.mark.parametrize(("hour", "minute"), [(10, 30), (3, 0), (8, 45), (15, 20)])
def test_a_clocks_hands_placed_by_the_time(hour, minute):
    """The hands where the time puts them, the hour hand between its hours as the minutes go
    by (half past ten: halfway from 10 to 11), never by eye."""
    body = f"#clock({hour}, {minute}, numbers: false, hour-color: rgb(255, 0, 0), minute-color: rgb(0, 0, 255))"
    png = figures.to_png(figures.clean(figures_typst.compile_svg("clock", body)))
    assert abs(hand_angle(png, (255, 0, 0)) - (hour % 12 + minute / 60) * 30) < 3
    assert abs(hand_angle(png, (0, 0, 255)) - minute * 6) % 360 < 3


def test_a_clock_at_an_impossible_time_refused():
    """A time that isn't one (25 h, 60 min, a half hour as 10.5): refused, saying why, for the
    AI to write it again; never a face drawn at a guess. 15 h is 3 o'clock's face."""
    for body in ("#clock(25, 0)", "#clock(10, 60)", "#clock(10.5, 0)"):
        with pytest.raises(figures_typst.Unusable, match="whole number"):
            figures_typst.compile_svg("clock", body)
    assert figures_typst.compile_svg("clock", "#clock(15, 30)") == figures_typst.compile_svg("clock", "#clock(3, 30)")


@pytest.mark.parametrize(
    "items",
    [
        'events: ((1789, "Prise de la Bastille"))',
        'events: (((1789, 7, 14), "Prise de la Bastille"))',
        'periods: ((1793, 1794, "La Terreur"))',
    ],
)
def test_a_timelines_single_item_without_its_comma_drawn(items):
    """One event or period written without its trailing comma, ((1789, "…")): Typst's pair,
    not a list of one ("integer has no method at"). Taken as the one item it means."""
    with_comma = items[:-1] + ",)"
    alone = figures_typst.compile_svg("timeline", f"#timeline(start: 1780, end: 1800, step: 5, {items})")
    assert alone == figures_typst.compile_svg("timeline", f"#timeline(start: 1780, end: 1800, step: 5, {with_comma})")


@pytest.mark.parametrize(
    ("body", "said"),
    [
        ("#timeline(start: 1780, end: 1800, step: 0)", "step is the years between two numbers"),
        ("#timeline(start: 1780, end: 1800, step: -5)", "step is the years between two numbers"),
        ("#timeline(start: 1789, end: 1789)", "end is after start"),
    ],
)
def test_a_timelines_line_refused_saying_why(body, said):
    """A step of 0 looped without end, a line from a year to the same one divided by zero:
    refused, saying what a line takes."""
    with pytest.raises(figures_typst.Unusable, match=said):
        figures_typst.compile_svg("timeline", body)
