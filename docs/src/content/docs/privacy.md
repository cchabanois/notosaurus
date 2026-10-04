---
title: "Privacy and security"
description: "What leaves your computer, where Notosaurus keeps its data, who can use it, and how to back it up."
---

Notosaurus has no account and no server of its own: it runs on your computer. A lesson often
shows a child's handwriting, sometimes their name: here is where it goes.

## What leaves your computer

- **The photos and the instructions** go to the **AI service chosen in the settings**, to make
  and correct the cards. The text of a digital PDF goes with its page.
- **The backs of the cards** go to Microsoft's text-to-speech service, to make the audio, when a
  voice is chosen.
- **The description of a picture** goes to the service that draws it, for “Words in pictures”.

Nothing else: no statistics, no tracking. With a model at home (see
[AI services](../ai-services/#a-model-at-home)), the photos don't leave the house either.

:::caution[Free tiers]
Free tiers usually let the AI service use what you send to improve its models. For children's
notebooks, prefer a paid key. Before taking the photo, you can also cover a name written on the
page.
:::

## Where the data is

Everything is kept as plain files, in Notosaurus's **data folder**: the lessons (photos, cards,
audio), the instructions and the settings.

- In the **add-on**, it is in the add-on's folder, under `user_files/data`. **Tools → Notosaurus
  → Server status…** shows where. It is kept when the add-on is updated, and removed with it.
- **Standalone**, it is the `data/` folder (or `NOTOSAURUS_DATA`).

The **API keys** are stored in that folder, in `settings.json`, readable only by your user
account. They are never sent back to a phone or a browser: the settings only show their last
four characters.

**To back up Notosaurus**, copy the data folder. The cards themselves are in Anki, backed up by
Anki and, with an account, by AnkiWeb.

## Who can use Notosaurus

- **Only paired devices.** Over the Wi-Fi, only the computer itself and the devices that scanned
  the QR code (**Settings → Phones**) can use Notosaurus: others can't spend your AI credits or
  delete lessons. **Disconnect every phone** unpairs them all, for instance after a phone was
  lost or lent.
- **Settings only on the computer.** In the add-on, the settings open only on the computer
  itself: children can't change the AI service or see the keys from a phone. Standalone, they are
  protected by a password.
- **A lesson belongs to a profile.** Only the profile that created a lesson can change it; a
  shared lesson is read only for the others.

## The Wi-Fi

Notosaurus talks to the phones in plain HTTP, on your local network. Pairing keeps out the
curious and other websites, but not someone spying on the Wi-Fi traffic: keep your Wi-Fi
protected (WPA2 or WPA3).

Notosaurus is made for home: the phones use it on the same Wi-Fi as the computer. **Never
expose Notosaurus** (or AnkiConnect) **to the Internet.**
