---
title: "Instalación avanzada"
description: "Hacer funcionar Notosaurus en autónomo o con Docker, sin el complemento de Anki, y sus variables de entorno."
---

El [complemento de Anki](../getting-started/) es la forma más sencilla de usar Notosaurus. Para
hacerlo funcionar por sí solo, por ejemplo en un servidor doméstico siempre encendido, instálalo
**en autónomo** o con **Docker**.

Diferencias con el complemento:

- Notosaurus funciona aunque Anki esté cerrado; la descarga del `.apkg` siempre funciona.
- **Añadir a Anki** necesita Anki abierto en el ordenador con el complemento
  [AnkiConnect](https://ankiweb.net/shared/info/2055492159) (código `2055492159`).
- Los ajustes (`/admin.html`) son accesibles desde la red, protegidos por una **contraseña de
  administrador** creada en la primera visita.

## En autónomo

Con Python 3.13:

```sh
git clone https://github.com/cchabanois/notosaurus.git
cd notosaurus
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --host 0.0.0.0
```

Abre http://localhost:8000 en el ordenador. Para el móvil (misma wifi): **⚙️ → Móviles**, y
escanea el código QR.

## Docker

```sh
docker build -t notosaurus .
docker run -p 8000:8000 -v notosaurus-data:/data --env-file .env \
  -e NOTOSAURUS_PUBLIC_URL=http://<ip-del-ordenador>:8000 notosaurus
```

Dentro de Docker, Notosaurus no puede ver la dirección del ordenador: `NOTOSAURUS_PUBLIC_URL` la
pone en el código QR de los móviles. El propio ordenador también pasa por la red de Docker: abre
**⚙️ → Móviles** y usa una vez el enlace bajo el código QR.

## Variables de entorno

Copia `.env.example` en `.env`. Estas variables dan los valores por defecto: lo guardado en la
página de ajustes tiene prioridad.

| Variable | Uso |
|---|---|
| `NOTOSAURUS_LLM` | servicio de IA: `gemini`, `anthropic`, `openai`, `openrouter`, `compatible` |
| `GEMINI_API_KEY`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `OPENROUTER_API_KEY` | claves de API |
| `NOTOSAURUS_MODEL` | el modelo (vacío: la elección de Notosaurus para el servicio) |
| `NOTOSAURUS_FALLBACK_MODEL` | modelos de Gemini probados cuando el principal está saturado |
| `NOTOSAURUS_COMPATIBLE_BASE_URL`, `NOTOSAURUS_COMPATIBLE_API_KEY` | otro servicio compatible con OpenAI (Ollama: `http://localhost:11434/v1`) |
| `NOTOSAURUS_PICTURE_SERVICE`, `NOTOSAURUS_PICTURE_MODEL` | el servicio que dibuja las imágenes de las tarjetas (`gemini`, `openai`, `openrouter`, `none`; vacío: el de las tarjetas) y su modelo |
| `NOTOSAURUS_DATA` | la carpeta de datos (por defecto: `data`) |
| `NOTOSAURUS_ANKICONNECT_URL`, `NOTOSAURUS_ANKICONNECT_KEY` | AnkiConnect (por defecto: `http://localhost:8765`) |
| `NOTOSAURUS_PUBLIC_URL` | la dirección del código QR de los móviles, cuando Notosaurus no puede verla (Docker); además de las direcciones IP y `localhost`, el único nombre al que responde Notosaurus |
