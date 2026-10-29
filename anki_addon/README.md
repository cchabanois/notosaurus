# The Anki add-on

Notosaurus inside Anki desktop: the add-on starts the Notosaurus server (`app/`) when Anki
starts, stops it with Anki, and lets it write the cards straight into the open profile. It
adds the **Tools → Notosaurus** menu. For using it, see the user documentation
([In Anki desktop](https://cchabanois.github.io/notosaurus/in-anki/)).

```
Anki (this add-on) ──starts──▶ Notosaurus server (app/, its own process, port 8000)
       ▲                                   │
       └──── bridge.py (127.0.0.1) ◀───────┘  "Add to Anki": the AnkiConnect actions it needs
```

| File | |
|---|---|
| `__init__.py` | the add-on's entry point: the menu, the server started and stopped with Anki, the first start (installing the components, then the setup assistant), the phone's QR code |
| `launcher.py` | the server as a separate process: in the packaged add-on, `uv` installs Python 3.13 and the dependencies once (`Anki2/notosaurus-runtime/`), then runs `server/`; in development, this repository's `.venv` |
| `bridge.py` | a small AnkiConnect-compatible endpoint inside Anki, on 127.0.0.1 with a random key: only the actions `app/ankiconnect.py` uses, so the same server code works with the real AnkiConnect (standalone) or without it (the add-on) |
| `config.json`, `config.md` | the add-on's options (Tools → Add-ons → Notosaurus → Config) and their help: `autostart`, `host`, `port`; `source`, `python`, `data` for development |
| `manifest.json` | the add-on's name and package for Anki |

The menu's texts come from `static/i18n/<lang>.json` (`addon.*`), in Anki's language.

## Developing

Link this folder into Anki's add-ons folder and restart Anki: the add-on then runs the server
from this repository, with its `.venv` and `data/`.

```sh
ln -s "$PWD/anki_addon" ~/.local/share/Anki2/addons21/notosaurus
```

- Build the add-on file: `.venv/bin/python tools/build_addon.py` → `dist/notosaurus-<version>.ankiaddon`
  (this folder, the server's code in `server/`, the pinned requirements).
- Check the packaged add-on installs and starts, outside Anki: `.venv/bin/python tools/check_addon_install.py`.
- Tests: `tests/test_addon*.py`; `tests/test_real_anki.py` runs the bridge against Anki's real engine
  (`pip install -r requirements-anki.txt`).

See also [CONTRIBUTING.md](../CONTRIBUTING.md#developing-the-add-on).
