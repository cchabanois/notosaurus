---
title: "Die App und AnkiDroid"
description: "Wie die App die Karten in AnkiDroid legt: ihre Berechtigung, Aktualisierungen ohne Duplikate, AnkiDroid öffnen, eine Karte aus AnkiDroid heraus korrigieren und der gefilterte Stapel eines Tests."
---

Auf diesem Handy kommen die Karten in **AnkiDroid**, die kostenlose Anki-App für Android: kein
`.apkg`, kein Computer, kein Warten auf die Synchronisierung.

## Beim ersten Mal

1. **Installiere AnkiDroid** aus Google Play, falls es fehlt: Die App öffnet dann seine Seite.
2. **Öffne AnkiDroid einmal**, damit es seine Sammlung anlegt.
3. Beim ersten **📥 Zu Anki hinzufügen** fragt AnkiDroid, ob Notosaurus Karten hinzufügen darf
   (ein Dialog von AnkiDroid selbst): Erlaube es.

**📥 AnkiDroid**, in den Einstellungen der App, sagt, wie es steht: **✓ AnkiDroid ist installiert
und Notosaurus darf Karten hinzufügen.**, oder eine Schaltfläche **AnkiDroid installieren** oder
**Erlauben**.

![AnkiDroid fragt, ob Notosaurus auf Notizen, Karten, Notiztypen und Stapel zugreifen und sie anlegen darf](../../../assets/screenshots/en/app-ankidroid-permission.png)

## Die Karten senden

**📥 Zu Anki hinzufügen** schreibt die Karten in AnkiDroid, in den Stapel der Lektion, mit ihren
Tönen und Bildern. Wie am Computer:

- **Erneut gesendet** **aktualisiert** eine Lektion ihre Karten, statt sie zu verdoppeln, und ihr
  Lernverlauf bleibt.
- **Aus der Lektion gelöschte Karten** bleiben in AnkiDroid: Nach dem Senden listet die App sie
  auf und bietet an, sie zu löschen (mit ihrem Lernverlauf), nie ohne zu fragen.
- **Eine Lektion löschen** bietet an, ihre Karten in AnkiDroid mitzulöschen.

AnkiDroid synchronisiert die Karten wie üblich mit AnkiWeb, wenn es mit einem Konto verbunden ist:
Dann kommen sie in Anki auf einem Computer oder auf einem anderen Handy an.

## AnkiDroid öffnen

**AnkiDroid öffnen**, oben auf der Seite und an ihrem Ende, öffnet es mit einem Tippen, um die
gerade gesendeten Karten zu lernen.

![Die Stapel in AnkiDroid nach dem Senden von Lektionen aus der App: ein Stapel pro Fach, ein Unterstapel pro Lektion](../../../assets/screenshots/en/app-ankidroid-decks.png)

## Eine Karte aus AnkiDroid heraus korrigieren

Unter jeder Antwort in AnkiDroid öffnet ein kleines **✎ Notosaurus** die Karte in der App, um sie
zu korrigieren (AnkiDroid öffnet zuerst eine kurze Webseite, deren Schaltfläche die App öffnet).
Die Korrektur aktualisiert dieselbe Notiz: Ihr Lernverlauf bleibt. Eine mit dem Computer
erstellte Lektion ([Mit deinem Computer](../app-with-computer/)) öffnet sich auf dem Computer,
nicht in der App.

Bis **AnkiDroid 2.25.2** schalte in AnkiDroid zuerst **Einstellungen → Erweitert → Erlauben
Karteikarten, andere Apps zu öffnen** ein: Ohne das blockiert AnkiDroid jeden Link auf einer Karte
(„Sicherheit: Karteikarten wurde daran gesperrt, eine andere App zu starten“). Ab AnkiDroid 2.25.3
gehen Links zu einer Webseite auch ohne das durch.

![Eine Karte in AnkiDroid mit ihrem Ton und, unter der Antwort, ✎ Notosaurus](../../../assets/screenshots/en/app-ankidroid-card.png)

## Der gefilterte Stapel eines Tests

Ein Test zum Vorbereiten sammelt Karten mehrerer Lektionen unter einem Schlagwort (siehe
[Einen Test vorbereiten](../tests/)). In seinem Fenster öffnet **In AnkiDroid öffnen** die Karten
des Tests in der Kartenübersicht von AnkiDroid, egal in welchen Stapeln; dann **⋮ → Gefilterten
Stapel erstellen → Erstellen** (bei mehr als 100 Karten erhöhe zuerst **Beschränken auf**).
AnkiDroid lässt keine andere App selbst einen gefilterten Stapel anlegen.

Geht etwas schief? Siehe [Fehlerbehebung in der App](../app-troubleshooting/).
