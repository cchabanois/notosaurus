# Contributing to Notosaurus

How to work on Notosaurus: set up a development environment, run the tests, find
your way in the code, add a language and publish a release. For installing and using
Notosaurus, see the [README](README.md).

## Setting up

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --reload
```

Set `NOTOSAURUS_LLM=fake` in `.env` to work on the interface without an API key: the
demo provider returns canned cards whatever the photo, at no cost.

### Developing the add-on

To develop the add-on against this checkout, link it into Anki's add-ons folder and
restart Anki:

```sh
ln -s "$PWD/anki_addon" ~/.local/share/Anki2/addons21/notosaurus
```

The add-on then runs the server from this repository, with its `.venv` and its
`data/` folder.

To build the add-on file: `python3 tools/build_addon.py` → `dist/notosaurus-<version>.ankiaddon`.

## Tests and checks

```sh
.venv/bin/pytest
node --test tests/frontend/*.test.mjs                       # the page scripts' unit tests (no dependency)
.venv/bin/ruff check . && .venv/bin/ruff format --check .   # lint and formatting (pyproject.toml)
```

`tests/frontend/` unit-tests `static/i18n.js`, `app.js` and `admin.js` as they
ship: the scripts run in a Node `vm` context with the browser globals stubbed and
the real translation files, so the fallback chain, the card preview's escaping,
the settings page's diffing and the like are checked without a browser.

`tests/test_page.py` drives the pages in a real browser (Playwright, headless
Chromium): the page saving as it goes, generating again and undoing, deleting a
lesson, the settings. It is skipped unless Playwright is installed:
`.venv/bin/pip install -r requirements-page.txt`, then
`.venv/bin/python -m playwright install chromium` (or set
`NOTOSAURUS_TEST_CHROMIUM=/usr/bin/chromium` to use the system's Chromium).

`tests/test_real_anki.py` runs the add-on's bridge and the `.apkg` import against
Anki's real engine (the `anki` package, no Anki window). It is skipped unless that
package is installed: `.venv/bin/pip install -r requirements-anki.txt`.

## Dependencies

`requirements.txt` pins every package to an exact version, for every system, so a new
release of a library can't break an install (the add-on installs it on the user's
computer). The direct dependencies are in `requirements.in`; to change them or update
the pins (Dependabot proposes updates every week):

```sh
uv pip compile requirements.in --universal --python-version 3.13 -o requirements.txt --upgrade
```

## Architecture

Stack:

- back end: FastAPI + Pydantic;
- front end: Alpine.js, with no build step;
- decks: [genanki](https://github.com/kerrickstaley/genanki), with stable GUIDs so re-importing updates cards;
- QR codes: [segno](https://github.com/heuer/segno).

The AI and card logic is a package of its own, `core/notosaurus_core`: it never reads
the app's settings, lessons or data folder (the AI configuration and everything else
come in as parameters), so that other programs can use it. A test keeps it that way.

| Path | Content |
|---|---|
| `core/notosaurus_core/llm.py` | card extraction, AI correction and explanations (Gemini, Claude, OpenAI-compatible, fake) |
| `core/notosaurus_core/config.py` | the AI configuration: service, model, keys, picture service |
| `core/notosaurus_core/models.py` | cards, decks, diagram masks and frames, AI calls |
| `core/notosaurus_core/tts.py` | edge-tts audio |
| `core/notosaurus_core/pictures.py`, `figures.py` | pictures on cards, drawn by an image model; figures drawn as SVG |
| `core/notosaurus_core/diagrams.py` | diagram labels: boxes from the AI, card images with the labels hidden |
| `core/notosaurus_core/recommended.py`, `prices.py` | recommended models, estimated costs |
| `core/notosaurus_core/errors.py` | errors as translatable codes |
| `core/notosaurus_core/files.py` | where the caches go, small file helpers |
| `app/main.py` | FastAPI routes and static files |
| `app/lessons.py` | saved lessons, one folder each |
| `app/anki.py` | `.apkg` builder (genanki, audio, reverse cards) |
| `app/ankiconnect.py` | direct send through AnkiConnect or the add-on's bridge |
| `app/prompts.py` | saved prompts |
| `app/settings.py` | settings (the AI configuration and the app's own), API keys, admin password |
| `app/i18n.py`, `static/i18n.js`, `static/i18n/` | languages |
| `app/storage.py` | data folder, atomic JSON writes |
| `static/` | the phone page and the settings page |
| `anki_addon/` | the Anki add-on: server launcher and an AnkiConnect-compatible bridge |
| `tools/build_addon.py` | builds `dist/notosaurus-<version>.ankiaddon` |
| `tools/changelog_section.py` | release notes of a version, from `CHANGELOG.md` |
| `tools/make_icons.py` | the logo images and the icons (home screen, browser), from `assets/notosaurus-logo.png` |

There is no database: everything is plain files under `data/` (see
[Data](README.md#data)). JSON files are written to a temporary file and then renamed,
so a crash never leaves a half-written file.

The AI's output format is always forced with a JSON schema; the user's prompt only says
*what* to extract. Instructions sent to the AI are in English, and the user's prompt
decides the language of the cards.

## Adding a language

Copy `static/i18n/en.json` to `static/i18n/<code>.json` (e.g. `es.json`, `pt-br.json`)
and translate the values. That single file covers:

- the interface;
- error messages;
- the default prompts;
- the add-on's menu.

A test checks that every language has exactly the same keys as English, and another
that every language fits a narrow phone (360 px): no page wider than the screen, no
button or title cut, no placeholder longer than its field. Translations use Anki's own
words (its official translations: deck = *mazo*, *Stapel*, *mazzo*, *baralho*…) and the
school words of the country.

The server never builds sentences: its errors are codes (`llm.overloaded`,
`lesson.not_owner`…) that the page translates.

## User documentation

The user documentation is a website in `docs/`, built with
[Astro Starlight](https://starlight.astro.build) and published on GitHub Pages
(https://cchabanois.github.io/notosaurus/) by the *Documentation site* workflow, on every
merge on `main` that changes it. It needs Node.js only to build the site; Notosaurus itself
doesn't use it.

```sh
cd docs
npm install
npm run dev      # http://localhost:4321/notosaurus/, reloads on every change
npm run build    # what the workflow publishes, in docs/dist
```

- Pages are Markdown files in `docs/src/content/docs/`: English at the root, the other
  languages in a folder named after their code (`fr/`, `es/`, `de/`, `it/`, `pt-br/`), with
  the same file names. A page not translated yet shows the English one, with a notice.
- The sidebar, the languages and the site's settings are in `docs/astro.config.mjs`.
- Use the interface's own words, in each language (`static/i18n/<lang>.json`), and Anki's.
- The app links to pages of the site with `$docs('page')` (the "?" at the end of some section
  titles), in the page's language: keep those page names when renaming a page.
- The image shown when the site's address is shared, `docs/public/og.jpg`, is made from
  `docs/demo/og-image.html`.

### Screenshots

The screenshots in `docs/src/assets/screenshots/<lang>/` are taken by
`tools/docs_screenshots.py`, from demo lessons stored in `docs/demo/<lang>/lessons/`
(made from the pages in `docs/demo/inputs/`, no personal data). Retake them whenever the
interface changes; it needs Playwright (`requirements-page.txt`) and makes no AI call:

```sh
.venv/bin/python tools/docs_screenshots.py shoot                # every language
.venv/bin/python tools/docs_screenshots.py shoot --lang fr
```

For a new language, make its demo lessons once with a real AI (a few cents; the API keys
are read from `--settings` and never written to the repository), then take its screenshots:

```sh
.venv/bin/python tools/docs_screenshots.py generate --lang es --settings data/settings.json
```

The script runs Notosaurus as in the add-on, with a fake Anki (profiles Léa and Paul) and a
fake API key, so no real key or name appears in the screenshots. A new language also needs
its entries in `LESSONS`, `INSTRUCTIONS` and `CORRECTION_TYPED` in the script, and its
`docs/demo/inputs/*.<lang>.html` pages.

## Pull requests

`main` is protected: every change goes through a pull request. Each pull request adds a
line under **Unreleased** in [CHANGELOG.md](CHANGELOG.md).

## Contributor License Agreement

Before your first pull request can be merged, you sign the
[Contributor License Agreement](CLA.md) once, by posting this comment on the pull
request:

> I have read the Notosaurus CLA (version 1.0) and I agree to it.

The pull request template reminds you. The maintainer checks the comment before
merging; it covers all your later contributions too.

Why: Notosaurus is open source under the [AGPL-3.0](LICENSE), and it will stay so. The
agreement also lets the maintainer offer Notosaurus under other terms where the AGPL
doesn't fit, for instance in an app store or as a hosted service, which helps fund its
development. In exchange, the agreement promises that every contribution stays
available as open source in this repository. You keep the copyright of your work and
remain free to use it however you like.

## Releasing

The version lives in one place, `pyproject.toml` ([semantic versioning](https://semver.org/)).
The server reads it (shown at the bottom of ⚙️), and the add-on build writes it into
Anki's add-on list.

`pyproject.toml` holds the version being prepared. After every merge on `main`, the
*Draft release* workflow keeps a draft GitHub release `vX.Y.Z` up to date: the add-on
built from `main`, and the **Unreleased** section of [CHANGELOG.md](CHANGELOG.md) as notes.

1. Every pull request adds a line under **Unreleased**.
2. To release, open a pull request that renames **Unreleased** to `[X.Y.Z] - yyyy-mm-dd`
   (keep an empty **Unreleased** above it, and update the links at the bottom). Once
   merged, the draft shows these notes.
3. Review the draft on GitHub (*Releases*) and click *Publish release*: GitHub creates
   the tag `vX.Y.Z` on that commit.
4. Upload the add-on to AnkiWeb, with the description kept in [docs/ankiweb.md](docs/ankiweb.md)
   (check that it still matches what Notosaurus does).
5. In the next pull request, set the next version in `pyproject.toml` (until then, the
   draft isn't updated).
