"""The scratch family (blockst): a Scratch script's blocks drawn from their text, a block
Scratch doesn't have refused, saying which."""

import re

import pytest

from notosaurus_core import figures, figures_typst


def _script(code: str, language: str = "fr") -> str:
    return figures.clean(figures_typst.compile_svg("scratch", f'#scratch("\n{code}\n", language: "{language}")'))


def test_a_scratch_script_is_a_family_of_its_own():
    """Scratch scripts were drawn as SVG by the AI, each block's width guessed: its words cut
    ("quand le drapeau vert es") or glued ("définircarrécôté"). A family of its own, picked for
    a Scratch script, not for a flowchart."""
    assert "scratch" in figures_typst.FAMILIES and "scratch" in figures_typst.FigureKind.__args__
    assert '"scratch": a Scratch script' in figures_typst.KINDS
    assert "never a Scratch script" in figures_typst.KINDS.split('"diagram":')[1].split(";")[0]


@pytest.mark.parametrize(
    ("code", "language"),
    [
        # a loop inside a loop, a block of the lesson's own defined and used
        (
            "définir carré (côté)\nrépéter (4) fois\n  avancer de (côté) pas\n  tourner ↻ de (90) degrés\nfin\n\n"
            "quand le drapeau vert est cliqué\nrépéter (3) fois\n  call carré (50)\n  tourner ↻ de (120) degrés\nfin",
            "fr",
        ),
        # a condition, a variable, a question, a loop until
        (
            "quand le drapeau vert est cliqué\nmettre [score v] à (0)\ndemander [Quel âge as-tu ?] et attendre\n"
            "si <(réponse) > (12)> alors\n  dire [Collège]\nsinon\n  dire [École] pendant (2) secondes\nfin\n"
            "répéter jusqu'à ce que <(score) = (10)>\n  ajouter (1) à [score v]\nfin",
            "fr",
        ),
        ("when green flag clicked\nrepeat (4)\n  move (10) steps\nend", "en"),
    ],
)
def test_a_scripts_blocks_drawn_with_their_words(code, language):
    svg = _script(code, language)
    assert "<image" not in svg and "<text" in svg  # drawn in its place, its words kept
    assert 'fill="#bfbfbf"' not in svg.lower()  # every block one Scratch has


def test_a_block_scratch_doesnt_have_refused_saying_which():
    """blockst draws a block it doesn't know grey, without an error: the AI's own words for a
    block ("voler vers la lune") would show as a block Scratch has. Refused, its words said,
    so that the AI writes it again."""
    with pytest.raises(figures_typst.Unusable, match='"voler vers la lune"'):
        _script("quand le drapeau vert est cliqué\navancer de (10) pas\nvoler vers la lune")


@pytest.mark.parametrize(
    ("code", "language"),
    [
        ("définir carré (côté)\navancer de (côté) pas\n\nquand le drapeau vert est cliqué\ncall carré (50)", "fr"),
        ("define square (size)\nmove (size) steps\n\nwhen green flag clicked\ncall square (50)", "en"),
    ],
)
def test_a_block_of_the_scripts_own_used_with_call_in_any_language(code, language):
    """blockst reads a block of the script's own used with its language's word, "appeler" in
    French: "call carré (50)" (as the rule writes it) wrote "call" on the block. Read in every
    language, the block shows its name and its values only, as Scratch shows it."""
    svg = _script(code, language)
    assert ">call<" not in svg and ">appeler<" not in svg and ">50<" in svg


def test_an_if_blocks_foot_drawn_whole_without_a_loops_arrow():
    """blockst drew an "if" with a loop's arrow at its foot (as if it looped), and an "if …
    else" ending a script without its foot (its SVG too short). A loop keeps its arrow, an
    "if" has none; the foot drawn whole, the figure grown to it."""
    loop = "quand le drapeau vert est cliqué\nrépéter (2) fois\n  dire [x]\nfin"
    assert _script(loop).count("#sb-loopArrow") == 1  # the loop's
    for language, code in (
        ("fr", "quand le drapeau vert est cliqué\nsi <(a) > (1)> alors\n  dire [x]\nfin"),
        ("en", "when green flag clicked\nif <(a) > (1)> then\n  say [x]\nend"),
    ):
        assert "#sb-loopArrow" not in _script(code, language), language
    ending = "quand le drapeau vert est cliqué\nsi <(a) > (1)> alors\n  dire [x]\nsinon\n  dire [y]\nfin"
    svg = figures_typst.compile_svg("scratch", f'#scratch("\n{ending}\n", language: "fr")')
    inner = figures.clean(svg)
    assert 'overflow="visible"' in inner
    drawn = float(re.search(r'viewBox="[-\d.]+ [-\d.]+ [\d.]+ ([\d.]+)"', svg)[1])
    image = float(re.search(r'<image[^>]* height="([\d.]+)"', svg)[1])
    assert drawn > image + 12 + 5  # grown past the image blockst gave (its margins, 6 pt each)


def test_blockst_shipped_without_the_cetz_of_its_stage():
    """Blockst's stage (`scratch-run`, never called by the figures) imports a cetz of its own,
    0.4.2: shipped, it was a third cetz for nothing. Not shipped, the blocks drawn as before."""
    assert not (figures_typst.ARCHIVES / "cetz-0.4.2.tar.gz").exists()
    assert "<svg" in _script("quand le drapeau vert est cliqué\nrépéter (4) fois\navancer de (100) pas\nfin")
