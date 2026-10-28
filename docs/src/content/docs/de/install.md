---
title: "Erweiterte Installation"
description: "Notosaurus eigenständig oder mit Docker betreiben, ohne die Anki-Erweiterung, und seine Umgebungsvariablen."
---

Die [Anki-Erweiterung](../getting-started/) ist der einfachste Weg, Notosaurus zu nutzen. Um es für
sich allein laufen zu lassen, zum Beispiel auf einem immer eingeschalteten Heimserver, installiere
es **eigenständig** oder mit **Docker**.

Unterschiede zur Erweiterung:

- Notosaurus läuft auch, wenn Anki geschlossen ist; der Download als `.apkg` funktioniert immer.
- **Zu Anki hinzufügen** braucht Anki am Computer geöffnet, mit der Erweiterung
  [AnkiConnect](https://ankiweb.net/shared/info/2055492159) (Code `2055492159`).
- Die Einstellungen (`/admin.html`) sind aus dem Netzwerk erreichbar, geschützt durch ein
  **Admin-Passwort**, das beim ersten Besuch angelegt wird.

## Eigenständig

Mit Python 3.13:

```sh
git clone https://github.com/cchabanois/notosaurus.git
cd notosaurus
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --host 0.0.0.0
```

Öffne http://localhost:8000 auf dem Computer. Für das Handy (im selben WLAN): **⚙️ → Handys**, und
scanne den QR-Code.

## Docker

```sh
docker build -t notosaurus .
docker run -p 8000:8000 -v notosaurus-data:/data --env-file .env \
  -e NOTOSAURUS_PUBLIC_URL=http://<IP-des-Computers>:8000 notosaurus
```

In Docker kann Notosaurus die Adresse des Computers nicht sehen: `NOTOSAURUS_PUBLIC_URL` setzt sie
in den QR-Code der Handys. Auch der Computer selbst geht über das Netzwerk von Docker: Öffne
**⚙️ → Handys** und benutze einmal den Link unter dem QR-Code.

## Umgebungsvariablen

Kopiere `.env.example` nach `.env`. Diese Variablen geben die Standardwerte: Was auf der
Einstellungsseite gespeichert ist, hat Vorrang.

| Variable | Verwendung |
|---|---|
| `NOTOSAURUS_LLM` | KI-Dienst: `gemini`, `anthropic`, `openai`, `openrouter`, `compatible` |
| `GEMINI_API_KEY`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `OPENROUTER_API_KEY` | API-Schlüssel |
| `NOTOSAURUS_MODEL` | das Modell (leer: die Wahl von Notosaurus für den Dienst) |
| `NOTOSAURUS_FALLBACK_MODEL` | Gemini-Modelle, die versucht werden, wenn das Hauptmodell überlastet ist |
| `NOTOSAURUS_COMPATIBLE_BASE_URL`, `NOTOSAURUS_COMPATIBLE_API_KEY` | ein anderer OpenAI-kompatibler Dienst (Ollama: `http://localhost:11434/v1`) |
| `NOTOSAURUS_PICTURE_SERVICE`, `NOTOSAURUS_PICTURE_MODEL` | der Dienst, der die Bilder der Karten zeichnet (`gemini`, `openai`, `openrouter`, `none`; leer: der der Karten), und sein Modell |
| `NOTOSAURUS_DATA` | der Datenordner (Standard: `data`) |
| `NOTOSAURUS_ANKICONNECT_URL`, `NOTOSAURUS_ANKICONNECT_KEY` | AnkiConnect (Standard: `http://localhost:8765`) |
| `NOTOSAURUS_PUBLIC_URL` | die Adresse im QR-Code der Handys, wenn Notosaurus sie nicht sehen kann (Docker); neben IP-Adressen und `localhost` der einzige Name, auf den Notosaurus antwortet |
