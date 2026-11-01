"""What each lesson's AI calls used and cost."""

import asyncio
import json
import types

import pytest
from conftest import ADMIN, PRICES

from notosaurus_core import prices
from notosaurus_core.providers import openai_like


def usd(model, input_tokens, output_tokens):
    """The expected price of a call, from the list conftest serves (per token)."""
    input_price, output_price = (float(v) for v in PRICES[model])
    return input_tokens * input_price + output_tokens * output_price


def test_fake_calls_kept_with_the_lesson(client):
    files = [("images", ("p.png", b"img", "image/png"))]
    lesson = client.post("/api/extract", files=files, data={"prompt": "FR → ES"}).json()
    assert [(c["kind"], c["provider"], c["cost"]) for c in lesson["ai_calls"]] == [("extract", "fake", 0.0)]
    body = {"deck": lesson["deck"], "cards": lesson["cards"], "instruction": "add the colours"}
    client.post(f"/api/lessons/{lesson['id']}/revise", json=body)
    client.post(f"/api/lessons/{lesson['id']}/revise", json=body)
    saved = client.get(f"/api/lessons/{lesson['id']}").json()
    assert [c["kind"] for c in saved["ai_calls"]] == ["extract", "revise", "revise"]
    # An edit afterwards keeps them
    client.put(f"/api/lessons/{lesson['id']}", json={"deck": "D", "cards": []})
    assert len(client.get("/api/lessons").json()[0]["ai_calls"]) == 3


@pytest.mark.parametrize(
    ("provider", "model", "cost"),
    [
        ("openai", "gpt-6.1-sol", usd("openai/gpt-6.1-sol", 1000, 100)),
        ("gemini", "gemini-3.8-flash", usd("google/gemini-3.8-flash", 1000, 100)),
        ("anthropic", "claude-sonnet-4-6", usd("anthropic/claude-sonnet-4.6", 1000, 100)),  # as OpenRouter lists it
        ("openai", "google/gemini-3.8-flash", usd("google/gemini-3.8-flash", 1000, 100)),  # an OpenRouter id
        ("anthropic", "claude-unknown", None),
        # OpenAI's image models aren't in OpenRouter's list: Notosaurus's own prices
        ("openai", "gpt-image-2", 1000 * 8e-6 + 100 * 30e-6),
        ("openai", "gpt-image-2-2026-04-21", 1000 * 8e-6 + 100 * 30e-6),  # a dated version: its model's
    ],
)
def test_estimated_cost(client, provider, model, cost):
    estimate = asyncio.run(prices.estimate(provider, model, 1000, 100))
    assert estimate == (pytest.approx(cost) if cost is not None else None)


def test_a_drawn_pictures_tokens_at_the_images_price(client):
    """An image model's output: its text at the text's price, its picture at the image's
    (20 times more: a picture would else cost a twentieth of its price)."""
    estimate = asyncio.run(prices.estimate("gemini", "gemini-3.1-flash-image", 20, 1300, image_tokens=1290))
    assert estimate == pytest.approx(20 * 0.5e-6 + 10 * 3e-6 + 1290 * 60e-6)
    # OpenAI's image models (Notosaurus's own prices): the output's
    assert asyncio.run(prices.estimate("openai", "gpt-image-2", 1000, 100, image_tokens=100)) == pytest.approx(
        1000 * 8e-6 + 100 * 30e-6
    )


def test_prices_fetched_once_a_day(client, monkeypatch):
    asyncio.run(prices.estimate("openai", "gpt-6.1-sol", 1, 1))
    monkeypatch.setattr(prices, "_transport", None)  # the network would now be used: the cache must answer
    assert asyncio.run(prices.estimate("openai", "gpt-6.1-sol", 1000, 0)) == pytest.approx(
        usd("openai/gpt-6.1-sol", 1000, 0)
    )


def fake_completion(cost=None, model="google/gemini-3.8-flash", content=None):
    usage = types.SimpleNamespace(prompt_tokens=2000, completion_tokens=300, model_extra={"cost": cost} if cost else {})
    content = content or json.dumps({"deck": "D", "cards": [{"front": "a", "back": "b"}]})
    message = types.SimpleNamespace(content=content)
    response = types.SimpleNamespace(usage=usage, model=model, choices=[types.SimpleNamespace(message=message)])

    class Completions:
        async def create(self, **kwargs):
            Completions.kwargs = kwargs
            return response

    return types.SimpleNamespace(chat=types.SimpleNamespace(completions=Completions())), Completions


def test_openrouter_gives_the_exact_cost(client, monkeypatch):
    monkeypatch.setenv("NOTOSAURUS_LLM", "openrouter")
    monkeypatch.setenv("NOTOSAURUS_MODEL", "google/gemini-3.8-flash")
    fake, completions = fake_completion(cost=0.0123)
    monkeypatch.setattr(openai_like, "_openai_client", lambda s: fake)
    lesson = client.post("/api/extract", data={"prompt": "words: le chat"}).json()
    (call,) = lesson["ai_calls"]
    assert call | {"at": None} == {
        "at": None,
        "kind": "extract",
        "provider": "openrouter.ai",
        "model": "google/gemini-3.8-flash",
        "input_tokens": 2000,
        "output_tokens": 300,
        "cost": 0.0123,
        "exact": True,
    }
    assert completions.kwargs["extra_body"] == {"usage": {"include": True}}  # asked for the cost


def test_claude_through_openrouter_asked_its_own_schema(client, monkeypatch):
    """Claude through OpenRouter: the card's schema within Claude's limit (CLAUDE_REQUIRED
    required), as with Anthropic's API."""
    monkeypatch.setenv("NOTOSAURUS_LLM", "openrouter")
    monkeypatch.setenv("NOTOSAURUS_MODEL", "anthropic/claude-sonnet-5.5")
    fake, completions = fake_completion(cost=0.01)
    monkeypatch.setattr(openai_like, "_openai_client", lambda s: fake)
    assert client.post("/api/extract", data={"prompt": "words: le chat"}).status_code == 201
    card = completions.kwargs["response_format"]["json_schema"]["schema"]["$defs"]["Card"]
    assert {"subdeck", "info", "figure", "picture_search", "picture_on_back"} <= set(card["required"])


def test_an_error_inside_a_200_said_not_crashed(client, monkeypatch):
    """OpenRouter answering 200 with an error and no choices (the model failed behind it):
    the service's message, not an internal error."""
    monkeypatch.setenv("NOTOSAURUS_LLM", "openrouter")
    monkeypatch.setenv("NOTOSAURUS_MODEL", "anthropic/claude-sonnet-5.5")
    fake, _ = fake_completion()
    failed = types.SimpleNamespace(
        usage=None, model=None, choices=None, model_extra={"error": {"message": "Schema is too complex.", "code": 400}}
    )

    async def create(**kwargs):
        return failed

    fake.chat.completions.create = create
    monkeypatch.setattr(openai_like, "_openai_client", lambda s: fake)
    res = client.post("/api/extract", data={"prompt": "words: le chat"})
    assert res.status_code == 502
    assert res.json()["detail"]["code"] == "llm.api_error"
    assert res.json()["detail"]["params"]["detail"] == "Schema is too complex."


def test_other_services_get_an_estimate(client, monkeypatch):
    monkeypatch.setenv("NOTOSAURUS_LLM", "openai")
    monkeypatch.setenv("NOTOSAURUS_MODEL", "gpt-6.1-sol")
    fake, completions = fake_completion(model="gpt-6.1-sol")
    monkeypatch.setattr(openai_like, "_openai_client", lambda s: fake)
    (call,) = client.post("/api/extract", data={"prompt": "words: le chat"}).json()["ai_calls"]
    assert (call["cost"], call["exact"]) == (pytest.approx(2000 * 0.000002 + 300 * 0.00001), False)
    assert completions.kwargs["extra_body"] is None


def test_deleting_a_lesson_keeps_what_was_spent(admin, monkeypatch, tmp_path):

    monkeypatch.setenv("NOTOSAURUS_LLM", "openrouter")
    monkeypatch.setenv("NOTOSAURUS_MODEL", "google/gemini-3.8-flash")
    fake, _ = fake_completion(cost=0.01)
    monkeypatch.setattr(openai_like, "_openai_client", lambda s: fake)
    first = admin.post("/api/extract", data={"prompt": "words: le chat"}).json()
    admin.post("/api/extract", data={"prompt": "words: le chien"})

    def costs():
        return admin.get("/api/admin/lessons", headers=ADMIN).json()["costs"]

    assert costs() == {"total": 0.02, "deleted": 0.0, "failed": 0.0, "estimated": False, "unknown": 0}
    admin.delete(f"/api/lessons/{first['id']}")
    assert costs() == {"total": 0.02, "deleted": 0.01, "failed": 0.0, "estimated": False, "unknown": 0}

    # Answered, but unusable: paid for, no lesson
    broken, _ = fake_completion(cost=0.005, content="not json")
    monkeypatch.setattr(openai_like, "_openai_client", lambda s: broken)
    assert admin.post("/api/extract", data={"prompt": "words"}).status_code == 502
    assert (costs()["total"], costs()["failed"]) == (0.025, 0.005)
    journal = json.loads((tmp_path / "data" / "ai-calls.json").read_text(encoding="utf-8"))["calls"]
    assert [e["lesson_id"] is None for e in journal] == [False, False, True]


def test_journal_starts_from_the_lessons(client, tmp_path):
    files = [("images", ("p.png", b"img", "image/png"))]
    lesson = client.post("/api/extract", files=files, data={"prompt": "FR → ES"}).json()
    journal = tmp_path / "data" / "ai-calls.json"
    journal.unlink()  # as before this version: the calls are only in the lessons
    from app import usage

    assert usage.totals().total == 0.0  # fake calls cost nothing, but they are back in the journal
    assert len(json.loads(journal.read_text(encoding="utf-8"))["calls"]) == 1
    body = {"deck": lesson["deck"], "cards": lesson["cards"], "instruction": "x"}
    client.post(f"/api/lessons/{lesson['id']}/revise", json=body)
    entries = json.loads(journal.read_text(encoding="utf-8"))["calls"]
    assert [e["kind"] for e in entries] == ["extract", "revise"]  # no duplicate


async def _answered(cost: float) -> None:
    """An AI call answered (and paid for) inside the current recording."""
    from notosaurus_core.calls import record
    from notosaurus_core.config import AIConfig

    await record(AIConfig(llm="fake"), "fake", "m", 10, 5, cost=cost)


def test_metered_calls_go_to_the_lesson_and_the_costs(client, tmp_path):
    from app import lessons, usage
    from app.errors import AppError
    from app.models import Generated, LessonIn

    lesson = lessons.create(Generated(LessonIn(deck="D", cards=[]), [], prompt="p"))

    async def calls():
        async with usage.metered("revise", lesson.id, "D"):
            await _answered(0.01)
        # An error after the AI answered: paid for, kept all the same
        with pytest.raises(AppError):
            async with usage.metered("explain", lesson.id, "D"):
                await _answered(0.02)
                raise AppError("llm.bad_answer", 502)
        async with usage.metered("rephrase"):  # for no lesson
            await _answered(0.03)

    asyncio.run(calls())
    assert [c.kind for c in lessons.get(lesson.id).ai_calls] == ["revise", "explain"]
    journal = json.loads((tmp_path / "data" / "ai-calls.json").read_text(encoding="utf-8"))["calls"]
    assert [(e["kind"], e["lesson_id"], e["deck"]) for e in journal] == [
        ("revise", lesson.id, "D"),
        ("explain", lesson.id, "D"),
        ("rephrase", None, ""),
    ]


def test_metered_calls_kept_by_a_new_lesson_counted_once(client, tmp_path):
    from app import lessons, usage
    from app.models import Generated, LessonIn

    async def made_with_its_calls():
        async with usage.metered("extract") as meter:
            await _answered(0.01)
            made = lessons.create(Generated(LessonIn(deck="D", cards=[]), [], prompt="p"), meter.calls)
            meter.kept_by(made)
        return made

    made = asyncio.run(made_with_its_calls())
    assert len(lessons.get(made.id).ai_calls) == 1  # not added a second time
    journal = json.loads((tmp_path / "data" / "ai-calls.json").read_text(encoding="utf-8"))["calls"]
    assert [(e["lesson_id"], e["deck"]) for e in journal] == [(made.id, "D")]

    # Failed before a lesson kept them: counted with none (a generation that failed)
    async def failed():
        async with usage.metered("extract"):
            await _answered(0.02)
            raise RuntimeError("disk full")

    with pytest.raises(RuntimeError):
        asyncio.run(failed())
    assert usage.totals().failed == 0.02


def test_the_relays_models_estimated_without_openrouters_list(client, monkeypatch, tmp_path):
    """OpenRouter's list unreachable: the relay's models still estimated (Notosaurus's own
    prices, not a flat price), and the list not asked again at every call meanwhile."""
    import httpx

    from notosaurus_core import files

    asked = []

    def unreachable(request):
        asked.append(request.url.path)
        raise httpx.ConnectError("down")

    monkeypatch.setattr(files, "_cache_root", lambda: tmp_path / "cache")  # nothing cached
    monkeypatch.setattr(prices, "_transport", httpx.MockTransport(unreachable))
    monkeypatch.setattr(prices, "_failed_at", 0.0)
    text = asyncio.run(prices.estimate("gemini", "gemini-3.8-flash", 1000, 100))
    assert text == pytest.approx(1000 * 0.825e-6 + 100 * 4.125e-6, abs=1e-6)  # (to the micro-dollar)
    figure = asyncio.run(prices.estimate("gemini", "gemini-3.1-flash-image", 20, 1300, image_tokens=1290))
    assert figure == pytest.approx(20 * 0.5e-6 + 10 * 3e-6 + 1290 * 60e-6, abs=1e-6)
    assert asked == ["/api/v1/models"]  # once: the failure remembered
