"""The pages load nothing from elsewhere: their scripts, styles and fonts are shipped
(static/vendor/README.md). A blocked CDN broke them, and no third party sees the visits."""

import re
from pathlib import Path

PAGES = [*Path("static").glob("*.html"), *Path("android/app/src/main/assets/page").glob("*.html")]
SCRIPTS = [*Path("static").glob("*.js"), *Path("android/app/src/main/assets/page").glob("*.js")]
STYLES = [p for p in Path("static").rglob("*.css")]

# A static src or href (not one Alpine binds, ":src"): what the browser loads as the page opens
LOADED = re.compile(r'<(?:script|link|img|iframe|source)\b[^>]*?(?<![:\w-])(?:src|href)="([^"]+)"')
REMOTE = re.compile(r"^(?:https?:)?//")


def test_the_pages_load_nothing_from_elsewhere():
    assert PAGES
    for page in PAGES:
        html = page.read_text(encoding="utf-8")
        loaded = LOADED.findall(html)
        assert loaded, page
        for url in loaded:
            assert not REMOTE.match(url), f"{page}: {url}"
            if not url.startswith(("/api/", "data:")):  # the page's own files: there
                # (the app's pages: their own folder first, then static/, as its server serves them)
                roots = [page.parent, Path("static")] if "android" in page.parts else [Path("static")]
                assert any((root / url.split("?")[0]).is_file() for root in roots), f"{page}: {url} missing"


def test_the_scripts_and_styles_load_nothing_from_elsewhere():
    for path in SCRIPTS:
        code = path.read_text(encoding="utf-8")
        assert not re.search(r"""import\(\s*["'`]https?:|["'`]https?://cdn""", code), path
    for path in STYLES:
        css = path.read_text(encoding="utf-8")
        assert not re.search(r"(?:url\(|@import)\s*['\"]?https?:", css), path


def test_each_shipped_file_has_its_licence():
    for folder in (p for p in Path("static/vendor").iterdir() if p.is_dir()):
        assert (folder / "LICENSE").is_file(), folder
