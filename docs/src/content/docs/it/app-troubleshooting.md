---
title: "Risolvere i problemi dell'app"
description: "Cosa fare quando l'app Android dice che i crediti sono finiti, che la prova o l'abbonamento sono terminati, che AnkiDroid non accetta le carte o che il computer non risponde."
---

I messaggi qui sotto sono quelli che mostra l'app.

## L'abbonamento

| Messaggio | Cosa fare |
|---|---|
| "Crediti esauriti per questo mese" | Tornano al prossimo rinnovo: **🔑 Abbonamento**, nelle impostazioni, dice quando. |
| "La tua prova gratuita è finita" | Abbonati nelle Impostazioni (**🔑 Abbonamento**) per continuare. |
| "Al momento nessuna nuova prova gratuita…" | Le nuove prove gratuite sono sospese per ora: abbonati nelle Impostazioni, o riprova domani. Una prova già iniziata continua. |
| "Il tuo abbonamento è terminato" | Abbonati di nuovo nell'app. |
| "Pagamento in sospeso" | Google Play non è riuscito a rinnovare l'abbonamento: aggiorna il metodo di pagamento in Google Play (**Impostazioni → Gestisci l'abbonamento**). |
| "La prova gratuita è possibile solo con l'app installata da Google Play, su un vero telefono" | Installa l'app da Google Play; la prova non è offerta su un emulatore. |
| "Nessun abbonamento trovato su questo account Google" (**Ho già un abbonamento**) | Controlla che il telefono usi l'account Google con cui è stato preso l'abbonamento. |

Vedi [L'abbonamento](../app-subscription/).

## AnkiDroid

| Messaggio | Cosa fare |
|---|---|
| "Notosaurus non ha il permesso di aggiungere carte ad AnkiDroid" | **Impostazioni → 📥 AnkiDroid → Consenti**, poi aggiungi di nuovo le carte. Rifiutato per sempre (Android non chiede più): consentilo nelle impostazioni di Android, **App → Notosaurus → Autorizzazioni**. |
| "AnkiDroid non è installato" / "AnkiDroid non ha accettato le carte" | Installa AnkiDroid, **aprilo una volta** (crea la sua raccolta), poi aggiungi di nuovo le carte. |

**✎ Notosaurus non fa nulla in AnkiDroid** ("Security: Card blocked from launching another
app"): fino ad AnkiDroid 2.25.2, attiva in AnkiDroid **Impostazioni → Avanzate → Allow cards to
launch other apps**, oppure aggiorna AnkiDroid (da 2.25.3, il link passa anche senza).

**Carte senza audio**: le voci del servizio Notosaurus non hanno risposto (il telefono ha bisogno
di Internet). Le carte vengono inviate senza audio, e il messaggio dice quante. Aggiungi di nuovo
la lezione ad Anki più tardi: gli audio mancanti vengono aggiunti.

Vedi [L'app e AnkiDroid](../app-ankidroid/).

## Con il tuo computer

| Messaggio | Cosa fare |
|---|---|
| "💻 Il tuo computer non risponde" | Anki deve essere aperto sul computer con l'add-on, e il telefono sulla stessa Wi-Fi. **Riprova**, oppure **Scansiona di nuovo il codice QR** se l'indirizzo del computer è cambiato. |

Vedi [Con il tuo computer](../app-with-computer/).

## Le carte

**Le carte sono sbagliate o ne mancano.** Controlla la foto (vedi [Foto e PDF](../photos/)), sii
più preciso nelle istruzioni, oppure correggile con l'IA (vedi [Rileggere le carte](../review/)).

**Segnalalo.** Una carta che non va (una parola letta male, una risposta sbagliata, una figura
storta, un'immagine inadatta): **⋯ → ⚑ Segnala** su di essa, con due parole su ciò che ti
aspettavi. Ogni segnalazione viene letta, ed è così che questi errori vengono corretti. Vedi
[Segnalare un problema](../review/#segnalare-un-problema).

## Un PDF non si aggiunge

- **"Ci sono già 10 pagine: togline qualcuna prima di aggiungere un PDF."** Una lezione contiene 10
  pagine: togli le foto che non ti servono (il pulsante **Togli questa pagina**, ✕, su ciascuna),
  oppure fai due lezioni.
- **"… è protetto da password: salvalo senza password, poi aggiungilo di nuovo."** Apri il PDF,
  salvalo senza password (o stampalo in un nuovo PDF), poi aggiungilo di nuovo.
- **Parole lette male in un PDF**: un PDF scansionato contiene solo immagini, lette come foto. Un
  PDF creato al computer dà all'IA il suo testo esatto.

## Ancora non funziona?

Segnala il bug su GitHub, con il [modulo Bug](https://github.com/cchabanois/notosaurus/issues/new?template=bug.yml) (serve un account GitHub, gratuito), con la
versione (**Impostazioni → ℹ️ Informazioni**). La issue è pubblica: mai la foto di un quaderno né il
nome di un bambino. Una carta sbagliata: **⋯ → ⚑ Segnala** su di essa, nell'app, è più rapido.
