"""What the page tests share: the prompts the demo AI answers, and the steps several of
them take (a lesson made, the settings' password)."""

import base64
import io
import re
from pathlib import Path

from helpers import plain_image
from PIL import Image as PILImage
from playwright import sync_api

FRONT_PROMPT = "Une carte par mot de la famille"  # demo mode: Spanish family words


CLOZE_PROMPT = "Texte à trous sur la Révolution"  # demo mode: sentences with gaps


SAVED = re.compile(r"\bsaved\b")  # the save pill once the server has the lesson


def new_password(page) -> None:
    """The settings' password typed twice, once the page runs (its title written by it): a
    field filled before, on a slow machine, was emptied as the page started, the form never sent."""
    sync_api.expect(page.get_by_role("heading", name=re.compile("🔐"))).to_be_visible()
    fields = page.locator("input[autocomplete=new-password]")
    fields.first.fill("secret-pw")
    fields.nth(1).fill("secret-pw")


def lessons(page) -> list[dict]:
    return page.request.get("/api/lessons").json()


def lesson(page, id: str) -> dict:
    return page.request.get(f"/api/lessons/{id}").json()


def started(page) -> None:
    """The page started: the lesson left in progress found again (app-draft.js), if any."""
    page.wait_for_function("window.Alpine && Alpine.$data(document.querySelector('[x-data]')).draftKept")


def draft_kept(page) -> None:
    """What the page changed, kept by the host (app-draft.js sends it a moment after the
    change, or as the page is left: a request the reload may cut short): before the page is
    loaded again, else the lesson it had open isn't found again."""
    page.wait_for_function("(d => d.draftSent === d.draftText())(Alpine.$data(document.querySelector('[x-data]')))")


def generate_free(page, prompt: str) -> None:
    """A new lesson from a prompt written for this time (no photo): the last one, open again
    when the page opens (app-draft.js), set aside first; photos left in progress (kept by the
    page as soon as it saves its draft: before the page opens again, or not) removed."""
    page.goto("/")
    started(page)
    if page.evaluate("Alpine.$data(document.querySelector('[x-data]')).lessonId"):
        page.get_by_role("button", name="Nouvelle leçon").click()
    while page.locator(".thumb-remove").count():
        page.locator(".thumb-remove").first.click()
    page.get_by_role("radio", name="✏️ Libre").click()
    page.locator("textarea[x-ref=promptText]").fill(prompt)
    page.get_by_role("button", name="✨ Générer à partir de la consigne seule").click()
    page.locator(".flash").first.wait_for()


def open_prompt(page) -> None:
    """Step 2 opened, as a parent does once the lesson has cards (folded then)."""
    folded = page.locator(".prompt-folded")
    if folded.is_visible():
        folded.get_by_role("button", name="✏️ Modifier").click()
    sync_api.expect(page.locator("textarea[x-ref=promptText]")).to_be_visible()


def off_contrast(page) -> float:
    """A main button off: its text's contrast with its background (WCAG's ratio)."""
    return page.evaluate(
        """(() => {
          const b = document.createElement('button');
          b.className = 'btn primary'; b.disabled = true; b.textContent = 'x';
          document.body.append(b); const s = getComputedStyle(b);
          const linear = (v) => (v <= .03928 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4);
          const rgb = (c) => c.match(/\\d+/g).slice(0, 3).map((v) => linear(Number(v) / 255));
          const lum = (c) => { const [r, g, bl] = rgb(c); return .2126 * r + .7152 * g + .0722 * bl; };
          const [a, z] = [lum(s.color), lum(s.backgroundColor)].sort((x, y) => y - x);
          b.remove(); return (a + .05) / (z + .05);
        })()"""
    )


def png(color: str) -> bytes:
    return plain_image(600, 800, color, "PNG")


# What doesn't fit on a narrow phone: the page wider than the screen, a button or
# title cut, a placeholder longer than its field
CUT = """() => {
  const width = document.documentElement.clientWidth, found = [];
  if (document.documentElement.scrollWidth > width) found.push(`page: ${document.documentElement.scrollWidth}px`);
  // An icon's button: no text to cut, its touch layer (::after, 44 px) wider than it on purpose
  const icon = [".icon-btn", ".chip-btn.icon-only", ".thumb-remove", ".thumb-rotate", ".thumb-hide",
    ".toast > button", ".flash .pick"].join(", ");
  for (const el of document.querySelectorAll("button, .chip, .badge, summary, h2, h3, label")) {
    if (el.matches(icon)) continue;
    if (el.getBoundingClientRect().width && el.scrollWidth > el.clientWidth + 2) found.push(el.innerText.trim());
  }
  const canvas = document.createElement("canvas").getContext("2d");
  for (const el of document.querySelectorAll("input[placeholder]")) {
    if (!el.getBoundingClientRect().width || el.value) continue;
    const style = getComputedStyle(el);
    canvas.font = style.font;
    const room = el.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight);
    if (canvas.measureText(el.placeholder).width > room + 1) found.push(el.placeholder);
  }
  return [...new Set(found)];
}"""


def pdf(pages: int) -> bytes:
    """A PDF of `pages` A4 pages, each of its own colour."""
    import io

    from PIL import Image

    images = [Image.new("RGB", (595, 842), (40 * n % 255, 90, 160)) for n in range(pages)]
    out = io.BytesIO()
    images[0].save(out, "PDF", save_all=True, append_images=images[1:])
    return out.getvalue()


def text_pdf(browser) -> bytes:
    """A real text PDF (a lesson printed by the browser), not a picture of one."""
    context = browser.new_context()
    try:
        page = context.new_page()
        page.set_content("<h1>La Révolution française</h1><p>En 1789, le peuple de Paris prend la Bastille.</p>")
        return page.pdf()
    finally:
        context.close()


def add_photo(page, buffer: bytes) -> None:
    page.locator('input[type=file][accept="image/*"][multiple]').set_input_files(
        {"name": "page.png", "mimeType": "image/png", "buffer": buffer}
    )
    sync_api.expect(page.locator(".thumb img")).to_have_count(1)


def add_text_pdf(page, browser) -> None:
    page.locator("input[type=file][accept*=pdf]").set_input_files(
        {"name": "cours.pdf", "mimeType": "application/pdf", "buffer": text_pdf(browser)}
    )
    sync_api.expect(page.locator(".thumb img")).to_have_count(1)


def open_hide(page):
    """The first photo's 🖍️ editor, open."""
    page.get_by_role("button", name="Cacher une partie de la page (un nom…)").click()
    editor = page.locator(".hide-editor")
    sync_api.expect(editor).to_be_visible()
    return editor


def stroke(page, y: float) -> None:
    """A stroke across the open editor's photo, at `y` of its height."""
    box = page.locator(".hide-editor canvas").bounding_box()
    page.mouse.move(box["x"] + box["width"] * 0.1, box["y"] + box["height"] * y)
    page.mouse.down()
    page.mouse.move(box["x"] + box["width"] * 0.9, box["y"] + box["height"] * y, steps=8)
    page.mouse.up()


def generate_from_photos(page, prompt: str) -> dict:
    """A lesson from the photos added and a free prompt: the saved lesson."""
    page.locator(".chip").first.click()  # the free prompt
    page.locator("textarea[x-ref=promptText]").fill(prompt)
    page.get_by_role("button", name="✨ Générer les cartes").click()
    page.locator(".flash").first.wait_for()
    (summary,) = lessons(page)
    return lesson(page, summary["id"])


def photo_not_sent(page, i: int = 0):
    """A photo not sent yet, as it would be sent (its blob in the page), in grey levels."""
    data = page.evaluate(
        """async (i) => {
            const blob = Alpine.$data(document.querySelector('[x-data]')).photos[i].blob;
            const bytes = new Uint8Array(await blob.arrayBuffer());
            let s = "";
            for (const b of bytes) s += String.fromCharCode(b);
            return btoa(s);
        }""",
        i,
    )
    return PILImage.open(io.BytesIO(base64.b64decode(data))).convert("L")


def editor_pixel(page, x: float, y: float) -> int:
    """The open editor's canvas at (`x`, `y`) of its size, in grey level."""
    return page.evaluate(
        """([x, y]) => {
            const c = document.querySelector('.hide-editor canvas');
            const at = [Math.floor(c.width * x), Math.floor(c.height * y)];
            const [r, g, b] = c.getContext('2d').getImageData(...at, 1, 1).data;
            return Math.round((r + g + b) / 3);
        }""",
        [x, y],
    )


PDF_NOTICE = re.compile("^Sur une page de PDF, son texte n'est alors pas envoyé")


def android_settings(page, account):
    """The Android app's settings page (its own files, then static/), its account as given."""
    roots = [Path("android/app/src/main/assets/page"), Path("static")]

    def files(route):
        name = route.request.url.split("/android/", 1)[1].split("?")[0]
        found = next((root / name for root in roots if (root / name).is_file()), None)
        if found:
            route.fulfill(path=found)
        else:
            route.fulfill(status=404)

    page.route("**/android/**", files)
    page.route("**/api/admin/**", lambda route: route.fulfill(json={}))
    settings = {
        "relay": "",
        "relays": {"real": ""},
        "key": "nts_…abcd",
        "has_key": True,
        "instructions": "",
        "fun_facts": True,
    }
    settings |= {"helps": True, "pictures": True, "tts_rate": "-10%", "voices": {}, "version": "1.1.0", "mode": "phone"}
    page.route("**/api/admin/settings", lambda route: route.fulfill(json=settings))
    page.route("**/api/admin/subscription", lambda route: route.fulfill(json={"offers": [], "trial": False}))
    page.route("**/api/admin/account", lambda route: route.fulfill(json=account))
    page.goto("/android/admin.html")


def reopen(page) -> None:
    """The page loaded again, its lesson opened from the list."""
    page.reload()
    page.get_by_role("button", name="Leçons").click()
    page.locator(".lesson-list .lesson").first.click()


def drop(page, target, files: list[tuple[str, str, bytes]]) -> None:
    """Files dragged from the computer and let go on `target` (a locator), as a browser does it."""
    payload = [{"name": n, "type": t, "data": base64.b64encode(b).decode()} for n, t, b in files]
    target.evaluate(
        """(el, files) => {
            const data = new DataTransfer();
            for (const f of files) {
                const bytes = Uint8Array.from(atob(f.data), (c) => c.charCodeAt(0));
                data.items.add(new File([bytes], f.name, { type: f.type }));
            }
            for (const type of ["dragenter", "dragover", "drop"]) {
                el.dispatchEvent(new DragEvent(type, { dataTransfer: data, bubbles: true, cancelable: true }));
            }
        }""",
        payload,
    )
