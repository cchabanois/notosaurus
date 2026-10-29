# The pages

What the user sees: the page that makes the lessons (on the phone or the computer), the
settings page, the setup assistant. Plain HTML, CSS and [Alpine.js](https://alpinejs.dev),
**no build step**: the files are served as they are, by the server (`app/`) and, copied at
build time, by the Android app (`android/`). The pages load nothing from elsewhere
(`vendor/`).

| File | |
|---|---|
| `index.html`, `app.js` | the lessons' page: its markup, and its Alpine component (state, start, shared helpers) |
| `app-*.js` | that component's methods by topic: `app-photos` (photos, PDFs, hiding a name), `app-prompts`, `app-lessons` (a lesson made, saved, opened), `app-cards` (the review), `app-revision` (the AI's correction), `app-diagram` (labels' masks), `app-pictures`, `app-anki` (audio, send, `.apkg`, an explanation), `app-children`, `app-exams` (tests to prepare), `app-dictation` (🎤), `app-report` (⚑) |
| `admin.html`, `admin.js`, `admin-*.js` | the settings page, on the computer: its component, and its methods by section (`service`, `pictures`, `saving`, `anki`, `lessons`, `phones`, `password`) |
| `setup.html` | the setup assistant (the AI and its key, then the phone), on the computer |
| `licences.html`, `licences.js` | the libraries' licences (and the Android app's, in the app) |
| `i18n.js`, `i18n/<lang>.json` | the translations: one file per language, English as fallback; the same files give the server's prompts and the add-on's menu |
| `ask-confirm.js`, `voice-choice.js` | a yes/no in the page's own sheet; the voice chosen per language variety |
| `style.css` | the pages' style (light and dark) |
| `vendor/` | Alpine.js, KaTeX and pdf.js, shipped with the pages (see its README) |
| `note-types.json` | the Anki note types, written by `tools/note_types.py`, for the Android app |
| `manifest.json`, `*.png`, `*.webp` | the web app's manifest and icons (`tools/make_icons.py`) |

The pages are `<script defer>` tags sharing their globals: each `app-*.js` adds methods to
the component in `app.js` (`this`). The server tells a page what it can do through
`/api/config` (the Android app: no `.apkg`, ⚑ Report, 🎤…). Every user-facing text is in
`i18n/`: a new key goes into every language (a test checks the keys match).

## Tests

```sh
node --test tests/frontend/*.test.mjs   # the scripts in a Node vm, no dependency
.venv/bin/pytest tests/test_page.py     # the pages in a real browser (Playwright)
```

See [CONTRIBUTING.md](../CONTRIBUTING.md#tests-and-checks) and
[Adding a language](../CONTRIBUTING.md#adding-a-language).
