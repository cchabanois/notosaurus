"""A bench of figures: each case's description drawn by the test relay (/v1/figure, as the
Android app asks), a few times, then judged: by code (a figure that renders, fills its
picture, has its labels, none of them hidden) and by the AI looking at it, with its thinking (stricter than the
light check of the "🔍 Check" button). A sheet of every figure to look at, its
verdicts, time and credits; compared with the run before.

The cases: <bench>/figures.json (private, never committed; notes/bench by default), the
figures users reported and the hard ones, a list of
  {"id": "parallelogram-marks", "description": "Un parallélogramme ABCD…", "why": "reported 2026-10-25"}

  .venv/bin/python tools/bench_figures.py [--only angles] [--times 3] [--jobs 3] [--bench notes/bench]
      [--cases other.json] [--local [--app ~/git/notosaurus]] [--recompile <run>]

--cases: another list of cases (a syllabus's figures, say), the runs still in <bench>/runs.
--local: drawn here, by the AI of the app's settings (<app>/data, its keys in <app>/.env;
the checkout by default), with this checkout's rules: a rule judged before it is deployed.
Every Typst drawing keeps its Typst beside its SVG (<case>-<n>.typ).
--recompile <run>: that run's Typst compiled again with this checkout's preambles, no AI
drawing: a preamble's change (a font, a size, a function) judged on the same drawings.

The AI judge: Gemini on Vertex AI, the project in BENCH_JUDGE_PROJECT (application default
credentials, `gcloud auth application-default login`); none: judged by code only. The test
relay's licence: as tools/bench.py.
"""

import argparse
import asyncio
import html
import io
import json
import os
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "core"), str(ROOT / "tools")]

from bench import CLIENT, relay  # noqa: E402

from notosaurus_core import ai, figure_making, figures, figures_typst  # noqa: E402
from notosaurus_core.calls import Image  # noqa: E402
from notosaurus_core.config import AIConfig  # noqa: E402

FILLS = 0.4  # the drawing spans at least this share of the picture's width or height
# Where a text is only defined, drawn elsewhere or not at all: not a label of the picture
NOT_DRAWN = {"defs", "symbol", "marker", "pattern", "clipPath", "mask"}


def draw(url: str, key: str, description: str) -> dict:
    """The relay's figure: its SVG, seconds, credits; or its error."""
    headers = {"Authorization": f"Bearer {key}", "X-Notosaurus-Version": CLIENT}
    start = time.monotonic()
    for wait in (5, 15, 30, 60, None):  # the relay starting, or the licence's calls all running: again
        res = httpx.post(f"{url}/v1/figure", json={"description": description}, headers=headers, timeout=300)
        if res.status_code not in (429, 500, 502, 503) or wait is None:
            break
        time.sleep(wait)
    seconds = round(time.monotonic() - start, 1)
    if res.status_code != 200:
        return {"error": f"{res.status_code} {res.text[:200]}", "seconds": seconds}
    answer = res.json()
    return {"svg": answer["svg"], "seconds": seconds, "credits": answer["usage"]["credits"]}


def draw_local(description: str) -> dict:
    """This checkout's figure, drawn by the AI of the app's settings: its SVG, seconds, how it
    was drawn (its family, its Typst); or its error."""
    from app import settings

    start = time.monotonic()
    try:
        made = asyncio.run(figure_making.made_figure(settings.current(), description))
    except Exception as e:
        return {"error": f"{type(e).__name__}: {str(e)[:200]}", "seconds": round(time.monotonic() - start, 1)}
    seconds = round(time.monotonic() - start, 1)
    return {"svg": made.svg, "seconds": seconds, "engine": made.engine, "family": made.family, "typst": made.typst}


def recompiled(run: Path, drawing: dict) -> dict:
    """A drawing of an earlier run: its Typst compiled again with this checkout's preambles;
    drawn as SVG, as it was."""
    family = drawing.get("family", "")
    if drawing.get("typst_file"):
        body = (run / drawing["typst_file"]).read_text()
        try:
            svg = figures.clean(figures_typst.compile_svg(family, body))
        except Exception as e:
            return {"error": f"{type(e).__name__}: {str(e)[:200]}", "family": family, "typst": body}
        return {"svg": svg, "seconds": 0, "engine": "typst", "family": family, "typst": body}
    if drawing.get("file"):
        return {"svg": (run / drawing["file"]).read_text(), "seconds": 0, "engine": "svg", "family": family}
    return {"error": drawing.get("problem", "not drawn")}


def _local(tag: object) -> str:
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def _labels(element: ElementTree.Element, parent: ElementTree.Element | None = None):
    """The figure's labels, each with its parent: a <text>, or a run of Typst's letters (a
    group of <use> only)."""
    tag = _local(element.tag)
    if tag in NOT_DRAWN:
        return
    if parent is not None and (
        tag == "text" or (tag == "g" and len(element) and all(_local(c.tag) == "use" for c in element))
    ):
        yield element, parent
        return
    for child in element:
        yield from _labels(child, element)


def hidden_labels(svg: str, png: bytes) -> int:
    """How many of a figure's labels can't be seen (`png`: the figure seen): taken out, not a
    pixel changes (under a filled shape drawn after it, or outside the picture)."""
    root = ElementTree.fromstring(svg)
    hidden = 0
    for label, parent in list(_labels(root)):
        at = list(parent).index(label)
        parent.remove(label)
        hidden += figures.to_png(ElementTree.tostring(root, encoding="unicode")) == png
        parent.insert(at, label)
    return hidden


def by_code(svg: str) -> tuple[bool, str, bytes | None]:
    """Right by what code can see: it renders, its drawing fills the picture (not a speck in
    a corner), it has text when it has labels to show, none of them hidden."""
    from PIL import Image as Picture

    png = figures.to_png(svg)
    if png is None:
        return False, "doesn't render", None
    grey = Picture.open(io.BytesIO(png)).convert("L")
    box = grey.point(lambda v: 255 if v < 200 else 0).getbbox()
    if box is None:
        return False, "empty", png
    width, height = (box[2] - box[0]) / grey.width, (box[3] - box[1]) / grey.height
    if max(width, height) < FILLS:
        return False, f"too small ({max(width, height):.0%} of the picture)", png
    hidden = hidden_labels(svg, png)
    if hidden:
        return False, f"{hidden} label(s) hidden (under a shape, or outside the picture)", png
    return True, "", png


async def by_ai(judge: AIConfig, description: str, png: bytes) -> tuple[bool, str]:
    """The AI looking at it, with its thinking: the light check's rules, stricter."""
    checked = await ai._ask_provider(
        judge, [Image(png, "image/png")], f"Description: {description}", figures.Checked, figures.CHECK_RULES
    )
    return checked.ok, checked.problem.strip()


def judged(judge: AIConfig | None, description: str, drawn: dict) -> dict:
    """The verdicts of one drawing, added to it (its PNG apart, for the sheet)."""
    if "error" in drawn:
        return {**drawn, "right": False, "problem": drawn["error"]}
    ok, problem, png = by_code(drawn["svg"])
    verdict = {**drawn, "code": ok, "png": png}
    if ok and judge:
        try:
            ok, problem = asyncio.run(by_ai(judge, description, png))  # pyright: ignore[reportArgumentType]
            verdict["ai"] = ok
        except Exception as e:  # the judge failing: said, the figure not counted either way
            ok, problem = None, f"not judged: {type(e).__name__}"
    return {**verdict, "right": ok, "problem": problem}


def sheet(path: Path, rows: list[tuple[str, str, list[dict]]]) -> None:
    """Every figure to look at: its case, then its drawings with their verdicts."""
    parts = []
    for title, description, drawings in rows:
        cells = []
        for n, d in enumerate(drawings, 1):
            mark = "✓" if d.get("right") else "?" if d.get("right") is None else "✗"
            image = f'<img src="{d["file"]}">' if d.get("file") else ""
            how = d.get("family") or d.get("engine", "")
            facts = f"{how} · {d.get('seconds', '?')} s · {d.get('credits', '?')} cr."
            problem = html.escape(d.get("problem", ""))
            cells.append(f"<figure>{image}<figcaption>{mark} #{n} · {facts}<br>{problem}</figcaption></figure>")
        parts.append(
            f"<section><h2>{html.escape(title)}</h2><p>{html.escape(description)}</p>{''.join(cells)}</section>"
        )
    style = (
        "body{font:14px sans-serif;margin:16px;max-width:1100px}section{margin-bottom:24px}"
        "figure{display:inline-block;width:250px;margin:4px;vertical-align:top}"
        "img{width:250px;height:190px;object-fit:contain;border:1px solid #ddd;background:#fff}"
        "figcaption{font-size:12px;color:#444}h2{margin:8px 0 2px;font-size:16px}p{margin:0 0 6px;color:#666}"
    )
    path.write_text(f"<!doctype html><meta charset=utf-8><title>Figures</title><style>{style}</style>{''.join(parts)}")


def judge_config() -> AIConfig | None:
    project = os.environ.get("BENCH_JUDGE_PROJECT", "")
    if not project:
        return None
    return AIConfig(llm="gemini", gemini_vertex_project=project, gemini_vertex_location="global")


def summary(drawings: list[dict]) -> dict:
    seconds = [d["seconds"] for d in drawings if "seconds" in d]
    credits = [d["credits"] for d in drawings if "credits" in d]
    return {
        "right": sum(d.get("right") is True for d in drawings),
        "judged": sum(d.get("right") is not None for d in drawings),
        "median_s": round(statistics.median(seconds), 1) if seconds else None,
        "credits": round(statistics.mean(credits), 1) if credits else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--bench", default=str(ROOT / "notes/bench"))
    parser.add_argument("--only", default="", help="cases whose id holds this")
    parser.add_argument("--times", type=int, default=3, help="drawings of each case")
    parser.add_argument("--jobs", type=int, default=3)
    parser.add_argument("--cases", default="", help="the cases' file (<bench>/figures.json by default)")
    parser.add_argument("--local", action="store_true", help="drawn here, by the app's AI, not by the relay")
    parser.add_argument("--app", default=str(ROOT), help="--local: the checkout whose data/ and .env give the AI")
    parser.add_argument("--recompile", default="", help="a run whose Typst is compiled again, not drawn")
    args = parser.parse_args()
    bench = Path(args.bench)
    judge = judge_config()
    at = datetime.now().isoformat(timespec="seconds").replace(":", "-")
    if args.recompile:
        old = Path(args.recompile)
        before = json.loads((old / "run.json").read_text())
        descriptions = before.get("descriptions", {})
        cases = [{"id": i, "description": descriptions.get(i, "")} for i in before["cases"] if args.only in i]
        jobs = [(c, n, d) for c in cases for n, d in enumerate(before["cases"][c["id"]], 1)]
        drawing = lambda case, d: recompiled(old, d)  # noqa: E731
        where = f"compiled again from {old}"
    else:
        listed = Path(args.cases) if args.cases else bench / "figures.json"
        cases = [c for c in json.loads(listed.read_text()) if args.only in c["id"]]
        jobs = [(c, n, {}) for c in cases for n in range(1, args.times + 1)]
        if args.local:
            from dotenv import load_dotenv

            app = Path(args.app).expanduser()
            load_dotenv(app / ".env")
            os.environ.setdefault("NOTOSAURUS_DATA", str(app / "data"))
            drawing = lambda case, d: draw_local(case["description"])  # noqa: E731
            where = "drawn here"
        else:
            url, key = relay()
            drawing = lambda case, d: draw(url, key, case["description"])  # noqa: E731
            where = f"drawn on {url}"
    out = bench / "runs" / f"{at}-figures"
    out.mkdir(parents=True)
    print(f"{len(cases)} cases, {len(jobs)} figures {where}, judged by {'the AI and ' if judge else ''}code…")

    def one(job: tuple[dict, int, dict]) -> tuple[str, dict]:
        case, n, earlier = job
        verdict = judged(judge, case["description"], drawing(case, earlier))
        if "svg" in verdict:
            name = f"{case['id']}-{n}.svg"
            (out / name).write_text(verdict.pop("svg"))
            verdict["file"] = name
        if verdict.get("typst"):
            name = f"{case['id']}-{n}.typ"
            (out / name).write_text(verdict.pop("typst"))
            verdict["typst_file"] = name
        verdict.pop("typst", None)
        verdict.pop("png", None)
        return case["id"], verdict

    with ThreadPoolExecutor(args.jobs) as pool:
        done = list(pool.map(one, jobs))
    run = {
        "at": at,
        "descriptions": {c["id"]: c["description"] for c in cases},
        "cases": {c["id"]: [v for i, v in done if i == c["id"]] for c in cases},
    }
    sheet(out / "sheet.html", [(c["id"], c["description"], run["cases"][c["id"]]) for c in cases])
    (out / "run.json").write_text(json.dumps(run, ensure_ascii=False, indent=1))

    everything = [d for drawings in run["cases"].values() for d in drawings]
    for case in cases:
        s = summary(run["cases"][case["id"]])
        wrong = [d["problem"] for d in run["cases"][case["id"]] if d.get("right") is False]
        mark = "✗" if wrong else "✓"
        print(f"{mark} {case['id']}: {s['right']}/{s['judged']} right, {s['median_s']} s, {s['credits']} cr.")
        for problem in wrong:
            print(f"   ✗ {problem}")
    total = summary(everything)
    print(
        f"\n{total['right']}/{total['judged']} figures right, median {total['median_s']} s, {total['credits']} credits "
        f"each. The sheet: {out / 'sheet.html'}"
    )
    previous = sorted(p for p in (bench / "runs").glob("*-figures/run.json") if p.parent != out)
    if previous:
        before = json.loads(previous[-1].read_text())["cases"]
        was = summary([d for drawings in before.values() for d in drawings])
        print(
            f"Before ({previous[-1].parent.name}): {was['right']}/{was['judged']} right, median {was['median_s']} s, "
            f"{was['credits']} credits"
        )
    return 0 if total["right"] == total["judged"] else 1


if __name__ == "__main__":
    sys.exit(main())
