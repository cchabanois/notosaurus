---
title: "Instalação avançada"
description: "Rodar o Notosaurus no modo autônomo ou com Docker, sem o complemento do Anki, e as variáveis de ambiente dele."
---

O [complemento do Anki](../getting-started/) é o jeito mais simples de usar o Notosaurus. Para
rodá-lo sozinho, por exemplo em um servidor doméstico sempre ligado, instale-o no **modo autônomo**
ou com **Docker**.

Diferenças em relação ao complemento:

- O Notosaurus roda mesmo com o Anki fechado; o download do `.apkg` sempre funciona.
- **Adicionar ao Anki** precisa do Anki aberto no computador com o complemento
  [AnkiConnect](https://ankiweb.net/shared/info/2055492159) (código `2055492159`).
- As configurações (`/admin.html`) são acessíveis pela rede, protegidas por uma **senha de
  administrador** criada na primeira visita.

## Modo autônomo

Com Python 3.13:

```sh
git clone https://github.com/cchabanois/notosaurus.git
cd notosaurus
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --host 0.0.0.0
```

Abra http://localhost:8000 no computador. Para o celular (mesma Wi-Fi): **⚙️ → Celulares**, e
escaneie o QR code.

## Docker

```sh
docker build -t notosaurus .
docker run -p 8000:8000 -v notosaurus-data:/data --env-file .env \
  -e NOTOSAURUS_PUBLIC_URL=http://<ip-do-computador>:8000 notosaurus
```

Dentro do Docker, o Notosaurus não consegue ver o endereço do computador: `NOTOSAURUS_PUBLIC_URL` o
coloca no QR code dos celulares. O próprio computador também passa pela rede do Docker: abra
**⚙️ → Celulares** e use uma vez o link abaixo do QR code.

## Variáveis de ambiente

Copie `.env.example` para `.env`. Essas variáveis dão os valores padrão: o que está salvo na
página de configurações tem prioridade.

| Variável | Uso |
|---|---|
| `NOTOSAURUS_LLM` | serviço de IA: `gemini`, `anthropic`, `openai`, `openrouter`, `compatible` |
| `GEMINI_API_KEY`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `OPENROUTER_API_KEY` | chaves de API |
| `NOTOSAURUS_MODEL` | o modelo (vazio: a escolha do Notosaurus para o serviço) |
| `NOTOSAURUS_FALLBACK_MODEL` | modelos do Gemini tentados quando o principal está sobrecarregado |
| `NOTOSAURUS_COMPATIBLE_BASE_URL`, `NOTOSAURUS_COMPATIBLE_API_KEY` | outro serviço compatível com a OpenAI (Ollama: `http://localhost:11434/v1`) |
| `NOTOSAURUS_PICTURE_SERVICE`, `NOTOSAURUS_PICTURE_MODEL` | o serviço que desenha as imagens dos cartões (`gemini`, `openai`, `openrouter`, `none`; vazio: o dos cartões) e o modelo dele |
| `NOTOSAURUS_DATA` | a pasta de dados (padrão: `data`) |
| `NOTOSAURUS_ANKICONNECT_URL`, `NOTOSAURUS_ANKICONNECT_KEY` | o AnkiConnect (padrão: `http://localhost:8765`) |
| `NOTOSAURUS_PUBLIC_URL` | o endereço no QR code dos celulares, quando o Notosaurus não consegue vê-lo (Docker); além dos endereços IP e de `localhost`, o único nome ao qual o Notosaurus responde |
