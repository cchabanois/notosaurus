"""The pages in a real browser (Playwright, headless Chromium): what the API tests
can't see — the page saving as it goes, generating again and undoing, deleting a
lesson, the cloze preview, the settings' order.

Skipped unless Playwright is installed: `pip install -r requirements-page.txt`, then
`python -m playwright install chromium` (or NOTOSAURUS_TEST_CHROMIUM=/usr/bin/chromium
to use the system's). The pages' Alpine.js and MathJax are shipped (static/vendor): no network needed.

This folder: one file per screen; conftest.py the fixtures (a server, a browser, a
phone-sized page on fresh data), support.py what the tests share."""

import os
import socket
import threading
import time

import pytest

try:
    from playwright import sync_api
except ModuleNotFoundError:  # each test file skips itself (importorskip)
    sync_api = None  # type: ignore[assignment]
import uvicorn
from conftest import fake_synthesize

from app import storage
from app.main import app
from notosaurus_core import tts


@pytest.fixture(scope="session")
def server():
    """Notosaurus on a free port, in this process: the tests' settings apply to it."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    runner = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=runner.run, daemon=True)
    thread.start()
    for _ in range(100):
        if runner.started:
            break
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    runner.should_exit = True
    thread.join(5)


# The package's, not the session's: Playwright's sync API runs an event loop as long as it
# is open, and the tests after this folder (asyncio.run) can't start one of their own
@pytest.fixture(scope="package")
def browser():
    with sync_api.sync_playwright() as p:
        executable = os.environ.get("NOTOSAURUS_TEST_CHROMIUM")
        try:
            browser = p.chromium.launch(executable_path=executable) if executable else p.chromium.launch()
        except sync_api.Error as e:  # no browser here: skipped, not 60 errors
            if executable:  # one asked for (CI's Chrome) that can't start: an error, not all skipped
                raise
            pytest.skip(f"no Chromium (python -m playwright install chromium, or NOTOSAURUS_TEST_CHROMIUM): {e}")
        yield browser
        browser.close()


@pytest.fixture
def page(browser, server, tmp_path, monkeypatch):
    """A phone-sized page in French, on fresh data and the demo AI (no key, no cost)."""
    monkeypatch.setenv("NOTOSAURUS_DATA", str(tmp_path / "data"))
    monkeypatch.setenv("NOTOSAURUS_LLM", "fake")
    monkeypatch.setenv("NOTOSAURUS_ANKICONNECT_URL", "http://127.0.0.1:1")  # Anki closed
    for key in ("GEMINI_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.delenv(key, raising=False)  # the same on every computer: no key (.env)
    monkeypatch.setattr(tts, "_synthesize", fake_synthesize)
    context = browser.new_context(locale="fr-FR", viewport={"width": 390, "height": 844}, base_url=server)
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    yield page
    # The lesson in progress kept now (app-draft.js keeps it a moment after a change): else
    # kept in the next test's data, which then finds it again
    page.evaluate(
        "async () => { const root = document.querySelector('[x-data]');"
        " const data = root && window.Alpine && Alpine.$data(root); if (data?.saveDraft) await data.saveDraft(); }"
    )
    # The page's requests done first (a lesson still being saved, its pictures): else one
    # lands after NOTOSAURUS_DATA is the next test's, a lesson made there (a flaky count)
    page.wait_for_load_state("networkidle")
    # A route handler still at work (route.fetch) when the context closes fails the
    # next test's new_context: "Response has been disposed"
    page.unroute_all(behavior="ignoreErrors")
    context.close()
    assert not errors, errors


@pytest.fixture
def clock(monkeypatch):
    """A second more at each save: the lessons made in a test are in order (saved to
    the second, they would all be at the same time)."""
    ticks = iter(range(3600))
    monkeypatch.setattr(storage, "now", lambda: "2026-10-03T10:{:02d}:{:02d}".format(*divmod(next(ticks), 60)))
