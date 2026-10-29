# The Notosaurus server

The FastAPI app behind the page (`static/`): it keeps the lessons, prompts, children and
settings as plain files under `data/`, asks the AI through `notosaurus_core` (`core/`), and
sends the cards to Anki. It runs inside Anki (the add-on, `anki_addon/`), standalone or in
Docker. The Android app doesn't use it: it answers the same `/api` on the phone (`android/`).

```sh
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --reload   # NOTOSAURUS_LLM=fake: the demo AI, no key
```

## Files

| File | |
|---|---|
| `main.py` | the app: settings and environment loaded, the paired-devices and host checks, errors, the routers, the static files |
| `routes/` | the `/api` routes, one module per topic (below) |
| `models.py` | the app's own data (lessons, prompts, settings forms, requests); the cards are `notosaurus_core`'s |
| `settings.py` | the settings (`data/settings.json`, `.env` for the defaults): the AI configuration, the app's own, API keys, admin password |
| `storage.py` | the data folder (`NOTOSAURUS_DATA`, `./data` by default), atomic JSON writes |
| `lessons.py` | saved lessons, one folder each (`lesson.json`, `page-N.jpg`, `audio/`) |
| `prompts.py` | Notosaurus's prompts (`builtinPrompts` in the i18n files) and the user's |
| `children.py` | the children's cards: first name (never sent to the AI), class, decks, instructions |
| `exams.py` | the tests to prepare: lessons or some of their cards, under an `Exam::<name>` tag in Anki |
| `access.py`, `hosts.py`, `attempts.py` | who may do what: paired devices and Anki profiles; the host names answered (DNS rebinding); wrong admin passwords slowed down |
| `anki.py`, `note_types/` | the notes a lesson gives and the `.apkg` (genanki); the note types, one module per family (text, cloze, choice, diagram, picture) |
| `ankiconnect.py` | the direct send: AnkiConnect, or the add-on's bridge |
| `lesson_notes.py`, `decks.py` | a lesson's notes found in Anki, and deleted with it; the decks that exist, given to the AI |
| `media.py`, `sounds.py` | what the cards take to Anki (audio, pictures, diagram images); the backs' sounds made ahead |
| `usage.py` | every AI call and its cost, in `data/ai-calls.json` |
| `i18n.py` | the languages (`static/i18n/<lang>.json`), shared with the page and the add-on |
| `errors.py` | errors as codes the page translates |
| `version.py` | the version, from `pyproject.toml` |

## Routes

| Module | |
|---|---|
| `routes/generation.py` | a lesson made from its photos (`/api/extract`), completed, made again, cancelled; the `.apkg` export |
| `routes/lessons.py` | lessons listed, opened, saved, copied for another child, deleted (with their notes in Anki), corrected by the AI |
| `routes/pictures.py` | the cards' pictures and figures: made, drawn, checked, found among free pictures, the user's photo |
| `routes/anki.py` | decks, Anki's status, the send |
| `routes/prompts.py`, `children.py`, `exams.py` | prompts (and tidying one up), children, tests |
| `routes/voices.py` | the voices, a back read aloud |
| `routes/admin.py` | the settings page's API: settings, password, models, tests of a key and of a picture model |
| `routes/pages.py` | the page's language and configuration, the web manifest, the QR code |
| `routes/devices.py`, `common.py` | the paired-devices check; what the routers share (the page's files, photos accepted, the asking page's language, work told as it goes) |

There is no database, and the server never builds a user-facing sentence: its errors are
codes (`llm.overloaded`…) that the page translates. See
[CONTRIBUTING.md](../CONTRIBUTING.md#architecture) and the tests in `tests/`.
