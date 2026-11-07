"""The page runs in Android's WebView from version 124 (Chrome 124: the app's minimum, chosen
with the release test plan). A feature newer than that leaves a blank page there, without a
word: the ones most likely to be reached for are refused here, each with the Chrome version
that brought it. Not exhaustive: a guard, not a proof."""

import re
from pathlib import Path

import pytest

STATIC = Path(__file__).parent.parent / "static"
# (pattern, the Chrome version that brought it): only what came after 124
NEWER = {
    "js": [
        (r"\bPromise\.try\b", 128),
        (r"\bRegExp\.escape\b", 136),
        (r"\bURL\.parse\b", 126),
        (r"\bError\.isError\b", 134),
        (r"\bIntl\.DurationFormat\b", 129),
        (r"\bFloat16Array\b", 135),
        (r"\b(fromBase64|toBase64|fromHex|toHex)\(", 140),
    ],
    "css": [
        (r"\banchor-name\s*:|\bposition-anchor\s*:|\banchor\(", 125),
        (r"@view-transition\b", 126),
        (r"\bcalc-size\(|\binterpolate-size\s*:", 129),
        (r"::details-content\b", 131),
        (r"\btext-box(-trim|-edge)?\s*:", 133),
        (r":open\b", 133),
        (r"\bscroll-state\(", 133),
        (r"::scroll-(marker|button)\b", 135),
        (r"\bshape\(", 135),
        (r"\breading-flow\s*:", 137),
        (r"\bsibling-(index|count)\(", 138),
        (r"\bcorner-shape\s*:", 139),
    ],
    "html": [
        (r"\bclosedby=", 134),
        (r"\bcommandfor=|\bcommand=\"", 135),
        (r"\binterestfor=", 142),
    ],
}
KINDS = {".js": ("js",), ".mjs": ("js",), ".css": ("css",), ".html": ("html", "css", "js")}


def _ours() -> list[Path]:
    return sorted(p for p in STATIC.rglob("*") if p.suffix in KINDS and "vendor" not in p.relative_to(STATIC).parts)


@pytest.mark.parametrize("path", _ours(), ids=lambda p: str(p.relative_to(STATIC)))
def test_nothing_newer_than_webview_124(path):
    text = path.read_text(encoding="utf-8")
    found = [
        f"{m.group()!r} (Chrome {version})"
        for kind in KINDS[path.suffix]
        for pattern, version in NEWER[kind]
        for m in re.finditer(pattern, text)
    ]
    assert not found, f"newer than WebView 124: {', '.join(found)}"


def test_a_newer_feature_is_found(tmp_path):
    """The guard itself: a feature of Chrome 125 in a page's CSS is refused."""
    page = tmp_path / "x.css"
    page.write_text(".tip { position-anchor: --button; }", encoding="utf-8")
    with pytest.raises(AssertionError, match="Chrome 125"):
        test_nothing_newer_than_webview_124(page)
