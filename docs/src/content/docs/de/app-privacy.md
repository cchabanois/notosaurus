---
title: "Datenschutzerklärung der Android-App"
description: "Die Daten, die die Android-App von Notosaurus und ihr Dienst verarbeiten, warum, wo, wie lange, und deine Rechte."
---

*Zuletzt aktualisiert: 21. Oktober 2026.*

Diese Seite betrifft **die Notosaurus-App für Android** und **den Notosaurus-Dienst**, den sie
nutzt, um die Fotos zu lesen und die Karten und Stimmen zu erstellen. Notosaurus auf einem
Computer (die Anki-Erweiterung) funktioniert anders: siehe [Datenschutz und Sicherheit](../privacy/).

**Verantwortlicher**: CHABANOIS Cédric.
**Kontakt**: notosaurus.app@gmail.com

**Wer die App nutzt**: ein **Elternteil** (ein Erwachsener), der das Lernen seiner Kinder
vorbereitet. Die App ist nicht dafür gemacht, von einem Kind benutzt zu werden.

## Kurz gesagt

- Deine **Lektionen bleiben auf deinem Handy**: Fotos, Karten, Anweisungen, Töne.
- Was die KI lesen muss (Fotos, Anweisungen, Diktate), **geht beim Erstellen der Karten über den
  Dienst** **und wird dort nicht gespeichert**.
- Die KI (**Gemini von Google**) und die Stimmen werden **in der Europäischen Union verarbeitet**.
  Google nutzt sie nicht, um seine Modelle zu trainieren.
- **Keine Werbung, keine Statistik, kein Tracking**, und nichts wird verkauft.
- Der Dienst speichert nur deine **Lizenz** (ihren Fingerabdruck, deinen Tarif und deine Credits)
  und was du mit ⚑ **meldest**, falls du es tust.

## Was auf deinem Handy bleibt

Lektionen (Fotos der Seiten, Karten, Anweisungen, Bilder der Karten, Töne), deine gespeicherten
Anweisungen und deine Einstellungen, einschließlich deines Lizenzschlüssels, werden **im privaten
Speicher der App** auf deinem Handy aufbewahrt. Andere Apps können nicht darauf zugreifen. Sie
werden gelöscht, wenn du eine Lektion oder die App löschst.

Die an **AnkiDroid** gesendeten Karten werden auf deinem Handy dort hineingeschrieben. Ihre
Synchronisierung mit AnkiWeb ist Sache von AnkiDroid und deinem AnkiWeb-Konto, nicht von
Notosaurus.

## Was über den Notosaurus-Dienst geht

Wenn du darum bittest, schickt die App dem Dienst über HTTPS:

| Was | Wofür |
|---|---|
| Die **Fotos** der Seiten und ihr Text (PDF), die **Anweisung**, deine festen Anweisungen, deine Stapelnamen | Die Karten der Lektion erstellen oder ergänzen |
| Die **Karten** einer Lektion und deine Korrektur | Sie korrigieren, eine Karte erklären, eine Anweisung aufräumen |
| Eine **Aufnahme deiner Stimme** (🎤) | Sie als Text schreiben (eine Anweisung oder eine Korrektur diktieren) |
| Die **Rückseite** einer Karte | Sie vorlesen (die Stimmen der Karten) |
| Die **Beschreibung** eines Bildes oder ein paar **Stichwörter** | Das Bild einer Karte zeichnen oder ein freies suchen |
| Dein **Lizenzschlüssel** | Deine Lizenz prüfen und deine Credits zählen |
| Wenn du ein Abo abschließt: das **Token deines Kaufs** bei Google Play | Das Abo bei Google Play prüfen und es zu deiner Lizenz machen |
| Für die **kostenlose Testphase**: ein **Fingerabdruck des Handys** (von der App berechnet, nie seine Kennung selbst) und die **Play Integrity**-Bestätigung von Google | Die Testphase nur einmal pro Handy anbieten, der aus Google Play installierten App auf einem echten Handy |

Der Dienst gibt diese Inhalte an die unten genannten Auftragsverarbeiter weiter, schickt das
Ergebnis an die App zurück und **speichert sie nicht**: Kein Foto, keine Karte, keine Aufnahme und
kein Lektionstext wird gespeichert oder in seine Protokolle geschrieben. Außer einer **Meldung**:
siehe unten.

Eine Heftseite zeigt oft den **Namen des Kindes**. Vor dem Senden eines Fotos kannst du ihn
**verdecken**: 🖍️ auf dem Foto, dann mit dem Finger schwärzen. Nur das geschwärzte Foto geht
hinaus und bleibt in der Lektion.

## Was der Dienst speichert

- **Deine Lizenz**: den Fingerabdruck ihres Schlüssels (nicht den Schlüssel selbst), deinen Tarif,
  deine übrigen Credits, ihr Erneuerungsdatum, was an diesem Tag verbraucht wurde, und eine kurze
  Notiz für den Support (zum Beispiel eine Bestellnummer). Gespeichert, solange sie gültig ist,
  dann **12 Monate** nach ihrem Ende (um eine Frage oder eine Reklamation zu beantworten), dann
  gelöscht.
- **Was du mit ⚑ meldest** (eine von der KI gemachte Karte, mit ihrer Erklärung, wenn sie
  angezeigt wird, und ihrem Bild, außer einem Foto, das du gemacht hast; anstößig oder falsch),
  falls du es tust: genau das, was die App dir vor dem Senden zeigt, den Grund, deinen Kommentar,
  die Anweisungen der Lektion, die Sprache und eine kurze Lizenzkennung. Nie die Fotos der Lektion
  oder den Namen des Kindes. Von Notosaurus gelesen, um die Inhalte der KI zu verbessern,
  **180 Tage** gespeichert, dann gelöscht.
- **Deine E-Mails an den Support**, falls vorhanden: **12 Monate** nach dem letzten Austausch
  gespeichert.
- **Technische Protokolle**, **30 Tage** gespeichert, um den Dienst zu betreiben und Ausfälle und
  Missbrauch zu erkennen: die Uhrzeit, die verlangte Aktion („eine Lektion erstellen“…), ihre
  Dauer, ihr Ergebnis, das KI-Modell und die verbrauchten Credits, die Version der App, eine kurze
  Lizenzkennung und, wie bei jeder Website, die **IP-Adresse** der Anfrage. Nie der Inhalt der
  Lektionen.

## Auftragsverarbeiter

| Dienst | Was er erhält | Wo |
|---|---|---|
| **Google Cloud**: Vertex AI (Gemini) | Fotos, Anweisungen, Karten, Diktate, Bildbeschreibungen | Europäische Union |
| **Google Cloud**: Cloud Run, Firestore, Protokolle | Der Dienst selbst, die Lizenzen, die Protokolle | Belgien (europe-west1) |
| **Google Cloud**: Text-to-Speech | Der vorzulesende Text (die Rückseite einer Karte) | Europäische Union |
| **Wikimedia Commons**, **Openverse**, **Pixabay** | Ein paar englische Stichwörter („dog“), nie ein Foto | Ihre Server |
| **Google Play**: Abos, Play Integrity | Das Token eines Kaufs; die Bestätigung für die kostenlose Testphase | Seine Server |
| **GitHub** (GitHub Pages) | Beim Start liest die App dort die Adresse des Dienstes: GitHub sieht deine IP-Adresse | Seine Server |

Google handelt als Auftragsverarbeiter nach den Bedingungen von Google Cloud und nutzt diese
Daten nicht, um seine Modelle zu trainieren. Um Missbrauch zu erkennen, kann Google die an Gemini
gesendeten Anfragen nach seinen Bedingungen jedoch **bis zu 90 Tage** aufbewahren, ohne sie für
etwas anderes zu nutzen.

### Übermittlungen außerhalb der Europäischen Union

Die Verarbeitung findet in der Europäischen Union statt, aber Google, GitHub, die Wikimedia
Foundation und Openverse sind US-Organisationen, die darauf zugreifen können. Diese Übermittlungen
sind durch die **Standardvertragsklauseln** der Europäischen Kommission abgedeckt und, für
zertifizierte Unternehmen wie Google, durch das **EU-US Data Privacy Framework**. Pixabay ist ein
Unternehmen aus der EU.

## Warum: die Rechtsgrundlagen

| Verarbeitung | Rechtsgrundlage |
|---|---|
| Karten erstellen, ergänzen, korrigieren und erklären; Diktat; Stimmen; Bilder | **Erbringung des Dienstes**, den du anforderst |
| Deine Lizenz prüfen und deine Credits zählen | **Erfüllung des Vertrags** (deine Lizenz) |
| Technische Protokolle, Sicherheit, Bekämpfung von Missbrauch | Das **berechtigte Interesse** am Betrieb eines sicheren Dienstes |
| Die kostenlose Testphase nur einmal pro Handy (Play Integrity) | Das **berechtigte Interesse**, Missbrauch der Testphase zu verhindern |
| Deine Meldungen zu Inhalten der KI | Deine **Anfrage** und das berechtigte Interesse an einer KI, die passende Inhalte macht |
| Das Mikrofon | Deine **Einwilligung**, beim ersten Diktat erbeten und in den Einstellungen des Handys widerrufbar |
| Deine E-Mails beantworten | Deine **Anfrage** |

Notosaurus trifft **keine automatisierte Entscheidung** über dich und betreibt **kein
Profiling**. Ohne deine Lizenz kann der Dienst nicht erbracht werden; alles andere wird nur
gesendet, wenn du darum bittest.

## Der Modus „Mit meinem Computer“

Wenn die App Notosaurus auf deinem Computer öffnet (die Anki-Erweiterung), spricht das Handy
direkt mit dem Computer, im WLAN zu Hause: Dann geht nichts über den Notosaurus-Dienst. Es gilt
die Seite [Datenschutz und Sicherheit](../privacy/).

## Die Berechtigungen der App

- **Internet**: um den Dienst zu erreichen.
- **Mikrofon**, beim ersten Tippen auf 🎤 erbeten und nur beim Diktieren benutzt.
- **AnkiDroid**, um Karten hinzuzufügen, beim ersten Senden erbeten.
- Fotos werden mit der Kamera des Handys gemacht oder in der Galerie ausgewählt, wenn du es tust.
  Die App braucht keinen Zugriff auf alle deine Fotos.

## Kinder

Die App wird von **einem Elternteil** benutzt, nicht vom Kind. Heftfotos können aber Daten des
Kindes enthalten (seinen Namen, seine Handschrift): Verdecke den Namen vor dem Senden mit 🖍️ und
schreib nichts Persönliches in die Anweisungen.

## Deine Rechte

Wenn du an **notosaurus.app@gmail.com** schreibst, kannst du:

- **Auskunft** über deine Daten erhalten und eine Kopie davon bekommen (**Datenübertragbarkeit**);
- sie **berichtigen** oder **löschen** lassen;
- ihre Verarbeitung **einschränken** oder der auf berechtigtem Interesse beruhenden Verarbeitung
  **widersprechen**;
- **deine Einwilligung** (das Mikrofon) jederzeit **widerrufen**, ohne Wirkung auf das, was vorher
  geschah.

Die Lektionen sind auf deinem Handy: Du löschst sie selbst in der App. Du bekommst innerhalb
eines Monats eine Antwort. Du kannst dich auch bei deiner Datenschutzbehörde beschweren (in
Frankreich bei der CNIL: cnil.fr).

## Sicherheit

Jeder Austausch mit dem Dienst nutzt **HTTPS**. Vom Dienst wird nur der Fingerabdruck deines
Lizenzschlüssels gespeichert. Auf deinem Handy bleibt der Schlüssel im privaten Speicher der App,
und die Einstellungen zeigen nur seine letzten Zeichen.

## Änderungen

Ändert sich diese Erklärung, ändert sich auch das Datum oben auf der Seite.
