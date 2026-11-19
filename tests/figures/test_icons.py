"""The figures' icons (common.typ's icon(), the notosaurus-icons package, tools/icons.py): a
pictogram named by an English word in any family, never written, one colour with its halo,
seen at the same size whichever set it comes from; refused when too small to see on a card."""

import json
import re
import shutil
import tarfile
from pathlib import Path

import pytest
import typst

from notosaurus_core import figures_typst, text_size
from notosaurus_core.figures_typst import Unusable

ROOT = Path(__file__).resolve().parents[2]


def _scheme(*boxes: str) -> str:
    named = ", ".join(f"b{i}: [{b}]" for i, b in enumerate(boxes))
    return f"#scheme(boxes: ({named},), arrows: ())"


def test_an_icon_chosen_by_an_english_word_in_any_family():
    """A word, in any form a sentence has it (a plural, a hyphen, capitals), gives the icon
    that shows it: one image, marked as an icon, in a scheme's box and on a timeline."""
    for word in ("factory", "Factories", "oil-well", "Wind Farm", "battle", "wheat"):
        svg = figures_typst.compile_svg("diagram", _scheme(f'#icon("{word}") Usine'))
        assert len(text_size.icons_px(svg)) == 1, word
    timeline = '#timeline(start: 1914, end: 1919, step: 1, events: ((1916, "Bataille de Verdun", "battle"),))'
    assert len(text_size.icons_px(figures_typst.compile_svg("timeline", timeline))) == 1


def test_an_unknown_word_draws_the_figure_without_its_icon():
    """A word no icon has: the figure drawn all the same (never refused: a refusal costs a
    drawing), no icon in its place, never one guessed, the text beside it kept; the word
    kept for the caller (the bench: what to tag next)."""
    missing: list[str] = []
    token = figures_typst.icons_missing.set(missing)
    try:
        svg = figures_typst.compile_svg("diagram", _scheme('#icon("zzyzx") Usine', '#icon("factory") Ferme'))
    finally:
        figures_typst.icons_missing.reset(token)
    assert len(text_size.icons_px(svg)) == 1 and missing == ["zzyzx"]
    assert "notosaurus-icon-missing" not in svg


def test_a_safe_near_form_finds_its_icon():
    """A plural, a singular, a hyphen, a phrase's last word, an icon family's first word: the
    same icon, as the index has them (tools/icons.py); objects Phosphor's, places still the
    map's (a port the harbour)."""
    (archive,) = (ROOT / "core" / "notosaurus_core" / "typst").glob("notosaurus-icons-*.tar.gz")
    with tarfile.open(archive) as tar:
        words = json.loads(tar.extractfile("index.json").read())["words"]  # type: ignore[union-attr]
    assert words["factories"] == words["factory"] == "industry"
    assert words["port"] == words["ports"] == "harbor"
    assert words["laptop"] == words["laptops"] == "laptop" and words["microscope"] == "microscope"
    assert words["test tubes"] == "test-tube" and words["computer"] == words["computers"]
    assert words["battery"].startswith("battery-")  # the family's first word
    for word in ("Factories", "test-tube", "steel factory", "Microscopes"):
        svg = figures_typst.compile_svg("diagram", _scheme(f'#icon("{word}") X'))
        assert len(text_size.icons_px(svg)) == 1, word


def test_the_word_is_never_written():
    """The word only chooses the icon: the timeline writes the same texts with it as without."""
    events = '(1916, "Bataille de Verdun"{}), (1919, "Traité de Versailles"{})'
    plain = figures_typst.compile_svg(
        "timeline", f"#timeline(start: 1914, end: 1920, step: 1, events: ({events.format('', '')}))"
    )
    with_icons = figures_typst.compile_svg(
        "timeline", f"#timeline(start: 1914, end: 1920, step: 1, events: ({events.format(', "battle"', ', "treaty"')}))"
    )
    assert len(text_size.icons_px(with_icons)) == 2
    assert len(text_size.runs(with_icons)) == len(text_size.runs(plain))


def test_an_svg_of_ones_own_cleaned_or_left_out():
    """icon(svg: …), for what no icon shows: drawn in one colour (its red the icon's black);
    text, an image, a link or too many shapes: not drawn (nothing in its place), never refused."""
    red = '<svg viewBox=\\"0 0 10 10\\"><circle cx=\\"5\\" cy=\\"5\\" r=\\"4\\" fill=\\"red\\"/></svg>'
    svg = figures_typst.compile_svg("diagram", _scheme(f'#icon(svg: "{red}") X'))
    (icon,) = re.findall(r'href="data:image/svg\+xml;base64,([^"]+)"', svg)
    import base64

    drawn = base64.b64decode(icon).decode()
    assert "red" not in drawn and 'fill="#000000"' in drawn
    for bad in ("<text>A</text>", '<image href=\\"x.png\\"/>', '<a href=\\"x\\"><rect/></a>', "<rect/>" * 41):
        svg = figures_typst.compile_svg("diagram", _scheme(f'#icon(svg: "<svg viewBox=\\"0 0 10 10\\">{bad}</svg>") X'))
        assert not text_size.icons_px(svg), bad


def test_an_icon_too_small_to_see_on_a_card_grown_or_refused():
    """An icon a little too small on a phone: grown round its middle to be seen; one far
    smaller than its text (a speck, more than twice too small): refused, its size said."""
    svg = figures_typst.compile_svg("diagram", _scheme('#icon("factory", size: 0.7em) Usine'))
    assert min(text_size.icons_px(svg)) >= figures_typst.MIN_ICON_PX - 0.01
    with pytest.raises(Unusable, match="icon is too small"):
        figures_typst.compile_svg("diagram", _scheme('#icon("factory", size: 0.3em) Usine'))


def test_a_figure_without_icons_never_reads_their_index(tmp_path):
    """The index is read when an icon is drawn, never when common.typ is merely imported: a
    figure without icons compiles with the index unreadable."""
    packages = tmp_path / "packages"
    shutil.copytree(figures_typst.packages(), packages)
    (index,) = packages.glob("preview/notosaurus-icons/*/index.json")
    index.write_text("not JSON", encoding="utf-8")

    def compile_(body: str) -> bytes:
        page = tmp_path / "figure.typ"
        page.write_text(figures_typst.source("diagram", body), encoding="utf-8")
        return typst.compile(str(page), format="svg", root=str(tmp_path), package_path=str(packages))

    assert compile_(_scheme("Usine"))
    with pytest.raises(RuntimeError, match="failed to parse JSON"):
        compile_(_scheme('#icon("factory") Usine'))


def test_every_icon_tagged_square_and_its_words_indexed():
    """Each icon in the package has its tags (tools/icons-tags.json), sits in a square round
    what it draws (Maki's and Temaki's seen the same size), and every word of the index names
    an icon there."""
    (archive,) = (ROOT / "core" / "notosaurus_core" / "typst").glob("notosaurus-icons-*.tar.gz")
    tags = json.loads((ROOT / "tools" / "icons-tags.json").read_text(encoding="utf-8"))
    with tarfile.open(archive) as tar:
        icons = {
            m.name.removeprefix("icons/").removesuffix(".svg"): m
            for m in tar.getmembers()
            if m.name.startswith("icons/")
        }
        index = json.loads(tar.extractfile("index.json").read())  # type: ignore[union-attr]
        assert "MIT License" in tar.extractfile("LICENSE-Phosphor").read().decode()  # type: ignore[union-attr]
        for name in ("industry", "harbor", "silo", "battle", "treaty", "wheat", "laptop", "microscope"):
            svg = tar.extractfile(icons[name]).read().decode()  # type: ignore[union-attr]
            w, h = re.search(r'viewBox="[-\d.]+ [-\d.]+ ([\d.]+) ([\d.]+)"', svg).groups()  # type: ignore[union-attr]
            assert w == h and text_size.ICON_MARK in svg, name
    assert set(tags) <= set(icons)  # Maki's, Temaki's and ours; Phosphor's tagged by Phosphor
    assert any(n.startswith("ph-") for n in icons) and "laptop" in icons
    assert set(index["words"].values()) <= set(icons)
    assert index["words"]["factory"] == "industry" and index["words"]["port"] == "harbor"
