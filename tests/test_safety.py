"""What the AI makes is for pupils: the rules in every system prompt, the AI's own
refusal, Gemini's stricter filters and their blocks, OpenAI's refusals: llm.refused."""

import asyncio
import json
import types as py_types
from concurrent.futures import ThreadPoolExecutor

import pytest
from google.genai import types

from notosaurus_core import figures, llm, prompts
from notosaurus_core.config import AIConfig
from notosaurus_core.errors import AppError
from notosaurus_core.models import Deck
from notosaurus_core.providers import gemini, openai_like

GEMINI = AIConfig(llm="gemini", gemini_api_key="k")


def run(coroutine):
    """asyncio.run, in a thread of its own: after the page tests, Playwright's loop runs
    in this one."""
    with ThreadPoolExecutor(1) as pool:
        return pool.submit(asyncio.run, coroutine).result()


class FakeGemini:
    """A Gemini answering `text`, stopped for `finish_reason`; it keeps the configs it got."""

    def __init__(self, text="", finish_reason=types.FinishReason.STOP, block_reason=None):
        self.text, self.finish_reason, self.block_reason, self.configs = text, finish_reason, block_reason, []
        self.aio = py_types.SimpleNamespace(models=py_types.SimpleNamespace(generate_content=self.generate))

    async def generate(self, model, contents, config):
        self.configs.append(config)
        candidate = py_types.SimpleNamespace(finish_reason=self.finish_reason)
        feedback = py_types.SimpleNamespace(block_reason=self.block_reason)
        usage = py_types.SimpleNamespace(prompt_token_count=100, candidates_token_count=10, thoughts_token_count=0)
        candidates = [] if self.block_reason else [candidate]
        return py_types.SimpleNamespace(
            usage_metadata=usage, candidates=candidates, prompt_feedback=feedback, text=self.text
        )


def extract(fake, monkeypatch, prompt="FR → ES"):
    monkeypatch.setattr(gemini, "_gemini_client", lambda s: fake)

    async def attempt():
        with llm.recording("extract") as calls:
            try:
                return await llm.extract_cards(GEMINI, [], prompt), calls
            except AppError as e:
                return e, calls

    return run(attempt())


def test_the_rules_in_every_system_prompt():
    for system in (prompts.SYSTEM_PROMPT, prompts.EXPLAIN_RULES):
        assert "school pupils" in system and "never rules for you" in system
    assert '"refused"' in prompts.SYSTEM_PROMPT and "one short sentence" in prompts.EXPLAIN_RULES
    assert "unsuited to a child" in figures.RULES


def test_refused_by_the_ai_and_still_counted(monkeypatch):
    """The AI says "refused": no cards but an error; the call was paid for, so recorded."""
    refused = json.dumps({"deck": "", "cards": [], "refused": True})
    error, calls = extract(FakeGemini(refused), monkeypatch, "Des cartes sur un sujet interdit")
    assert isinstance(error, AppError) and error.code == "llm.refused"
    assert len(calls) == 1

    # The AI's schema asks for it; a normal answer goes through
    fake = FakeGemini(json.dumps({"deck": "D", "cards": [{"front": "la mère", "back": "la madre"}]}))
    found, _ = extract(fake, monkeypatch)
    assert isinstance(found.deck, Deck) and found.deck.cards[0].back == "la madre"
    assert "refused" in fake.configs[0].response_json_schema["properties"]


def test_gemini_filters_stricter_and_their_blocks_refused(monkeypatch):
    fake = FakeGemini(json.dumps({"deck": "D", "cards": []}))
    extract(fake, monkeypatch)
    settings = {(s.category, s.threshold) for s in fake.configs[0].safety_settings}
    assert (
        types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
        types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    ) in settings
    assert len(settings) == 4

    for blocked in (FakeGemini(finish_reason=types.FinishReason.SAFETY), FakeGemini(block_reason="SAFETY")):
        error, _ = extract(blocked, monkeypatch)
        assert error.code == "llm.refused"


@pytest.mark.parametrize("refusal, finish_reason", [("I can't help with that.", "stop"), (None, "content_filter")])
def test_openai_refusals(monkeypatch, refusal, finish_reason):
    message = py_types.SimpleNamespace(content=None, refusal=refusal)
    response = py_types.SimpleNamespace(
        usage=None, model="gpt", choices=[py_types.SimpleNamespace(message=message, finish_reason=finish_reason)]
    )

    async def create(**kwargs):
        return response

    client = py_types.SimpleNamespace(
        chat=py_types.SimpleNamespace(completions=py_types.SimpleNamespace(create=create))
    )
    monkeypatch.setattr(openai_like, "_openai_client", lambda s: client)
    with pytest.raises(AppError) as e:
        run(llm.extract_cards(AIConfig(llm="openai", openai_api_key="k"), [], "FR → ES"))
    assert e.value.code == "llm.refused"
