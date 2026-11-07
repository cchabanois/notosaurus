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


def test_every_figure_package_shipped_is_listed():
    """Each Typst package shipped (core's typst/ archives, ours too) on the licences page, at
    its version; the maps' data credited with them."""
    script = (STATIC / "licences.js").read_text(encoding="utf-8")
    listed = set(re.findall(r'name: "([^"]+)", version: "([^"]+)"', script))
    archives = (STATIC.parent / "core" / "notosaurus_core" / "typst").glob("*.tar.gz")
    shipped = {re.fullmatch(r"(.+)-([\d.]+)\.tar\.gz", a.name).groups() for a in archives}
    assert shipped <= listed, shipped - listed
    assert ("Natural Earth", "5.1.2") in listed  # notosaurus-atlas's data (tools/atlas.py)
    assert {("Unicode CLDR", "46.0"), ("Wikidata", "2026-11")} <= listed  # its names, its places of history
