---
title: "Datenschutz und Sicherheit am Computer"
description: "Was deinen Computer verlässt, wo Notosaurus seine Daten speichert, wer es benutzen kann und wie man es sichert."
---

Diese Seite betrifft Notosaurus auf einem Computer. Für die Android-App und ihren Dienst siehe die
[Datenschutzerklärung der App](../app-privacy/).

Auf einem Computer hat Notosaurus kein Konto und keinen eigenen Server: Es läuft auf deinem
Computer. Eine Lektion zeigt oft die Handschrift eines Kindes, manchmal seinen Namen: Hier steht,
wohin sie geht.

## Was deinen Computer verlässt

- **Die Fotos und die Anweisungen** gehen an den **in den Einstellungen gewählten KI-Dienst**, um
  die Karten zu machen und zu korrigieren. Der Text eines digitalen PDFs geht mit seiner Seite mit.
  Mit ihnen gehen die Klasse des Kindes und deine Anweisungen für es, **nie sein Vorname**.
- **Die Rückseiten der Karten** gehen an den Sprachausgabe-Dienst von Microsoft, um das Audio zu
  erstellen, wenn eine Stimme gewählt ist.
- **Die Beschreibung eines Bildes** geht an den Dienst, der es zeichnet, bei „Sprache: Vokabeln in
  Bildern“.
- **Die Wörter einer Bildsuche** (ein paar englische Wörter: „dog“, „Storming of the Bastille
  painting“) gehen an Wikimedia Commons und Openverse, um freie Bilder zu finden; nie die Fotos.

Die Seiten selbst laden nichts von woanders: Ihre Skripte und Schriften kommen mit Notosaurus
(kein Google Fonts, kein CDN).

Sonst nichts: keine Statistik, kein Tracking. Mit einem Modell zu Hause (siehe
[KI-Dienste](../ai-services/#ein-modell-zu-hause)) verlassen auch die Fotos das Haus nicht.

:::caution[Kostenlose Kontingente]
Bei kostenlosen Kontingenten darf der KI-Dienst meist das Gesendete nutzen, um seine Modelle zu
verbessern. Für die Hefte von Kindern nimm lieber einen kostenpflichtigen Schlüssel. Vor dem Foto
kannst du auch einen auf der Seite geschriebenen Namen abdecken.
:::

## Wo die Daten liegen

Alles wird als einfache Dateien im **Datenordner** von Notosaurus gespeichert: die Lektionen
(Fotos, Karten, Audio), die Anweisungen und die Einstellungen.

- In der **Erweiterung** liegt er im Ordner der Erweiterung, unter `user_files/data`. **Extras →
  Notosaurus → Serverstatus …** zeigt, wo. Er bleibt bei einem Update der Erweiterung erhalten und
  wird mit ihr entfernt.
- **Eigenständig** ist es der Ordner `data/` (oder `NOTOSAURUS_DATA`).

Die **API-Schlüssel** werden in diesem Ordner gespeichert, in `settings.json`, nur für dein
Benutzerkonto lesbar. Sie werden nie an ein Handy oder einen Browser zurückgeschickt: Die
Einstellungen zeigen nur ihre letzten vier Zeichen.

**Um Notosaurus zu sichern**, kopiere den Datenordner. Die Karten selbst sind in Anki, gesichert
von Anki und, mit einem Konto, von AnkiWeb.

## Wer Notosaurus benutzen kann

- **Nur zugelassene Geräte.** Über das WLAN können nur der Computer selbst und die Geräte, die den
  QR-Code gescannt haben (**Einstellungen → Handys**), Notosaurus benutzen: Andere können weder
  deine KI-Guthaben verbrauchen noch Lektionen löschen. **Alle Handys abmelden** hebt alle
  Zulassungen auf, zum Beispiel nachdem ein Handy verloren oder verliehen wurde.
- **Einstellungen nur am Computer.** In der Erweiterung öffnen sich die Einstellungen nur am
  Computer selbst: Kinder können vom Handy aus weder den KI-Dienst ändern noch die Schlüssel sehen.
  Eigenständig sind sie durch ein Passwort geschützt.
- **Eine Lektion gehört zu einem Profil.** Eine Lektion lässt sich nur im Anki-Benutzerprofil
  ändern, in dem sie gemacht wurde; ein anderes Kind bekommt seine eigene Kopie (**⧉ Kopieren
  für…**).

## Das WLAN

Notosaurus spricht mit den Handys in einfachem HTTP, in deinem lokalen Netzwerk. Die Zulassung
hält Neugierige und andere Websites fern, aber nicht jemanden, der den WLAN-Verkehr ausspioniert:
Halte dein WLAN geschützt (WPA2 oder WPA3).

Notosaurus ist für zu Hause gemacht: Die Handys nutzen es im selben WLAN wie der Computer. **Stelle
Notosaurus** (oder AnkiConnect) **nie ins Internet.**
