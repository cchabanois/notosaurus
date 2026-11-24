"""Typst's plumbing (figures_typst.py): the packages shipped and unpacked once, compiled
offline and cut when too long, the families' rules and preambles, the kinds, the credits."""

import re

import pytest

from figures.support import TRIANGLE, rule_example
from notosaurus_core import figures, figures_typst


def bench_figures():
    """tools/bench_figures.py, a script: imported from its folder."""
    import sys

    sys.path.insert(0, str(figures_typst.HERE.parent.parent / "tools"))
    import bench_figures

    return bench_figures


def test_a_figure_drawn_in_typst_compiled_offline():
    """Typst with the packages and the font shipped (nothing downloaded): an SVG, black and
    grey, its letters kept by the cleaning (their shapes, used where they go)."""
    svg = figures.clean(figures_typst.compile_svg("geometry", TRIANGLE))
    assert svg.startswith("<svg") and "<use" in svg and "<symbol" in svg  # the letter A
    assert set(re.findall(r'(?:fill|stroke)="(#[0-9a-f]{6})"', svg)) <= {"#000000", "#e1e1e1", "#ffffff"}
    assert figures.to_png(svg)


def test_typst_packages_unpacked_once_from_their_archives():
    """One archive per package (tools/typst_packages.py), each where Typst looks for it
    (preview/<name>/<version>/typst.toml), unpacked once: drawn again, the same folder."""
    archives = sorted(figures_typst.ARCHIVES.glob("*.tar.gz"))
    assert archives and not (figures_typst.ARCHIVES / "preview").exists()
    folder = figures_typst.packages()
    for archive in archives:
        name, version = archive.name.removesuffix(".tar.gz").rsplit("-", 1)
        assert (folder / "preview" / name / version / "typst.toml").is_file()
    stamp = (folder / "preview").stat().st_mtime_ns
    assert figures_typst.packages() == folder and (folder / "preview").stat().st_mtime_ns == stamp
    assert [p.name for p in folder.parent.iterdir() if p.name.startswith("typst-")] == [folder.name]


def test_typst_packages_of_other_archives_removed(monkeypatch, tmp_path):
    """Unpacked for new archives (a new atlas), the folders older archives were unpacked in go
    (about 30 MB each), not the current one, nor what only looks like one (a folder being
    written aside, a link: never followed); one that can't be removed fails nothing."""
    from notosaurus_core import files

    monkeypatch.setattr(files, "_cache_root", lambda: tmp_path / "cache")  # restored after
    cache = tmp_path / "cache"
    (cache / "typst-0123456789ab" / "preview").mkdir(parents=True)
    (cache / "typst-0123456789ab" / "preview" / "typst.toml").write_text("")
    stuck = cache / "typst-ba9876543210"
    (stuck / "preview").mkdir(parents=True)
    (stuck / "preview" / "typst.toml").write_text("")
    (cache / "typst-k3x_8abc").mkdir()  # another process's, being unpacked
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "kept.txt").write_text("")
    (cache / "typst-aaaaaaaaaaaa").symlink_to(elsewhere, target_is_directory=True)
    # Its file can't be removed: its folder read-only (Linux, macOS), the file open as another
    # process reading it holds it (Windows, where a folder's mode doesn't keep its files)
    (stuck / "preview").chmod(0o500)
    try:
        with (stuck / "preview" / "typst.toml").open("rb"):
            folder = figures_typst.packages()
    finally:
        (stuck / "preview").chmod(0o700)
    assert folder.parent == cache and (folder / "preview").is_dir()
    assert not (cache / "typst-0123456789ab").exists()
    assert (stuck / "preview" / "typst.toml").is_file()  # left, the compile not failed
    assert (cache / "typst-k3x_8abc").is_dir() and (elsewhere / "kept.txt").is_file()
    assert figures_typst.compile_svg("geometry", TRIANGLE).startswith("<svg")


def test_typst_cut_when_too_long_and_nothing_loaded(monkeypatch):
    import subprocess

    def slow(*args, **kwargs):
        raise subprocess.TimeoutExpired("typst", figures_typst.COMPILE_S)

    for bad in ('#read("/etc/passwd")', '#plugin("p.wasm")', '#include "x.typ"', '#eval("read(1)")'):
        with pytest.raises(figures_typst.Unusable):
            figures_typst.source("geometry", bad)
    monkeypatch.setattr(subprocess, "run", slow)
    with pytest.raises(figures_typst.Unusable, match="too long"):
        figures_typst.compile_svg("geometry", TRIANGLE)


def test_a_runaway_compile_cut_at_the_timeout(monkeypatch):
    """A body that never ends in time (Typst stops an endless `while` itself, not a long
    loop): its process killed after COMPILE_S, the figure refused. Its own short timeout
    (the tests give Typst a minute: conftest.py)."""
    import time

    monkeypatch.setattr(figures_typst, "COMPILE_S", 1)
    body = "#let n = 0\n#for i in range(100000) { for j in range(100000) { n += 1 } }"
    start = time.monotonic()
    with pytest.raises(figures_typst.Unusable, match="too long"):
        figures_typst.compile_svg("geometry", body)
    assert time.monotonic() - start < 30  # cut, not run to its end (minutes)


# Each word a body may not write, in the forms that reach it without calling it by its name
# where it stands: held in a variable, its arguments given beforehand, called within a text
LOADERS = ("read", "json", "csv", "yaml", "toml", "xml", "cbor", "plugin", "eval")
ALIASED = ('#let f = {w}\n#f("x")', '#let f = {w}.with("x")\n#f()', '#{{ let f = {w}; f("x") }}')


@pytest.mark.parametrize(
    "body",
    [form.format(w=w) for w in LOADERS for form in ALIASED]
    + [
        '#let p = "@preview/no-such-package:1.0.0"\n#{ import p }',  # a package's name held in a variable
        '#let p = "@preview/no-such-package:1.0.0"\n#import p: *',
        '#let p = "x.typ"\n#include p',
        '#read("x")',  # code in a text
        'A text, then #read("x") in it',
        '#{ read("x") }',
        '#strong[a text #read("x")]',
        '$ read("x") $',  # a formula's names are code
        '#if true {\n  1\n}\nelse { read("x") }',
        '#let r = std.read\n#r("x")',  # Typst's own library
        '#std.image("x.png")',
        # a module's name given a string, then imported from
        '#{ cetz = (draw: "@preview/no-such-package:1.0.0") }\n#{ import cetz.draw: * }',
        '#let f(cetz) = { import cetz.draw: * }\n#f((draw: "@preview/no-such-package:1.0.0"))',
    ],
)
def test_nothing_loaded_or_read_however_written(body):
    """A body never loads nor reads anything, whatever it holds the loading in: a name refused
    as it is, not only called (`#let r = read` then `r("…")`; a package's name in a string,
    then imported from: Typst would fetch it)."""
    with pytest.raises(figures_typst.Unusable, match="Only drawing commands"):
        figures_typst.source("geometry", body)


@pytest.mark.parametrize("call", ['#eval("1+1")', '#read("x")', '#plugin("x.wasm")'])
def test_nothing_loaded_once_the_body_is_rewritten(call):
    """What the body becomes before it is compiled is what is checked: a quote escaped in a
    formula (unescaped then, latex_math) pairs again with another, and what was within a string
    is code; refused, the AI told the word."""
    body = '$ \\" a " ' + call + ' \\" b " $'
    word = call[1 : call.index("(")]
    with pytest.raises(figures_typst.Unusable, match=f'Only drawing commands.*"{word}" is refused'):
        figures_typst.source("geometry", body)


@pytest.mark.parametrize("form", ALIASED)
def test_no_image_drawn_however_written(form):
    """`image`, a word a label or a comment says (l'image A'B'), isn't refused as a name: the
    body's draws nothing however it is reached, and says so; the preamble's icons still drawn
    (theirs is Typst's)."""
    with pytest.raises(figures_typst.Unusable, match="No image: only drawing commands"):
        figures_typst.compiled(figures_typst.source("geometry", form.format(w="image")))
    assert figures_typst.compile_svg("diagram", '#scheme(boxes: (a: [#icon("farm") Ferme]))')


# Each forbidden word where it is no code: a comment, a text, a label, a string
SAID = """// {w} in a comment
/* {w} in a block of comment */
{w} in the text
#cetz.canvas({{ import cetz.draw: *
  // {w}, said in the code's comment
  content((0, 0), [{w} in a label, "quoted"])
  content((0, 2), "{w} \\" in a string")
}})"""


def test_a_labels_or_a_comments_words_never_refused():
    """A word a label or a comment says ("import / export", "the json format", "read the
    graph") is never refused: only a name Typst reads as code is; what the body says compiled."""
    for word in figures_typst.FORBIDDEN_WORDS:
        assert not figures_typst.forbidden(SAID.format(w=word)), word
    said = "\n".join(SAID.format(w=word) for word in figures_typst.FORBIDDEN_WORDS)
    assert figures_typst.compiled(figures_typst.source("chemistry", said))


def test_what_the_families_examples_write_accepted():
    """What the AI writes as the rules show it is never refused: every family's example (a
    module of the preamble's imported from, `import cetz.draw: *`), a label's word that is a
    name of Typst's (l'image A'B'), a module's own function called."""
    for family in figures_typst.FAMILIES:
        assert not figures_typst.forbidden(rule_example(family)), family
    for body in (
        "#cetz.canvas({ import cetz.draw: *\n content((0, 0), [l'image A'B'])\n })",
        "#cetz.canvas({ import cetz.draw as d\n d.circle((0, 0)) })",
        '#lq.diagram(lq.plot((0, 1), (0, 1), label: "zero"))',
        "#let s = json.encode((a: 1))",  # a text written, no file read
    ):
        assert not figures_typst.forbidden(body), body


def test_a_package_not_shipped_never_downloaded():
    """Typst downloads a package it doesn't have (Typst Universe's @preview): its compiler
    sent nowhere (a closed port of this computer), so that it finds the packages shipped
    and nothing else; never the network (else "package not found", or a name not looked up)."""
    with pytest.raises(figures_typst.Unusable, match="failed to download package") as refused:
        figures_typst.compiled('#import "@preview/no-such-package-of-ours:9.9.9": *\n')
    assert "refused" in str(refused.value)


def test_the_figures_colours_kept():
    """A figure keeps its colours: a lesson's colour code (an atom's, a legend's) is what the
    card teaches, never turned black."""
    body = "#cetz.canvas({ import cetz.draw: *\n circle((0, 0), radius: 0.8, fill: red) })"
    svg = figures_typst.compile_svg("chemistry", body)
    assert re.search(r'fill="#ff4136"|fill="#ff0000"', svg), svg[:300]


def test_credited_with_what_its_typst_uses():
    """A figure credits the packages its Typst really calls, not all its family imports: a
    model of balls drawn with cetz under the chemistry family is cetz's, not alchemist's."""
    balls = "#cetz.canvas({ import cetz.draw: *\n circle((0, 0), radius: 0.8, fill: red) })"
    formula = '#skeletize({ fragment("CH_3"); single(); fragment("OH") })'
    assert figures_typst.made_with("chemistry", balls)[1:] == ["cetz 0.5.2"]
    assert figures_typst.made_with("chemistry", formula)[1:] == ["alchemist 0.2.0"]
    polar = formula.replace("})", '; charge("fragment-0", "δ+") })')  # our charges, drawn with cetz
    assert sorted(figures_typst.made_with("chemistry", polar)[1:]) == ["alchemist 0.2.0", "cetz 0.5.2"]
    assert figures_typst.made_with("geometry", TRIANGLE)[1:] == ["ctz-euclide 0.3.0"]
    assert figures_typst.made_with("graph", "#lq.diagram(lq.plot((0, 1), (0, 1)))")[1:] == ["lilaq 0.6.0"]
    timeline = "#timeline(start: 1914, end: 1918, events: ((1916, [Verdun]),))"  # our function: what it uses
    assert figures_typst.made_with("timeline", timeline)[1:] == ["cetz 0.5.2"]
    # the icons, imported by every family: credited only to a figure that draws one
    iconic = '#timeline(start: 1914, end: 1918, events: ((1916, "Verdun", "battle"),))'
    assert figures_typst.made_with("timeline", iconic)[1:] == ["cetz 0.5.2", "notosaurus-icons 0.3.1"]
    assert "notosaurus-icons 0.3.1" in figures_typst.made_with("diagram", '#scheme(boxes: (a: [#icon("farm") Ferme]))')
    assert figures_typst.made_with("clock", "#clock(10, 25)")[1:] == ["cetz 0.5.2"]
    assert figures_typst.made_with("solid", "#cuboid(3, 3, 3)")[1:] == ["cetz 0.5.2"]
    assert figures_typst.made_with("other", balls) == []


def test_nested_zones_are_no_diagram():
    """fletcher writes a node's text at its centre and draws its boxes side by side: zones
    inside one another (rings, layers) drawn with it hide or pile up their labels (TYP-09h)."""
    assert "never shapes inside one another" in figures_typst.KINDS
    assert "zones nested or overlapping" in figures_typst.KINDS.split('"other"')[1]


def test_objects_to_see_are_no_diagram_of_boxes():
    """Steps whose description asks to see objects (a cell dividing and its chromosomes, a
    population of organisms and its coloured ones) went to diagram: boxes of text, nothing
    drawn (mitosis, resistant bacteria 0/3). Said to the AI that picks a figure's kind: drawn."""
    diagram, other = figures_typst.KINDS.split('"diagram"')[1].split(";")[0], figures_typst.KINDS.split('"other"')[1]
    assert "never objects the description asks to see" in diagram and "even in steps joined by arrows" in diagram
    assert "steps where objects are seen" in other


def test_a_model_of_balls_is_no_chemistry():
    """The chemistry family draws formulas (its package's): a molecular model of coloured
    balls is "other", said to the AI that picks a figure's kind."""
    assert "never a model of balls" in figures_typst.KINDS and "molecular model" in figures_typst.KINDS


@pytest.mark.parametrize("family", sorted(figures_typst.FAMILIES))
def test_each_familys_rule_example_compiles(family):
    """Each family's Typst (typst_rules/<family>.typ: its preamble, then the example the AI
    is shown) compiles as it is, with the packages shipped: a rule out of step with its
    package (a version changed) shows here. Read on a card (compile_svg refuses a text too
    small: TooSmall), and none of its labels hidden (tools/bench_figures.py, which judges
    the AI's drawings by them). Compiled once, here: it is slow."""
    svg = figures.clean(figures_typst.compile_svg(family, rule_example(family)))
    assert svg.startswith("<svg")
    assert bench_figures().hidden_labels(svg, figures.to_png(svg)) == 0


def test_a_drawing_past_its_page_kept_whole():
    """A graph's axis names, written by lilaq past the diagram's ends: the page grown to them
    ("temps (min)", not "te"); a figure within its page the same as Typst made it."""
    body = (
        "#lq.diagram(width: 6cm, height: 4cm, xlim: (0, 15), ylim: (-10, 25),\n"
        "  xaxis: (position: 0, label: [temps (min)]), yaxis: (position: 0, label: [température (°C)]),\n"
        "  lq.plot((0, 4, 10, 14), (20, 0, 0, -10), mark: none))"
    )
    width = float(re.search(r'viewBox="[-\d.]+ [-\d.]+ ([\d.]+)', figures_typst.compile_svg("graph", body)).group(1))
    assert width > 6 * 28.35 + 12 + 40  # the diagram, its margins, and "temps (min)" past its end
    cuboid = figures_typst.compile_svg("solid", "#cuboid(5, 3, 2)")
    assert "<rect" not in cuboid.split(">", 1)[1][:200]  # within its page: no ground of ours


def test_each_familys_rule_and_typst_in_their_files():
    """A rule says where its example goes ({example}, once), its Typst where the AI's part
    starts (EXAMPLE, once); the example is in the rule the AI is given."""
    for family, made in figures_typst.FAMILIES.items():
        rule = (figures_typst.RULES / f"{family}.md").read_text(encoding="utf-8")
        typst = (figures_typst.RULES / f"{family}.typ").read_text(encoding="utf-8")
        assert rule.count("{example}") == 1 and typst.count(figures_typst.EXAMPLE) == 1, family
        assert typst.split(figures_typst.EXAMPLE)[1].strip() in made.rules and "{example}" not in made.rules


@pytest.mark.parametrize("family", sorted(figures_typst.FAMILIES))
def test_every_familys_text_in_the_svg_figures_font(family):
    """A figure's text in DejaVu Sans, whichever family draws it: not Typst's own serif."""
    plain = figures_typst.compile_svg(family, '#text("Mi 12")')
    sans = figures_typst.compile_svg(family, '#text(font: "DejaVu Sans", "Mi 12")')
    assert plain == sans


@pytest.mark.parametrize(
    "colour",
    [
        "color.mix(red, blue)",
        "color.mix(green, red, blue)",
        "oklch(60%, 0.15, 200deg)",
        "color.hsl(200deg, 50%, 50%)",
        "color.linear-rgb(20%, 40%, 60%)",
        "color.mix(red, blue).transparentize(40%)",
    ],
)
def test_a_typst_colour_kept_as_typst_makes_it(colour):
    """Typst writes a mixed colour (oklab by default), an oklch, an hsl or a linear RGB as
    CSS's newer functions, which figures.clean drops (a value with brackets): a pH scale's
    bands came out black. Written #rrggbb(aa) instead, Typst's own colour (to-hex), kept by
    the clean and painted."""
    import io

    from PIL import Image

    def filled(body: str) -> list[str]:
        svg = figures.clean(figures_typst.compile_svg("geometry", body))
        return [v for v in re.findall(r'fill="([^"]*)"', svg) if v not in ("#ffffff", "none")]

    rect = "#rect(width: 2cm, height: 1cm, fill: {})"
    assert filled(rect.format(colour)) == filled(rect.format(f"rgb(({colour}).to-hex())")) != []
    png = figures.to_png(figures.clean(figures_typst.compile_svg("geometry", rect.format(colour))))
    middle = Image.open(io.BytesIO(png)).convert("RGB")
    assert middle.getpixel((middle.width // 2, middle.height // 2)) != (0, 0, 0)


def test_a_figure_credits_the_typst_that_drew_it():
    """Typst's own version, the compiler typst-py ships: typst-py 0.15.2 ships Typst 0.15.1,
    there is no Typst 0.15.2 to credit."""
    import json

    import typst

    engine = json.loads(typst.query(b"#metadata(str(sys.version)) <v>", "<v>", field="value"))[0]
    assert figures_typst.made_with("clock", "#clock(10, 25)")[0] == f"Typst {engine}"


def test_typsts_message_read_whole_whatever_the_systems_encoding(monkeypatch):
    """Typst's message is told to the AI to correct the figure. Its process wrote it in the
    system's encoding (cp1252 on Windows): "…" or "δ" came out as "\\ufffd". Written in
    UTF-8 as it is read, whatever the encoding."""
    monkeypatch.setenv("PYTHONIOENCODING", "cp1252")  # Windows' console
    with pytest.raises(figures_typst.Unusable) as refused:
        figures_typst.compile_svg("geometry", '#assert(false, message: "pas O…N, ni δ, ni é")')
    assert "pas O…N, ni δ, ni é" in str(refused.value)


def test_the_kinds_give_each_case_one_family():
    """Read by the AI that picks a figure's family: a classification whose groups hold members
    is sets' (nested-groups), diagram keeps the key of questions leading to groups; measures set
    as points (a scatter) are a chart's like measures joined by a line (a scatter went to graph
    1 time in 3); a map of the past's areas isn't told to use today's countries only (map.md: the
    states of the time from 1815)."""
    kinds = dict(re.findall(r'"(\w+)": (.*?)(?=; "\w+": |$)', figures_typst.KINDS))
    assert "a classification key" in kinds["diagram"] and "a classification)" not in kinds["diagram"]
    assert "classification's nested groups" in kinds["sets"]
    assert "a scatter of measures" in kinds["chart"]
    assert "those of the time" in kinds["map"]


@pytest.mark.parametrize(
    "body",
    [
        '#chart(kind: "bars", values: (("a", 3), ("b", 5)), colours: green)',
        '#chart(kind: "bars", horizontal: true, values: (("a", 3), ("b", 5)), colours: (green, green))',
        '#chart(kind: "pie", values: (("a", 3), ("b", 5)), colours: (green, green))',
        '#chart(kind: "line", values: (("A", ((0, 1), (1, 2))), ("B", ((0, 2), (1, 1)))), colours: green)',
        '#chart(kind: "histogram", values: ((0, 5, 3), (5, 10, 4)), colours: green)',
    ],
)
def test_a_charts_colours_as_the_description_asks(body):
    """ "The bars in green": the chart refused a colour (fill: green, "unexpected argument"),
    its bars drawn grey whatever the description asked. Its colours given, they are drawn."""
    svg = figures.clean(figures_typst.compile_svg("chart", body))
    assert "#2ecc40" in svg  # Typst's green


def test_the_compiler_never_given_the_servers_secrets(monkeypatch):
    """Typst runs on code the AI wrote: its process gets what Python and the system need to
    start it, never the server's own environment (an AI service's key, the relay's secrets),
    which a flaw in Typst found one day could read. It still compiles."""
    import subprocess

    monkeypatch.setenv("NOTOSAURUS_TEST_SECRET", "s3cret")
    monkeypatch.setenv("GEMINI_API_KEY", "key")
    given = []
    run = subprocess.run

    def watched(*args, **kwargs):
        given.append(kwargs["env"])
        return run(*args, **kwargs)

    monkeypatch.setattr(subprocess, "run", watched)
    assert figures_typst.compile_svg("geometry", TRIANGLE).startswith("<svg")
    (env,) = given
    assert "NOTOSAURUS_TEST_SECRET" not in env and "GEMINI_API_KEY" not in env
    assert env["MALLOC_ARENA_MAX"] == "2" and set(env) <= {*figures_typst.COMPILE_ENV_KEPT, "MALLOC_ARENA_MAX"}
