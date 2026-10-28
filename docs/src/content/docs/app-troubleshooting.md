---
title: "Troubleshooting the app"
description: "What to do when the Android app says it has no credits, the trial or the subscription is over, AnkiDroid doesn't take the cards, or the computer doesn't answer."
---

The messages below are the ones the app shows.

## The subscription

| Message | What to do |
|---|---|
| “No credits left this month” | They come back with the next renewal: **🔑 Subscription**, in the settings, says when. |
| “Your free trial is over” | Subscribe in the Settings (**🔑 Subscription**) to go on. |
| “No new free trial for now…” | New free trials are paused for the moment: subscribe in the Settings, or try again tomorrow. A trial already started goes on. |
| “Your subscription has ended” | Subscribe again in the app. |
| “Payment pending” | Google Play couldn't renew the subscription: update your payment method in Google Play (**Settings → Manage the subscription**). |
| “The free trial is only possible with the app installed from Google Play, on a real phone” | Install the app from Google Play; the trial isn't offered on an emulator. |
| “No subscription found on this Google account” (**I already have a subscription**) | Check that the phone uses the Google account the subscription was taken with. |

See [The subscription](../app-subscription/).

## AnkiDroid

| Message | What to do |
|---|---|
| “Notosaurus isn't allowed to add cards to AnkiDroid” | **Settings → 📥 AnkiDroid → Allow**, then add the cards again. Refused for good (Android asks no more): allow it in Android's settings, **Apps → Notosaurus → Permissions**. |
| “AnkiDroid isn't installed” / “AnkiDroid didn't take the cards” | Install AnkiDroid, **open it once** (it creates its collection), then add the cards again. |

**✎ Notosaurus does nothing in AnkiDroid** (“Card blocked from launching another app”): up to
AnkiDroid 2.25.2, turn on **Settings → Advanced → Allow cards to launch other apps** in
AnkiDroid, or update AnkiDroid (from 2.25.3, the link goes through without it).

**Cards without sound**: the Notosaurus service's voices didn't answer (the phone needs the
Internet). The cards are sent without their sound, and the message says how many. Add the lesson
to Anki again later: the missing sounds are added.

See [The app and AnkiDroid](../app-ankidroid/).

## With your computer

| Message | What to do |
|---|---|
| “💻 Your computer doesn't answer” | Anki must be open on the computer with the add-on, and the phone on the same Wi-Fi. **Try again**, or **Scan the QR code again** if the computer's address changed. |

See [With your computer](../app-with-computer/).

## The cards

**The cards are wrong or missing.** Check the photo (see [Photos and PDFs](../photos/)), be more
precise in the instructions, or correct them with the AI (see [Reviewing the cards](../review/)).
A card the AI made that is wrong or unsuitable: **⋯ → ⚑ Report** on it.

## A PDF can't be added

- **“Already 10 pages: remove some before adding a PDF.”** A lesson holds 10 pages: remove the
  photos you don't need (the **Remove this page** button, ✕, on each), or make two lessons.
- **“… is password-protected: save it without a password, then add it again.”** Open the PDF,
  save it without its password (or print it to a new PDF), then add it again.
- **Words misread in a PDF**: a scanned PDF is only pictures, read like photos. A PDF made on a
  computer gives the AI its exact text.
