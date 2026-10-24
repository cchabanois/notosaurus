<p align="center"><img src="static/logo.webp" alt="Notosaurus logo: a dinosaur with a school bag, surrounded by flashcards" width="320"></p>

# Notosaurus

> From school bag to flashcards: snap a lesson, get an Anki deck.

<p align="center"><a href="https://www.youtube.com/shorts/Q7bUTMEj6Kk"><img src="docs/src/assets/demo.gif" alt="Notosaurus on a phone: a notebook page becomes Anki cards. Click to watch the full demo on YouTube." width="280"></a><br>
▶ <a href="https://www.youtube.com/shorts/Q7bUTMEj6Kk">Watch the full demo</a> (75 s) · 📖 <a href="https://cchabanois.github.io/notosaurus/">Documentation</a> · ☕ <a href="https://ko-fi.com/notosaurus">Support on Ko-fi</a></p>

Take photos of a lesson with your phone. A vision AI reads the pages and drafts Anki cards. You review and fix them, then send them straight into Anki or AnkiDroid, or download a `.apkg`.

Notosaurus was first built for learning languages (vocabulary and sentences, with audio), and now makes cards for any subject: history dates, definitions and theorems, diagrams, formulas, dictations, poems to learn by heart…

## What it does

The [documentation](https://cchabanois.github.io/notosaurus/) explains each of these in detail.

**From the lesson**

- **Photos or PDFs**, up to 10 pages per lesson. A digital PDF's text goes to the AI with its page: the exact words, no misreading. A child's name or school can be blacked out with a finger before the photo is sent.
- **Instructions** say what to make: about twenty come with Notosaurus (vocabulary, conjugation, questions, dates and landmarks, definitions and properties, fill in the blanks, multiple choice, diagram to complete, dictation, by heart…), and **Automatic** chooses from the lesson. You can write your own.
- **Complete a lesson** days later with its next pages: only the new pages' cards are made.

**The cards**

- **Question and answer**, **fill in the blanks** (cloze), **multiple choice** and **true/false**, the same on every Anki.
- **Diagrams**: every label hidden behind a number, one card per label; the masks can be moved in the review.
- **Formulas** in MathJax, and **figures** (geometry, labelled shapes) drawn exactly as SVG.
- **Pictures** where they truly help: a free picture found first (Wikimedia Commons, Openverse), else one drawn by an image model.
- **Audio**: the back read aloud, embedded in the deck, so it plays everywhere, even offline. **Dictations** and **typed answers** for spelling.
- **"Did you know?"** facts and **helps on the back** (why the answer is the answer, a way to remember it).

**The review**

- Edit, delete or add cards, or ask the AI in plain words ("remove the card about the father", "you forgot the colours").
- **💬** explains a card at a pupil's level; **⚑** reports a wrong or unsuitable content.

**Into Anki**

- **Straight into Anki** desktop or **AnkiDroid**, or as a `.apkg`. Sending a corrected lesson again updates its cards instead of duplicating them, and cards left over in Anki are listed, to delete if you want.
- **✎ Notosaurus** under every answer in Anki opens the card in Notosaurus to correct it, its review history kept.
- **Tests to prepare**: gather several lessons, or some of their cards, under one tag, and revise them together with Anki's custom study ("Revise now in Anki" on the computer).

**For families**

- **One card per child** (class, decks, standing instructions), linked to their Anki profile; each child has their own lessons, and **⧉ Copy for…** gives one to another child.
- **English, French, Spanish, German, Italian and Portuguese (Brazil)**, and adding a language takes a single file.

## Three ways to run it

### The Android app (recommended)

Coming soon to Google Play. Notosaurus on its own, on the phone: no computer, no AI key. Photograph the lesson, check the cards, and they go straight into AnkiDroid.

- **The same Notosaurus** as on the computer: the same page, instructions, card types, review and languages, with pictures, voices, diagrams, figures, children and tests to prepare. Only the `.apkg` download is left out: the cards go into AnkiDroid.
- **The Notosaurus service does the work**: the AI (Google's Gemini), the voices and the pictures (drawn, or found free on Wikimedia Commons, Openverse and Pixabay). It works in the European Union, and keeps neither the photos nor the cards.
- **Lessons stay on the phone**, in the app's private storage. The cards are written into AnkiDroid, which syncs them with AnkiWeb as usual. AnkiDroid asks once for its permission; when it's missing, the app opens its Google Play page.
- **Made for the phone**: the camera, the gallery or a PDF; 🎤 to dictate an instruction or a correction; 🎓 opens AnkiDroid in one tap; ✎ Notosaurus under an answer in AnkiDroid opens the card in the app; a test's cards opened in AnkiDroid, to make its filtered deck.
- **A subscription through Google Play**, by the month or by the year, with credits each month (a drawn picture says what it costs before). The first lesson starts a free trial: no card, once per phone.

**With your computer, for free.** In the app's settings, *📍 Where does Notosaurus work?* → *💻 On my computer*, then scan the QR code of *Anki → Tools → Notosaurus → Open on the phone*: the app shows the computer's page, and lessons, AI and cards stay on the computer, with the [add-on](#the-anki-add-on) below. Each mode keeps its own lessons, and the icon's shortcuts switch between them.

The app's code is in [`android/`](android/README.md).

### The Anki add-on

Notosaurus starts and stops with Anki desktop and writes cards directly into the open profile. You use it from the phone's browser (or the app), on the same Wi-Fi. You don't need AnkiConnect.

1. Download `notosaurus-<version>.ankiaddon` from the [latest release](https://github.com/cchabanois/notosaurus/releases/latest) (to build it yourself, see [CONTRIBUTING.md](CONTRIBUTING.md)).
2. Double-click the file (or *Tools → Add-ons → Install from file*) and restart Anki.
3. On first start, the add-on asks before installing its components into `Anki2/notosaurus-runtime/`, next to the add-ons (about 300 MB, kept by add-on updates, removed with the add-on; outside the add-on's own folder, so that Anki can update it while Notosaurus runs, Windows included): [uv](https://docs.astral.sh/uv/), Python 3.13 and the Python libraries. It uses the uv shipped with Anki 25.07 to 26.05 or one already installed; otherwise it downloads a pinned uv release from GitHub and checks its SHA-256.
4. The setup assistant opens: choose the AI service and paste its key, then scan the QR code with the phone and add the page to the home screen. See [Getting started](https://cchabanois.github.io/notosaurus/getting-started/).

Everything else is in the **Tools → Notosaurus** menu: open, open on the phone (QR code), getting started, settings, server status, restart, log and help.

- **Settings** (AI provider, API keys…) only open on the computer, without a password. Phones are refused, so API keys never travel over the Wi-Fi and children can't change them.
- The server listens on port 8000 by default. The port and other options are in the add-on's config (*Tools → Add-ons → Notosaurus → Config*).

### Standalone or with Docker

Notosaurus runs on its own, even when Anki is closed, for instance on a home server. The `.apkg` download always works. "Add to Anki" needs Anki desktop open with the [AnkiConnect](https://ankiweb.net/shared/info/2055492159) add-on.

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --host 0.0.0.0
```

Then open http://localhost:8000 on the computer. For the phone (same Wi-Fi): ⚙️ → **Phones**, and scan the QR code. The ⚙️ page is reachable from the network in this mode, protected by an admin password created on the first visit.

Docker and the environment variables: see [Advanced installation](https://cchabanois.github.io/notosaurus/install/).

## Good to know

- **Always review the cards.** Even good models misread a word now and then.
- **Children's schoolwork is private data.** A notebook page often shows the child's name: hide it with 🖍️ before sending. In the app, photos go through the Notosaurus service to Gemini, without being kept there (see the [app's privacy policy](https://cchabanois.github.io/notosaurus/app-privacy/)). On the computer, they go to the AI provider you choose (see [Privacy and security](https://cchabanois.github.io/notosaurus/privacy/)).

## On the computer

For the add-on, standalone and Docker, and for the app's "💻 On my computer" mode, which uses them. The app "📱 On this phone" needs none of this: no AI key, and its own settings page.

### Settings

The ⚙️ page chooses:

- the AI service and model, and the image model for the pictures;
- API keys, which are stored in `data/settings.json` (readable only by the server's user) and never sent back to the browser;
- a voice per language, and its speed;
- standing instructions for every child ("Spanish from Spain"), added to the prompt of each lesson; each child's own (their class, decks and instructions) are in their card, 🧒 on the main page;
- pictures, "Did you know?" facts and helps on the back (on by default);
- AnkiConnect and syncing options.

Environment variables (see `.env.example`) provide defaults. Whatever is saved on the ⚙️ page wins.

#### AI providers

| Provider | Notes |
|---|---|
| **Gemini** (default) | Official `google-genai` SDK. A free [AI Studio](https://aistudio.google.com/) key is enough to start. Falls back to other models when the main one is overloaded. |
| **Claude** | Official `anthropic` SDK. |
| **OpenAI** | GPT models, with an OpenAI key. |
| **OpenRouter** | One key for Gemini, Claude, GPT, Mistral…; the exact cost of each call. ⚙️ suggests its `~…-latest` models (always the latest version of a family), the latest Gemini Flash by default. |
| **Other OpenAI-compatible service** | Any address: Ollama or LM Studio at home, Mistral… |
| **Demo** (`fake`) | Canned cards whatever the photo, no key and no cost: for the tests and for working on the interface. Not offered in ⚙️; set `NOTOSAURUS_LLM=fake` in `.env`. |

For the last three, *Load models* lists only models that accept images (and structured output, when the service says so). *Test* sends a small image to check that the model can read it and answer in JSON. The output format is always forced with a JSON schema. The user's prompt only says *what* to extract.

Local models (Ollama, LM Studio) work, but they read handwritten pages much less reliably. Claude and local models can't draw: pictures are then drawn by another service, chosen in ⚙️. What each costs: see [AI services and costs](https://cchabanois.github.io/notosaurus/ai-services/).

### Data

There is no database. Everything is plain files under `data/` (or `NOTOSAURUS_DATA`), so backing up Notosaurus means copying that folder.

```
data/
  settings.json                              settings and API keys
  prompts.json                               saved prompts
  children.json                              the children: class, decks, instructions
  exams.json                                 tests to prepare
  ai-calls.json                              every AI call and its cost
  lessons/
    2026-09-28-espagnol-lecon-5-la-famille/  one folder per lesson
      lesson.json                            deck, cards, prompt, voice, owner, dates
      page-1.jpg, page-2.jpg                 photos
      audio/la-madre-3f2a1c9e.mp3            card audio (included in the .apkg)
      images/                                card pictures, and diagrams with their labels hidden or shown
  cache/                                     voices and pictures, safe to delete
```

In the add-on, `data/` lives in the add-on's `user_files/` folder.

### Good to know on the computer

- **A local model keeps the photos at home**, at the cost of accuracy.
- **Only paired devices.** On the Wi-Fi, only the computer itself and the devices that scanned Notosaurus's QR code (Tools → Notosaurus → Open on the phone, or ⚙️ → Phones) can use it: the others can't spend your AI credits or delete lessons. "Disconnect every phone" in ⚙️ → Phones unpairs them all (a phone lost or lent).
- **Plain HTTP on the local network.** The camera works over plain HTTP, and the page can be added to the home screen as a shortcut. Pairing stops the curious and other websites, not someone spying on the Wi-Fi traffic: keep your Wi-Fi protected (WPA2/WPA3).
- **Never expose AnkiConnect or Notosaurus to the Internet.** Keep them on your local network.
- **edge-tts is unofficial.** The computer's voices come from [edge-tts](https://github.com/rany2/edge-tts); Microsoft could shut it down.

## Languages

The interface follows the page's language picker, then Anki's language (in the add-on), then the browser's, and falls back to English.

To add a language, see [CONTRIBUTING.md](CONTRIBUTING.md#adding-a-language): it takes a single file.

## Support

Notosaurus is free software, with no ads and no tracking; the add-on is free to use. If it helps your family, you can [buy me a coffee on Ko-fi](https://ko-fi.com/notosaurus) ☕.

## Contributing

Setting up, tests, architecture, translations and releases: see [CONTRIBUTING.md](CONTRIBUTING.md). The Android app: see [android/README.md](android/README.md).

## License

[AGPL-3.0](LICENSE)
