---
title: "Fehlerbehebung in der App"
description: "Was tun, wenn die Android-App keine Credits mehr hat, die Testphase oder das Abo vorbei ist, AnkiDroid die Karten nicht annimmt oder der Computer nicht antwortet."
---

Die Meldungen unten sind die, die die App anzeigt.

## Das Abo

| Meldung | Was tun |
|---|---|
| „Diesen Monat keine Credits mehr“ | Sie kommen mit der nächsten Erneuerung zurück: **🔑 Abo**, in den Einstellungen, sagt wann. |
| „Deine kostenlose Testphase ist vorbei“ | Schließe in den Einstellungen (**🔑 Abo**) ein Abo ab, um weiterzumachen. |
| „Gerade keine neue kostenlose Testphase…“ | Neue kostenlose Testphasen sind im Moment ausgesetzt: Schließe in den Einstellungen ein Abo ab oder versuche es morgen erneut. Eine schon begonnene Testphase läuft weiter. |
| „Dein Abo ist beendet“ | Schließe es in der App erneut ab. |
| „Zahlung ausstehend“ | Google Play konnte das Abo nicht verlängern: Aktualisiere deine Zahlungsmethode in Google Play (**Einstellungen → Abo verwalten**). |
| „Die kostenlose Testphase ist nur mit der App aus Google Play auf einem echten Telefon möglich“ | Installiere die App aus Google Play; auf einem Emulator wird die Testphase nicht angeboten. |
| „Kein Abo in diesem Google-Konto gefunden“ (**Ich habe schon ein Abo**) | Prüfe, ob das Handy das Google-Konto nutzt, mit dem das Abo abgeschlossen wurde. |

Siehe [Das Abo](../app-subscription/).

## AnkiDroid

| Meldung | Was tun |
|---|---|
| „Notosaurus darf AnkiDroid keine Karten hinzufügen“ | **Einstellungen → 📥 AnkiDroid → Erlauben**, dann die Karten erneut hinzufügen. Endgültig abgelehnt (Android fragt nicht mehr): Erlaube es in den Einstellungen von Android, **Apps → Notosaurus → Berechtigungen**. |
| „AnkiDroid ist nicht installiert“ / „AnkiDroid hat die Karten nicht übernommen“ | Installiere AnkiDroid, **öffne es einmal** (es legt seine Sammlung an), dann füge die Karten erneut hinzu. |

**✎ Notosaurus tut in AnkiDroid nichts** („Sicherheit: Karteikarten wurde daran gesperrt, eine
andere App zu starten“): Bis AnkiDroid 2.25.2 schalte in AnkiDroid **Einstellungen → Erweitert →
Erlauben Karteikarten, andere Apps zu öffnen** ein, oder aktualisiere AnkiDroid (ab 2.25.3 geht
der Link auch ohne das durch).

**Karten ohne Ton**: Die Stimmen des Notosaurus-Dienstes haben nicht geantwortet (das Handy
braucht Internet). Die Karten werden ohne ihren Ton gesendet, und die Meldung sagt, wie viele.
Füge die Lektion später erneut zu Anki hinzu: Die fehlenden Töne werden ergänzt.

Siehe [Die App und AnkiDroid](../app-ankidroid/).

## Mit deinem Computer

| Meldung | Was tun |
|---|---|
| „💻 Dein Computer antwortet nicht“ | Anki muss auf dem Computer mit der Erweiterung geöffnet sein, und das Handy im selben WLAN. **Erneut versuchen**, oder **QR-Code erneut scannen**, wenn sich die Adresse des Computers geändert hat. |

Siehe [Mit deinem Computer](../app-with-computer/).

## Die Karten

**Die Karten sind falsch oder es fehlen welche.** Prüfe das Foto (siehe
[Fotos und PDFs](../photos/)), sei in den Anweisungen genauer, oder korrigiere sie mit der KI
(siehe [Die Karten durchsehen](../review/)).

**Melde es.** Eine Karte, die nicht stimmt (ein falsch gelesenes Wort, eine falsche Antwort, eine
schiefe Figur, ein unpassendes Bild): **⋯ → ⚑ Melden** auf ihr, mit einem Wort dazu, was du
erwartet hast. Jede Meldung wird gelesen, und so werden solche Fehler behoben. Siehe
[Ein Problem melden](../review/#ein-problem-melden).

## Ein PDF lässt sich nicht hinzufügen

- **„Schon 10 Seiten: Entferne welche, bevor du ein PDF hinzufügst.“** Eine Lektion fasst 10
  Seiten: Entferne die Fotos, die du nicht brauchst (die Schaltfläche **Diese Seite entfernen**, ✕,
  auf jedem), oder mach zwei Lektionen.
- **„… ist passwortgeschützt: Speichere es ohne Passwort und füge es dann erneut hinzu.“** Öffne
  das PDF, speichere es ohne Passwort (oder drucke es in ein neues PDF), dann füge es erneut hinzu.
- **Falsch gelesene Wörter in einem PDF**: Ein gescanntes PDF besteht nur aus Bildern, die wie
  Fotos gelesen werden. Ein am Computer erstelltes PDF gibt der KI seinen genauen Text.
