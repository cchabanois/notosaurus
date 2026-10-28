---
title: "An Anki am Computer senden"
description: "Aus der Erweiterung oder eigenständig: die Karten direkt in Anki am Computer senden oder eine .apkg-Datei herunterladen, und die Karten aufs Handy bringen."
---

Mit der Erweiterung (oder eigenständig) gehen die Karten, sind sie einmal geprüft, mit einem
Tippen in Anki am Computer, oder als Datei. In der Android-App gehen sie direkt in AnkiDroid:
siehe [Die App und AnkiDroid](../app-ankidroid/).

## Zu Anki hinzufügen

**📥 Zu Anki hinzufügen** schreibt die Karten direkt in das **in Anki geöffnete Benutzerprofil**,
in den Stapel der Lektion, mit ihrem Audio und ihren Bildern. Eine Meldung sagt, was getan wurde,
zum Beispiel „✓ In Anki: 9 Karten hinzugefügt. Mit AnkiWeb synchronisiert.“ Werden die Bilder und
Figuren noch gezeichnet, wartet die Schaltfläche auf sie und sagt, wie viele fertig sind („⏳ Bilder
und Figuren: 2 / 5 fertig…“).

![Die an Anki gesendeten Karten](../../../assets/screenshots/en/sent.png)

- Mit der **Erweiterung** schreibt Notosaurus selbst in Anki: nichts weiter zu installieren.
- Notosaurus **eigenständig** (ohne die Erweiterung) braucht Anki am Computer geöffnet, mit der
  Erweiterung [AnkiConnect](https://ankiweb.net/shared/info/2055492159).
- Gehört die Lektion einem anderen Kind als dem in Anki geöffneten Profil, fragt Notosaurus, bevor
  es sie in die falsche Sammlung schreibt (siehe [Mehrere Kinder](../several-children/)).

## Eine Lektion erneut senden

Ist die Lektion gesendet und ändert sich nichts, zeigt die Schaltfläche **✓ In Anki aktuell** (sie
sendet die Lektion bei Bedarf trotzdem erneut). Hat sich etwas geändert, das Anki bekommt (eine
Karte, ihr Bild, der Stapel, die Stimme, die Optionen), wird sie zu **🔄 In Anki aktualisieren**:
Eine korrigierte, erneut gesendete Lektion aktualisiert ihre Karten in Anki, Verlauf erhalten,
statt sie zu verdoppeln. Siehe [Die Karten in Anki](../cards-in-anki/).

## Die .apkg-Datei

**⬇️ .apkg** lädt den Stapel als Datei herunter, mit seinem Audio und seinen Bildern, ohne dass
Anki geöffnet sein muss:

- **auf einem Computer** doppelklicke darauf: Anki importiert sie;
- **auf Android** öffne die heruntergeladene Datei und wähle **AnkiDroid**. Wird AnkiDroid nicht
  angeboten, teile die Datei mit AnkiDroid oder nutze **Importieren** im Menü von AnkiDroid;
- **auf einem iPhone** öffne sie über das Teilen-Menü mit **AnkiMobile**.

Das Importieren einer neueren `.apkg` derselben Lektion aktualisiert ihre Karten ebenfalls, statt
sie zu verdoppeln.

Mit der **Notosaurus-Erweiterung** ergeben eine mit **📥 Zu Anki hinzufügen** gesendete Lektion und
ihre `.apkg` dieselben Karten: Du kannst beides mischen, am Computer und auf dem Handy. Mit
**AnkiConnect** wähle einen Weg pro Anki-Profil: Eine `.apkg`, importiert dort, wohin die Lektion
schon direkt gesendet wurde (oder in ein damit synchronisiertes Profil), würde jede Karte ein
zweites Mal hinzufügen.

## Die Karten aufs Handy bringen

Nach **Zu Anki hinzufügen** **synchronisiert Notosaurus das Profil mit AnkiWeb** (die Option **Nach
dem Senden mit AnkiWeb synchronisieren**, in den Einstellungen). Die Karten kommen dann beim
nächsten Synchronisieren in AnkiDroid oder AnkiMobile an. Ist das Profil nicht bei AnkiWeb
angemeldet, werden die Karten zu Anki am Computer hinzugefügt, und die Meldung sagt, dass nicht
synchronisiert wurde.

Ohne AnkiWeb-Konto legt die auf dem Handy geöffnete `.apkg`-Datei den Stapel direkt in AnkiDroid,
aber das Lernen bleibt dann nur auf diesem Handy.
