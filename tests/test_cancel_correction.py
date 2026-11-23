""" "Cancel" while the AI corrects: the lesson's correction or a card's stops where it is, as a
lesson being made does (common.jobs, /api/generations/{job}/cancel); nothing changes."""

import asyncio
import threading

from conftest import extract_lesson
from test_streaming import NDJSON, lines


def _held(monkeypatch, name: str):
    """The AI's call `name` (app.routes.lessons') held until cancelled: (started, stopped)."""
    from app.routes import lessons as routes

    started, stopped = threading.Event(), []

    async def held(*_, **__):
        started.set()
        try:
            await asyncio.sleep(30)  # the AI writing
        except asyncio.CancelledError:
            stopped.append(True)
            raise

    monkeypatch.setattr(routes if name == "revise_cards" else routes.llm, name, held)
    return started, stopped


def _cancelled_while(client, started, path: str, **asked):
    """`path` asked in a thread, cancelled ("r1") once the AI started: its answer."""
    answer = {}
    thread = threading.Thread(target=lambda: answer.update(res=client.post(f"{path}?job=r1", **asked)))
    thread.start()
    assert started.wait(5)
    assert client.post("/api/generations/r1/cancel").json() == {"cancelled": True}
    thread.join(5)
    return answer["res"]


def test_a_lesson_corrected_cancelled(client, monkeypatch):
    lesson = extract_lesson(client)
    body = {"deck": lesson["deck"], "cards": lesson["cards"], "instruction": "supprime la dernière carte"}
    for headers in (NDJSON, {}):
        started, stopped = _held(monkeypatch, "revise_cards")
        res = _cancelled_while(client, started, f"/api/lessons/{lesson['id']}/revise", json=body, headers=headers)
        if headers:  # as the page asks: told in the stream
            assert lines(res) == [{"cancelled": True}]
        else:  # all at once: 409, as a lesson being made
            assert (res.status_code, res.json()["detail"]["code"]) == (409, "extract.cancelled")
        assert stopped == [True]
        assert client.get(f"/api/lessons/{lesson['id']}").json()["cards"] == lesson["cards"]  # nothing changed
    assert client.post("/api/generations/r1/cancel").json() == {"cancelled": False}  # done: nothing to cancel


def test_a_card_corrected_cancelled(client, monkeypatch):
    lesson = extract_lesson(client)
    started, stopped = _held(monkeypatch, "fix_card")
    body = {"card": lesson["cards"][0], "instruction": "la réponse est 1789", "others": []}
    res = _cancelled_while(client, started, f"/api/lessons/{lesson['id']}/fix-card", json=body)
    assert (res.status_code, res.json()["detail"]["code"]) == (409, "extract.cancelled")
    assert stopped == [True]


def test_a_card_corrected_seeing_its_figure(client, monkeypatch):
    """A card with a figure corrected: its drawing (the SVG in the lesson's images) given to
    the AI, a request about it understood; a card without one: none."""
    from app import lessons
    from app.routes import lessons as routes
    from notosaurus_core import llm

    lesson = extract_lesson(client)
    name, folder = "picture-c1-0123abcd.svg", lessons.folder(lesson["id"])
    assert folder is not None
    (folder / "images").mkdir(exist_ok=True)
    (folder / "images" / name).write_text("<svg>drawn</svg>", encoding="utf-8")
    seen = []

    async def fix(*args, figure_svg="", **kwargs):
        seen.append(figure_svg)
        return llm.FixedCard(card=args[4], summary="ok")

    monkeypatch.setattr(routes.llm, "fix_card", fix)
    card = {**lesson["cards"][0], "figure": "Triangle ABC", "picture": name}
    for asked in (card, lesson["cards"][1]):
        res = client.post(f"/api/lessons/{lesson['id']}/fix-card", json={"card": asked, "instruction": "E à droite"})
        assert res.status_code == 200
    assert seen == ["<svg>drawn</svg>", ""]


def test_corrections_asked_quick_by_the_page(client, monkeypatch):
    """The page's "Quick" passed on to the AI, for a lesson's correction and a card's."""
    from app.routes import lessons as routes
    from notosaurus_core import llm
    from notosaurus_core.models import Revision

    lesson = extract_lesson(client)
    asked = []

    async def fix(*args, quick=False, **kwargs):
        asked.append(("fix", quick))
        return llm.FixedCard(card=args[4], summary="ok")

    async def revise(*args, quick=False, **kwargs):
        asked.append(("revise", quick))
        return Revision(deck=args[3].deck, cards=args[3].cards, summary="ok")

    monkeypatch.setattr(routes.llm, "fix_card", fix)
    monkeypatch.setattr(routes, "revise_cards", revise)
    for quick in (True, False):
        fixed = {"card": lesson["cards"][0], "instruction": "x", "quick": quick}
        assert client.post(f"/api/lessons/{lesson['id']}/fix-card", json=fixed).status_code == 200
        revised = {"deck": lesson["deck"], "cards": lesson["cards"], "instruction": "x", "quick": quick}
        assert client.post(f"/api/lessons/{lesson['id']}/revise", json=revised).status_code == 200
    assert asked == [("fix", True), ("revise", True), ("fix", False), ("revise", False)]


def test_a_correction_cancelled_while_it_is_saved_answers_what_is_saved(client, monkeypatch):
    """A "Cancel" landing while the corrected lesson is being saved: the save goes on (a thread),
    so the page is given the lesson as saved, not "cancelled" over the old cards it would keep
    (a reload showing the correction, the next save writing over it)."""
    from app import lessons
    from app.routes import lessons as routes
    from notosaurus_core.models import Revision

    lesson = extract_lesson(client)
    kept = lesson["cards"][:1]

    async def revise(*args, **kwargs):
        return Revision(deck=args[3].deck, cards=kept, summary="une carte")

    monkeypatch.setattr(routes, "revise_cards", revise)
    update = lessons.update
    for headers in (NDJSON, {}):
        saving, go = threading.Event(), threading.Event()

        def slow(*args, saving=saving, go=go, **kwargs):
            saving.set()
            assert go.wait(5)
            return update(*args, **kwargs)

        monkeypatch.setattr(lessons, "update", slow)
        body = {"deck": lesson["deck"], "cards": lesson["cards"], "instruction": "garde la première carte"}
        answer = {}
        thread = threading.Thread(
            target=lambda body=body, headers=headers, answer=answer: answer.update(
                res=client.post(f"/api/lessons/{lesson['id']}/revise?job=r1", json=body, headers=headers)
            )
        )
        thread.start()
        assert saving.wait(5)
        client.post("/api/generations/r1/cancel")
        go.set()
        thread.join(5)
        res = answer["res"]
        assert res.status_code == 200
        said = lines(res)[-1]["result"] if headers else res.json()
        assert [c["front"] for c in said["lesson"]["cards"]] == [kept[0]["front"]]
        assert client.get(f"/api/lessons/{lesson['id']}").json()["cards"] == said["lesson"]["cards"]
