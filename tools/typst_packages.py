"""The Typst packages the figures are drawn with (notosaurus_core/figures_typst.py), kept
in core/notosaurus_core/typst/ so that nothing is downloaded when a figure is drawn: one
archive per package, as Typst Universe publishes it (<name>-<version>.tar.gz), their
versions fixed, their licences inside (LGPL-3.0 for cetz, the others MIT or Apache-2.0).
The figures unpack them once, in the cache (figures_typst.packages). Run again to change a
version (PACKAGES), then commit what it wrote.

  .venv/bin/python tools/typst_packages.py
"""

import io
import re
import tarfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "core" / "notosaurus_core" / "typst"
# The figures' families (figures_typst.FAMILIES), each package's version fixed; what they
# import themselves (another cetz, oxifmt, lilaq's) is found in their files and added
PACKAGES = {
    "cetz": "0.5.2",  # the drawing every family but lilaq's builds on (the one most of them import)
    "ctz-euclide": "0.3.0",  # geometry: constructions, marks (tkz-euclide's port)
    "lilaq": "0.6.0",  # graphs of functions
    "cetz-venn": "0.2.0",  # sets
    "fletcher": "0.5.8",  # diagrams: nodes and arrows
    "zap": "0.6.0",  # electric circuits
    "alchemist": "0.2.0",  # chemistry: skeletal formulas
}

IMPORT = re.compile(r"@preview/([\w-]+):(\d+\.\d+\.\d+)")
COMMENT = re.compile(r"^\s*//.*", re.M)  # an import in a comment line (its docs): not imported


def main() -> None:
    TARGET.mkdir(parents=True, exist_ok=True)
    todo, done = list(PACKAGES.items()), set()
    while todo:
        name, version = todo.pop()
        if (name, version) in done:
            continue
        done.add((name, version))
        todo += fetch(name, version)
    kept = {f"{name}-{version}.tar.gz" for name, version in done}
    for old in TARGET.glob("*.tar.gz"):
        if old.name not in kept:
            old.unlink()
    print(f"{len(done)} packages, {sum(f.stat().st_size for f in TARGET.glob('*.tar.gz')) / 1e6:.2f} MB")


def fetch(name: str, version: str) -> list[tuple[str, str]]:
    """One package's archive written in TARGET, as published; the packages it imports."""
    url = f"https://packages.typst.org/preview/{name}-{version}.tar.gz"
    with urllib.request.urlopen(url, timeout=60) as res:
        data = res.read()
    imports = []
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
        for member in archive.getmembers():
            if member.isfile() and member.name.endswith(".typ"):
                text = archive.extractfile(member).read().decode("utf-8", "replace")  # type: ignore[union-attr]
                imports += IMPORT.findall(COMMENT.sub("", text))
    (TARGET / f"{name}-{version}.tar.gz").write_bytes(data)
    print(f"{name} {version}: {len(data) / 1e3:.0f} kB")
    return imports


if __name__ == "__main__":
    main()
