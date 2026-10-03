"""Screenshots of Notosaurus for the user documentation, in each language.

Two steps:

    python tools/docs_screenshots.py generate --lang fr --settings data/settings.json
        Makes the demo lessons of a language once, with a real AI (a few cents): it
        photographs docs/demo/inputs/*.<lang>.html, generates the cards, applies a
        correction, and stores the lessons in docs/demo/<lang>/lessons/. The API keys
        come from --settings and are never written to the repository.

    python tools/docs_screenshots.py shoot --lang fr
        Runs Notosaurus on these lessons (no AI call, a fake API key, a fake Anki with
        the profiles Léa and Paul) and takes the screenshots into
        docs/src/assets/screenshots/<lang>/. Run it again whenever the interface changes.

Needs Playwright (requirements-page.txt); NOTOSAURUS_TEST_CHROMIUM picks a system Chromium.
"""

import argparse
import contextlib
import itertools
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
DEMO = ROOT / "docs" / "demo"
SHOTS = ROOT / "docs" / "src" / "assets" / "screenshots"
PROFILES = ["Léa", "Paul"]
APP = "document.querySelector('[x-data]')._x_dataStack[0]"

# The lessons made by "generate": the page photographed (docs/demo/inputs/<input>.<lang>.html,
# None: no photo), the Notosaurus prompt, a topic added to it, the deck name, and a correction
# applied afterwards. The deck name finds the lesson again in "shoot".
LESSONS = {
    "en": {
        "vocab": {
            "input": "vocab",
            "prompt": "notosaurus:vocabulary",
            "deck": "Spanish::Unit 3 - At school",
            "correction": "Add the plural on the back, like: la regla / las reglas",
        },
        "plant": {"input": "plant", "prompt": "notosaurus:diagram", "deck": "Science::Parts of a plant"},
        "cloze": {"input": "water", "prompt": "notosaurus:cloze", "deck": "Science::The water cycle - Gaps"},
        "quiz": {"input": "water", "prompt": "notosaurus:quiz", "deck": "Science::The water cycle - Quiz"},
        "geometry": {
            "prompt": "notosaurus:geometry",
            "topic": "Topic: the right triangle and Pythagoras, the circle (radius, diameter).",
            "deck": "Maths::Geometry",
        },
    },
    "fr": {
        "vocab": {
            "input": "vocab",
            "prompt": "notosaurus:vocabulary",
            "deck": "Espagnol::Unité 3 - À l'école",
            "correction": "Ajoute le pluriel au verso, comme : la regla / las reglas",
        },
        "plant": {"input": "plant", "prompt": "notosaurus:diagram", "deck": "Sciences::Les parties d'une plante"},
        "cloze": {"input": "water", "prompt": "notosaurus:cloze", "deck": "Sciences::Le cycle de l'eau - Trous"},
        "quiz": {"input": "water", "prompt": "notosaurus:quiz", "deck": "Sciences::Le cycle de l'eau - QCM"},
        "geometry": {
            "prompt": "notosaurus:geometry",
            "topic": "Sujet : le triangle rectangle et Pythagore, le cercle (rayon, diamètre).",
            "deck": "Maths::Géométrie",
        },
    },
}
# Shown in the settings screenshots
INSTRUCTIONS = {
    "en": (
        "Spanish from Spain; always the article with nouns",
        {"Léa": "in year 8", "Paul": "in year 5; short answers"},
    ),
    "fr": (
        "Espagnol d'Espagne ; toujours l'article avec les noms",
        {"Léa": "en 5ᵉ", "Paul": "en CM2 ; réponses courtes"},
    ),
}
CORRECTION_TYPED = {
    "en": "You forgot: el libro = the book",
    "fr": "Tu as oublié : el libro = le livre",
}


# --- A fake Anki: two profiles, every write accepted ---------------------------------


def fake_anki(port: int, profiles: list[str]) -> ThreadingHTTPServer:
    ids = itertools.count(1)
    results = {
        "version": 6,
        "getActiveProfile": profiles[0],
        "getProfiles": profiles,
        "modelNames": [],
        "findNotes": [],
        "notesInfo": [],
        "deckNames": ["Default"],
    }

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            action = body.get("action")
            if action == "multi":
                result = [{"result": results.get(a["action"]), "error": None} for a in body["params"]["actions"]]
            else:
                result = results.get(action, next(ids) if action in ("addNote", "createDeck") else None)
            data = json.dumps({"result": result, "error": None}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@contextlib.contextmanager
def notosaurus(data: Path):
    """The Notosaurus server on `data`, as in the Anki add-on (settings open on this computer)."""
    anki_port, port = free_port(), free_port()
    anki = fake_anki(anki_port, PROFILES)
    env = {
        **os.environ,
        "NOTOSAURUS_DATA": str(data),
        "NOTOSAURUS_EMBEDDED": "1",
        "NOTOSAURUS_ANKICONNECT_URL": f"http://127.0.0.1:{anki_port}",
        "NOTOSAURUS_ANKICONNECT_KEY": "",
    }
    python = ROOT / ".venv" / "bin" / "python"
    proc = subprocess.Popen(
        [
            str(python if python.exists() else sys.executable),
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    url = f"http://127.0.0.1:{port}/"
    try:
        for _ in range(100):
            with contextlib.suppress(OSError):
                urllib.request.urlopen(url, timeout=1)
                break
            time.sleep(0.2)
        yield url
    finally:
        proc.terminate()
        proc.wait()
        anki.shutdown()


@contextlib.contextmanager
def browser():
    with sync_playwright() as p:
        chromium = os.environ.get("NOTOSAURUS_TEST_CHROMIUM")
        b = p.chromium.launch(executable_path=chromium) if chromium else p.chromium.launch()
        try:
            yield b
        finally:
            b.close()


def phone(b, lang: str):
    ctx = b.new_context(
        viewport={"width": 390, "height": 844},
        device_scale_factor=2,
        is_mobile=True,
        has_touch=True,
        locale=lang,
        color_scheme="light",
    )
    ctx.add_init_script(f"localStorage.setItem('notosaurus.lang', {json.dumps(lang)})")
    return ctx.new_page()


def wait_for(page, condition: str, timeout: float = 420):
    page.wait_for_function(condition, timeout=timeout * 1000, polling=500)


# --- generate ------------------------------------------------------------------------


def generate(lang: str, settings_file: Path, only: list[str] | None = None) -> None:
    """Make the demo lessons `only` (default: all) of a language, replacing those with the same deck."""
    out = DEMO / lang / "lessons"
    lessons = {k: v for k, v in LESSONS[lang].items() if not only or k in only}
    with tempfile.TemporaryDirectory() as tmp, browser() as b:
        tmp = Path(tmp)
        data = tmp / "data"
        data.mkdir()
        shutil.copy(settings_file, data / "settings.json")  # real keys, temporary folder only
        page = b.new_page(viewport={"width": 1200, "height": 1600})
        for name in {lesson["input"] for lesson in lessons.values() if lesson.get("input")}:  # the "photos"
            page.goto((DEMO / "inputs" / f"{name}.{lang}.html").as_uri())
            page.wait_for_load_state("networkidle")
            page.evaluate("document.fonts.ready")
            page.screenshot(path=tmp / f"{name}.jpg", type="jpeg", quality=88)
        with notosaurus(data) as url:
            page = phone(b, lang)
            page.goto(url)
            page.wait_for_load_state("networkidle")
            for key, lesson in lessons.items():
                page.evaluate(f"{APP}.newLesson()")
                photos = 1 if lesson.get("input") else 0
                if photos:
                    page.locator("input[type=file][multiple]").first.set_input_files(tmp / f"{lesson['input']}.jpg")
                    wait_for(page, f"{APP}.photos.length === 1", timeout=30)  # read and resized by the page
                page.evaluate(f"{APP}.choose({json.dumps(lesson['prompt'])})")
                if lesson.get("topic"):
                    page.evaluate(f"t => {{ {APP}.form.text += '\\n' + t; }}", lesson["topic"])
                page.evaluate(f"{APP}.extract()")
                wait_for(page, f"!{APP}.loading && {APP}.cards.length > 0")
                wait_for(page, f"{APP}.cards.every(c => !(c.figure || c.picture_prompt) || c.picture)")
                if page.evaluate(f"{APP}.photos.length") != photos:
                    raise RuntimeError(f"{lang}/{key}: the photo wasn't sent")
                page.evaluate(f"d => {{ {APP}.deck = d; }}", lesson["deck"])
                page.evaluate(f"{APP}.saveNow()")
                if lesson.get("correction"):
                    page.evaluate(f"t => {{ {APP}.revision.text = t; {APP}.revise(); }}", lesson["correction"])
                    wait_for(page, f"!{APP}.revision.busy && !!{APP}.revision.summary")
                page.evaluate(f"{APP}.saveNow()")
                time.sleep(1)
                print(f"{lang}: {key} → {page.evaluate(f'{APP}.cards.length')} cards", flush=True)
        out.mkdir(parents=True, exist_ok=True)
        decks = {lesson["deck"] for lesson in lessons.values()}
        for old in out.glob("*/lesson.json"):  # the lessons made again
            if json.loads(old.read_text(encoding="utf-8"))["deck"] in decks:
                shutil.rmtree(old.parent)
        for folder in (data / "lessons").iterdir():
            target = out / folder.name
            shutil.copytree(folder, target, ignore=shutil.ignore_patterns("audio"))
            lesson = target / "lesson.json"  # the demo profile, whoever ran it
            content = json.loads(lesson.read_text(encoding="utf-8"))
            content["owner"] = PROFILES[0]
            lesson.write_text(json.dumps(content, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Lessons saved in {out.relative_to(ROOT)}")


# --- shoot ---------------------------------------------------------------------------


def demo_data(lang: str, tmp: Path) -> Path:
    data = tmp / "data"
    shutil.copytree(DEMO / lang / "lessons", data / "lessons")
    general, per_profile = INSTRUCTIONS[lang]
    settings = {
        "llm": "gemini",
        "gemini_api_key": "AIzaSy-notosaurus-demo-key-1234",
        "instructions": general,
        "profile_instructions": per_profile,
    }
    (data / "settings.json").write_text(json.dumps(settings, ensure_ascii=False), encoding="utf-8")
    return data


def scroll_to(page, selector: str, offset: int = 70) -> None:
    page.evaluate(f"""() => {{ const el = document.querySelector({json.dumps(selector)});
        window.scrollTo(0, el.getBoundingClientRect().top + window.scrollY - {offset}); }}""")
    time.sleep(0.4)


def lesson_id(page, prefix: str) -> str:
    return page.evaluate(f"p => {APP}.lessons.find(l => l.deck.startsWith(p)).id", prefix)


def shoot(lang: str) -> None:
    out = SHOTS / lang
    out.mkdir(parents=True, exist_ok=True)
    vocab_deck, plant_deck = LESSONS[lang]["vocab"]["deck"], LESSONS[lang]["plant"]["deck"]
    with tempfile.TemporaryDirectory() as tmp, browser() as b, notosaurus(demo_data(lang, Path(tmp))) as url:
        page = phone(b, lang)

        def shot(name):
            time.sleep(0.5)
            page.screenshot(path=out / f"{name}.png")
            print(f"{lang}/{name}.png", flush=True)

        page.goto(url)
        page.wait_for_load_state("networkidle")
        time.sleep(1)
        shot("home")

        vocab_photo = next(
            f.parent / "page-1.jpg"
            for f in (DEMO / lang / "lessons").glob("*/lesson.json")
            if json.loads(f.read_text(encoding="utf-8"))["deck"] == vocab_deck
        )
        page.locator("input[type=file][multiple]").first.set_input_files(vocab_photo)
        wait_for(page, f"{APP}.photos.length === 1", timeout=30)
        page.evaluate(f"{APP}.choose('notosaurus:vocabulary')")
        scroll_to(page, "section.panel:has(input[type=file])", 70)
        shot("instructions")

        page.evaluate(f"{APP}.openViewer({APP}.photos.map(p => p.url), 0)")
        time.sleep(0.8)
        shot("photo-viewer")
        page.evaluate(f"{APP}.viewer.open = false")

        page.evaluate(f"{APP}.openPicker()")
        time.sleep(0.8)
        shot("prompt-picker")
        page.evaluate(f"{APP}.picker.open = false")

        page.evaluate(f"{APP}.openEditor('edit')")  # a Notosaurus prompt: read-only, with "Duplicate"
        time.sleep(0.8)
        shot("prompt-editor")
        page.evaluate(f"{APP}.editor.open = false")
        page.evaluate(f"{APP}.clearPhotos()")

        page.evaluate(f"{APP}.lessonsOpen = true")
        time.sleep(0.8)
        shot("lessons")
        page.evaluate(f"{APP}.lessonsOpen = false")

        page.evaluate(f"id => {APP}.openLesson(id)", lesson_id(page, vocab_deck))
        page.wait_for_load_state("networkidle")
        scroll_to(page, "section.review", 10)
        shot("review")
        page.locator("form.revise textarea").fill(CORRECTION_TYPED[lang])
        scroll_to(page, "form.revise", 120)
        shot("correction")
        page.locator("form.revise textarea").fill("")
        scroll_to(page, ".export-options", 420)
        shot("review-options")

        page.evaluate(f"id => {APP}.openLesson(id)", lesson_id(page, plant_deck))
        page.wait_for_load_state("networkidle")
        scroll_to(page, "section.review", 10)
        page.evaluate("window.scrollBy(0, 300)")
        shot("diagram")

        for key, name in (("cloze", "cloze"), ("quiz", "quiz"), ("geometry", "figures")):
            page.evaluate(f"id => {APP}.openLesson(id)", lesson_id(page, LESSONS[lang][key]["deck"]))
            page.wait_for_load_state("networkidle")
            scroll_to(page, "section.review", 10)
            page.evaluate("window.scrollBy(0, 230)")
            shot(name)

        page.evaluate(f"id => {APP}.openLesson(id)", lesson_id(page, vocab_deck))
        page.wait_for_load_state("networkidle")
        scroll_to(page, "section.review", 10)
        page.evaluate(f"{APP}.sendToAnki()")  # to the fake Anki
        wait_for(page, f"!{APP}.sending", timeout=60)
        shot("sent")

        page.goto(url + "admin.html")
        page.wait_for_load_state("networkidle")
        time.sleep(1)
        shot("settings-ai")
        scroll_to(page, "section.phones", 80)
        shot("settings-phones")
        page.evaluate("""() => {
            const h = [...document.querySelectorAll('section.panel h2')].find(e => e.textContent.includes('📝'));
            window.scrollTo(0, h.getBoundingClientRect().top + scrollY - 90);
        }""")
        time.sleep(0.4)
        shot("settings-instructions")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("step", choices=("generate", "shoot"))
    parser.add_argument("--lang", action="append", help="language code (several allowed); default: all")
    parser.add_argument("--only", action="append", help="for generate: only these lessons (vocab, plant…)")
    parser.add_argument(
        "--settings",
        type=Path,
        default=ROOT / "data" / "settings.json",
        help="settings with the API keys, for generate",
    )
    args = parser.parse_args()
    for lang in args.lang or list(LESSONS):
        generate(lang, args.settings, args.only) if args.step == "generate" else shoot(lang)


if __name__ == "__main__":
    main()
