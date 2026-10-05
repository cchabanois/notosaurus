# notosaurus-android

Private. Notosaurus for Android: photos of a lesson become cards in AnkiDroid,
through the Notosaurus relay (`/v1`, see the public repository's
`core/notosaurus_core/relay_api.py` and `core/relay-api-v1.json`). No computer,
no API key.

## Status: prototype

One screen: the relay's address and a licence key, photos (camera or gallery),
the prompt, the cards, "Add to AnkiDroid". Checked end to end on an emulator
(Android 15, AnkiDroid 2.25.0) against a relay run on the computer: connection
test, a photo sent in multipart, cards back, AnkiDroid's permission asked, 6 cards
added under `Espagnol::Leçon 5 - La famille`, sent again → 6 duplicates, none added.

| File | |
|---|---|
| `Api.kt` | the relay's requests and answers (the part used), errors `{code, params}` |
| `Relay.kt` | the relay's client (OkHttp): `/v1/account`, `/v1/extract` in multipart |
| `Photos.kt` | photos upright, at most 1568 px, JPEG (as the relay's AI sees them) |
| `Anki.kt` | AnkiDroid's API: our note type, decks and sub-decks, notes, duplicates |
| `MainActivity.kt` | the screen (Compose) |

## Build and try

Android SDK with platform 37 (`sdkmanager "platforms;android-37.0"`), JDK 17+.

```sh
./gradlew assembleDebug    # app/build/outputs/apk/debug/app-debug.apk
```

A relay on the computer (in `notosaurus-cloud`), reachable from the phone on the same Wi-Fi:

```sh
RELAY_STORE=memory RELAY_LLM=fake RELAY_DEV_KEY=nts_dev .venv/bin/uvicorn --factory relay.main:create_app --host 0.0.0.0 --port 8080
```

In the app: relay `http://<computer-ip>:8080` (`http://10.0.2.2:8080` from the
emulator), key `nts_dev`.

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
- Reviewing and correcting the cards (`/v1/revise`), lessons kept on the phone,
  updating notes sent before (stable ids), pictures (`/v1/picture`).
- Licence through Google Play billing; Play Store listing (an app **for parents**,
  not "for children", see the Families policy); a "my own key" mode.
- The final application id: `app.notosaurus` here, unchangeable once published.
