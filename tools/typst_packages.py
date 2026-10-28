"""The Typst packages the figures are drawn with (notosaurus_core/figures_typst.py), kept
in core/notosaurus_core/typst/ so that nothing is downloaded when a figure is drawn: their
versions fixed, their licences with them (LGPL-3.0 for cetz, GPL-3.0 for herodot, the others
MIT or Apache-2.0). Run again to change a version (PACKAGES), then commit what it wrote.

  .venv/bin/python tools/typst_packages.py
"""

import io
import re
import shutil
import tarfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "core" / "notosaurus_core" / "typst" / "preview"
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
    "herodot": "1.0.0",  # timelines
}
SKIP = {
    "gallery",
    "docs",
    "doc",
    "tests",
    "test",
    "manual",
    "examples",
    "example",
    ".github",
    "screenshots",
}  # not needed to compile


IMPORT = re.compile(r"@preview/([\w-]+):(\d+\.\d+\.\d+)")


def main() -> None:
    shutil.rmtree(TARGET, ignore_errors=True)
    todo, done = list(PACKAGES.items()), set()
    while todo:
        name, version = todo.pop()
        if (name, version) in done:
            continue
        done.add((name, version))
        todo += fetch(name, version)
    print(f"{len(done)} packages, {sum(f.stat().st_size for f in TARGET.rglob('*') if f.is_file()) / 1e6:.1f} MB")


def fetch(name: str, version: str) -> list[tuple[str, str]]:
    """One package written under TARGET; the packages it imports."""
    imports = []
    if True:  # (one package)
        url = f"https://packages.typst.org/preview/{name}-{version}.tar.gz"
        with urllib.request.urlopen(url, timeout=60) as res:
            data = res.read()
        folder = TARGET / name / version
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
            for member in archive.getmembers():
                parts = Path(member.name).parts
                if not member.isfile() or SKIP.intersection(parts) or ".." in parts or member.name.startswith("/"):
                    continue
                keep = (".typ", ".toml", ".wasm", ".ttf", ".otf", ".svg", ".png", ".json", ".csv")
                if not (parts[-1].endswith(keep) or parts[-1].startswith(("LICENSE", "README"))):
                    continue
                path = folder.joinpath(*parts)
                path.parent.mkdir(parents=True, exist_ok=True)
                data = archive.extractfile(member).read()  # type: ignore[union-attr]
                path.write_bytes(data)
                if path.suffix == ".typ":
                    imports += IMPORT.findall(data.decode("utf-8", "replace"))
        print(f"{name} {version}: {sum(1 for _ in folder.rglob('*') if _.is_file())} files")
    return imports


if __name__ == "__main__":
    main()
