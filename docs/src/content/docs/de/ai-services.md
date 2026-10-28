---
title: "Einstellungen und KI-Dienste"
description: "Die Einstellungen der Erweiterung am Computer; welchen KI-Dienst wählen, wie man Schritt für Schritt seinen API-Schlüssel bekommt, das Modell, lokale Modelle, und was eine Lektion kostet."
---

Notosaurus hat keine eigene KI: Es nutzt den Dienst, den du wählst, mit **deinem eigenen
Schlüssel**. Du bezahlst den Dienst direkt, für das, was du nutzt: kein Abo.

## Die Einstellungen

Am Computer öffnet **Extras → Notosaurus → Einstellungen** sie im Browser. Sie öffnen sich nur am
Computer selbst: Ein Handy kann sie weder ändern noch die Schlüssel sehen. Eigenständig oder mit
Docker ist die Einstellungsseite (`/admin.html`) aus dem Netzwerk erreichbar, geschützt durch ein
**🔐 Admin-Passwort**, das beim ersten Besuch angelegt wird.

Was nur der Computer hat:

- **KI-Dienst**, **Zugang** (die API-Schlüssel) und **Modell**: siehe unten.
- **Bilder auf den Karten**: der **Dienst, der sie zeichnet** (der der Karten, wenn er zeichnen
  kann: Gemini, OpenAI, OpenRouter; Claude und lokale Modelle können es nicht) und sein
  **Bildmodell**, mit **🖼️ Testen: eine Giraffe zeichnen**. Siehe
  [Kartentypen](../card-types/#bilder).
- **📥 Direkt an Anki senden**: AnkiConnect, eigenständig, und die Synchronisierung mit AnkiWeb.
  Siehe [An Anki senden](../send-to-anki/).
- **📱 Handys**: der QR-Code, der Notosaurus auf einem Handy öffnet und es zulässt, und **Alle
  Handys abmelden**. Siehe [Auf dem Handy](../phone/) und [Datenschutz und Sicherheit](../privacy/).
- **Lektionen**: wem jede Lektion gehört, was sie gekostet hat, sie löschen (siehe
  [Was es kostet](#was-es-kostet)).

![Einstellungen: die Handys, per QR-Code](../../../assets/screenshots/en/settings-phones.png)

**📝 Anweisungen für die KI** und **Stimmen der Karten** gibt es auch in den Einstellungen der
Android-App: siehe [Anweisungen](../instructions/#feste-anweisungen) und [Stimmen](../voices/).

## Welcher Dienst?

| Dienst | Für wen | Kosten einer Lektion |
|---|---|---|
| **Gemini** (Google) | der Standard: schnell, günstig, liest gut; ein kostenloses Kontingent zum Ausprobieren | ein Bruchteil eines Cents |
| **Claude** (Anthropic) | liest Handschrift mit am besten, und am schnellsten (Sonnet) | ein paar Cent |
| **OpenAI** (GPT) | wenn du schon ein OpenAI-Konto hast | ein paar Cent |
| **OpenRouter** | ein Schlüssel für Gemini, Claude, GPT, Mistral…; die genauen Kosten jeder Lektion | der Preis des gewählten Modells |
| **Anderer OpenAI-kompatibler Dienst** | ein Modell zu Hause (Ollama, LM Studio) oder ein anderer Dienst | zu Hause kostenlos |

Wechsle den Dienst jederzeit unter **Einstellungen → KI-Dienst**: Die schon gemachten Lektionen
bleiben, wie sie sind.

![Einstellungen: den KI-Dienst wählen](../../../assets/screenshots/en/settings-ai.png)

## Einen Schlüssel bekommen

Erstelle den Schlüssel auf der Website des Dienstes, füge ihn unter **Einstellungen → Zugang** ein
und tippe auf **🔌 Testen**: Notosaurus prüft, ob das Modell ein Bild liest und im richtigen Format
antwortet. Beim ersten Mal erledigt der
[Einrichtungsassistent](../getting-started/#2-der-einrichtungsassistent) dasselbe in zwei Schritten.

![Einstellungen: der API-Schlüssel und das Modell](../../../assets/screenshots/en/settings-key.png)

### Gemini

1. Öffne [aistudio.google.com/apikey](https://aistudio.google.com/apikey) und melde dich mit einem
   Google-Konto an.
2. **Create API key**, dann kopiere ihn.
3. Das kostenlose Kontingent reicht, um Notosaurus auszuprobieren, aber seine Grenzen sind niedrig
   (ein paar Dutzend Anfragen pro Tag bei den besten Modellen), und Google darf das Gesendete nutzen,
   um seine Produkte zu verbessern. Für die Hefte deiner Kinder aktiviere in Google AI Studio die
   Abrechnung für das Projekt des Schlüssels: Du zahlst dann einen Bruchteil eines Cents pro
   Lektion, und laut den Bedingungen von Google werden deine Daten nicht genutzt, um seine Produkte
   zu verbessern.

### Claude

1. Öffne [console.anthropic.com](https://console.anthropic.com) und lege ein Konto an.
2. Lade unter **Billing** etwas Guthaben auf: Ein paar Euro reichen lange.
3. Unter **Settings → API keys** **Create key**, dann kopiere ihn.

### OpenAI

1. Öffne [platform.openai.com](https://platform.openai.com) und lege ein Konto an.
2. Lade in den Abrechnungseinstellungen etwas Guthaben auf.
3. Erstelle unter **API keys** einen geheimen Schlüssel, dann kopiere ihn.

### OpenRouter

1. Öffne [openrouter.ai](https://openrouter.ai) und melde dich an.
2. Kauf Credits: OpenRouter schlägt auf jeden Kauf eine kleine Gebühr auf, also lieber ein Kauf ab
   15 $ als mehrere kleine.
3. Erstelle unter **Keys** einen Schlüssel, dann kopiere ihn.

Ein OpenRouter-Schlüssel gibt Zugang zu Gemini, Claude, GPT und vielen anderen: praktisch, um sie
zu vergleichen. Standardmäßig nutzt Notosaurus über OpenRouter Gemini Flash.

## Das Modell

- **Notosaurus wählt für dich**: Ist das Feld **Modell** leer, nutzt jeder Dienst seinen Standard,
  das mit ⭐ markierte.
- **Empfohlen, nach unseren Tests**, unter **Modell**, listet die Modelle, die wir für diesen Dienst
  empfehlen, vom besten Preis-Leistungs-Verhältnis bis zum teuersten, mit den Kosten einer Lektion.
  Tippe auf eins, um es zu wählen, oder gib ein beliebiges anderes Modell des Dienstes ein; bei
  OpenAI-kompatiblen Diensten listet **📋 Modelle des Dienstes laden** nur die Modelle, die Bilder
  annehmen.
- **Wie wir sie gewählt haben**, und die Modelle, die man meiden sollte: siehe
  [Welches Modell?](../which-model/).

Gemini hat auch **Ersatzmodelle**, der Reihe nach versucht, wenn das Hauptmodell überlastet oder
nicht im Tarif des Schlüssels enthalten ist (ein kostenloser Schlüssel bekommt nicht das neueste
Modell: Er nutzt dann ein älteres).

## Ein Modell zu Hause

Mit **Anderer OpenAI-kompatibler Dienst** kann Notosaurus ein Modell nutzen, das auf deinem
Computer läuft, mit [Ollama](https://ollama.com) oder [LM Studio](https://lmstudio.ai). Die Adresse
endet meist mit `/v1` (Ollama: `http://localhost:11434/v1`). Nichts verlässt das Haus und nichts
wird bezahlt, aber:

- das Modell muss **Bilder annehmen** (ein „Vision“-Modell): **📋 Modelle des Dienstes laden**
  listet sie;
- es braucht eine **gute Grafikkarte** (oder einen neueren Mac mit viel Speicher);
- es liest **Handschrift viel weniger zuverlässig** als Gemini oder Claude;
- mit Ollama brauchen Korrekturen einen längeren Kontext als den Standard: Setze
  `OLLAMA_CONTEXT_LENGTH` (zum Beispiel auf 16384), bevor du es startest.

## Was es kostet

**Einstellungen → Lektionen** zeigt, was die KI gekostet hat, insgesamt, pro Profil und pro
Lektion, mit jeder Erzeugung, Korrektur und jedem Bild.

![Einstellungen: die Kosten jeder Lektion](../../../assets/screenshots/en/settings-costs.png)

Diese Zahlen sind aus den öffentlichen Preisen der Dienste geschätzt (OpenRouter liefert die
genauen Kosten). Mit einem kostenlosen Gemini-Schlüssel wird tatsächlich nichts berechnet. Als
Beispiel kostete die Vokabellektion dieser Screenshots mit Claude Sonnet etwa 2 US-Cent für die
Erzeugung, und ebenso viel für ihre Korrektur. Bilder kosten weniger als einen Cent bis ein paar
Cent pro Stück; Figuren unter einem Cent (schnell gezeichnet, ein paar Sekunden pro Stück, während
du die Karten durchsiehst). Eine Figur, bei der du Zweifel hast: „🔍“ darunter lässt die KI sie
ansehen; findet sie etwas Falsches, wählst du, ob sie neu gezeichnet wird, mit dem Hinweis auf den
Fehler: schnell (ein paar Sekunden), dann, wenn sie immer noch falsch ist, sorgfältig, mit dem
Nachdenken des Modells (bis zu einer Minute).
