# Notosaurus for Android

Photos of a lesson become cards in AnkiDroid, through the Notosaurus relay (`/v1`,
see `core/notosaurus_core/relay_api.py` and `core/relay-api-v1.json`). No computer,
no API key. Not published yet.

## Status: prototype 2, the web page in the app

The app shows **Notosaurus's own page** (the repository's `static/`: the same
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
| `assets/page/unreachable.html` | "With my computer", the computer not answering: try again, scan again, use without computer |
| `Shortcuts.kt` | the icon's shortcuts ("Without computer", "With my computer"), once a computer is connected |
| `Preferences.kt` | the settings, kept on the phone |
| `Lessons.kt` | lessons on the phone, as the computer keeps them (lesson.json, page-N.jpg) |
| `Relay.kt`, `Api.kt` | the relay's client (`/v1`), its errors |
| `Anki.kt` | AnkiDroid's API: note type, decks and sub-decks, notes, duplicates. Asked for at the first "Add to Anki": its Play Store page when it's missing, its permission dialog when it isn't allowed yet |

The page is copied at build time from this revision's `static/` (another with
`-Pnotosaurus.web=<path>`): a change to the page and the app goes in one pull request,
and a build always ships the page it was tested with. The app's own files
(`assets/page/`) are served first, then the web page's: its `admin.html` replaces the
computer's. The relay's address is the emulator's by default (`LocalServer.DEFAULT_RELAY`),
changed in the settings ("Advanced"); the licence key is entered there too.

Not done yet (answered as "nothing" for now): voices and audio previews, pictures and
figures, regenerating a lesson, rotating a photo, `.apkg` export, sharing lessons,
updating notes sent before; photos aren't turned upright (the relay's `turns`).
The page also needs small changes for the phone: no Anki profile badge ("none"), no
`.apkg` button, Alpine.js and KaTeX bundled instead of a CDN (offline use).

## Two modes

- **Without computer** (the default): the app's own page, the AI through the relay
  (subscription), the cards into AnkiDroid.
- **On my computer** (free, for the Anki add-on's users): in the settings, "📍 Where
  does Notosaurus work?" → "💻 On my computer": scan the QR code of *Anki → Tools → Notosaurus → Open on the phone*
  (Google's code scanner: no camera permission; Google Play services download it at
  first use), or type the address. Checked (the computer's `/api/lang`), kept, and
  the app shows the computer's page instead of its own: lessons, AI and cards stay
  on the computer. The computer not answering: `unreachable.html`. Back to the phone:
  that page, or the icon's shortcuts. Each mode keeps its own lessons.

The settings point to it where it matters: the subscription section, without a
licence, says the app is free with the add-on. In the computer's mode the settings
show only that choice (with the computer's name, from its `/api/config`), the
language and "About": the AI's instructions and the rest are the computer's own.

## Build and try

Android SDK with platform 37 (`sdkmanager "platforms;android-37.0"`), JDK 17+.

```sh
./gradlew testDebugUnitTest   # the tests (JVM: no phone needed)
./gradlew assembleDebug       # app/build/outputs/apk/debug/app-debug.apk
```

The tests call LocalServer's routes as the page does, with a fake relay
(MockWebServer) and a fake AnkiDroid (`LocalServerTest`), and check the relay's
client (`RelayTest`) and the lessons' storage (`LessonsTest`). They run on every pull
request that touches `android/` or `static/`.

### Tests on a device

What only a device shows (`app/src/androidTest`): `AnkiDroidTest` (AnkiDroid's real
API: note type, decks and sub-decks, duplicates), `AppTest` (the activity, its
WebView and the page, a lesson made with a fake relay and sent to AnkiDroid),
`ModesTest` (a fake computer's page, the page when it stops answering, back to the
phone). With an emulator (or a phone) connected and AnkiDroid installed (the
`dev-AnkiDroid-<version>-play-universal.apk` of its releases; never opened is fine):

```sh
./gradlew connectedDebugAndroidTest
```

⚠️ Gradle installs the app for the tests and **uninstalls it afterwards**: its lessons
and settings on that device are gone. Use an emulator, not your own phone.

On GitHub, on demand: Actions → "Android on a device" → Run workflow (an emulator,
AnkiDroid 2.25.0; a few minutes). Without AnkiDroid the tests are skipped.

Without a computer, the app needs a relay implementing the `/v1` API. Notosaurus's own
isn't public; run on the computer for development (demo AI, a test licence), reachable
from the phone on the same Wi-Fi:

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
- Licence through Google Play billing; Play Store listing (an app **for parents**,
  not "for children", see the Families policy); a "my own key" mode.
- **Android 17's local network permission**: targeting SDK 37, `ACCESS_LOCAL_NETWORK`
  (group "Nearby devices") will be needed for "With my computer" (LAN; WebView traffic
  too). Ask for it when a computer is connected, after a sentence of ours; check that
  LocalServer (127.0.0.1) doesn't need it.
- The final application id: `app.notosaurus` here, unchangeable once published.
