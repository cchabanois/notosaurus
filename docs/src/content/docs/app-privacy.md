---
title: "Privacy policy of the Android app"
description: "The data the Notosaurus Android app and its service process, why, where, for how long, and your rights."
---

*Last updated: 11 October 2026.*

This page is about **the Notosaurus app for Android** and **the Notosaurus service** it uses to
read the photos, make the cards and the voices. Notosaurus on a computer (the Anki add-on) works
differently: see [Privacy and security](../privacy/).

**Data controller**: [to complete: the publisher's name and address].
**Contact**: notosaurus.app@gmail.com

## In short

- Your **lessons stay on your phone**: photos, cards, instructions, sounds.
- What the AI must read (photos, instructions, dictations) **goes through the service** while
  the cards are made, **and isn't kept there**.
- The AI (**Google's Gemini**) and the voices are **processed in the European Union**. Google
  doesn't use them to train its models.
- **No ads, no statistics, no tracking**, and nothing is sold.
- The service keeps only your **licence**: its fingerprint, your plan and your credits.

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

The service passes these contents to the processors below, sends the result back to the app,
and **doesn't keep them**: no photo, card, recording or lesson text is stored or written into
its logs.

A notebook page often shows the **child's name**. Before sending a photo you can **hide** it:
🖍️ on the photo, then black it out with your finger. Only the blacked-out photo leaves and stays
in the lesson.

## What the service keeps

- **Your licence**: its key's fingerprint (not the key itself), your plan, your credits left,
  their renewal date and what was used that day. Kept as long as the licence exists, then
  deleted on request.
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
| **GitHub** (GitHub Pages) | At start, the app reads the service's address there: GitHub sees your IP address | Its servers |

Google acts as a processor, under the Google Cloud terms, and doesn't use this data to train
its models.

## The app's permissions

- **Internet**: to reach the service.
- **Microphone**, asked the first time you tap 🎤, and used only while dictating.
- **AnkiDroid**, to add the cards to it, asked at the first send.
- Photos are taken by the phone's camera or picked in the gallery, when you do it. The app
  doesn't need access to all your photos.

## Children

Notosaurus is made for **parents** preparing their children's revision. Notebook photos may
hold a child's data (name, handwriting): hide the name with 🖍️ before sending, and put nothing
personal in the instructions.

## Your rights

You can ask for access to your data, its correction or its deletion, by writing to
**notosaurus.app@gmail.com**. Lessons are on your phone: you delete them yourself in the app.
You can also complain to your data protection authority (in France, the CNIL: cnil.fr).

## Security

Every exchange with the service uses **HTTPS**. Only your licence key's fingerprint is kept by
the service. On your phone, the key stays in the app's private storage, and the settings show
only its last characters.

## Changes

If this policy changes, the date at the top of the page changes too.
