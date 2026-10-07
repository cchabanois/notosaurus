"""The cards as the AI writes them: read from the streamed answer, sent to the page one
JSON per line, then the lesson (or the error)."""

import asyncio
import json
import types as py_types
from concurrent.futures import ThreadPoolExecutor

from google.genai import errors, types

from notosaurus_core import llm
from notosaurus_core.config import AIConfig
from notosaurus_core.llm import CardStream

NDJSON = {"Accept": "application/x-ndjson"}


def run(coroutine):
    """asyncio.run, in a thread of its own (after the page tests, Playwright's loop runs here)."""
    with ThreadPoolExecutor(1) as pool:
        return pool.submit(asyncio.run, coroutine).result()


def test_cards_read_as_they_come():
    answer = '{\n "cards": [\n  {"front": "a \\"b\\" {x}", "back": "c"},\n  {"front": "d", "choices": ["}", "{"]},\n'
    answer += '  {"front": "e", "back": "f"}\n ],\n "deck": "D"\n}'
    stream, cards, seen = CardStream(), [], []
    for i in range(0, len(answer), 5):  # in small pieces, cut anywhere
        new = stream.feed(answer[i : i + 5])
        cards += new
        seen.append(len(cards))
    assert cards == [
        {"front": 'a "b" {x}', "back": "c"},
        {"front": "d", "choices": ["}", "{"]},
        {"front": "e", "back": "f"},
    ]
    assert seen[0] == 0 and seen.index(1) < seen.index(2) < seen.index(3)  # one by one, before the end


class StreamingGemini:
    """A Gemini writing its answer in pieces; `fail_first`: the first model overloaded halfway."""

    def __init__(self, answer, fail_first=False):
        self.answer, self.fail_first, self.models = answer, fail_first, []
        self.aio = py_types.SimpleNamespace(models=py_types.SimpleNamespace(generate_content_stream=self.stream))

    async def stream(self, model, contents, config):
        self.models.append(model)
        failing = self.fail_first and len(self.models) == 1

        async def chunks():
            pieces = [self.answer[i : i + 20] for i in range(0, len(self.answer), 20)]
            for n, text in enumerate(pieces):
                if failing and n == len(pieces) // 2:
                    raise errors.ServerError(
                        503, {"error": {"code": 503, "message": "overloaded", "status": "UNAVAILABLE"}}
                    )
                last = n == len(pieces) - 1
                candidate = py_types.SimpleNamespace(finish_reason=types.FinishReason.STOP if last else None)
                usage = py_types.SimpleNamespace(
                    prompt_token_count=100, candidates_token_count=50, thoughts_token_count=0
                )
                yield py_types.SimpleNamespace(
                    text=text, candidates=[candidate], usage_metadata=usage if last else None, prompt_feedback=None
                )

        return chunks()


def test_gemini_tells_each_card_and_starts_again_with_the_next_model(monkeypatch):
    answer = json.dumps(
        {"cards": [{"front": "la mère", "back": "la madre"}, {"front": "le père", "back": "el padre"}], "deck": "D"}
    )
    fake = StreamingGemini(answer, fail_first=True)
    monkeypatch.setattr(llm, "_gemini_client", lambda s: fake)
    told = []

    async def on_card(card):
        told.append(card)

    s = AIConfig(gemini_api_key="k", model="gemini-x", fallback_models="gemini-y")
    found = run(llm.extract_cards(s, [], "FR → ES", on_card=on_card))
    assert fake.models == ["gemini-x", "gemini-y"]
    assert told == [told[0], None, {"front": "la mère", "back": "la madre"}, {"front": "le père", "back": "el padre"}]
    assert [c.back for c in found.deck.cards] == ["la madre", "el padre"]


def lines(res) -> list[dict]:
    assert res.headers["content-type"].startswith("application/x-ndjson")
    return [json.loads(line) for line in res.text.splitlines() if line.strip()]


def test_the_page_gets_the_cards_then_the_lesson(client):
    res = client.post("/api/extract", data={"prompt": "FR → ES"}, headers=NDJSON)
    items = lines(res)
    cards, last = items[:-1], items[-1]
    assert cards and all("card" in i for i in cards)
    assert [i["card"]["front"] for i in cards] == [c["front"] for c in last["lesson"]["cards"]]
    assert client.get(f"/api/lessons/{last['lesson']['id']}").status_code == 200  # saved

    # Generated again in its place, streamed too
    again = lines(
        client.post(f"/api/lessons/{last['lesson']['id']}/regenerate", data={"prompt": "FR → ES"}, headers=NDJSON)
    )
    assert again[-1]["lesson"]["id"] == last["lesson"]["id"] and len(client.get("/api/lessons").json()) == 1

    # Without asking for it: the lesson at once, as before
    plain = client.post("/api/extract", data={"prompt": "FR → ES"})
    assert plain.status_code == 201 and plain.json()["cards"]


def test_an_error_is_the_last_line(client):
    (item,) = lines(client.post("/api/extract", data={"prompt": " "}, headers=NDJSON))
    assert item == {"error": {"code": "extract.no_input", "params": {}}}
