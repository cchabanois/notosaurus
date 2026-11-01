# Changelog

All notable changes to Notosaurus. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and versions follow [Semantic Versioning](https://semver.org/).

Each pull request's entries (the `## Changelog` of its description) are put under **Unreleased** once it is merged, by the *Changelog* workflow: see [Pull requests](CONTRIBUTING.md#pull-requests), and [Releasing](CONTRIBUTING.md#releasing) for how a version is published.

## [Unreleased]

### Added

**The Android app**

- 📱 Notosaurus on Android: a lesson photographed, its cards made and sent straight to AnkiDroid, no computer needed. The AI is the Notosaurus service's (no key to get), with a subscription through Google Play, by the month or the year, restored by itself on a new phone. Or, for free, the app shows the computer's page (the Anki add-on): scan its QR code.
- 🎁 A free trial without a card, once per phone: it starts with the first lesson.
- The cards in AnkiDroid are the computer's: the same note types, so a lesson sent from the phone or from the computer is the same notes, never added twice. Natural voices (Google Chirp 3 HD), pictures and figures, dictations, typed answers, reversed cards, multiple choice, texts with gaps and diagrams with their labels hidden.
- 🎤 Instructions and corrections by voice, written down as you meant them (hesitations out, "ten, no, twelve" → twelve), then read over.
- 📚 A lesson reviewed in AnkiDroid right after it is sent; **Open AnkiDroid** in the top bar.
- The app follows the phone's dark mode; Android's back button closes the open sheet first.

**Making a lesson**

- ⚡ Quick or 🎯 Careful: quick by default, 2 to 4 times faster and cheaper; careful for a rich lesson (a diagram, maths). After a quick lesson, **Make again, carefully**.
- The cards show as the AI writes them, the waiting card says what the AI is at, and **Cancel** stops it.
- ➕ A page added to a lesson days later: the AI reads only the new pages; the cards made already, and their notes in Anki, stay as they are.
- 🖍️ On a photo not sent yet, black out with a finger what the AI shouldn't see (a name, a school).
- ✨ **Tidy up** rewrites the instructions clear and short, nothing added; ↩ Undo brings them back.
- The lesson in progress is never lost by leaving the page: its photos and prompt are found again.
- On a computer, photos and PDFs dragged from a folder onto the page.

**Notosaurus's prompts**

- New: **Dictation**, **Gap dictation**, **By heart** (a poem, a recitation, line by line), **Recognise from an example**, **Dates and landmarks** (learned both ways), **Table to learn**, **Definitions and properties** (a theorem's name → its full statement, and its converse when the lesson gives it), **Language: conjugation**, **Methods (steps)**. **Automatic** recognises each of these kinds of page.
- Any prompt can ask for the reverse card, the backs read aloud, slow or normal speed, no pictures, no helps.

**Cards**

- ✨ **Correct this card** (a card's ⋯): say what's wrong ("the answer is 1789", "shorter"), typed or dictated, and the AI rewrites that card alone; ↩ Undo. A card just added, still empty: **Write with the AI**.
- ⚠️ A lesson that looks wrong (a pupil's notes, a copy mistake: a wrong date, name or number) is said on its card, with the correction to take or not; never sent to Anki.

**Pictures and figures**

- One **✨ Image** button, the cheapest first: a drawing from the lesson's own page cut out of the photo (35 right out of 36 on 11 lessons); else a free picture (Wikimedia Commons, Openverse; Pixabay in the app), with no credit to give and filtered for pupils, the best ones first; drawn by the AI only once you say yes.
- Figures drawn in Typst with the package made for each kind: geometry (marks and angles computed), graphs computed from their function, sets, diagrams, circuits, chemistry, timelines. 🔍 under a figure has the AI check it and redraw it when it's wrong.
- Each picture says where it comes from (its source, licence and page), and each figure what drew it, crediting the open-source projects behind it.

**Into Anki**

- ✎ **Notosaurus** under every answer in Anki: the card opened in Notosaurus to correct it, in the app on Android or in the page on the computer.
- 🔊 **Add to Anki** is quicker (the sounds made in the background beforehand) and says how far it is. A lesson not changed since its send says **✓ Up to date in Anki**.
- After a send, the cards in Anki that no longer match the lesson are listed, deleted only on **Delete from Anki**.

**Tests to prepare**

- 📌 A lesson, whole or some of its cards, added to a test (a name, a date): its cards tagged in Anki, and its sheet says how to review them all (custom study, a filtered deck). On the computer, **Revise now in Anki** makes the filtered deck; on Android, **Open in AnkiDroid**. The lessons not in Anki yet are sent from the test's sheet.

**Children and settings**

- 🧒 **Children**: a card each, with a first name, a class typed freely (another country's, Prépa, university…), its decks and instructions for the AI. The AI is told the class and the instructions, never the first name. The next lesson is for the child chosen.
- 💾 **Back up or move my lessons**: every lesson in one file (photos, cards, pictures, sounds), with the children, the tests and your prompts, no key or password; imported on another computer or in the Android app. A lesson's cards already in Anki are found again, never added twice.
- **About**: Notosaurus is free software (AGPL-3.0), with the privacy policy and the libraries' licences.

**For developers**

- `notosaurus-core` (in `core/`): the AI and card logic as a package of its own. The Notosaurus relay's API, `core/relay-api-v1.json`, is frozen for each released app (`core/relay-api-releases/`), and a test refuses a change that would break one.
- The Android app in `android/`, built and tested with the same page; device tests with real AnkiDroid (on Mondays, several of its versions side by side).
- Notosaurus's prompts and the AI's fixed rules in files of their own: `static/prompts/<lang>/`, `core/notosaurus_core/rules/`, `core/notosaurus_core/typst_rules/`.
- `NOTOSAURUS_PICTURE_SERVICE` and `NOTOSAURUS_PICTURE_MODEL` (`.env`) give the pictures' service and model by default (Docker).

### Changed

- A picture can be on any card in Anki, no longer on a card of its own: a dictation, a reversed or typed card keeps its picture. **Anki asks for a full sync once.** The picture cards sent by 1.0.0 are sent again as new notes; the old ones are offered for deletion (their review history isn't kept).
- A photo is kept as taken, no longer turned upright by guess (sometimes upside down): **↻** turns it.
- Pictures where they truly help (a work of art, a person, a place, an animal), never on every card; a picture that would give the answer away goes on the back. **Settings → Instructions for the AI → 🖼️ Pictures on the cards** turns them off.
- Every card says its deck above its question, small (the subject and the lesson). A front that allows another right answer says what tells it apart.
- Only short answers are typed (a word or two); a definition or a sentence is said in one's own words.
- **Did you know?** and the helps on the back are settings (on by default), no longer switches under the prompt. The **Add the reverse card** switch is gone: how the cards are asked comes from the prompt, and can be changed in the correction ("one way only").
- The voices are slowed only for a language being learned and for dictations.
- The review's cards are a third shorter: their buttons on the front's line, Report and Delete behind **⋯**.
- The page speaks of children, not of Anki profiles.
- The big button at the bottom is always the next action: photograph the lesson, generate the cards, or generate from the prompt alone once it says what to learn.
- Notosaurus's prompts reviewed: none imposes French or English any more, and each lesson gets a deck of its own.
- The AI only makes learning material suited to pupils; anything else is refused with a clear message. Lessons on hard topics (history, biology, health) still work.
- The pages load nothing from elsewhere (no CDN, no Google Fonts): they work offline, and no third party sees their visits.
- Gemini not answering is given up on after 45 s for the next model, instead of waiting forever.

### Fixed

- A card corrected after a send updates its own note in Anki (its review history kept) instead of adding a second one; a lesson whose deck changed moves its cards there. A part named like the deck's last level no longer makes a second deck inside it.
- A formula shows as meant when the AI wrote it with a single backslash or with brackets for an interval; formulas in the info and "Did you know?" are drawn, no longer shown as LaTeX.
- Accents written as HTML entities ("trach&eacute;e"), tags or Markdown the AI wrote in a card: made plain text.
- 🔊 reads a back in Russian, Greek, Chinese, Japanese, Arabic…; a phonetic transcription is no longer read aloud; a dictation's sound no longer makes words up; listening again no longer plays two voices at once.
- A dictation in the pupil's own language gets its voice with **Automatic**.
- Without a photo, an unchanged prompt no longer makes cards on a made-up subject: the page says to write what to learn.
- A picture an image service refused or didn't give leaves that card without one, no longer failing the lesson's other pictures. A picture drawn by Gemini is counted at the image's price (it counted a twentieth of it).
- Claude makes lessons again with the helps or the fun facts on.
- A lesson keeps to its 10 pages, from the gallery and the camera too.
- Instructions typed while the page was starting are no longer replaced; a long back is seen whole in the review; scrolling the lessons no longer moves the page behind.
- Notosaurus's prompts as each language writes them (Brazilian Portuguese throughout).

### Security

- Notosaurus answers only when opened by an IP address, `localhost` or `NOTOSAURUS_PUBLIC_URL`: a website open on the computer can no longer reach it (DNS rebinding) to read the lessons or change the settings. A `Host` with a line break or an impossible port is refused.
- A new settings password needs 8 characters; after 5 wrong ones the device must wait, longer at each try. Those typed on the computer itself never lock it out.
- A card's id is checked (it names its picture's file); a photo over 4 MB, or claiming an enormous size in a few kilobytes, is refused.
- Nothing of a lesson in the logs any more, on the computer and on the relay.
- The Docker image runs Notosaurus as its own user, not root. A `notosaurus-data` volume made by an older image is handed over once with `docker run --rm -u 0 -v notosaurus-data:/data notosaurus chown -R notosaurus: /data`.

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
