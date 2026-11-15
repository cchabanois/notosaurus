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


def colour_box(png: bytes, colour: tuple[int, int, int]) -> tuple[int, int, int, int] | None:
    """The box (left, top, right, bottom) of a PNG's pixels of that colour, None when none."""
    import io

    from PIL import Image

    image = Image.open(io.BytesIO(png)).convert("RGB")
    near = lambda p: sum(abs(a - b) for a, b in zip(p, colour, strict=True)) < 12  # noqa: E731
    points = [(x, y) for y in range(image.height) for x in range(image.width) if near(image.getpixel((x, y)))]
    if not points:
        return None
    return min(x for x, _ in points), min(y for _, y in points), max(x for x, _ in points), max(y for _, y in points)


FIRST, SECOND = (0x9C, 0xC9, 0xE8), (0xF6, 0xC7, 0x6B)  # the first two periods' colours


def test_a_timelines_overlapping_periods_each_on_its_own_lane():
    """Periods drew one grey bar on the line, a period within another (a battle in its war, a
    council during wars) hidden under it: each period now in its own colour, under the line,
    one that overlaps another on a lane of its own, one that follows another beside it on the
    same lane; its name on its bar."""
    line = "#timeline(start: 1540, end: 1600, step: 10, periods: ({}))"
    overlapping = figures_typst.compile_svg(
        "timeline", line.format('(1545, 1563, "Concile de Trente"), (1562, 1598, "Guerres de Religion")')
    )
    png = figures.to_png(figures.clean(overlapping))
    one, two = colour_box(png, FIRST), colour_box(png, SECOND)
    assert one and two and one[3] < two[1]  # the second lane under the first
    following = figures_typst.compile_svg(
        "timeline", line.format('(1545, 1562, "Concile de Trente"), (1562, 1598, "Guerres de Religion")')
    )
    png = figures.to_png(figures.clean(following))
    one, two = colour_box(png, FIRST), colour_box(png, SECOND)
    assert one and two and abs(one[1] - two[1]) <= 1 and one[2] <= two[0] + 1  # one lane, side by side


def test_a_timelines_numbers_on_the_steps_multiples():
    """The numbers written on the line fall on the step's round multiples (600, 800…), not
    on the start's (476, 676…)."""
    svg = figures_typst.compile_svg("timeline", "#timeline(start: 3, end: 30, step: 10)")
    assert svg.count("<use") == len("102030")


def test_a_timelines_event_keeps_its_year():
    """An event whose text doesn't say its year (the AI dropped it): the function writes it
    after the text; a text that has it unchanged."""
    line = "#timeline(start: 1780, end: 1800, step: 20, events: ((1789, {}),))"
    bare = figures_typst.compile_svg("timeline", line.format('"Bastille"'))
    assert bare.count("<use") == len("17801800" + "Bastille(1789)")
    dated = figures_typst.compile_svg("timeline", line.format('"Bastille 1789"'))
    assert dated.count("<use") == len("17801800" + "Bastille1789")


def test_a_timelines_line_holds_every_date():
    """An event after the line's end (the AI's end a year too short): the line goes on to
    it, as if its end had been that date, never a dot past the arrow."""
    events = 'events: (((1945, 8), "Hiroshima"),)'
    short = figures_typst.compile_svg("timeline", f"#timeline(start: 1939, end: 1945, step: 1, {events})")
    held = figures_typst.compile_svg("timeline", f"#timeline(start: 1939, end: 1945 + 7 / 12, step: 1, {events})")
    assert short == held


def test_a_timelines_numbers_never_cut_in_their_groups():
    """A number written with its thousands apart ("vers -18 000"): never cut at its space,
    "000" alone on the next line; drawn as with a narrow no-break space."""
    line = '#timeline(start: -20000, end: 0, step: 5000, events: ((-18000, "Peintures de Lascaux vers -18{}000"),))'
    assert figures_typst.compile_svg("timeline", line.format(" ")) == figures_typst.compile_svg(
        "timeline", line.format("\\u{202F}")
    )


def test_a_timelines_one_year_period_lasts_its_year():
    """A period of one year, (1914, 1914): its bar from its start to its end drew nothing, a
    sliver. It lasts that year: in its colour, as wide as (1914, 1915)'s."""
    line = '#timeline(start: 1900, end: 1920, step: 5, periods: (({}, "Guerre"),))'

    def bar(period: str) -> tuple[int, int, int, int]:
        box = colour_box(
            figures.to_png(figures.clean(figures_typst.compile_svg("timeline", line.format(period)))), FIRST
        )
        assert box is not None
        return box

    one, year = bar("1914, 1914"), bar("1914, 1915")
    assert one[2] - one[0] > 10
    assert one[2] - one[0] == pytest.approx(year[2] - year[0], abs=2)
