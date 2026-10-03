---
title: "AI services and costs"
description: "Which AI service to choose, how to get its API key step by step, local models, and what a lesson costs."
---

Notosaurus doesn't have its own AI: it uses the service you choose, with **your own key**. You
pay the service directly, for what you use: no subscription.

## Which service?

| Service | For whom | Cost of a lesson |
|---|---|---|
| **Gemini** (Google) | the default: fast, cheap, reads well; a free tier to try | a fraction of a cent |
| **Claude** (Anthropic) | the best reading of handwriting and the best corrections | a few cents |
| **OpenAI** (GPT) | if you already have an OpenAI account | a few cents |
| **OpenRouter** | one key for Gemini, Claude, GPT, Mistral…; the exact cost of each lesson | the price of the model chosen |
| **Other OpenAI-compatible service** | a model at home (Ollama, LM Studio), or another service | free at home |

Change service at any time in **Settings → AI service**: the lessons already made stay as they
are.

![Settings: choosing the AI service](../../assets/screenshots/en/settings-ai.png)

## Getting a key

Create the key on the service's site, then paste it in **Settings → Access** and tap
**🔌 Test**: Notosaurus checks that the model reads an image and answers in the right format.

![Settings: the API key and the model](../../assets/screenshots/en/settings-key.png)

### Gemini

1. Open [aistudio.google.com/apikey](https://aistudio.google.com/apikey) and sign in with a
   Google account.
2. **Create API key**, then copy it.
3. The free tier is enough to try Notosaurus, but its limits are low (a few dozen requests a
   day on the best models) and Google may use what you send to improve its products. For your
   children's notebooks, turn on billing for the key's project in Google AI Studio: you then
   pay a fraction of a cent per lesson, and, according to Google's terms, your data isn't used
   to improve its products.

### Claude

1. Open [console.anthropic.com](https://console.anthropic.com) and create an account.
2. In **Billing**, add some credit: a few euros last a long time.
3. In **Settings → API keys**, **Create key**, then copy it.

### OpenAI

1. Open [platform.openai.com](https://platform.openai.com) and create an account.
2. Add some credit in the billing settings.
3. In **API keys**, create a secret key, then copy it.

### OpenRouter

1. Open [openrouter.ai](https://openrouter.ai) and sign in.
2. Buy credits: OpenRouter adds a small fee to each purchase, so prefer one purchase of
   15 $ or more to several small ones.
3. In **Keys**, create a key, then copy it.

One OpenRouter key gives access to Gemini, Claude, GPT and many others: handy to compare them.
By default, Notosaurus uses the latest Gemini Flash through OpenRouter.

## The model

Under **Model**, leave the field empty to use Notosaurus's choice for that service, or type
another model. With OpenAI, OpenRouter and the other services, **📋 Load the service's models** lists only the
models that accept images. Gemini also has **fallback models**, tried in order when the main one is
overloaded.

## A model at home

With **Other OpenAI-compatible service**, Notosaurus can use a model running on your computer,
with [Ollama](https://ollama.com) or [LM Studio](https://lmstudio.ai). The address usually ends
with `/v1` (Ollama: `http://localhost:11434/v1`). Nothing leaves the house and nothing is
paid, but:

- the model must **accept images** (a “vision” model): **📋 Load the service's models** lists them;
- it needs a **good graphics card** (or a recent Mac with plenty of memory);
- it reads **handwriting much less reliably** than Gemini or Claude;
- with Ollama, corrections need a longer context than the default: set
  `OLLAMA_CONTEXT_LENGTH` (for instance to 16384) before starting it.

## What it costs

**Settings → Lessons** shows what the AI cost, in total, per profile and per lesson, with
each generation, correction and picture.

![Settings: the cost of each lesson](../../assets/screenshots/en/settings-costs.png)

These figures are estimated from the services' public prices (OpenRouter gives the exact
cost). With a free Gemini key, nothing is actually charged. As an example, the vocabulary
lesson of these screenshots cost about 2 US cents to generate with Claude Sonnet, and as much
for its correction. Pictures cost from under a cent to a few cents each; figures, a fraction of
a cent.
