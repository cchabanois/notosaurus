"""What the Android app and the page keep of the computer's and core's own (Kotlin and
JavaScript can't import Python): the same limits, the same picture fields, the same formula
commands kept out of Anki, the same kinds of photo, the same security headers, read from their
sources."""

import re
from pathlib import Path

import pytest

from app import draft
from app.note_types import formulas
from app.origins import PAGE_POLICY, PICTURE_POLICY
from app.routes.common import IMAGE_TYPES, MAX_PAGES
from notosaurus_core import pictures
from notosaurus_core.calls import MAX_IMAGES
from notosaurus_core.relay_api import MAX_CARD, MAX_IMAGE_BYTES, MAX_SUBJECT

ROOT = Path(__file__).parent.parent
KOTLIN = ROOT / "android/app/src/main/java/app/notosaurus"


def kotlin_const(file: str, name: str) -> int:
    """A number declared `const val NAME = 4 * 1024 * 1024` in the app's `file`."""
    declared = re.search(rf"const val {name} = ([0-9_L* ]+?)\s*(?://|\n)", (KOTLIN / file).read_text(encoding="utf-8"))
    assert declared, (file, name)
    value = 1
    for factor in declared[1].split("*"):
        value *= int(factor.strip().rstrip("L"))
    return value


def kotlin_list(file: str, name: str) -> list[str]:
    """A list of strings declared `val NAME = listOf("a", "b")` in the app's `file`, or another
    one with more: `val NAME = OTHER + "c"`."""
    source = (KOTLIN / file).read_text(encoding="utf-8")
    declared = re.search(rf"val {name} = listOf\(([^)]*)\)", source)
    if declared:
        return re.findall(r'"([^"]*)"', declared[1])
    grown = re.search(rf"val {name} = (\w+) \+ \"([^\"]*)\"\n", source)
    assert grown, (file, name)
    return [*kotlin_list(file, grown[1]), grown[2]]


def kotlin_string(file: str, name: str) -> str:
    """A string declared `const val NAME = "a" + "b"` (over several lines) in the app's `file`."""
    source = (KOTLIN / file).read_text(encoding="utf-8")
    declared = re.search(rf'const val {name} = ((?:"[^"]*"\s*\+\s*)*"[^"]*")', source)
    assert declared, (file, name)
    return "".join(re.findall(r'"([^"]*)"', declared[1]))


def page_list(name: str) -> list[str]:
    """A list of strings declared `const NAME = ["a", "b"];` in the page's app-pictures.js."""
    page = (ROOT / "static/app-pictures.js").read_text(encoding="utf-8")
    declared = re.search(rf"const {name} = \[([^\]]*)\]", page)
    assert declared, name
    return re.findall(r'"([^"]*)"', declared[1])


@pytest.mark.parametrize(
    ("file", "name", "value"),
    [
        ("LocalServer.kt", "MAX_PHOTOS", MAX_PAGES),
        ("LocalServer.kt", "MAX_PER_CALL", MAX_IMAGES),
        ("LocalServer.kt", "MAX_IMAGE_BYTES", MAX_IMAGE_BYTES),
        ("Draft.kt", "MAX_TEXT", draft.MAX_TEXT),
        ("Draft.kt", "MAX_PHOTO_BYTES", draft.MAX_PHOTO_BYTES),
        ("Pictures.kt", "MAX_CARD", MAX_CARD),
        ("PictureRoutes.kt", "MAX_SUBJECT", MAX_SUBJECT),
    ],
)
def test_the_apps_limits_are_the_computers(file, name, value):
    assert kotlin_const(file, name) == value


def test_the_apps_picture_fields_are_cores():
    assert kotlin_list("Pictures.kt", "PICTURE_FIELDS") == list(pictures.PICTURE_FIELDS)
    assert kotlin_list("Pictures.kt", "REMOVED") == list(pictures.REMOVED)
    assert kotlin_list("Pictures.kt", "DESCRIBED") == list(pictures.DESCRIBED)
    ready = kotlin_list("Pictures.kt", "READY")
    assert set(ready) == pictures.READY and len(ready) == len(pictures.READY)


def test_the_apps_formula_commands_kept_out_are_the_computers():
    assert kotlin_list("Formulas.kt", "HTML_COMMANDS") == formulas.HTML_COMMANDS


def test_the_pages_picture_fields_are_cores():
    """What the page takes of a card's picture (takePicture): all of what "ready" tells; what
    it tells a card described anew by (describedAs)."""
    ready = page_list("READY")
    assert set(ready) == pictures.READY and len(ready) == len(pictures.READY)
    assert page_list("DESCRIBED") == list(pictures.DESCRIBED)


@pytest.mark.parametrize(
    ("file", "name", "value"),
    [("LocalServer.kt", "PAGE_POLICY", PAGE_POLICY), ("PictureRoutes.kt", "PICTURE_POLICY", PICTURE_POLICY)],
)
def test_the_apps_security_headers_are_the_computers(file, name, value):
    """The phone serves the same page, and the same figures, with the computer's policies."""
    assert kotlin_string(file, name) == value


def test_the_apps_photo_kinds_are_the_computers():
    """A card's own photo: the kinds the computer takes (common.IMAGE_TYPES), the phone too."""
    assert set(kotlin_list("LocalServer.kt", "IMAGE_TYPES")) == IMAGE_TYPES


def test_the_pages_card_length_is_the_relays():
    """What the page cuts a card's text to before a picture search (cutText): relay_api.MAX_CARD."""
    page = (ROOT / "static/app-pictures.js").read_text(encoding="utf-8")
    declared = re.search(r"const MAX_CARD = (\d+);", page)
    assert declared and int(declared[1]) == MAX_CARD
