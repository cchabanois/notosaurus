"""The timeline and clock families (our timeline and clock functions)."""

import itertools
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


def test_a_timelines_colours_as_the_description_gives_them():
    """A period or an event given a colour (« la Terreur en rouge »): its bar, or its dot and
    text, drawn in it, the others in the function's own; a period said red was drawn in the
    palette's blue, the function taking no colour."""
    body = (
        '#timeline(start: 1788, end: 1800, step: 2, events: ((1789, "Prise de la Bastille", red), '
        '(1792, "République", "flag", blue), (1795, "Directoire")), '
        'periods: ((1793, 1794, "La Terreur", red), (1789, 1792, "Monarchie constitutionnelle")))'
    )
    svg = figures.clean(figures_typst.compile_svg("timeline", body))
    fills = set(re.findall(r'fill="(#[0-9a-f]{6})"', svg))
    assert "#ff847c" in fills  # the red period's bar (red, lightened: its name read on it)
    assert {"#ff4136", "#0074d9"} <= fills  # the events' dots and texts
    assert "#f6c76b" in fills  # the other period: the palette's second (its place)
    plain = figures.clean(
        figures_typst.compile_svg(
            "timeline", '#timeline(start: 1788, end: 1800, step: 2, periods: ((1793, 1794, "La Terreur"),))'
        )
    )
    assert "#9cc9e8" in plain and "#ff847c" not in plain  # none given: the palette's


@pytest.mark.parametrize(
    ("body", "said"),
    [
        ('#timeline(periods: ((1793, 1794, "La Terreur", "red"),))', r"periods: each \(start, end, name\)"),
        ('#timeline(events: ((1789, "Prise", 3),))', r"events: each \(date, text\)"),
    ],
)
def test_a_timelines_colour_written_otherwise_refused(body, said):
    """A colour written as a word, a stray item: refused saying how an item is written."""
    with pytest.raises(figures_typst.Unusable, match=said):
        figures_typst.compile_svg("timeline", body)


def text_runs(svg: str) -> list[tuple[float, float, float]]:
    """Each text run of a Typst SVG: its left, its right (its last glyph's start plus a glyph's
    mean advance) and its baseline's y, its groups' moves added."""
    stack, runs = [(0.0, 0.0)], []
    for tag in re.findall(r"<g(?:\s[^>]*)?>|</g>|<use\s[^>]*>", svg):
        if tag.startswith("<use"):
            if runs and runs[-1][3]:  # a glyph of the run open
                x = float(re.search(r'\sx="([-\d.e]+)"', tag)[1])
                runs[-1][2].append(x)
            continue
        if tag == "</g>":
            stack.pop()
            if runs:
                runs[-1][3] = False
            continue
        x, y = stack[-1]
        if moved := re.search(r'transform="translate\(([-\d.e]+)(?:[ ,]([-\d.e]+))?\)"', tag):
            x, y = x + float(moved[1]), y + float(moved[2] or 0)
        elif text := re.search(r'transform="matrix\(1 0 0 -1 ([-\d.e]+) ([-\d.e]+)\)"', tag):
            x, y = x + float(text[1]), y + float(text[2])
            runs.append([x, y, [], True])
        stack.append((x, y))
    measured = []
    for x, y, glyphs, _ in runs:
        advance = glyphs[-1] / (len(glyphs) - 1) if len(glyphs) > 1 else 6.0
        measured.append((x, x + glyphs[-1] + advance, y))
    return measured


@pytest.mark.parametrize(
    ("start", "end", "step"),
    [(-3500, 2025, 500), (1700, 2025, 10), (-20000, 2000, 1000), (1914, 1918, 1)],
)
def test_a_timelines_numbers_never_on_one_another(start, end, step):
    """The great periods of History from −3500 to 2025, a step of 500: twelve numbers glued
    together on the line ("−3500−3000−2500…"). The function writes every number that fits,
    a round multiple of the step when they don't (every 1000): each apart from the next."""
    svg = figures_typst.compile_svg("timeline", f"#timeline(start: {start}, end: {end}, step: {step})")
    runs = sorted(text_runs(svg))
    assert len(runs) >= 3
    assert len({round(y, 1) for _, _, y in runs}) == 1  # one row, the line's numbers
    for (_, right, _), (left, _, _) in itertools.pairwise(runs):
        assert left - right > 3  # pt: a gap between two numbers


def test_a_timelines_great_periods_numbers_apart():
    """The very frise that went wrong: its numbers each apart from the next, written on round
    multiples of its step (−3000, −2000…: six, not twelve)."""
    body = (
        '#set text(lang: "fr")\n#timeline(start: -3500, end: 2025, step: 500,\n'
        '  events: ((-3000, "Invention de l\'écriture (−3000)"), '
        "(476, \"Chute de l'Empire romain d'Occident (476)\"), "
        '(1492, "Découverte de l\'Amérique (1492)"), (1789, "Révolution française (1789)")),\n'
        '  periods: ((-3500, -3000, "Préhistoire"), (-3000, 476, "Antiquité"), (476, 1492, "Moyen Âge"), '
        '(1492, 1789, "Temps modernes"), (1789, 2025, "Époque contemporaine")),\n)'
    )
    axis = figures_typst.compile_svg("timeline", "#timeline(start: -3500, end: 2025, step: 500)")
    assert len(text_runs(axis)) == len(range(-3000, 2001, 1000))
    figures_typst.compile_svg("timeline", body)  # compiles, the periods and events as before


def test_a_timelines_period_without_its_start_written_open():
    """A period the lesson gives no start for (Prehistory before −3000): a start invented,
    written under its name as a date (−3500 – −3000). Its bound `none`: its bar from the
    line's start, only its known year written (… – −3000); its other bound refused when both
    are missing."""
    line = (
        "#timeline(start: -3500, end: 500, step: 1000, "
        'periods: (({}, -3000, "Préhistoire"), (-3000, 476, "Antiquité")))'
    )
    open_ = figures_typst.compile_svg("timeline", line.format("none"))
    closed = figures_typst.compile_svg("timeline", line.format("-3500"))
    assert closed.count("<use") - open_.count("<use") == len("−3500") - len("…")
    png = lambda svg: figures.to_png(figures.clean(svg))  # noqa: E731
    solid, whole = colour_box(png(open_), FIRST), colour_box(png(closed), FIRST)
    assert solid and whole and solid[2] == pytest.approx(whole[2], abs=2)  # ends at −3000
    import io

    from PIL import Image

    image = Image.open(io.BytesIO(png(open_))).convert("RGB")
    middle = (solid[1] + solid[3]) // 2
    # its fading part from the line's start, where the closed bar starts
    left = next(x for x in range(image.width) if sum(image.getpixel((x, middle))) < 3 * 250)
    assert left == pytest.approx(whole[0], abs=3) and left < solid[0] - 5
    ongoing = figures_typst.compile_svg(
        "timeline", '#timeline(start: 1780, end: 2025, step: 50, periods: ((1789, none, "Époque contemporaine"),))'
    )
    assert ongoing.count("<use") == len("18001850190019502000" + "Époquecontemporaine" + "1789–…")
    with pytest.raises(figures_typst.Unusable, match="none when not known"):
        figures_typst.compile_svg("timeline", '#timeline(start: 0, end: 10, periods: ((none, none, "X"),))')
