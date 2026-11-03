"""Make the logo images and the icons from the Notosaurus logo (assets/notosaurus-logo.png).

Run again after changing the logo (and the crop boxes below, in its pixels):
- static/logo.webp: the whole logo, drawing and name (the README);
- static/logo-mark.webp: the head alone, in the app bar: the whole drawing is a blur
  at that size, the head is still recognised;
- the icons, from the head, named after the logo (notosaurus-…): phones keep an
  icon by its address, so a new logo needs new names to be seen at all. Phones don't
  use an SVG for the home screen (Chrome on Android makes a plain letter icon without
  a PNG, an iPhone wants a 180 px PNG). The "maskable" one keeps the head in the
  middle 80%: Android crops it to its own shape;
- android/play/icon-512.png: the Google Play listing's icon, 512 px, a 32-bit PNG as Play
  Console asks (not quantized), Google Play rounding its corners itself. From the icon drawn
  large (assets/notosaurus-icon-1024.jpg: the same head, star and sparkles as the logo's,
  1024 px): the logo's head is 160 px, blurred at 512.
"""

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "assets" / "notosaurus-logo.png"
ICON_SOURCE = ROOT / "assets" / "notosaurus-icon-1024.jpg"  # the icon drawn large: the Play icon's
STATIC = ROOT / "static"
PLAY = ROOT / "android" / "play"  # the Google Play listing's graphics
WHOLE = (253, 30, 764, 495)  # the drawing and the name, with a margin
HEAD = (590, 85, 750, 245)  # the head and the top of the neck


def square(image: Image.Image, side: int, fill: float) -> Image.Image:
    """The image in a white square of `side`, taking `fill` of it."""
    inner = round(side * fill)
    scaled = image.copy()
    scaled.thumbnail((inner, inner), Image.LANCZOS)
    if scaled.width < inner:  # smaller than wanted: enlarge, the head is small in the logo
        scaled = image.resize((inner, round(inner * image.height / image.width)), Image.LANCZOS)
    out = Image.new("RGB", (side, side), "white")
    out.paste(scaled, ((side - scaled.width) // 2, (side - scaled.height) // 2))
    return out


def save_png(image: Image.Image, path: Path) -> None:
    """256 colours: plenty for an icon, a third of the size (they ship with the add-on)."""
    image.quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE).save(path, optimize=True)


def main() -> None:
    logo = Image.open(SOURCE).convert("RGB")
    whole, head = logo.crop(WHOLE), logo.crop(HEAD)
    whole.thumbnail((640, 640), Image.LANCZOS)
    whole.save(STATIC / "logo.webp", quality=85, method=6)
    square(head, 192, 0.92).save(STATIC / "logo-mark.webp", quality=88, method=6)
    save_png(square(head, 192, 0.92), STATIC / "notosaurus-192.png")
    save_png(square(head, 512, 0.92), STATIC / "notosaurus-512.png")
    save_png(square(head, 512, 0.72), STATIC / "notosaurus-maskable-512.png")
    save_png(square(head, 180, 0.92), STATIC / "notosaurus-touch-180.png")  # iOS rounds the corners
    save_png(square(head, 64, 0.95), STATIC / "notosaurus-64.png")
    PLAY.mkdir(exist_ok=True)
    play_icon().save(PLAY / "icon-512.png", optimize=True)


def play_icon() -> Image.Image:
    """The icon drawn large, at 512 px, RGBA."""
    return Image.open(ICON_SOURCE).convert("RGB").resize((512, 512), Image.LANCZOS).convert("RGBA")


if __name__ == "__main__":
    main()
