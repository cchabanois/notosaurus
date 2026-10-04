---
title: Several children
description: "One Anki profile and one AnkiWeb account per child, each with their own lessons and cards; or, on a shared tablet, one deck per child."
---

Each child gets their own **Anki profile**: their own cards, their own progress. Notosaurus
follows the profile open in Anki. Children sharing one phone or tablet: see
[One tablet for several children](#one-tablet-for-several-children).

## Set up one profile per child

1. In Anki, **File → Switch Profile → Add**, and create a profile per child (Léa, Paul…).
2. For each profile, create an **AnkiWeb account** and log in to it in that profile
   (**Tools → Preferences → Syncing**). One AnkiWeb account holds one collection, so each
   child needs their own.
3. On each child's phone, log in to **AnkiDroid** or **AnkiMobile** with that child's
   AnkiWeb account.

:::tip[No mailbox per child]
Many e-mail services accept aliases with a `+`: `parent+lea@example.com` and
`parent+paul@example.com` arrive in your own mailbox, but count as two addresses.
:::

## Lessons belong to a profile

- A lesson belongs to the profile **open in Anki when it is created**. The list of lessons
  shows that profile's lessons.
- To make a lesson for Paul, **open Paul's profile in Anki first**, then take the photo.
- If you send a lesson while another child's profile is open, Notosaurus warns you before
  writing it into the wrong collection.
- A lesson can be **shared with the other profiles** (the switch in the review), for
  instance when two children have the same lesson.

![The lessons of the open profile](../../assets/screenshots/en/lessons.png)

## Instructions per child

In **Settings → Instructions for the AI**, you can add instructions for every profile
(“Spanish from Spain”) and for each child (“in year 8; short answers”). They are added to
every lesson of that child.

![Settings: instructions for every profile and for each child](../../assets/screenshots/en/settings-instructions.png)

## Getting the cards to the phone

After **Add to Anki**, Notosaurus syncs the open profile with AnkiWeb. The cards reach the
child's phone at its next sync.

## One tablet for several children

**AnkiDroid has no profiles**: an installation holds one collection, logged in to one AnkiWeb
account. AnkiMobile doesn't switch accounts without logging out either. If the children share
a phone or a tablet, the simplest is **a single Anki profile, with one deck per child**:

1. Keep a single profile in Anki, logged in to a single AnkiWeb account, and log AnkiDroid in
   to that account.
2. Start each lesson's deck name with the child's name: `Léa::Spanish::Unit 3`,
   `Paul::Maths::Fractions`. In the review, fix the **Deck** before sending.
3. To review, each child opens **their own** deck (Léa, Paul): Anki then only takes their
   cards. Not the button that reviews everything.

:::tip[The name typed for you]
To avoid typing the name every time, duplicate your instructions for each child
(“Spanish – Léa”) and put their name in the **suggested deck name**:
`Léa::{subject}::{lesson title}`. You can add what is specific to them (“in year 8; short
answers”). See [Instructions](../instructions/).
:::

What you lose compared with one profile per child:

- each child sees the other children's decks, and Anki's statistics are shared;
- Notosaurus groups the lessons by the deck's first level: the list of lessons groups them by
  child, no longer by subject;
- the settings' instructions “for each child” are actually per profile: with a single
  profile, they apply to everyone. Use instructions per child instead, as above.

If each child has their own device, prefer **one profile per child** (at the top of this
page). For the tech-savvy: AnkiDroid can be installed several times on the same device, one
per child, each with their own AnkiWeb account (the “parallel builds”, see the
[AnkiDroid FAQ](https://github.com/ankidroid/Anki-Android/wiki/FAQ)).
