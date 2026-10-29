---
title: "Die Karten in Anki"
description: "Wohin Notosaurus die Karten in Anki legt, wie sie aussehen, wie eine erneut gesendete Lektion sie aktualisiert, und ✎ Notosaurus, um eine aus Anki heraus zu korrigieren."
---

Ob sie aus der App (in AnkiDroid) oder vom Computer (in Anki) kommen, die Karten sind dieselben:
dieselben Stapel, dieselben Kartentypen, dieselben Aktualisierungen. Wie man sie sendet: siehe
[Die App und AnkiDroid](../app-ankidroid/) oder [An Anki senden](../send-to-anki/).

## Die Stapel

Jede Lektion hat ihren Stapel, zum Beispiel `Spanisch::Unidad 3 - En la escuela`: `::` legt einen
Stapel in einen anderen, sodass die Lektionen eines Fachs zusammen gruppiert sind. Karten mit
einem Abschnitt (Vokabeln, Quiz…) kommen in einen Unterstapel des Lektionsstapels.

![Die Stapel von Notosaurus in Anki](../../../assets/screenshots/en/anki-decks.png)

Um ein ganzes Fach zu lernen, klicke auf seinen Stapel: Anki nimmt die Karten aller Stapel darin.

## Eine Lektion erneut senden

Ist die Lektion gesendet, zeigt die Schaltfläche **✓ In Anki aktuell**, dann **🔄 In Anki
aktualisieren**, sobald sich etwas ändert. Du kannst eine Lektion korrigieren und so oft du
willst erneut senden:

- ihre Karten werden in Anki **aktualisiert**, **nicht verdoppelt**, und jede Karte behält ihren
  Lernverlauf, auch wenn du ihre Vorderseite korrigiert hast;
- hast du den Stapel der Lektion geändert, werden ihre Karten dorthin **verschoben**, mit ihrem
  Verlauf;
- seit dem letzten Senden hinzugefügte Karten werden hinzugefügt;
- aus der Lektion gelöschte Karten bleiben in Anki: Nach dem Senden listet Notosaurus sie auf und
  bietet an, sie zu löschen (mit ihrem Lernverlauf), nie ohne zu fragen.

Eine ganze Lektion in Notosaurus zu löschen, bietet an, ihre Karten in Anki mitzulöschen, mit
ihrem Lernverlauf.

Am Computer verschiebt das Ändern einer Kartenoption (die umgekehrte Karte, die eingetippte
Antwort) bei einer schon gesendeten Lektion ihre Karten in den passenden Notiztyp, Verlauf
erhalten.

In Anki tragen die Notizen jeder Lektion ein Schlagwort `notosaurus::<Lektion>`: praktisch, um
sie in der Kartenverwaltung zu finden.

## Eine Karte aus Anki heraus korrigieren

Unter jeder Antwort öffnet ein kleines **✎ Notosaurus** die Karte in Notosaurus, um sie zu
korrigieren: in der App auf Android (AnkiDroid öffnet zuerst eine kurze Webseite, deren
Schaltfläche die App öffnet), auf der Seite am Computer (Anki geöffnet, Notosaurus auf seinem
üblichen Port). Nichts geht verloren: Die Korrektur aktualisiert dieselbe Notiz, ihr Lernverlauf
bleibt. Der Link weiß nur, wo die Lektion liegt: Eine am Computer erstellte Lektion öffnet sich
dort, eine in der App erstellte in der App. AnkiWeb und AnkiMobile zeigen ihn nicht.

Bis AnkiDroid 2.25.2 schalte zuerst **Einstellungen → Erweitert → Erlauben Karteikarten, andere
Apps zu öffnen** ein: Ohne das blockiert AnkiDroid jeden Link auf einer Karte („Sicherheit:
Karteikarten wurde daran gesperrt, eine andere App zu starten“). Ab AnkiDroid 2.25.3 gehen Links
zu einer Webseite auch ohne das durch.

## Wie sie aussehen

So sehen die [Kartentypen](../card-types/) beim Lernen in Anki am Computer aus. AnkiDroid und
AnkiMobile zeigen dieselben Karten.

**Frage und Antwort**: ein Wort mit seinem Audio (▶) und einer Notiz.

![Eine Vokabelkarte in Anki](../../../assets/screenshots/en/anki-vocab.png)

**Lückentext**: Die Frage verdeckt das Wort, die Antwort zeigt es.

![Eine Lückentextkarte: die Frage](../../../assets/screenshots/en/anki-cloze-q.png)

![Eine Lückentextkarte: die Antwort](../../../assets/screenshots/en/anki-cloze-a.png)

**Multiple Choice**: Die Antwort markiert die richtige Wahl mit ✔ und gibt die Erklärung.

![Eine Multiple-Choice-Karte: die Frage](../../../assets/screenshots/en/anki-quiz-q.png)

![Eine Multiple-Choice-Karte: die Antwort](../../../assets/screenshots/en/anki-quiz-a.png)

**Abbildungen**: das Foto der Lektion mit nummerierten Beschriftungen; eine Karte pro zu
benennender Beschriftung.

![Eine Abbildungskarte in Anki](../../../assets/screenshots/en/anki-diagram.png)

**Bilder**: eine Zeichnung, die in der Lernsprache zu benennen ist, mit ihrem Audio.

![Eine Bildkarte in Anki](../../../assets/screenshots/en/anki-picture.png)

**Figuren**: Die von Notosaurus gezeichnete Figur kommt mit der Frage.

![Eine Karte mit einer Figur in Anki](../../../assets/screenshots/en/anki-figure.png)
