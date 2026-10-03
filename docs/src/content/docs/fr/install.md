---
title: "Installation avancée"
description: "Faire tourner Notosaurus en autonome ou avec Docker, sans le greffon Anki, et ses variables d'environnement."
---

Le [greffon Anki](../getting-started/) est la façon la plus simple d'utiliser Notosaurus. Pour le
faire tourner seul, par exemple sur un serveur toujours allumé à la maison, installe-le **en
autonome** ou avec **Docker**.

Les différences avec le greffon :

- Notosaurus tourne même quand Anki est fermé ; le téléchargement du `.apkg` marche toujours.
- **Ajouter à Anki** a besoin d'Anki ouvert sur l'ordinateur, avec le greffon
  [AnkiConnect](https://ankiweb.net/shared/info/2055492159) (code `2055492159`).
- Les réglages (`/admin.html`) sont accessibles depuis le réseau, protégés par un **mot de passe
  d'administration** créé à la première visite.

## En autonome

Avec Python 3.13 :

```sh
git clone https://github.com/cchabanois/notosaurus.git
cd notosaurus
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --host 0.0.0.0
```

Ouvre http://localhost:8000 sur l'ordinateur. Pour le téléphone (même Wi-Fi) : **⚙️ →
Téléphones**, et scanne le QR code.

## Docker

```sh
docker build -t notosaurus .
docker run -p 8000:8000 -v notosaurus-data:/data --env-file .env \
  -e NOTOSAURUS_PUBLIC_URL=http://<ip-de-l-ordinateur>:8000 notosaurus
```

Dans Docker, Notosaurus ne voit pas l'adresse de l'ordinateur : `NOTOSAURUS_PUBLIC_URL` la met
dans le QR code des téléphones. L'ordinateur lui-même passe aussi par le réseau de Docker : ouvre
**⚙️ → Téléphones** et utilise une fois le lien sous le QR code.

## Variables d'environnement

Copie `.env.example` en `.env`. Ces variables donnent les valeurs par défaut : ce qui est
enregistré dans la page des réglages l'emporte.

| Variable | Rôle |
|---|---|
| `NOTOSAURUS_LLM` | service d'IA : `gemini`, `anthropic`, `openai`, `openrouter`, `compatible` |
| `GEMINI_API_KEY`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `OPENROUTER_API_KEY` | clés d'API |
| `NOTOSAURUS_MODEL` | le modèle (vide : le choix de Notosaurus pour le service) |
| `NOTOSAURUS_FALLBACK_MODEL` | modèles Gemini essayés quand le principal est surchargé |
| `NOTOSAURUS_COMPATIBLE_BASE_URL`, `NOTOSAURUS_COMPATIBLE_API_KEY` | un autre service compatible OpenAI (Ollama : `http://localhost:11434/v1`) |
| `NOTOSAURUS_DATA` | le dossier de données (par défaut : `data`) |
| `NOTOSAURUS_ANKICONNECT_URL`, `NOTOSAURUS_ANKICONNECT_KEY` | AnkiConnect (par défaut : `http://localhost:8765`) |
| `NOTOSAURUS_PUBLIC_URL` | l'adresse du QR code des téléphones, quand Notosaurus ne la voit pas (Docker, un proxy) |

## HTTPS et hors de la maison

Voir [Confidentialité et sécurité](../privacy/#le-wi-fi) : Tailscale donne à Notosaurus une
adresse HTTPS accessible depuis tes appareils partout, sans l'exposer sur Internet.
