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
