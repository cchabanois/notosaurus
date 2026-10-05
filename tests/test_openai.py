"""The OpenAI-like services: what the request asks of the model."""

from test_costs import fake_completion

from notosaurus_core import llm
from notosaurus_core.llm import ai_schema
from notosaurus_core.models import Extraction


def test_openai_models_get_a_strict_schema():
    """GPT refuses a response schema that isn't strict: every object closed, every
    property required."""
    strict = llm._strict(ai_schema(Extraction).model_json_schema())

    def objects(node):
        if isinstance(node, dict):
            if "properties" in node:
                yield node
            for value in node.values():
                yield from objects(value)
        elif isinstance(node, list):
            for value in node:
                yield from objects(value)

    found = list(objects(strict))
    assert len(found) >= 4  # the extraction, its cards, masks, text lines…
    assert all(o["additionalProperties"] is False and set(o["required"]) == set(o["properties"]) for o in found)


def test_only_openai_models_are_sent_it(client, monkeypatch):
    sent = {}
    for model, strict in (
        ("~openai/gpt-mini-latest", True),
        ("openai/gpt-6-luna", True),
        ("~google/gemini-flash-latest", False),
        ("~anthropic/claude-sonnet-latest", False),
    ):
        monkeypatch.setenv("NOTOSAURUS_LLM", "openrouter")
        monkeypatch.setenv("NOTOSAURUS_MODEL", model)
        fake, completions = fake_completion(model=model)
        monkeypatch.setattr(llm, "_openai_client", lambda s, fake=fake: fake)
        assert client.post("/api/extract", data={"prompt": "words: le chat"}).status_code == 201
        sent[model] = completions.kwargs["response_format"]["json_schema"].get("strict", False)
        assert sent[model] is strict, model
    monkeypatch.setenv("NOTOSAURUS_LLM", "openai")  # an OpenAI key: strict too
    monkeypatch.setenv("NOTOSAURUS_MODEL", "gpt-6.1-sol")
    fake, completions = fake_completion(model="gpt-6.1-sol")
    monkeypatch.setattr(llm, "_openai_client", lambda s: fake)
    client.post("/api/extract", data={"prompt": "words: le chat"})
    assert completions.kwargs["response_format"]["json_schema"]["strict"] is True
