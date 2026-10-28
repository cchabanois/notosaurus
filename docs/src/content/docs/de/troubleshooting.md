---
title: "Fehlerbehebung der Erweiterung"
description: "Was tun, wenn die Erweiterung nicht startet, das Handy sich nicht verbinden kann, die KI scheitert oder die Karten nicht in Anki ankommen."
---

Die Meldungen unten sind die, die Notosaurus anzeigt. Geht in der Erweiterung etwas schief, zeigt
**Extras → Notosaurus → Serverprotokoll**, was passiert ist, und **Server neu starten** behebt es
oft.

## Notosaurus startet nicht

**„Notosaurus ist nicht gestartet.“** Du hast beim ersten Start die Installation seiner
Komponenten abgelehnt. Um sie zu installieren: **Extras → Notosaurus → Notosaurus öffnen**.

**„uv konnte nicht von GitHub heruntergeladen werden“** oder **„Die Komponenten von Notosaurus
konnten nicht installiert werden“.** Der erste Start lädt etwa 300 MB herunter: Prüfe die
Internetverbindung, dann **Extras → Notosaurus → Server neu starten**. Das Protokoll sagt, was
fehlgeschlagen ist.

**Der Server hält gleich nach dem Start an.** Ein anderes Programm nutzt vielleicht Port 8000, zum
Beispiel ein gleichzeitig eigenständig gestartetes Notosaurus. Beende es oder wähle einen anderen
Port in der Konfiguration der Erweiterung (**Extras → Erweiterungen → Notosaurus →
Konfiguration**, `port`), dann starte Anki neu.

## Das Handy kann Notosaurus nicht öffnen

Siehe auch [Auf dem Handy](../phone/).

- Handy und Computer müssen im **selben WLAN** sein. Ein „Gast“-Netz hält seine Geräte oft
  getrennt: Nimm das Hauptnetz.
- Erlaube unter Windows Anki (oder Python), wenn die **Firewall** beim ersten Mal fragt.
- Hat sich die Adresse des Computers geändert (nach einem Neustart des Routers), **scanne den
  QR-Code erneut**: **Extras → Notosaurus → Auf dem Handy öffnen …**.
- **„Der Server hört nur auf diesem Computer“**: Setze `host` in der Konfiguration der
  Erweiterung auf `0.0.0.0`.
- **„Dieses Gerät ist noch nicht zugelassen“**: Das Handy hat den QR-Code nicht gescannt, oder
  alle Handys wurden abgemeldet. Scanne ihn erneut.

## Die Einstellungen öffnen sich nicht auf dem Handy

**„Die Einstellungen öffnest du in Anki, auf dem Computer.“** Das ist Absicht: In der Erweiterung
sind die Einstellungen (und die API-Schlüssel) nur am Computer selbst erreichbar. Öffne sie mit
**Extras → Notosaurus → Einstellungen**.

## Die KI scheitert

| Meldung | Was tun |
|---|---|
| „Schlüssel fehlt“ / „Ungültiger …-Schlüssel“ | Füge den Schlüssel unter **Einstellungen → Zugang** erneut ein, dann **🔌 Testen**. |
| „… ist gerade überlastet“ | Häufig bei Gemini: Versuch es in einer Minute noch einmal. Ersatzmodelle springen automatisch ein. |
| „…-Kontingent erreicht“ | Das Limit eines kostenlosen Schlüssels ist erreicht: Warte, oder aktiviere die Abrechnung. |
| „Antwort abgeschnitten: zu viele Karten auf einmal“ | Sende weniger Seiten auf einmal, oder bitte um weniger Karten. |
| „Das Modell hat keine gültigen Karten geliefert“ | Versuch es noch einmal; passiert es weiter, wähle ein anderes Modell. |
| Das Modell „scheint das Bild nicht zu sehen“ (Testen) | Das Modell liest keine Bilder: Wähle ein Modell mit Bilderkennung. |

## Die Karten sind falsch oder es fehlen welche

Prüfe das Foto (siehe [Fotos und PDFs](../photos/)), sei in den Anweisungen genauer, oder
korrigiere sie mit der KI (siehe [Die Karten durchsehen](../review/)). Bei Handschrift liest Claude
am besten: siehe [Einstellungen und KI-Dienste](../ai-services/).

## Ein PDF lässt sich nicht hinzufügen

- **„Schon 10 Seiten: Entferne welche, bevor du ein PDF hinzufügst.“** Eine Lektion fasst 10
  Seiten: Entferne die Fotos, die du nicht brauchst (die Schaltfläche **Diese Seite entfernen**, ✕,
  auf jedem), oder mach zwei Lektionen.
- **„… ist passwortgeschützt: Speichere es ohne Passwort und füge es dann erneut hinzu.“** Öffne
  das PDF, speichere es ohne Passwort (oder drucke es in ein neues PDF), dann füge es erneut hinzu.
- **Falsch gelesene Wörter in einem PDF**: Ein gescanntes PDF besteht nur aus Bildern, die wie
  Fotos gelesen werden. Ein am Computer erstelltes PDF gibt der KI seinen genauen Text.

## Die Karten kommen nicht in Anki an

- **„Anki ist nicht erreichbar“**: Starte Anki auf dem Computer. Eigenständig braucht Anki die
  Erweiterung AnkiConnect.
- **„Kein Benutzerprofil in Anki geöffnet“**: Öffne das Profil des Kindes, dann sende erneut.
- **Eine Warnung zu einem anderen Profil**: Die Lektion gehört einem anderen Kind als dem in Anki
  geöffneten Profil. Öffne das richtige Profil oder bestätige.
- **Die Karten kommen nicht auf dem Handy an**: Die Meldung sagt „keine Synchronisierung mit
  AnkiWeb“, wenn das Profil nicht bei AnkiWeb angemeldet ist. Klicke in Anki einmal auf
  **Synchronisieren**, um dich anzumelden, dann sende erneut. Synchronisiere auf dem Handy AnkiDroid
  oder AnkiMobile.
- **Karten ohne Ton**: Der Sprachdienst hat nicht geantwortet (er braucht Internet). Sende die
  Lektion später erneut: Das fehlende Audio wird ergänzt.

## Die Erweiterung deinstallieren

In Anki **Extras → Erweiterungen**, wähle Notosaurus, **Löschen**. Seine Komponenten und **sein
Datenordner (Lektionen, Fotos, Einstellungen) werden mitgelöscht**: Kopiere den Datenordner vorher,
wenn du sie behalten willst (siehe
[Datenschutz und Sicherheit am Computer](../privacy/#wo-die-daten-liegen)). Die schon gesendeten
Karten bleiben in Anki.
