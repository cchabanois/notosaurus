"""A bench of real lessons: each made again by the AI (the test relay, as the Android app
does), its Anki package then built as the app builds it, and checked: each card's note
type (its family, the lesson's options), the voice (its language, the side it is heard
on), the diagrams' masks, and the cards against the lesson's own.

The lessons are private (children's notebooks): a folder of lesson folders, each its
lesson.json and its page-N.jpg, never committed (notes/bench/lessons by default). A
lesson's expect.json, if any, says what the general rules can't:
  {"voice": "any" | "none" | "en", "cards": [3, 8], "contains": ["vendredi"], "dictation": true, "why": "…"}
("dictation": the page is one to prepare, which Automatic must see: --prompt auto)

  .venv/bin/python tools/bench.py [--only espagnol] [--jobs 6] [--bench notes/bench]

The test relay's licence: RELAY_KEY, else ~/git/notosaurus-cloud/.test-licence-bench (its
own: 5,000 credits a day), else .test-licence-dev. Each run is kept in <bench>/runs/, the
AI's answers with it (--reuse <run>: checked again without asking the AI), and compared
with the one before.
"""

import argparse
import json
import os
import re
import sys
import tempfile
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "core"), str(ROOT / "tests")]

DIRECTORY = "https://cchabanois.github.io/notosaurus/relay.json"
CLIENT = "9.9.9"  # never refused as outdated
PAGE = "fr"  # the page's language: the pupil's own
VARIETY = {"en": "en-gb", "pt": "pt-pt"}  # a language's usual variety (Speech.VARIETY)
# The language a lesson's subject is learned in: its voice's (the others, the pupil's own: none, but for a dictation)
LEARNED = {"espagnol": "es", "anglais": "en", "allemand": "de", "italien": "it", "portugais": "pt"}


# --- Making a lesson again --------------------------------------------------------


def relay() -> tuple[str, str]:
    url = httpx.get(DIRECTORY, timeout=10).json()["test"]
    key = os.environ.get("RELAY_KEY", "")
    if not key:
        for name in (".test-licence-bench", ".test-licence-dev"):
            path = Path.home() / "git/notosaurus-cloud" / name
            found = re.search(r"nts_[A-Za-z0-9_-]+", path.read_text()) if path.is_file() else None
            if found:
                key = found.group()
                break
    return url, key


def options(lesson: dict, builtins: list, forced: str = "") -> dict:
    """How the lesson was asked for: its prompt's options when it is one of Notosaurus's (its
    voice "auto"), else the lesson's own. `forced`: a built-in prompt's key, for every lesson
    with only its options ("auto": does the AI make what each page calls for?)."""
    if forced:
        prompt = next(p for p in builtins if p.id == f"notosaurus:{forced}")
        lesson = {"prompt": prompt.text}

    def same(text: str) -> str:
        return " ".join(text.split())  # a phone's line ends (\r\n) as the computer's

    prompt = next((p for p in builtins if same(p.text) == same(lesson.get("prompt", ""))), None)
    return {
        "prompt": lesson.get("prompt") or "Crée des cartes pour réviser la leçon.",
        "builtin": prompt.id if prompt else "",
        "deck": prompt.deck if prompt else "",
        "voice": prompt.voice if prompt else ("auto" if lesson.get("voice") else ""),
        "reverse": bool(lesson.get("reverse")),
        "typing": bool(lesson.get("typing") or (prompt and prompt.typing)),
        "dictation": bool(lesson.get("dictation") or (prompt and prompt.dictation)),
        "dictation_only": bool(lesson.get("dictation_only") or (prompt and prompt.dictation_only)),
    }


class Limit(RuntimeError):
    """The licence's credits or today's limit reached: the other lessons not tried."""


def extract(url: str, key: str, folder: Path, asked: dict, lesson: dict) -> dict:
    photos = sorted(folder.glob("page-*.jpg"), key=lambda p: int(p.stem.split("-")[1]))
    # The fun facts, helps and pictures asked, as the app's settings do at first
    request = {"prompt": asked["prompt"], "deck": asked["deck"], "fun_facts": True, "helps": True, "pictures": True}
    texts = lesson.get("page_texts") or []
    if any(texts):
        request["page_texts"] = texts
    files = [("request", (None, json.dumps(request), "application/json"))]
    files += [("images", (p.name, p.read_bytes(), "image/jpeg")) for p in photos]
    headers = {"Authorization": f"Bearer {key}", "X-Notosaurus-Version": CLIENT}
    for wait in (5, 15, 30, None):  # the relay starting, or the licence's calls all running: again
        res = httpx.post(f"{url}/v1/extract", files=files, headers=headers, timeout=300)
        limit = res.status_code in (402, 429) and "busy" not in res.text  # credits or today's limit: no use again
        if res.status_code not in (429, 500, 502, 503) or limit or wait is None:
            break
        time.sleep(wait)
    if limit:
        raise Limit(res.text[:200])
    if res.status_code != 200:
        raise RuntimeError(f"{res.status_code} {res.text[:200]}")
    return res.json()


def voice_for(url: str, key: str, language: str) -> str:
    """The relay's voice for a language, as the app picks it (Speech.voiceFor): the variety
    asked for, else the language's own, its default voice."""
    if not language:
        return ""
    voices = httpx.get(
        f"{url}/v1/voices", headers={"Authorization": f"Bearer {key}", "X-Notosaurus-Version": CLIENT}, timeout=30
    ).json()
    tag = language.lower().replace("_", "-")
    base = tag.split("-")[0]
    ranked = sorted(
        (v for v in voices if v["locale"].lower().split("-")[0] == base),
        key=lambda v: (
            v["locale"].lower() != tag,
            v["locale"].lower() != VARIETY.get(base, f"{base}-{base}"),
            not v["voice"].endswith("-Aoede"),
        ),
    )
    return ranked[0]["voice"] if ranked else ""


# --- The Anki package, as the app builds it ------------------------------------------


def got(res) -> dict:
    if res.status_code != 200:
        raise RuntimeError(f"{res.request.url.path}: {res.status_code} {res.text[:300]}")
    return res.json()


def package(client, folder: Path, made: dict, asked: dict, voice: str, scratch: Path):
    """The lesson saved as the app saves it (its photos, the new cards), then exported."""
    import apkg  # pyright: ignore[reportMissingImports] (tests/, on the path above)

    lesson = json.loads((folder / "lesson.json").read_text())
    lesson_id = lesson.get("id") or folder.name.split("-", 1)[1]  # the computer's: its folder's name
    target = Path(os.environ["NOTOSAURUS_DATA"]) / "lessons" / lesson_id
    target.mkdir(parents=True, exist_ok=True)
    for photo in folder.glob("page-*.jpg"):
        (target / photo.name).write_bytes(photo.read_bytes())
    cards = made["deck"]["cards"]
    frames = made.get("frames") or []
    saved = {
        **{k: lesson.get(k) for k in ("created_at", "updated_at", "prompt", "page_texts") if k in lesson},
        "deck": made["deck"]["deck"],
        "cards": cards,
        "frames": frames,
        "voice": voice,
    }
    (target / "lesson.json").write_text(json.dumps(saved, ensure_ascii=False))
    body = {
        "deck": made["deck"]["deck"],
        "cards": got(client.get(f"/api/lessons/{lesson_id}"))["cards"],  # with the ids the app gives
        "voice": voice,
        "reverse": asked["reverse"] or bool(made.get("reverse")),  # the lesson's, or read by the AI
        "typing": asked["typing"] or bool(made.get("typing")),  # the prompt's, or read by the AI
        "dictation": asked["dictation"],
        "dictation_only": asked["dictation_only"],
        "frames": frames,
        "lesson_id": lesson_id,
    }
    out = scratch / lesson_id
    out.mkdir(parents=True, exist_ok=True)
    return body, apkg.export(client, body, out)


# --- The checks ----------------------------------------------------------------------


def own_language_heard(asked: dict, made: dict) -> bool:
    """Whether the backs are heard in the pupil's own language too, as the app tells it: the
    prompt's options, or what the AI read (a typed answer, a dictation, "read aloud")."""
    said = ("typing", "dictation_card", "read_aloud")
    return asked["typing"] or asked["dictation"] or asked["dictation_only"] or any(made.get(k) for k in said)


def plain(text: str) -> str:
    text = unicodedata.normalize("NFKD", re.sub(r"<[^>]+>|\{\{c\d+::|\}\}|::[^}]*", " ", text or ""))
    return " ".join("".join(c for c in text if not unicodedata.combining(c)).lower().split())


def family(name: str) -> str:
    from app import anki

    return anki.family(name)


def check(
    lesson: dict, asked: dict, made: dict, voice: str, body: dict, package, expect: dict
) -> list[tuple[bool | None, str]]:
    """(passed, what) for each check; None: told, not checked. `expect`: the lesson's own
    expectations (expect.json), over the general rules."""
    results: list[tuple[bool | None, str]] = []
    cards = body["cards"]
    # The subject: any level of the deck (a child's lesson's starts with its name, its class)
    parts = [part.strip().lower() for part in lesson.get("deck", "").split("::")]
    learned = next((LEARNED[part] for part in parts if part in LEARNED), "")
    spelling = own_language_heard(asked, made)

    # Automatic: a dictation recognised when the page is one (expect.json "dictation"), never otherwise
    if asked["builtin"] == "notosaurus:auto":
        dictated, page_is_one = bool(made.get("dictation")), bool(expect.get("dictation"))
        said = "recognised" if dictated else "not chosen"
        results.append((dictated == page_is_one, f"dictation {said} (expected: {page_is_one})"))

    # The reverse card when the page calls for one (expect.json "reverse")
    if "reverse" in expect:
        both = asked["reverse"] or bool(made.get("reverse"))
        results.append((both == expect["reverse"], f"reverse card: {both} (expected: {expect['reverse']})"))

    # A typed answer when the page calls for one (expect.json "typing"): the prompt's, or read by the AI
    if "typing" in expect:
        typed = asked["typing"] or bool(made.get("typing"))
        results.append((typed == expect["typing"], f"typed answer: {typed} (expected: {expect['typing']})"))

    # The voice: the language learned's, the pupil's own for a dictation, else none
    said = made.get("back_language") or "none"  # (the voice's language the AI said)
    if expect.get("voice") == "any":
        results.append((None, f"voice {voice or 'none'} (any; the AI said {said})"))
    elif asked["voice"] == "auto":
        expected = expect.get("voice", learned or (PAGE if spelling else ""))
        expected = "" if expected == "none" else expected
        language = voice.split("-")[0].lower() if voice else ""
        what = f"voice {voice or 'none'} (expected {expected or 'none'}; the AI said {said})"
        results.append((language == expected, what))

    # Each card's note type: its family by what it is
    def expected_family(c: dict) -> str:
        if re.search(r"\{\{c\d+::", c.get("front", "")):
            return "cloze"
        if c.get("choices"):
            return "choice"
        if c.get("mask"):
            return "diagram"
        return "text"

    wanted: dict[str, int] = {}
    for c in cards:
        if expected_family(c) != "cloze" and not (c.get("back") or "").strip():
            continue  # no back: not sent
        wanted[expected_family(c)] = wanted.get(expected_family(c), 0) + 1
    got: dict[str, int] = {}
    for note in package.notes:
        f = family(package.models[note[1]]["name"])
        got[f] = got.get(f, 0) + 1
    results.append((got == wanted, f"note families {got} (cards: {wanted})"))

    # The text note types: the lesson's options in their name
    for model in {
        package.models[n[1]]["name"] for n in package.notes if family(package.models[n[1]]["name"]) == "text"
    }:
        heard = (asked["dictation"] or asked["dictation_only"]) and bool(voice)
        if asked["dictation_only"] and heard:
            ok = model.startswith("Notosaurus dictée")
        else:
            ok = model.startswith("Notosaurus recto/verso")
            ok &= ("à taper" in model) == body["typing"]
            ok &= ("+ dictée" in model) == bool(heard)
            ok &= ("+ inverse" in model) == body["reverse"]
        results.append((ok, f"note type {model!r}"))

    # The voice heard on the right side: on the answer (front → back), on the question
    # (back → front, dictation); never on a question that would give the answer away
    for model in {package.models[n[1]]["name"]: package.models[n[1]] for n in package.notes}.values():
        if "Audio" not in [f["name"] for f in model["flds"]]:
            continue
        for t in model["tmpls"]:
            on_question, on_answer = "{{Audio}}" in t["qfmt"], "{{Audio}}" in t["afmt"]
            if t["name"] in ("Dictée", "Verso → Recto"):
                ok = on_question
            else:
                ok = on_answer and not on_question
            side = "question" if on_question else "answer" if on_answer else "neither"
            results.append((ok, f"{model['name']} / {t['name']}: sound on {side}"))

    # Every card heard when there is a voice (but formulas, texts with gaps, choices); none without
    silent = []
    for note in package.notes:
        fields = package.fields_by_name(note)
        if "Audio" not in fields:
            continue
        has = fields["Audio"].startswith("[sound:")
        if bool(voice) != has and not ("\\(" in fields.get("Back", "") or "\\[" in fields.get("Back", "")):
            silent.append(fields.get("Front", "")[:30] or fields.get("Back", "")[:30])
    results.append(
        (not silent, "sound on every card" if voice else "no sound" + (f" (wrong: {silent[:3]})" if silent else ""))
    )

    # A dictation's sound: the sentence, then the word (two parts), when its front has a blank
    if (asked["dictation"] or asked["dictation_only"]) and voice:
        blanks = [c for c in cards if re.search(r"…|\.{3}|_{3,}", c.get("front", ""))]
        if blanks:
            from notosaurus_core import tts
            from notosaurus_core.models import Card

            said = tts.spoken(Card(**{k: v for k, v in blanks[0].items() if k in Card.model_fields}), True)
            results.append(
                (said.count("\n") == 1 and said.endswith(blanks[0]["back"].strip()), f"dictation heard {said!r}")
            )

    # The diagrams' masks: in the photo, in their frame
    frames = {f["page"]: f["box"] for f in body.get("frames") or []}
    outside = []
    for c in cards:
        m = c.get("mask")
        if not m:
            continue
        x0, y0, x1, y1 = m["box"]
        inside = 0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1
        if m["page"] in frames:
            fx0, fy0, fx1, fy1 = frames[m["page"]]
            inside &= fx0 - 0.02 <= x0 and fy0 - 0.02 <= y0 and x1 <= fx1 + 0.02 and y1 <= fy1 + 0.02
        if not inside:
            outside.append(c.get("back", "")[:20])
    if any(c.get("mask") for c in cards):
        results.append((not outside, "masks in their frame" + (f" (not: {outside[:3]})" if outside else "")))

    # Against the lesson's own cards: about as many (the answers themselves told, not checked:
    # the AI words them anew each time)
    before = [c for c in lesson.get("cards", []) if (c.get("back") or c.get("front", "")).strip()]
    if "cards" in expect:
        low, high = expect["cards"]
        results.append((low <= len(cards) <= high, f"{len(cards)} cards (expected {low} to {high})"))
    elif before:
        ratio = len(cards) / len(before)
        results.append((0.5 <= ratio <= 2, f"{len(cards)} cards ({len(before)} before)"))
    text = plain(" ".join(f"{c.get('front', '')} {c.get('back', '')} {c.get('info', '')}" for c in cards))
    for word in expect.get("contains", []):
        results.append((plain(word) in text, f"contains {word!r}"))
    if before:
        new = [set(plain(c.get("back") or c.get("front", "")).split()) for c in cards]
        alike = sum(
            1
            for c in before
            if (old := set(plain(c.get("back") or c.get("front", "")).split()))
            and max((len(old & n) / len(old) for n in new), default=0) >= 0.6
        )
        results.append((None, f"{alike}/{len(before)} answers of before alike"))
    return results


# --- Running it ------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--bench", default=str(ROOT / "notes/bench"))
    parser.add_argument("--only", default="", help="lessons whose folder name holds this")
    parser.add_argument("--jobs", type=int, default=3)
    parser.add_argument("--reuse", default="", help="a run's folder (runs/<at>): its AI answers, not asked again")
    parser.add_argument("--prompt", default="", help='a built-in prompt for every lesson ("auto": its choices checked)')
    args = parser.parse_args()
    bench = Path(args.bench)
    folders = [f for f in sorted((bench / "lessons").iterdir()) if f.is_dir() and args.only.lower() in f.name.lower()]

    data = Path(tempfile.mkdtemp(prefix="notosaurus-bench-"))
    os.environ["NOTOSAURUS_DATA"] = str(data / "data")
    os.environ["NOTOSAURUS_LLM"] = "fake"  # the app's own AI is never called: the relay makes the cards
    from fastapi.testclient import TestClient

    from notosaurus_core import tts

    async def fake_sound(text, voice, path, rate):  # what matters is that it is there
        path.write_bytes(b"ID3bench " + text.encode())

    tts._synthesize = fake_sound
    from app.main import app
    from app.prompts import list_all

    client = TestClient(app, client=("127.0.0.1", 50000), base_url="http://127.0.0.1:8000")  # the computer itself
    builtins = list_all(PAGE)
    url, key = relay()

    at = datetime.now().isoformat(timespec="seconds").replace(":", "-")
    answers = bench / "runs" / at / "answers"
    answers.mkdir(parents=True, exist_ok=True)
    reused = Path(args.reuse) / "answers" if args.reuse else None
    stop = []

    def make(folder: Path):
        lesson = json.loads((folder / "lesson.json").read_text())
        asked = options(lesson, builtins, args.prompt)
        kept = reused / f"{folder.name}.json" if reused else None
        if kept and kept.is_file():
            made = json.loads(kept.read_text())
        elif stop:
            return folder, lesson, asked, Limit("not tried: " + stop[0])
        else:
            try:
                made = extract(url, key, folder, asked, lesson)
            except Limit as e:
                stop.append(str(e))
                return folder, lesson, asked, e
            except Exception as e:  # one lesson failing leaves the others
                return folder, lesson, asked, e
        (answers / f"{folder.name}.json").write_text(json.dumps(made, ensure_ascii=False))  # never paid twice
        return folder, lesson, asked, made

    print(f"{len(folders)} lessons, the AI on {url}…", flush=True)
    with ThreadPoolExecutor(args.jobs) as pool:
        made = list(pool.map(make, folders))

    from app.routes.generation import _learned

    run = {"at": at, "lessons": {}}
    failed = 0
    for folder, lesson, asked, result in made:
        name = folder.name
        if isinstance(result, Exception):
            print(f"\n✗ {name}: the AI failed: {result}")
            run["lessons"][name] = {"error": str(result)}
            failed += 1
            continue
        if result.get("dictation"):  # a dictation the AI recognised (Automatic): as the app does
            asked = {**asked, "dictation": True, "dictation_only": True}
        voice = asked["voice"]
        if voice == "auto":
            voice = voice_for(
                url,
                key,
                _learned(result.get("back_language", ""), PAGE, own_language_heard(asked, result)),
            )
        try:
            body, pack = package(client, folder, result, asked, voice, data / "packages")
            expect_file = folder / "expect.json"
            expect = json.loads(expect_file.read_text()) if expect_file.is_file() else {}
            results = check(lesson, asked, result, voice, body, pack, expect)
        except Exception as e:  # the bench's own fault: the others still checked
            print(f"\n✗ {name}: not checked: {type(e).__name__}: {e}")
            run["lessons"][name] = {"error": f"{type(e).__name__}: {e}"}
            failed += 1
            continue
        bad = [what for ok, what in results if ok is False]
        failed += bool(bad)
        print(f"\n{'✗' if bad else '✓'} {name}  [{asked['builtin'] or 'own prompt'}]")
        for ok, what in results:
            print(f"   {'·' if ok is None else '✓' if ok else '✗'} {what}")
        run["lessons"][name] = {
            "checks": [[ok, what] for ok, what in results],
            "cards": len(body["cards"]),
            "voice": voice,
        }

    runs = bench / "runs"
    previous = sorted(p for p in runs.glob("*/run.json") if p.parent.name != at)
    (runs / at / "run.json").write_text(json.dumps(run, ensure_ascii=False, indent=1))
    print(f"\n{len(folders) - failed}/{len(folders)} lessons pass all their checks.")
    if previous:
        before = json.loads(previous[-1].read_text())["lessons"]
        for name, now in run["lessons"].items():
            was = before.get(name, {})
            ok_now = "checks" in now and all(ok is not False for ok, _ in now["checks"])
            ok_was = "checks" in was and all(ok is not False for ok, _ in was["checks"])
            if name in before and ok_now != ok_was:
                print(f"  {'now passes' if ok_now else 'NOW FAILS'}: {name}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
