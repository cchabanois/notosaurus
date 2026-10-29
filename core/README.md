# notosaurus_core

Notosaurus's brain, as a package of its own: lesson photos read into cards, corrected and
explained by the AI, pictures and figures drawn or found, the backs read aloud. The server
(`app/`) uses it with the user's own keys; the Notosaurus relay (private, behind the Android
app's subscription) uses it too, through the API described in `relay_api.py`.

It **never reads the app's settings, lessons or data folder**: the AI configuration
(`config.AIConfig`) and everything else come in as parameters. A test keeps it that way.

## Files

| Path | |
|---|---|
| `notosaurus_core/llm.py` | the entry points: cards from photos (`extract_cards`), corrections, explanations, a prompt tidied up, one interface over the services |
| `notosaurus_core/providers/` | one module per AI service: `gemini.py` (key or Vertex AI, fallback models), `anthropic.py`, `openai_like.py` (OpenAI, OpenRouter, any compatible service: Ollama, LM Studio…), `demo.py` (the demo AI, provider `fake`: canned cards, no key) |
| `notosaurus_core/prompts.py` | what the AI is told: each task's rules, the pupils' safety rules, the requests built from the user's prompt |
| `notosaurus_core/calls.py` | what every call shares: the photos sent, the errors, each call recorded with its model, tokens and cost, the cards read as the AI writes them |
| `notosaurus_core/models.py`, `cards.py` | cards, decks, diagram masks and frames, corrections, explanations; what kind of card a card is |
| `notosaurus_core/config.py` | the AI configuration: the cards' service, model and key, the pictures' service |
| `notosaurus_core/diagrams.py` | diagram labels hidden on the photo (image occlusion) |
| `notosaurus_core/pictures.py`, `stock.py` | pictures drawn by an image model; free pictures found instead (Wikimedia Commons, Openverse, Pixabay) |
| `notosaurus_core/figures.py`, `figures_typst.py` | figures (geometry, graphs, sets, timelines…) written in Typst, one package per kind, compiled offline; their check |
| `notosaurus_core/typst/`, `fonts/` | the Typst packages (`tools/typst_packages.py`) and the font the figures use, shipped so nothing is downloaded, their licences with them |
| `notosaurus_core/tts.py` | the backs' audio (edge-tts) |
| `notosaurus_core/images.py` | photos opened safely (no decompression bomb) |
| `notosaurus_core/recommended.py`, `prices.py` | the models recommended per service (the only list written by hand); a call's estimated cost |
| `notosaurus_core/errors.py` | errors as codes + parameters, translated by the page |
| `notosaurus_core/files.py` | where the caches go, small file helpers |
| `notosaurus_core/relay_api.py` | the relay's API, version 1: what its clients and the relay both import |
| `relay-api-v1.json` | its OpenAPI description, written by `tools/relay_openapi.py` (a test checks it is up to date) |
| `relay-api-releases/` | the API each released app speaks, frozen at its release; `tools/relay_compat.py` checks today's doesn't break them |
| `shared-cases.json` | cases Python, Kotlin (the Android app) and JavaScript (the page) must answer alike; Python's answers are the reference |
| `pyproject.toml` | the package (`notosaurus-core`, AGPL-3.0-only), its minimal dependencies; its version is the app's (`../pyproject.toml`) |

In the repository, `app/__init__.py` puts `core/` on the path; the add-on and the Docker image
ship `notosaurus_core` next to `app/`. Instructions sent to the AI are in English, the AI's
answers are always forced with a JSON schema. Tests: `tests/test_core.py`, `test_extract.py`,
`test_figures.py`, `test_gemini.py`, `test_relay_api.py`… See
[CONTRIBUTING.md](../CONTRIBUTING.md#architecture).
