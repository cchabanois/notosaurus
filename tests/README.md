# Tests

```sh
.venv/bin/pytest                          # the Python tests (pytest.ini options in pyproject.toml)
.venv/bin/pytest tests/test_lessons.py -q # one file
node --test tests/frontend/*.test.mjs     # the page scripts, no dependency
```

The tests need no AI key and no Anki: `conftest.py` gives each test fresh data,
a paired phone, the demo AI (provider `fake`), the voices and AnkiConnect faked (`FakeAnki`, in
memory). Two files need more and are skipped without it:

- `test_page.py`: the pages in a real browser (Playwright, headless Chromium):
  `pip install -r requirements-page.txt` and `python -m playwright install chromium`, or
  `NOTOSAURUS_TEST_CHROMIUM=/usr/bin/chromium` (the system's).
- `test_real_anki.py`: the add-on's bridge and the `.apkg` import against Anki's real engine:
  `pip install -r requirements-anki.txt`.

## Shared helpers

| File | |
|---|---|
| `conftest.py` | the fixtures: fresh data, a paired phone, the demo AI, TTS and AnkiConnect faked |
| `helpers.py` | a coroutine run in its own thread, a plain image as bytes, a Gemini client that only listens |
| `apkg.py` | an exported `.apkg` opened: its notes, note types, decks and media read from the real package |
| `frontend/harness.mjs` | the page scripts (`static/i18n.js`, `app*.js`, `admin.js`) loaded in a Node `vm` with the browser's globals stubbed, as they ship |

## What is tested where

| Topic | Files |
|---|---|
| Making a lesson | `test_extract.py` (photos, prompt alone, PDFs), `test_streaming.py` (cards as the AI writes them), `test_fix_card.py`, `test_rephrase.py`, `test_explain.py`, `test_helps.py`, `test_dictation.py` |
| Lessons, children, tests | `test_lessons.py`, `test_children.py`, `test_instructions.py`, `test_exams.py`, `test_sharing.py`, `test_formats.py` (old data files read) |
| Pictures, figures, diagrams | `test_pictures.py`, `test_picture_services.py`, `test_stock.py`, `test_figures.py`, `test_diagrams.py` |
| Anki | `test_export.py` (the `.apkg`), `test_send.py` (AnkiConnect), `test_note_types.py`, `test_fix_link.py` (✎ Notosaurus), `test_sounds_ahead.py`, `test_markup.py`, `test_real_anki.py` |
| AI services | `test_gemini.py`, `test_anthropic.py`, `test_openai.py`, `test_costs.py`, `test_safety.py` (pupils' safety rules and filters) |
| Settings and security | `test_admin.py`, `test_devices.py` (pairing), `test_properties.py` (Hypothesis on the most exposed filters: Host, SVG) |
| The add-on | `test_addon.py`, `test_addon_launcher.py`, `test_addon_bridge.py` (without Anki: `aqt` faked) |
| The relay's API | `test_relay_api.py`, `test_relay_compat.py` (released apps keep working), `test_relay_directory.py` (`docs/public/relay.json`) |
| Shared with the Android app and the page | `test_shared_cases.py` and `frontend/shared-cases.test.mjs` (`core/shared-cases.json`, Python's answers the reference) |
| The repository | `test_core.py` (`notosaurus_core` on its own), `test_i18n.py` (same keys in every language, every error code translated, docs links), `test_prompts.py`, `test_requirements.py`, `test_vendor.py` (nothing loaded from elsewhere), `test_licences.py` |
| The pages | `test_page.py` (browser), `frontend/app.test.mjs`, `admin.test.mjs`, `i18n.test.mjs` |

The Android app has its own tests, in `android/` (see its README). See also
[CONTRIBUTING.md](../CONTRIBUTING.md#tests-and-checks).
