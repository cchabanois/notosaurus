"""Make the app's launcher icon from the Notosaurus logo (the repository's
assets/notosaurus-logo.png): the head, as on the web page's icons (its
tools/make_icons.py, HEAD), on a white background.

An adaptive icon (Android 8+): a 108 dp foreground the phone crops to its own shape
(circle, rounded square…), keeping at least the middle 66 dp: the head stays in it.

Usage (from android/): ../.venv/bin/python tools/make_icon.py [path/to/notosaurus-logo.png]
"""

import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SOURCE = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT.parent / "assets" / "notosaurus-logo.png"
RES = ROOT / "app" / "src" / "main" / "res"
HEAD = (590, 85, 750, 245)  # the head and the top of the neck (as the web page's icons)
FILL = 0.6  # of the 108 dp: inside the 66 dp every shape keeps
DENSITIES = {"mdpi": 1, "hdpi": 1.5, "xhdpi": 2, "xxhdpi": 3, "xxxhdpi": 4}


def main() -> None:
    head = Image.open(SOURCE).convert("RGBA").crop(HEAD)
    for density, scale in DENSITIES.items():
        side = round(108 * scale)
        inner = round(side * FILL)
        layer = Image.new("RGBA", (side, side), (255, 255, 255, 0))
        layer.paste(head.resize((inner, inner), Image.LANCZOS), ((side - inner) // 2, (side - inner) // 2))
        folder = RES / f"mipmap-{density}"
        folder.mkdir(parents=True, exist_ok=True)
        layer.save(folder / "ic_launcher_foreground.png", optimize=True)


if __name__ == "__main__":
    main()
