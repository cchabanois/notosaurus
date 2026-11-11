"""The libraries' licences page (static/licences.js): the page's own as static/vendor ships
them, each with its licence file."""

import re
from pathlib import Path

STATIC = Path(__file__).resolve().parent.parent / "static"


def test_the_pages_libraries_as_vendor_ships_them():
    script = (STATIC / "licences.js").read_text(encoding="utf-8")
    listed = re.findall(r'version: "([^"]+)", licence: "([^"]+)", file: "([^"]+)"', script)
    readme = (STATIC / "vendor/README.md").read_text(encoding="utf-8")
    shipped = {
        folder: (version, licence)
        for folder, version, licence in re.findall(r"\| `(\w+)/` \|[^|]*\| `[^`]*@([\d.]+)`[^|]*\| (\S+) \|", readme)
    }
    assert len(listed) == len(shipped) == 3
    for version, licence, file in listed:
        folder = file.split("/")[1]
        assert shipped[folder] == (version, licence), folder  # the README's version and licence
        assert (STATIC / file).is_file()  # its licence, shipped next to it


def test_every_figure_package_shipped_is_credited():
    """Each Typst package shipped (core's typst/ archives, ours too) in the figures' credits
    at its version, with its licence and its page; the maps' data credited with them. One
    list, core's: the relay gives it to the phone (/v1/credits), the computer to its page
    (/api/credits), so that a package added is credited without a new app; the page lists
    none of its own."""
    from notosaurus_core.figures_typst import CREDITS

    listed = {(c["name"], c["version"]) for c in CREDITS}
    archives = (STATIC.parent / "core" / "notosaurus_core" / "typst").glob("*.tar.gz")
    shipped = {re.fullmatch(r"(.+)-([\d.]+)\.tar\.gz", a.name).groups() for a in archives}
    assert shipped <= listed, shipped - listed
    assert ("Natural Earth", "5.1.2") in listed  # notosaurus-atlas's data (tools/atlas.py)
    assert {("Unicode CLDR", "46.0"), ("Wikidata", "2026-11")} <= listed  # its names, its places of history
    assert all(c["licence"] and c["url"].startswith("https://") for c in CREDITS)
    script = (STATIC / "licences.js").read_text(encoding="utf-8")
    assert "/api/credits" in script and "typst.app/universe" not in script


def test_the_computer_gives_its_page_the_figures_credits(client):
    """The computer draws its figures itself: its own credits, core's, as the relay gives the phone."""
    from notosaurus_core.figures_typst import CREDITS

    res = client.get("/api/credits")
    assert res.status_code == 200 and res.json() == CREDITS


def test_the_atlas_ships_cldrs_licence():
    """The atlas's names from Unicode CLDR: its licence's copyright and permission notice goes
    with every copy of them (as it asks), in the archive the add-on and the app ship."""
    import tarfile

    (archive,) = (STATIC.parent / "core" / "notosaurus_core" / "typst").glob("notosaurus-atlas-*.tar.gz")
    with tarfile.open(archive) as tar:
        notice = tar.extractfile("LICENSE-CLDR").read().decode()
        assert "LICENSE-CLDR" in tar.extractfile("NOTICE").read().decode()
    assert "UNICODE LICENSE V3" in notice and "Copyright © 2004-2024 Unicode, Inc." in notice
