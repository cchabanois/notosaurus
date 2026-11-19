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


def test_an_unknown_word_refused_with_the_icons_nearest():
    """A word no icon has: refused, the icons whose words come near it named (its beginning
    shared, one within the other), so the AI can choose one."""
    with pytest.raises(Unusable, match=r'no icon for "factorie".*industry \(factory'):
        figures_typst.compile_svg("diagram", _scheme('#icon("factorie") Usine'))


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


def test_an_svg_of_ones_own_cleaned_or_refused():
    """icon(svg: …), for what no icon shows: drawn in one colour (its red the icon's black);
    text, an image, a link or too many shapes refused."""
    red = '<svg viewBox=\\"0 0 10 10\\"><circle cx=\\"5\\" cy=\\"5\\" r=\\"4\\" fill=\\"red\\"/></svg>'
    svg = figures_typst.compile_svg("diagram", _scheme(f'#icon(svg: "{red}") X'))
    (icon,) = re.findall(r'href="data:image/svg\+xml;base64,([^"]+)"', svg)
    import base64

    drawn = base64.b64decode(icon).decode()
    assert "red" not in drawn and 'fill="#000000"' in drawn
    for bad in ("<text>A</text>", '<image href=\\"x.png\\"/>', '<a href=\\"x\\"><rect/></a>', "<rect/>" * 41):
        with pytest.raises(Unusable, match="icon\\(svg"):
            figures_typst.compile_svg("diagram", _scheme(f'#icon(svg: "<svg viewBox=\\"0 0 10 10\\">{bad}</svg>") X'))


def test_an_icon_too_small_to_see_on_a_card_refused():
    """An icon drawn far smaller than its text (a speck on a phone): refused, its size said."""
    with pytest.raises(Unusable, match="icon is too small"):
        figures_typst.compile_svg("diagram", _scheme('#icon("factory", size: 0.4em) Usine'))


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
        for name in ("industry", "harbor", "silo", "battle", "treaty", "wheat"):
            svg = tar.extractfile(icons[name]).read().decode()  # type: ignore[union-attr]
            w, h = re.search(r'viewBox="[-\d.]+ [-\d.]+ ([\d.]+) ([\d.]+)"', svg).groups()  # type: ignore[union-attr]
            assert w == h and text_size.ICON_MARK in svg, name
    assert set(icons) == set(tags)
    assert set(index["words"].values()) <= set(icons)
    assert index["words"]["factory"] == "industry" and index["words"]["port"] == "harbor"
