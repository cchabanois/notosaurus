# Changelog

All notable changes to Notosaurus. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and versions follow [Semantic Versioning](https://semver.org/).

Each pull request adds a line under **Unreleased**. See [Releasing](CONTRIBUTING.md#releasing) for how a version is published.

## [Unreleased]

### Added

- On a computer, photos and PDFs dragged from a folder can be dropped on **Gallery** or **PDF** (each goes where its type says); a file let go elsewhere on the page no longer makes the browser open it (and leave the lesson).
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
- 🎤 The coming Android app takes the instructions and the AI correction by voice: what you say is written down as you meant it (hesitations out, “ten, no, twelve” → twelve, a lesson's foreign words spelled right), then you read it over.
- For developers: the relay's `/v1/transcribe`.
- ✨ “Tidy up” under the instructions: the AI rewrites them clear and short, every intention kept and nothing added (typed in a hurry or dictated); “↩ Undo” brings them back. On the computer (your AI) and in the coming Android app (the relay's).
- For developers: the relay's `/v1/rephrase`.
- While 🎤 listens and its text is being written (or the instructions tidied up), the field is greyed out and says so (“Listening…”, then “Writing down what you said…”); “Generate” waits.

- 🔎 “Find a picture” in a card's picture panel: free pictures of its subject to choose from (Wikimedia Commons, Openverse; in the coming Android app, Pixabay too), only public domain, CC0 or Pixabay's licence (no credit to give), filtered for pupils. Free, instantly, and exact for real things (a painting, a place, a species); “Draw” is still there.
- For developers: the relay's `/v1/pictures/search` and `/v1/pictures/found`.
- A card's picture showing a real thing (a person, a place, a work, an animal) is now found before it is drawn: the AI writes what to search for, looks at the free pictures found and keeps the one that fits (drawn when none does). Free (the choice costs well under a cent), and exact. **Settings → Pictures on cards → Look for a free picture first** turns it off.
- Each card keeps where its picture comes from (a free picture's source, licence and page; drawn by the AI; your photo), said in its picture panel with a link to the page; on the computer, its Anki note keeps it too, in a hidden **Source** field (on no card; the Android app's notes don't have it: AnkiDroid can't add a field to its note types).
- A picture that shows the answer (the portrait of the person asked about) goes on the back; a sentence with gaps gets no picture (Anki shows none on it: it was paid for nothing).

### Changed

- A card's picture panel: “What the picture should show”, in your own language (no more “in English”), empty when the card has none (it showed the back, LaTeX included). **🎨 Draw** lets the AI decide from the card and what you wrote an exact figure (a diagram, sets, geometry) or a drawn picture, and describes it; a figure's description changed redraws that figure. **🔎 Find a picture** turns what you wrote into English search words first. Buttons of the panel no longer stay greyed on a card never touched.
- A figure the AI meant to put on a card's back but left undescribed (now and then, more in Quick mode with the helps on) is described by one light call that sees the lesson's page: the set theory page went from about 1 lesson in 8 without its figures to 1 in 16 in Quick, none in Careful. No call when the cards are consistent.
- Figures beyond geometry: in any subject, a notion a figure makes clearer gets one, in particular when the lesson's page shows a figure for it (a lesson on sets got none: its Venn diagrams are now redrawn on the intersection and union cards). Figures may hatch an area and cut a shared one (patterns and clip paths, inside the figure only): an intersection came out wrong. “Automatic” says so; “Word list” no longer imposes Spanish (or English): the language being learned.
- Notosaurus's instructions: “Words in pictures” is now “Vocabulary in pictures (languages)”, with only words a picture clearly shows; “Automatic” adds a picture only when it truly helps (a person, a place, a work, an animal), on the back when it shows the answer, on the front only when the question is about it; “Middle school maths formulas” removed (too specific: “Formulas” covers a lesson's). The Android app also gets “Dictating words”, missing from its list.
- Gemini's answer stopping halfway (seen once: nothing for minutes) is given up on after 45 s of silence (90 s before its first part): the next model starts again, and if none answers, “Gemini didn't answer in time: try again” instead of waiting forever.
- For developers: a fresh install of the Android app calls the test relay in a debug build, the real one in a release (never the test one); the release build passes Android's checks.
- For developers: the relay's API each released app speaks is frozen (`core/relay-api-releases/`), and a test (`tools/relay_compat.py`) refuses a change that would break an app already released.
- For developers: the Android app makes its AnkiDroid note types from `static/note-types.json`, written from `app/anki.py` (`tools/note_types.py`): one definition for both. Picture cards get the computer's picture note type on Android too.
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

- 🎤 vanished as soon as a lesson was shown, and a lesson's saving could fail until one was: the 🎤's state and the lesson's dictation option had the same name.
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
