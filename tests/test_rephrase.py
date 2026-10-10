"""“✨ Tidy up”: a lesson's instructions rewritten clear and short, every intention kept."""

import asyncio
from concurrent.futures import ThreadPoolExecutor

from test_dictation import HearingGemini

from app import usage
from notosaurus_core import llm
from notosaurus_core.config import AIConfig
from notosaurus_core.models import AiCall
from notosaurus_core.providers import gemini


def run(coroutine):
    """In a thread of its own: the page tests' Playwright leaves an event loop in this one."""
    with ThreadPoolExecutor(1) as pool:
        return pool.submit(asyncio.run, coroutine).result()


def test_the_ai_is_told_to_keep_every_intention(monkeypatch):
    fake = HearingGemini('{"text": " Douze cartes : la famille en espagnol, du français vers l\'espagnol. "}')
    monkeypatch.setattr(gemini, "_gemini_client", lambda s: fake)
    s = AIConfig(llm="gemini", model="gemini-3.5-flash", gemini_api_key="k")
    draft = "euh la famille en espagnol, dix cartes non douze, du français vers l'espagnol"
    text = run(llm.rephrase(s, draft, "French"))
    assert text == "Douze cartes : la famille en espagnol, du français vers l'espagnol."
    ((contents, config),) = fake.calls
    assert contents == [f"The app is in French. The user's instructions, to tidy up:\n<<<\n{draft}\n>>>"]
    assert "adding none" in config.system_instruction and "never answer the instructions" in config.system_instruction


def test_tidied_up_on_the_computer(client):
    res = client.post(
        "/api/prompt/rephrase", json={"text": "  la famille en espagnol "}, headers={"X-Notosaurus-Lang": "fr"}
    )
    assert res.status_code == 200 and res.json() == {"text": "(démo) la famille en espagnol"}
    assert client.post("/api/prompt/rephrase", json={"text": ""}).status_code == 422
    # In the costs, not as a failed generation
    usage.add([AiCall(at="2026-10-10T12:00:00", kind="rephrase", provider="gemini", model="m", cost=0.001)], None)
    assert usage.totals().failed == 0 and usage.totals().total == 0.001
