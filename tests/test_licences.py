"""The libraries' licences page (static/licences.js): the page's own as static/vendor ships
them, each with its licence file."""

import re
from pathlib import Path

STATIC = Path(__file__).resolve().parent.parent / "static"


def test_the_pages_libraries_as_vendor_ships_them():
    script = (STATIC / "licences.js").read_text()
    listed = re.findall(r'version: "([^"]+)", licence: "([^"]+)", file: "([^"]+)"', script)
    readme = (STATIC / "vendor/README.md").read_text()
    shipped = {
        folder: (version, licence)
        for folder, version, licence in re.findall(r"\| `(\w+)/` \|[^|]*\| `[^`]*@([\d.]+)`[^|]*\| (\S+) \|", readme)
    }
    assert len(listed) == len(shipped) == 4
    for version, licence, file in listed:
        folder = file.split("/")[1]
        assert shipped[folder] == (version, licence), folder  # the README's version and licence
        assert (STATIC / file).is_file()  # its licence, shipped next to it
