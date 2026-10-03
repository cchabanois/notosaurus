---
title: "Troubleshooting and FAQ"
description: "What to do when Notosaurus doesn't start, the phone can't connect, the AI fails, or the cards don't reach Anki, and answers to common questions."
---

The messages below are the ones Notosaurus shows. When something goes wrong in the add-on,
**Tools → Notosaurus → Server log** shows what happened, and **Restart the server** often
fixes it.

## Notosaurus doesn't start

**“Notosaurus isn't started.”** You declined the installation of its components on first
start. To install them: **Tools → Notosaurus → Open Notosaurus**.

**“Couldn't download uv from GitHub”** or **“Couldn't install Notosaurus's dependencies”.** The
first start downloads about 300 MB: check the Internet connection, then **Tools → Notosaurus →
Restart the server**. The log says what failed.

**The server stops right after starting.** Another program may use port 8000, for instance
Notosaurus started standalone at the same time. Stop it, or choose another port in the add-on's
config (**Tools → Add-ons → Notosaurus → Config**, `port`), then restart Anki.

## The phone can't open Notosaurus

- The phone and the computer must be on the **same Wi-Fi**. A “guest” network often keeps its
  devices apart: use the main one.
- On Windows, allow Anki (or Python) when the **firewall** asks, the first time.
- If the computer's address changed (after restarting the router), **scan the QR code again**:
  **Tools → Notosaurus → Open on the phone…**.
- **“The server only listens on this computer”**: set `host` to `0.0.0.0` in the add-on's
  config.
- **“This device isn't allowed yet”**: the phone hasn't scanned the QR code, or every phone was
  disconnected. Scan it again.

## The settings don't open on the phone

**“Settings open from Anki, on the computer.”** That's on purpose: in the add-on, the settings
(and the API keys) are only reachable on the computer itself. Open them with **Tools →
Notosaurus → Settings**.

## The AI fails

| Message | What to do |
|---|---|
| “No … key” / “Invalid … key” | Paste the key again in **Settings → Access**, then **🔌 Test**. |
| “… is overloaded right now” | Common with Gemini: try again in a minute. Fallback models take over automatically. |
| “… quota reached” | A free key's limit is reached: wait, or turn on billing. |
| “Answer cut off: too many cards at once” | Send fewer pages at a time, or ask for fewer cards. |
| “The model didn't return valid cards” | Try again; if it keeps happening, choose another model. |
| The model “doesn't seem to see the image” (Test) | The model doesn't read images: choose a vision model. |

**The cards are wrong or missing.** Check the photo (see [Taking good photos](../photos/)), be
more precise in the instructions, or correct them with the AI. Claude reads handwriting best.

## The cards don't reach Anki

- **“Anki can't be reached”**: start Anki on the computer. Standalone, Anki needs the AnkiConnect
  add-on.
- **“No profile open in Anki”**: open the child's profile, then send again.
- **A warning about another profile**: the lesson belongs to another child than the profile open
  in Anki. Open the right profile, or confirm.
- **The cards don't reach the phone**: the message says “no AnkiWeb sync” when the profile isn't
  logged in to AnkiWeb. Click **Sync** once in Anki to log in, then send again. On the phone,
  sync AnkiDroid or AnkiMobile.
- **Cards without sound**: the voice service didn't answer (it needs the Internet). Send the
  lesson again later: the missing audio is added.

## Questions

**Does Notosaurus work without Anki desktop?**
The add-on needs Anki on a computer. Notosaurus can also run [standalone](../install/), and the
`.apkg` file opens in AnkiDroid without a computer. But the phone page itself always needs the
computer (or a server) running Notosaurus.

**Does it work on an iPhone?**
Yes: the page opens in Safari and can be added to the home screen. Reviews happen in AnkiMobile
(paid, it funds Anki's development).

**Can several children use it?**
Yes, with one Anki profile each: see [Several children](../several-children/).

**How much does it cost?**
Notosaurus is free. The AI service costs from a fraction of a cent to a few cents per lesson:
see [AI services and costs](../ai-services/).

**How do I uninstall it?**
In Anki, **Tools → Add-ons**, select Notosaurus, **Delete**. Its components and **its data
folder (lessons, photos, settings) are deleted too**: copy the data folder first if you want to
keep them (see [Privacy and security](../privacy/#where-the-data-is)). The cards already sent
stay in Anki.
