---
title: "Advanced installation"
description: "Run Notosaurus standalone or with Docker, without the Anki add-on, and its environment variables."
---

The [Anki add-on](../getting-started/) is the simplest way to use Notosaurus. To run it on its
own, for instance on a home server always on, install it **standalone** or with **Docker**.

Differences with the add-on:

- Notosaurus runs even when Anki is closed; the `.apkg` download always works.
- **Add to Anki** needs Anki desktop open with the
  [AnkiConnect](https://ankiweb.net/shared/info/2055492159) add-on (code `2055492159`).
- The settings (`/admin.html`) are reachable from the network, protected by an **admin
  password** created on the first visit.

## Standalone

With Python 3.13:

```sh
git clone https://github.com/cchabanois/notosaurus.git
cd notosaurus
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --host 0.0.0.0
```

Open http://localhost:8000 on the computer. For the phone (same Wi-Fi): **⚙️ → Phones**, and
scan the QR code.

## Docker

```sh
docker build -t notosaurus .
docker run -p 8000:8000 -v notosaurus-data:/data --env-file .env \
  -e NOTOSAURUS_PUBLIC_URL=http://<computer-ip>:8000 notosaurus
```

Inside Docker, Notosaurus can't see the computer's address: `NOTOSAURUS_PUBLIC_URL` puts it in
the phones' QR code. The computer itself goes through Docker's network too: open **⚙️ → Phones**
and use the link under the QR code once.

## Environment variables

Copy `.env.example` to `.env`. These variables give the defaults: what is saved in the settings
page wins.

| Variable | Use |
|---|---|
| `NOTOSAURUS_LLM` | AI service: `gemini`, `anthropic`, `openai`, `openrouter`, `compatible` |
| `GEMINI_API_KEY`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `OPENROUTER_API_KEY` | API keys |
| `NOTOSAURUS_MODEL` | the model (empty: Notosaurus's choice for the service) |
| `NOTOSAURUS_FALLBACK_MODEL` | Gemini models tried when the main one is overloaded |
| `NOTOSAURUS_COMPATIBLE_BASE_URL`, `NOTOSAURUS_COMPATIBLE_API_KEY` | another OpenAI-compatible service (Ollama: `http://localhost:11434/v1`) |
| `NOTOSAURUS_DATA` | the data folder (default: `data`) |
| `NOTOSAURUS_ANKICONNECT_URL`, `NOTOSAURUS_ANKICONNECT_KEY` | AnkiConnect (default: `http://localhost:8765`) |
| `NOTOSAURUS_PUBLIC_URL` | the address in the phones' QR code, when Notosaurus can't see it (Docker) |
