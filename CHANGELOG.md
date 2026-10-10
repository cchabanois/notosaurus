# Changelog

All notable changes to Notosaurus. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and versions follow [Semantic Versioning](https://semver.org/).

Each pull request adds a line under **Unreleased**. See [Releasing](CONTRIBUTING.md#releasing) for how a version is published.

## [Unreleased]

### Added

- 📚 Review a lesson in AnkiDroid right after adding it (the coming Android app): AnkiDroid opens on its deck.
- ⚡ Quick or 🎯 Careful, on the page that makes the cards: quick by default, 2 to 4 times faster (a few seconds) and cheaper; careful thinks longer, for a rich lesson (a diagram, maths). After a quick lesson, “Make again, carefully” redoes it in its place.
- The cards show while they are being made: each one as soon as the AI has written it (the first after a few seconds).
- “Cancel” while the cards are being made: the AI stops, no lesson is saved, the page comes back as it was (generated again: the old lesson stays).
- The coming Android app shows the cards as the AI writes them too, and its “Cancel” stops the AI on the relay.
- For developers: the relay's `/v1/extract` can answer as the AI writes (`application/x-ndjson`, `relay_api.ExtractLine`).
- The coming Android app reads the backs aloud with natural voices (Google Chirp 3 HD, through the relay): 🔊 in the review, and the sound on the cards sent to AnkiDroid. A lesson in a language being learned gets its voice by itself.
- For developers: the relay's `/v1/speak` and `/v1/voices`.
- The coming Android app draws the cards' pictures and figures (through the relay), takes your own photo or none, and sends the pictures to AnkiDroid (“Draw” said “Not Found”).
- The coming Android app sends diagram labels (the photo, its labels hidden, one asked) and texts with gaps (Anki's own cloze, a card per gap) to AnkiDroid: they were left out.
- The coming Android app sends a diagram cropped to it (its frame, holding every label), as the computer: easier to read, lighter to sync.
- The coming Android app saves photos taken sideways upright (their diagram labels with them), turns a saved photo with ↻ (it said “Not Found”), has the voice's speed in its settings, and no longer shows the “.apkg” button (the cards go straight to AnkiDroid).
- The coming Android app sends multiple-choice and true/false cards to AnkiDroid with their options (the right one marked on the answer): only the question and answer went.
- The coming Android app's cards in AnkiDroid are the computer's: the helps on the back and the “Did you know?”, reversed cards, typed answers and dictation; a lesson sent again updates its notes; deleting a lesson can delete its notes in AnkiDroid too.
- The Android app can generate a lesson again in its place (“Regenerate”, “Make again, carefully”).

### Changed

- For developers: `notosaurus-core` can call Gemini through Google Cloud's Vertex AI instead of a key (`gemini_vertex_project`, `gemini_vertex_location`), for the coming relay.
- The AI only makes learning material suited to pupils: other requests (sexual content, violence, dangerous instructions, anything that isn't a lesson) are refused with a clear message, and Gemini's own filters are stricter. Lessons on hard topics (history, biology, health) still work.
- The coming Android app, where Notosaurus is paid for by its subscription, doesn't show “Support Notosaurus”.
- The coming Android app has Notosaurus's version (`pyproject.toml`), like the server and the add-on.
- The coming Android app, on the phone, doesn't show an Anki profile badge (“none”): AnkiDroid doesn't say its profile.
- For developers: the AI and card logic is a package of its own, `notosaurus-core` (in `core/`), which other programs can use without the app. Nothing changes for users.
- For developers: the API of the coming Notosaurus relay (no API key needed, with a subscription): `relay_api.py` and its OpenAPI description, `core/relay-api-v1.json`.
- For developers: the tests build the Docker image and make a lesson with it.
- The texts of the coming Android app's settings and of the Notosaurus service's errors, in every language.
- The texts of the coming Android app's “With my computer” mode (the Anki add-on used from the app), in every language.
- The coming Android app's messages when AnkiDroid is missing or not allowed yet, in every language.
- In the coming Android app, the computer's page shows a ⚙️ that opens the app's settings (to use it without the computer again).
- For developers: the Android app (not published yet) now lives in this repository, in `android/`, built and tested with the same revision of the web page.
- For developers: the Android app's tests on an emulator (real AnkiDroid, the whole app, its two modes), run on demand.
- The coming Android app's settings: a clear choice of where Notosaurus works (on the phone, or on the computer with the add-on, shown by its name).

### Fixed

- The message after adding to Anki keeps its width on a phone: its buttons go under it (it was squeezed into a narrow column).
- Without AnkiDroid, the coming Android app no longer opens Google Play by surprise: its message says why, with an “Install AnkiDroid” button.
- Scrolling the lessons (or another sheet) with a finger no longer moves the lesson behind, on a phone.
- 🔊 Listening to a card again, or to another one, no longer plays two voices at once: the sound playing stops.
- A long back, info, wrong option or “Did you know?” is seen whole in the review, on as many lines as it needs (only the front grew before): nothing cut on a phone.

## [1.0.0] - 2026-10-04

The first version.

### Added

**From a lesson to cards**

- Photos of a lesson (handwriting included, pages taken sideways straightened), a PDF (its text read exactly) or the instructions alone: a vision AI drafts the cards. Gemini, Claude, GPT, OpenRouter or a local model.
- Instructions for each kind of lesson, ⭐ "Automatic" choosing the cards from the page; your own saved instructions, or written for one lesson; standing instructions per child ("in year 8").
- Card types: questions and answers, fill in the blanks, multiple choice, true or false, vocabulary and sentences of a language, formulas, geometry with exact figures, diagrams with their labels hidden, pictures drawn by an image model, typed answers and dictations.
- Helps on the back where they help (why the answer is right, a genuine way to remember it), optional "Did you know?" facts, and 💬 an explanation of any card while reviewing.
- Review: edit, add or delete cards, fix them in plain words with the AI, generate again, undo.
- Natural audio of the backs, in the deck: it plays everywhere, even offline.

**Into Anki**

- An Anki add-on: Notosaurus starts with Anki, installs its components after asking (about 300 MB, once), and a setup assistant guides the first steps (the AI and its key, then the phone).
- Sent straight to Anki and synced, updated without duplicates; or an `.apkg` file. Each lesson has its own deck, under the subjects already there.

**For families**

- One Anki profile per child, each with their own lessons, shared or not; the lessons grouped by subject, with a search.
- Only the phones that scanned the QR code use Notosaurus; the settings open on the computer only.
- What each lesson cost, call by call.

**Settings, languages, help**

- Recommended models for each service, from our tests on real notebook pages, with what a lesson or a picture costs; a test for the AI and for the pictures. A free Gemini key works, with an older model.
- The app, its instructions and the add-on in English, French, Spanish, German, Italian and Portuguese (Brazil); the documentation in English and French (https://cchabanois.github.io/notosaurus/).

[Unreleased]: https://github.com/cchabanois/notosaurus/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/cchabanois/notosaurus/releases/tag/v1.0.0
