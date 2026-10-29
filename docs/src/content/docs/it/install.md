---
title: "Installazione avanzata"
description: "Far girare Notosaurus in autonomo o con Docker, senza l'add-on di Anki, e le sue variabili d'ambiente."
---

L'[add-on di Anki](../getting-started/) è il modo più semplice di usare Notosaurus. Per farlo girare
da solo, per esempio su un server di casa sempre acceso, installalo **in autonomo** o con
**Docker**.

Differenze con l'add-on:

- Notosaurus gira anche quando Anki è chiuso; il download dell'`.apkg` funziona sempre.
- **Aggiungi ad Anki** richiede Anki aperto sul computer con l'add-on
  [AnkiConnect](https://ankiweb.net/shared/info/2055492159) (codice `2055492159`).
- Le impostazioni (`/admin.html`) sono raggiungibili dalla rete, protette da una **password di
  amministrazione** creata alla prima visita.

## In autonomo

Con Python 3.13:

```sh
git clone https://github.com/cchabanois/notosaurus.git
cd notosaurus
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --host 0.0.0.0
```

Apri http://localhost:8000 sul computer. Per il telefono (stessa Wi-Fi): **⚙️ → Telefoni**, e
scansiona il codice QR.

## Docker

```sh
docker build -t notosaurus .
docker run -p 8000:8000 -v notosaurus-data:/data --env-file .env \
  -e NOTOSAURUS_PUBLIC_URL=http://<ip-del-computer>:8000 notosaurus
```

Dentro Docker, Notosaurus non può vedere l'indirizzo del computer: `NOTOSAURUS_PUBLIC_URL` lo mette
nel codice QR dei telefoni. Anche il computer stesso passa dalla rete di Docker: apri **⚙️ →
Telefoni** e usa una volta il link sotto il codice QR.

## Variabili d'ambiente

Copia `.env.example` in `.env`. Queste variabili danno i valori predefiniti: ciò che è salvato
nella pagina delle impostazioni ha la precedenza.

| Variabile | Uso |
|---|---|
| `NOTOSAURUS_LLM` | servizio di IA: `gemini`, `anthropic`, `openai`, `openrouter`, `compatible` |
| `GEMINI_API_KEY`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `OPENROUTER_API_KEY` | chiavi API |
| `NOTOSAURUS_MODEL` | il modello (vuoto: la scelta di Notosaurus per il servizio) |
| `NOTOSAURUS_FALLBACK_MODEL` | modelli Gemini provati quando quello principale è sovraccarico |
| `NOTOSAURUS_COMPATIBLE_BASE_URL`, `NOTOSAURUS_COMPATIBLE_API_KEY` | un altro servizio compatibile con OpenAI (Ollama: `http://localhost:11434/v1`) |
| `NOTOSAURUS_PICTURE_SERVICE`, `NOTOSAURUS_PICTURE_MODEL` | il servizio che disegna le immagini delle carte (`gemini`, `openai`, `openrouter`, `none`; vuoto: quello delle carte) e il suo modello |
| `NOTOSAURUS_DATA` | la cartella dati (predefinita: `data`) |
| `NOTOSAURUS_ANKICONNECT_URL`, `NOTOSAURUS_ANKICONNECT_KEY` | AnkiConnect (predefinito: `http://localhost:8765`) |
| `NOTOSAURUS_PUBLIC_URL` | l'indirizzo nel codice QR dei telefoni, quando Notosaurus non può vederlo (Docker); oltre agli indirizzi IP e `localhost`, l'unico nome a cui Notosaurus risponde |
