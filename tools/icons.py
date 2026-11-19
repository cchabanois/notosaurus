"""The figures' icons (common.typ's icon(): a pictogram any family may draw), as a Typst
package of our own: core/notosaurus_core/typst/notosaurus-icons-<version>.tar.gz, unpacked with
the others (figures_typst.packages). Run again to change the icons, their tags or the function
(VERSION raised with it), then commit what it wrote.

The icons: all of Maki's (Mapbox) and Temaki's (the iD editor's), both CC0 1.0, at the fixed
versions below (their npm archives, checked by their SHA-256); an icon of Temaki's named as one
of Maki's (town_hall and town-hall) left out; and ours (tools/icons-own/, CC0 1.0 too) for
what history and geography sketches need and neither has (a battle, a treaty, a pyramid, a
temple, a crown, wheat); then Phosphor's (MIT), its `fill` weight, for the objects a scheme,
a timeline or a science lesson shows (a laptop, a microscope, a flask, a book), a name of
Maki's or Temaki's or ours kept by theirs, Phosphor's then prefixed `ph-` (ph-house). Each one
refitted to the box of what it draws (rendered by resvg), in
a square, so that all are seen at the same size; one colour, a white halo under it (readable
on a map's colours): icons/<name>.svg, its colours placeholders the function replaces.

Their tags: tools/icons-tags.json, English words for each icon of Maki's, Temaki's and ours (its
name's, then what it shows or stands for: industry, factory, plant, works), and a few added to
Phosphor's (a word the bench asked and no icon had: a router, the network's), the AI naming an icon by an English word
whatever the lesson's language; written once, reviewed by hand for the icons a sketch needs.
index.json: each word (lower case, `-` and `_` as spaces) to its icon, the icon whose tags
give it first (its name, then its first tags), so that Typst looks a word up and computes no
distance (a search in Typst over every name took 15 s in the atlas, #632). Phosphor's tags are
its own (its index.mjs: `tags`, English), and it answers only the words no map or place icon
(Maki's, Temaki's, ours) answers: "port" stays the harbour, "laptop" is Phosphor's.

  .venv/bin/python tools/icons.py [folder]

`folder`: where the npm archives are (by their names), else downloaded.
"""

import gzip
import hashlib
import io
import json
import re
import sys
import tarfile
import urllib.request
from pathlib import Path

import resvg_py
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
LIB = ROOT / "core" / "notosaurus_core" / "icons" / "lib.typ"
TARGET = ROOT / "core" / "notosaurus_core" / "typst"
NAME, VERSION = "notosaurus-icons", "0.2.0"
SOURCES = {  # name: (archive, its SHA-256, the licence file it ships)
    "maki": (
        "https://registry.npmjs.org/@mapbox/maki/-/maki-8.2.0.tgz",
        "f6e59156521117c311c0e73a6aeef8d5039daea9c7fbe1ff9264e18a3ebec87f",
        "LICENSE.txt",
    ),
    "temaki": (
        "https://registry.npmjs.org/@rapideditor/temaki/-/temaki-5.13.0.tgz",
        "52ae214da81bb1ac8ccaf4b2869deffede5e2eb17c76b1b73bb7b1098ea33b9e",
        "LICENSE.md",
    ),
    "phosphor": (
        "https://registry.npmjs.org/@phosphor-icons/core/-/core-2.1.1.tgz",
        "313332be6190b724da24107addd781799b48bf76b13963f24501112ffe1baadd",
        "LICENSE",
    ),
}
PREFIX = "ph-"  # a Phosphor icon named as a map's or a place's one
OWN = TOOLS / "icons-own"
TAGS = TOOLS / "icons-tags.json"
# The colours the function replaces: the icon's (its fill), its halo's (white, or none)
INK, HALO = "#010203", "#fefefd"
MARK = "<!--notosaurus-icon-->"  # an icon's SVG, found in a figure's (figures_typst: its size on a card)
HALO = 0.15  # the halo's stroke, as a share of what the icon draws (its larger side): a rim round it
SHAPES = re.compile(r"<(path|circle|ellipse|rect|polygon|polyline|line)\b[^>]*?/?>", re.S)


def key(name: str) -> str:
    """An icon's name, or a word, as the index keys it: lower case, `-` and `_` as spaces."""
    return re.sub(r"\s+", " ", re.sub(r"[-_]", " ", name.lower())).strip()


def _archive(name: str, folder: Path | None) -> tarfile.TarFile:
    url, sha, _ = SOURCES[name]
    local = folder / url.rsplit("/", 1)[1] if folder else None
    data = local.read_bytes() if local and local.is_file() else urllib.request.urlopen(url, timeout=60).read()
    if hashlib.sha256(data).hexdigest() != sha:
        sys.exit(f"{name}: not the archive expected ({url})")
    return tarfile.open(fileobj=io.BytesIO(data), mode="r:gz")


def _phosphor_tags(code: str) -> dict[str, list[str]]:
    """Phosphor's tags by icon, read from its index.mjs (each icon's `name` and `tags`), its
    marks ("*new*") left out; its brands' logos (a company's, a platform's) none of ours."""
    found = {}
    for name, categories, tags in re.findall(
        r'name: "([\w-]+)",.*?categories: \[([^\]]*)\].*?tags: \[([^\]]*)\]', code, re.S
    ):
        if "BRAND" not in categories:
            found[name] = [t for t in re.findall(r'"([^"]*)"', tags) if not t.startswith("*")]
    return found


def _icons(folder: Path | None) -> tuple[dict[str, str], dict[str, str], dict[str, list[str]]]:
    """Every icon's SVG by its name (Maki's, then Temaki's not named as one of them, ours,
    then Phosphor's), each source's licence text, and Phosphor's tags by its icons' names."""
    icons: dict[str, str] = {}
    licences = {}
    phosphor: dict[str, list[str]] = {}
    for source in ("maki", "temaki"):
        with _archive(source, folder) as tar:
            licences[source] = tar.extractfile(f"package/{SOURCES[source][2]}").read().decode()  # type: ignore[union-attr]
            for member in sorted(tar.getmembers(), key=lambda m: m.name):
                found = re.fullmatch(r"package/icons/([\w-]+)\.svg", member.name)
                if found:
                    name = found[1].replace("_", "-").lower()
                    if name not in icons:
                        icons[name] = tar.extractfile(member).read().decode()  # type: ignore[union-attr]
    for path in sorted(OWN.glob("*.svg")):
        if path.stem in icons:
            sys.exit(f"{path.stem}: ours named as one of Maki's or Temaki's")
        icons[path.stem] = path.read_text(encoding="utf-8")
    with _archive("phosphor", folder) as tar:
        licences["phosphor"] = tar.extractfile("package/LICENSE").read().decode()  # type: ignore[union-attr]
        tags = _phosphor_tags(tar.extractfile("package/dist/index.mjs").read().decode())  # type: ignore[union-attr]
        for member in sorted(tar.getmembers(), key=lambda m: m.name):
            found = re.fullmatch(r"package/assets/fill/([\w-]+)-fill\.svg", member.name)
            if found and found[1] in tags:
                name = found[1] if found[1] not in icons else PREFIX + found[1]
                icons[name] = tar.extractfile(member).read().decode()  # type: ignore[union-attr]
                phosphor[name] = [found[1].replace("-", " ")] * (name != found[1]) + tags.get(found[1], [])
    return icons, licences, phosphor


def _box(svg: str) -> tuple[float, float, float, float]:
    """What the icon draws, in its own units: left, top, right, bottom (rendered by resvg 600
    px wide, its pixels' box)."""
    view = [float(v) for v in re.search(r'viewBox="([^"]+)"', svg)[1].replace(",", " ").split()]  # type: ignore[index]
    scale = 600 / view[2]
    opening = re.search(r"<svg\b[^>]*>", svg)[0]  # type: ignore[index]
    bare = re.sub(r'\s(width|height)="[^"]*"', "", opening)
    sized = svg.replace(
        opening, bare.replace("<svg", f'<svg width="{view[2] * scale}" height="{view[3] * scale}"', 1), 1
    )
    png = Image.open(io.BytesIO(bytes(resvg_py.svg_to_bytes(svg_string=sized))))
    left, top, right, bottom = png.getchannel("A").getbbox() or (0, 0, png.width, png.height)
    return (view[0] + left / scale, view[1] + top / scale, view[0] + right / scale, view[1] + bottom / scale)


def refitted(svg: str) -> str:
    """The icon in a square round what it draws, its halo's room with it: all seen at the
    same size; its shapes in one colour over the same shapes in a wide stroke (the halo);
    nothing else of its own (no size, no title)."""
    left, top, right, bottom = _box(svg)
    halo = HALO * max(right - left, bottom - top)
    side = max(right - left, bottom - top) + halo
    cx, cy = (left + right) / 2, (top + bottom) / 2
    shapes = "".join(re.sub(r'\s(fill|stroke|fill-opacity|style|id)="[^"]*"', "", m[0]) for m in SHAPES.finditer(svg))
    view = f"{cx - side / 2:.3f} {cy - side / 2:.3f} {side:.3f} {side:.3f}"
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{view}">{MARK}'
        f'<g fill="{HALO}" stroke="{HALO}" stroke-width="{halo:.3f}" stroke-linejoin="round">{shapes}</g>'
        f'<g fill="{INK}">{shapes}</g></svg>'
    )


def index(tags: dict[str, list[str]], after: dict[str, list[str]] | None = None) -> dict[str, str]:
    """Each word to its icon: the one that gives it first (its name, then its tags in their
    order), Maki's, Temaki's, then ours when two give it as soon; `after`'s (Phosphor's) only
    for the words none of `tags` gives."""
    best: dict[str, tuple[int, int, str]] = {}
    for order, (icon, words) in enumerate(tags.items()):
        for rank, word in enumerate([icon, *words]):
            k = key(word)
            if k and (k not in best or (rank, order) < best[k][:2]):
                best[k] = (rank, order, icon)
    first = dict(best)
    for order, (icon, words) in enumerate((after or {}).items()):
        for rank, word in enumerate([icon, *words]):
            k = key(word)
            if k and k not in first and (k not in best or (rank, order) < best[k][:2]):
                best[k] = (rank, order, icon)
    words = {k: v[2] for k, v in best.items()}
    # an icon's family by its name's first word (battery: battery-full, map: map-trifold), the
    # shortest name of those that start with it, when no word gives it: one of them shows it
    for icon in sorted([*tags, *(after or {})], key=lambda n: (len(n), n)):
        head = key(icon).split(" ")[0]
        if len(head) > 2 and head not in words:
            words[head] = icon
    # each word's plural and singular, its last word's, when no other word is them: a safe
    # near-form (factories, a bus's buses), never an icon guessed
    for k, icon in list(words.items()):
        for form in forms(k):
            words.setdefault(form, icon)
    return dict(sorted(words.items()))


def forms(k: str) -> list[str]:
    """A word's plural and singular forms, its last word's (factory: factories; boxes: box)."""
    *first, last = k.split(" ")
    found = []
    if last.endswith("ies") and len(last) > 4:
        found.append(last[:-3] + "y")
    elif last.endswith(("ches", "shes", "sses", "xes", "zes")):
        found.append(last[:-2])
    elif last.endswith("s") and not last.endswith("ss") and len(last) > 3:
        found.append(last[:-1])
    if last.endswith("y") and last[-2:-1] not in "aeiou":
        found.append(last[:-1] + "ies")
    elif last.endswith(("ch", "sh", "ss", "x", "z")) or last.endswith("s"):
        found.append(last + "es")
    else:
        found.append(last + "s")
    return [" ".join([*first, f]) for f in found]


def main() -> None:
    folder = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    icons, licences, phosphor = _icons(folder)
    tags: dict[str, list[str]] = json.loads(TAGS.read_text(encoding="utf-8"))
    missing = sorted(set(icons) - set(tags) - set(phosphor))
    unknown = sorted(set(tags) - set(icons))
    # a word of ours for a Phosphor icon (the bench's words no icon had: a router's network),
    # after its own
    phosphor = {name: words + [w for w in tags.get(name, []) if w not in words] for name, words in phosphor.items()}
    tags = {name: words for name, words in tags.items() if name not in phosphor}
    if missing or unknown:
        sys.exit(f"tags: icons without tags {missing[:10]}, tags of no icon {unknown[:10]}")
    words = index({name: tags[name] for name in icons if name in tags}, phosphor)
    every = {**tags, **phosphor}
    first = {name: (every[name][0] if every[name] else key(name)) for name in icons}
    files: dict[str, bytes] = {
        "typst.toml": (
            f'[package]\nname = "{NAME}"\nversion = "{VERSION}"\nentrypoint = "lib.typ"\n'
            'authors = ["Notosaurus"]\nlicense = "CC0-1.0 AND MIT"\n'
            'description = "Pictograms for school figures: Maki, Temaki, Phosphor and ours, by English words"\n'
        ).encode(),
        "lib.typ": LIB.read_bytes(),
        "index.json": json.dumps({"words": words, "icons": first}, ensure_ascii=False, separators=(",", ":")).encode(),
        "LICENSE-Maki": licences["maki"].encode(),
        "LICENSE-Temaki": licences["temaki"].encode(),
        "LICENSE-Phosphor": licences["phosphor"].encode(),
        "NOTICE": (
            b"Icons from Maki 8.2.0 (Mapbox, https://github.com/mapbox/maki) and Temaki 5.13.0\n"
            b"(https://github.com/rapideditor/temaki), both CC0 1.0 (LICENSE-Maki, LICENSE-Temaki);\n"
            b"battle, treaty, pyramid, temple, crown and wheat Notosaurus's own, CC0 1.0. The objects'\n"
            b"icons from Phosphor 2.1.1, its fill weight but its brands' logos (https://phosphoricons.com),\n"
            b"MIT: Copyright (c) 2023 Phosphor Icons, its licence and notice in LICENSE-Phosphor. Each one\n"
            b"refitted to what it draws and given a halo (tools/icons.py).\n"
        ),
    }
    for name, svg in icons.items():
        files[f"icons/{name}.svg"] = refitted(svg).encode()
    TARGET.mkdir(parents=True, exist_ok=True)
    for old in TARGET.glob(f"{NAME}-*.tar.gz"):
        old.unlink()
    out = TARGET / f"{NAME}-{VERSION}.tar.gz"
    buffer = io.BytesIO()
    # gzip's header without a date (mtime=0), as the files': the same sources, the same archive
    with (
        gzip.GzipFile(fileobj=buffer, mode="wb", mtime=0, compresslevel=9) as packed,
        tarfile.open(fileobj=packed, mode="w") as tar,
    ):
        for name in sorted(files):
            info = tarfile.TarInfo(name)
            info.size, info.mtime, info.mode = len(files[name]), 0, 0o644
            tar.addfile(info, io.BytesIO(files[name]))
    out.write_bytes(buffer.getvalue())
    print(f"{out.name}: {len(icons)} icons, {len(words)} words, {out.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
