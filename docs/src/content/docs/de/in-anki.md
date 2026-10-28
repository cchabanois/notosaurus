---
title: "In Anki am Computer"
description: "Die Erweiterung in Anki am Computer: ihr Menü Extras → Notosaurus und ihre Konfiguration."
---

Mit der Erweiterung läuft Notosaurus in Anki am Computer: Es startet mit Anki, hält mit ihm an und
schreibt die Karten direkt in das geöffnete Benutzerprofil.

## Das Menü Extras → Notosaurus

![Das Menü Notosaurus in Anki](../../../assets/screenshots/en/anki-menu.png)

- **Notosaurus öffnen** öffnet Notosaurus im Browser des Computers.
- **Auf dem Handy öffnen …** zeigt einen QR-Code, um Notosaurus auf dem Handy zu öffnen, und die
  drei Schritte dorthin (siehe [Auf dem Handy](../phone/)).
- **Einrichtungsassistent** öffnet den Assistenten: die KI und ihren Schlüssel, dann das Handy
  (siehe [Erste Schritte mit der Erweiterung](../getting-started/#2-der-einrichtungsassistent)).
  Beim ersten Mal bietet Anki ihn von selbst an, wenn noch keine KI eingerichtet ist.
- **Einstellungen** öffnet die Einstellungen (KI-Dienst und Schlüssel, Stimmen, Kinder…) im Browser
  des Computers. Sie öffnen sich nur am Computer: Das Handy kann sie nicht ändern.
- **Serverstatus …** sagt, ob Notosaurus läuft, seine Adressen (auf dem Handy und auf diesem
  Computer) und wo seine Dateien und deine Lektionen liegen.
- **Server neu starten** hält Notosaurus an und startet es neu: nach einer Änderung der
  Konfiguration der Erweiterung, oder wenn etwas hängt.
- **Serverprotokoll** zeigt, was Notosaurus zuletzt getan hat. Es ist das Erste, was man ansieht,
  wenn etwas schiefgeht (siehe [Fehlerbehebung der Erweiterung](../troubleshooting/)).
- **Hilfe** öffnet diese Dokumentation, in der Sprache von Anki.
- **Notosaurus unterstützen…** öffnet seine [Ko-fi](https://ko-fi.com/notosaurus)-Seite, um zu
  spenden, wenn es dir gefällt. Notosaurus bleibt kostenlos.

![Der QR-Code, um Notosaurus auf dem Handy zu öffnen](../../../assets/screenshots/en/anki-phone.png)

Ein Wechsel des Benutzerprofils in Anki lässt Notosaurus weiterlaufen: Die Karten kommen dann in
das geöffnete Profil (siehe [Mehrere Kinder](../several-children/)).

## Die Konfiguration der Erweiterung

Ein paar technische Optionen stehen unter **Extras → Erweiterungen**, wähle **Notosaurus**, dann
**Konfiguration**:

- `autostart`: Notosaurus mit Anki starten (standardmäßig `true`). Mit `false` startet es beim
  ersten Benutzen des Menüs.
- `host`: `0.0.0.0` (Standard) lässt das Handy Notosaurus im selben WLAN erreichen; `127.0.0.1`
  beschränkt es auf diesen Computer.
- `port`: standardmäßig `8000`. Ändere ihn, wenn ein anderes Programm diesen Port schon nutzt.
- `source`, `python`, `data`: Lass sie leer. Sie sind nur für die Entwicklung von Notosaurus.

Nach einer Änderung: **Extras → Notosaurus → Server neu starten**.

Die Stapel, die Notosaurus anlegt, und wie seine Karten in Anki aussehen, am Computer und auf den
Handys: siehe [Die Karten in Anki](../cards-in-anki/).
