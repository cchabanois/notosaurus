# Tools

Scripts for developing and releasing Notosaurus, run from the repository's root with its
virtual environment (`.venv/bin/python tools/<script>.py`). Each one's docstring says more
(`--help` for those with options).

## Building and checking

| Script | |
|---|---|
| `build_addon.py` | builds `dist/notosaurus-<version>.ankiaddon`: the add-on (`anki_addon/`) with the server inside and the pinned requirements |
| `check_addon_install.py` | installs that file as Anki would, outside Anki, and starts its server |
| `changelog_section.py <version>` | a version's release notes, from `CHANGELOG.md` (its section, or **Unreleased**) |

## Files written from the code

Run them after changing what they read; a test checks each output is up to date.

| Script | Writes |
|---|---|
| `relay_openapi.py` | `core/relay-api-v1.json`, the relay's OpenAPI description, from `notosaurus_core/relay_api.py` |
| `relay_compat.py` | nothing: checks today's relay API against those of the released apps (`core/relay-api-releases/`) |
| `note_types.py` | `static/note-types.json`, the Anki note types for the Android app, from `app/note_types/` |
| `typst_packages.py` | `core/notosaurus_core/typst/<name>-<version>.tar.gz`: the Typst packages the figures use, one archive each as published, at fixed versions |
| `make_icons.py` | the logo images and the icons (home screen, browser), from `assets/notosaurus-logo.png` |

## Documentation

| Script | |
|---|---|
| `docs_screenshots.py shoot [--lang fr]` | the documentation's screenshots, in each language, from the demo lessons in `docs/demo/` (no AI call) |
| `docs_screenshots.py generate --lang <code> --settings data/settings.json` | a new language's demo lessons, once, with a real AI (a few cents) |

## Benches

They call the AI for real, through the test relay (a licence: `RELAY_KEY`), and cost a little.
Run them before changing a prompt, a rule or a model.

| Script | |
|---|---|
| `bench.py` | real lessons made again and checked: each card's note type, the voice and its side, the diagrams' masks, the lesson's `expect.json`; the lessons are private (`notes/bench/lessons`, never committed); `--reuse <run>` checks again for free |
| `bench_figures.py` | figures drawn a few times from their descriptions, then judged by code and by the AI looking at them |

See also [CONTRIBUTING.md](../CONTRIBUTING.md).
