"""What the Android app and the page keep of the computer's and core's own (Kotlin and
JavaScript can't import Python): the same limits, the same picture fields, the same formula
commands kept out of Anki, read from their sources."""

import re
from pathlib import Path

import pytest

from app import draft
from app.note_types import formulas
from app.routes.common import MAX_PAGES
from notosaurus_core import pictures
from notosaurus_core.calls import MAX_IMAGES
from notosaurus_core.relay_api import MAX_IMAGE_BYTES

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
    """A list of strings declared `val NAME = listOf("a", "b")` in the app's `file`."""
    declared = re.search(rf"val {name} = listOf\(([^)]*)\)", (KOTLIN / file).read_text(encoding="utf-8"))
    assert declared, (file, name)
    return re.findall(r'"([^"]*)"', declared[1])


@pytest.mark.parametrize(
    ("file", "name", "value"),
    [
        ("LocalServer.kt", "MAX_PHOTOS", MAX_PAGES),
        ("LocalServer.kt", "MAX_PER_CALL", MAX_IMAGES),
        ("LocalServer.kt", "MAX_IMAGE_BYTES", MAX_IMAGE_BYTES),
        ("Draft.kt", "MAX_TEXT", draft.MAX_TEXT),
        ("Draft.kt", "MAX_PHOTO_BYTES", draft.MAX_PHOTO_BYTES),
    ],
)
def test_the_apps_limits_are_the_computers(file, name, value):
    assert kotlin_const(file, name) == value


def test_the_apps_picture_fields_are_cores():
    assert kotlin_list("Pictures.kt", "PICTURE_FIELDS") == list(pictures.PICTURE_FIELDS)
    assert kotlin_list("Pictures.kt", "REMOVED") == list(pictures.REMOVED)


def test_the_apps_formula_commands_kept_out_are_the_computers():
    assert kotlin_list("Formulas.kt", "HTML_COMMANDS") == formulas.HTML_COMMANDS


def test_the_pages_picture_fields_are_cores():
    """What the page takes of a card's picture (takePicture): all of what "ready" tells."""
    page = (ROOT / "static/app-pictures.js").read_text(encoding="utf-8")
    declared = re.search(r"const PICTURE_FIELDS = \[([^\]]*)\]", page)
    assert declared
    assert set(re.findall(r'"([^"]*)"', declared[1])) == pictures.READY
