# notosaurus-android

Private. Notosaurus for Android: photos of a lesson become cards in AnkiDroid,
through the Notosaurus relay (`/v1`, see the public repository's
`core/notosaurus_core/relay_api.py` and `core/relay-api-v1.json`). No computer,
no API key.

## Status: prototype 2, the web page in the app

The app shows **Notosaurus's own page** (the public repository's `static/`: the same
screens, prompts and languages as on the computer) in a WebView. What the computer's
server does for it (`/api/...`, app/main.py) is done on the phone by `LocalServer`:
the AI through the relay, the lessons on the phone, the cards into AnkiDroid.

```
Notosaurus page (static/) ──/api──▶ LocalServer (Ktor, 127.0.0.1) ──┬── relay /v1 (AI)
                                                                     ├── Lessons (phone storage)
                                                                     └── AnkiDroid (cards)
```

Checked on an emulator (Android 15, AnkiDroid 2.25.0) against a relay on the
computer (demo AI): the page with its 13 prompts; a photo from the gallery and one
from the camera; cards generated; a correction in plain words ("add the brother": 7
cards, Undo); an explanation (💬, with its follow-ups); "Add to Anki" (only the new
card: the others were already there); the lesson kept after a restart.

| File | |
|---|---|
| `MainActivity.kt` | the WebView: the page's file inputs (camera, gallery, PDF), back button, AnkiDroid's permission |
| `LocalServer.kt` | the page's `/api` routes, and its files (assets/web/) |
| `assets/page/admin.html`, `settings.js` | the app's settings page (the page's ⚙️): licence and its credits, AnkiDroid, standing instructions, lessons on the phone, relay address (advanced); texts under `android` in the web page's i18n files |
| `Preferences.kt` | the settings, kept on the phone |
| `Lessons.kt` | lessons on the phone, as the computer keeps them (lesson.json, page-N.jpg) |
| `Relay.kt`, `Api.kt` | the relay's client (`/v1`), its errors |
| `Anki.kt` | AnkiDroid's API: note type, decks and sub-decks, notes, duplicates |

The page is copied at build time from the public repository checked out next to this
one (`../notosaurus/static`, or `-Pnotosaurus.web=<path>`). The app's own files
(`assets/page/`) are served first, then the web page's: its `admin.html` replaces the
computer's. The relay's address is the emulator's by default (`LocalServer.DEFAULT_RELAY`),
changed in the settings ("Advanced"); the licence key is entered there too.

Not done yet (answered as "nothing" for now): voices and audio previews, pictures and
figures, regenerating a lesson, rotating a photo, `.apkg` export, sharing lessons,
updating notes sent before; photos aren't turned upright (the relay's `turns`).
The page also needs small changes for the phone: no Anki profile badge ("none"), no
`.apkg` button, Alpine.js and KaTeX bundled instead of a CDN (offline use).

## Build and try

Android SDK with platform 37 (`sdkmanager "platforms;android-37.0"`), JDK 17+.

```sh
./gradlew testDebugUnitTest   # the tests (JVM: no phone needed)
./gradlew assembleDebug       # app/build/outputs/apk/debug/app-debug.apk
```

The tests call LocalServer's routes as the page does, with a fake relay
(MockWebServer) and a fake AnkiDroid (`LocalServerTest`), and check the relay's
client (`RelayTest`) and the lessons' storage (`LessonsTest`). AnkiDroid's API
itself is only tried on a device.

A relay on the computer (in `notosaurus-cloud`), reachable from the phone on the same Wi-Fi:

```sh
RELAY_STORE=memory RELAY_LLM=fake RELAY_DEV_KEY=nts_dev .venv/bin/uvicorn --factory relay.main:create_app --host 0.0.0.0 --port 8080
```

The app uses `http://10.0.2.2:8080` (the computer, from the emulator) and the key
`nts_dev`.

## What we learnt

- **AnkiDroid's API** (`com.github.ankidroid:Anki-Android:api-v1.1.0`, JitPack; the
  only published version) does what the app needs: custom note types with their CSS,
  decks and sub-decks (`::`), notes in bulk with tags, duplicates by first field,
  updating fields, media (`addMediaFromUri`, not tried yet).
- The user grants **one permission** (AnkiDroid's own dialog: "access existing
  notes, cards, note types and decks, as well as create new ones"). AnkiDroid must
  have been opened once (its collection created).
- `<queries>` for `com.ichi2.anki` is needed (Android 11+).

## Before a real app

- **Client version**: the relay checks `X-Notosaurus-Version` against the PC app's
  versions (minimum 1.1.0); the app sends "1.1.0" for now. The contract needs a
  client kind (e.g. "android/0.1.0") with its own minimum.
- Notosaurus's **note types** (cloze, multiple choice, typing, diagram masks,
  pictures) instead of the prototype's front/back: their templates and CSS, from
  the PC app's `anki.py` (exposed by the relay, or copied by a script).
- **Audio**: the PC uses edge-tts; here Android's text-to-speech, or a `/v1/speak`.
- **Diagrams**: cropped images and masks (`diagrams.py` on the PC): a relay route,
  or done in the app.
- Updating notes sent before (stable ids), pictures (`/v1/picture`).
- The page's AGPL code in a closed app: fine because Notosaurus has a single author
  and a CLA; keep the CLA for any outside contribution to `static/`.
- Licence through Google Play billing; Play Store listing (an app **for parents**,
  not "for children", see the Families policy); a "my own key" mode.
- The final application id: `app.notosaurus` here, unchangeable once published.
