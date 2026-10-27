---
title: "Privacy policy of the Android app"
description: "The data the Notosaurus Android app and its service process, why, where, for how long, and your rights."
---

*Last updated: 21 October 2026.*

This page is about **the Notosaurus app for Android** and **the Notosaurus service** it uses to
read the photos, make the cards and the voices. Notosaurus on a computer (the Anki add-on) works
differently: see [Privacy and security](../privacy/).

**Data controller**: CHABANOIS Cédric.
**Contact**: notosaurus.app@gmail.com

**Who uses the app**: a **parent** (an adult), preparing their children's revision. The app
isn't made to be used by a child.

## In short

- Your **lessons stay on your phone**: photos, cards, instructions, sounds.
- What the AI must read (photos, instructions, dictations) **goes through the service** while
  the cards are made, **and isn't kept there**.
- The AI (**Google's Gemini**) and the voices are **processed in the European Union**. Google
  doesn't use them to train its models.
- **No ads, no statistics, no tracking**, and nothing is sold.
- The service keeps only your **licence** (its fingerprint, your plan and your credits), and
  what you **report** with ⚑, if you do.

## What stays on your phone

Lessons (page photos, cards, instructions, card pictures, sounds), your saved instructions and
your settings, including your licence key, are kept **in the app's private storage** on your
phone. Other apps can't reach them. They are deleted when you delete a lesson, or the app.

The cards sent to **AnkiDroid** are written into it on your phone. Their sync with AnkiWeb is
up to AnkiDroid and your AnkiWeb account, not Notosaurus.

## What goes through the Notosaurus service

When you ask for it, the app sends the service, over HTTPS:

| What | What for |
|---|---|
| The pages' **photos** and their text (PDF), the **instruction**, your standing instructions, your deck names | Making or completing the lesson's cards |
| A lesson's **cards** and your correction | Correcting them, explaining a card, tidying up an instruction |
| A **recording of your voice** (🎤) | Writing it as text (dictating an instruction or a correction) |
| A card's **back** | Reading it aloud (the cards' voices) |
| A picture's **description**, or a few **keywords** | Drawing a card's picture, or looking for a free one |
| Your **licence key** | Checking your licence and counting your credits |
| If you subscribe: your Google Play **purchase's token** | Checking the subscription with Google Play and making it your licence |
| For the **free trial**: a **fingerprint of the phone** (worked out by the app, never its identifier itself) and Google's **Play Integrity** attestation | Offering the trial only once per phone, to the app installed from Google Play on a real phone |

The service passes these contents to the processors below, sends the result back to the app,
and **doesn't keep them**: no photo, card, recording or lesson text is stored or written into
its logs. Except a **report**: see below.

A notebook page often shows the **child's name**. Before sending a photo you can **hide** it:
🖍️ on the photo, then black it out with your finger. Only the blacked-out photo leaves and stays
in the lesson.

## What the service keeps

- **Your licence**: its key's fingerprint (not the key itself), your plan, your credits left,
  their renewal date, what was used that day, and a short note for support (an order number,
  for instance). Kept while it is valid, then **12 months** after it ends (to answer a question
  or a claim), then deleted.
- **What you report** with ⚑ (a card the AI made, with its explanation if shown and its
  picture, unless it's a photo you took; shocking or wrong), if you do: exactly what the app shows you before sending, the reason, your comment,
  the lesson's instructions, the language and a short licence identifier. Never the lesson's
  photos, nor the child's name. Read by Notosaurus to improve the AI's content, kept **180
  days**, then deleted.
- **Your emails to support**, if any: kept **12 months** after the last exchange.
- **Technical logs**, kept **30 days** to run the service and spot failures and abuse: the
  time, the action asked for ("make a lesson"…), its duration, its outcome, the AI model and the
  credits used, the app's version, a short licence identifier, and, as for any website, the
  request's **IP address**. Never the lessons' content.

## Processors

| Service | What it receives | Where |
|---|---|---|
| **Google Cloud**: Vertex AI (Gemini) | Photos, instructions, cards, dictations, picture descriptions | European Union |
| **Google Cloud**: Cloud Run, Firestore, logs | The service itself, the licences, the logs | Belgium (europe-west1) |
| **Google Cloud**: Text-to-Speech | The text to read (a card's back) | European Union |
| **Wikimedia Commons**, **Openverse**, **Pixabay** | A few English keywords ("dog"), never a photo | Their servers |
| **Google Play**: subscriptions, Play Integrity | A purchase's token; the free trial's attestation | Its servers |
| **GitHub** (GitHub Pages) | At start, the app reads the service's address there: GitHub sees your IP address | Its servers |

Google acts as a processor, under the Google Cloud terms, and doesn't use this data to train
its models. To detect abuse, Google may however keep the requests sent to Gemini **up to 90
days**, under its terms, using them for nothing else.

### Transfers outside the European Union

Processing happens in the European Union, but Google, GitHub, the Wikimedia Foundation and
Openverse are US organisations, which may access it. These transfers are covered by the
European Commission's **standard contractual clauses** and, for certified companies such as
Google, by the **EU–US Data Privacy Framework**. Pixabay is an EU company.

## Why: the legal bases

| Processing | Legal basis |
|---|---|
| Making, completing, correcting and explaining cards; dictation; voices; pictures | **Providing the service** you ask for |
| Checking your licence and counting your credits | **Performing the contract** (your licence) |
| Technical logs, security, fighting abuse | The **legitimate interest** in running a safe service |
| The free trial only once per phone (Play Integrity) | The **legitimate interest** in preventing abuse of the trial |
| Your reports of the AI's content | Your **request**, and the legitimate interest in an AI that makes fit content |
| The microphone | Your **consent**, asked at the first dictation and withdrawable in the phone's settings |
| Answering your emails | Your **request** |

Notosaurus makes **no automated decision** about you and does **no profiling**. Without your
licence the service can't be provided; everything else is sent only when you ask for it.

## The "With my computer" mode

When the app opens Notosaurus on your computer (the Anki add-on), the phone talks straight to
the computer, on the home Wi-Fi: nothing goes through the Notosaurus service then. The
[Privacy and security](../privacy/) page applies.

## The app's permissions

- **Internet**: to reach the service.
- **Microphone**, asked the first time you tap 🎤, and used only while dictating.
- **AnkiDroid**, to add the cards to it, asked at the first send.
- Photos are taken by the phone's camera or picked in the gallery, when you do it. The app
  doesn't need access to all your photos.

## Children

The app is used by **a parent**, not by the child. But notebook photos may hold the child's
data (their name, their handwriting): hide the name with 🖍️ before sending, and put nothing
personal in the instructions.

## Your rights

By writing to **notosaurus.app@gmail.com**, you can:

- **access** your data and get a copy of it (**portability**);
- have it **corrected** or **erased**;
- **restrict** its processing, or **object** to the processing based on legitimate interest;
- **withdraw your consent** (the microphone) at any time, without effect on what was done before.

Lessons are on your phone: you delete them yourself in the app. You get an answer within a
month. You can also complain to your data protection authority (in France, the CNIL: cnil.fr).

## Security

Every exchange with the service uses **HTTPS**. Only your licence key's fingerprint is kept by
the service. On your phone, the key stays in the app's private storage, and the settings show
only its last characters.

## Changes

If this policy changes, the date at the top of the page changes too.
