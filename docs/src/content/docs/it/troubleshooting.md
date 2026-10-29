---
title: "Risolvere i problemi dell'add-on"
description: "Cosa fare quando l'add-on non si avvia, il telefono non si collega, l'IA non riesce o le carte non arrivano in Anki."
---

I messaggi qui sotto sono quelli che mostra Notosaurus. Quando qualcosa va storto nell'add-on,
**Strumenti → Notosaurus → Registro del server** mostra cosa è successo, e **Riavvia il server**
spesso risolve.

## Notosaurus non si avvia

**"Notosaurus non è avviato."** Hai rifiutato l'installazione dei suoi componenti al primo avvio.
Per installarli: **Strumenti → Notosaurus → Apri Notosaurus**.

**"Impossibile scaricare uv da GitHub"** o **"Impossibile installare i componenti di
Notosaurus".** Il primo avvio scarica circa 300 MB: controlla la connessione a Internet, poi
**Strumenti → Notosaurus → Riavvia il server**. Il registro dice cosa non è andato.

**Il server si ferma subito dopo l'avvio.** Un altro programma potrebbe usare la porta 8000, per
esempio un Notosaurus avviato in autonomo nello stesso momento. Fermalo, o scegli un'altra porta
nella configurazione dell'add-on (**Strumenti → Add-on → Notosaurus → Configura**, `port`), poi
riavvia Anki.

## Il telefono non riesce ad aprire Notosaurus

Vedi anche [Sul telefono](../phone/).

- Il telefono e il computer devono essere sulla **stessa Wi-Fi**. Una rete "ospiti" spesso tiene
  separati i suoi dispositivi: usa quella principale.
- Su Windows, autorizza Anki (o Python) quando il **firewall** lo chiede, la prima volta.
- Se l'indirizzo del computer è cambiato (dopo aver riavviato il router), **scansiona di nuovo il
  codice QR**: **Strumenti → Notosaurus → Apri sul telefono…**.
- **"Il server ascolta solo su questo computer"**: imposta `host` su `0.0.0.0` nella
  configurazione dell'add-on.
- **"Questo dispositivo non è ancora autorizzato"**: il telefono non ha scansionato il codice QR,
  o tutti i telefoni sono stati disconnessi. Scansionalo di nuovo.

## Le impostazioni non si aprono sul telefono

**"Le impostazioni si aprono da Anki, sul computer."** È voluto: nell'add-on, le impostazioni (e le
chiavi API) sono raggiungibili solo sul computer stesso. Aprile con **Strumenti → Notosaurus →
Impostazioni**.

## L'IA non riesce

| Messaggio | Cosa fare |
|---|---|
| "Chiave mancante" / "Chiave … non valida" | Incolla di nuovo la chiave in **Impostazioni → Accesso**, poi **🔌 Prova**. |
| "… è sovraccarico in questo momento" | Frequente con Gemini: riprova tra un minuto. I modelli di riserva subentrano automaticamente. |
| "Quota … raggiunta" | È stato raggiunto il limite di una chiave gratuita: aspetta, o attiva la fatturazione. |
| "Risposta interrotta: troppe carte in una volta" | Invia meno pagine alla volta, o chiedi meno carte. |
| "Il modello non ha restituito carte valide" | Riprova; se continua, scegli un altro modello. |
| Il modello "non sembra vedere l'immagine" (Prova) | Il modello non legge immagini: scegli un modello con visione. |

## Le carte sono sbagliate o ne mancano

Controlla la foto (vedi [Foto e PDF](../photos/)), sii più preciso nelle istruzioni, oppure
correggile con l'IA (vedi [Rileggere le carte](../review/)). Con la scrittura a mano, Claude legge
meglio: vedi [Impostazioni e servizi di IA](../ai-services/).

## Un PDF non si aggiunge

- **"Ci sono già 10 pagine: togline qualcuna prima di aggiungere un PDF."** Una lezione contiene 10
  pagine: togli le foto che non ti servono (il pulsante **Togli questa pagina**, ✕, su ciascuna),
  oppure fai due lezioni.
- **"… è protetto da password: salvalo senza password, poi aggiungilo di nuovo."** Apri il PDF,
  salvalo senza password (o stampalo in un nuovo PDF), poi aggiungilo di nuovo.
- **Parole lette male in un PDF**: un PDF scansionato contiene solo immagini, lette come foto. Un
  PDF creato al computer dà all'IA il suo testo esatto.

## Le carte non arrivano in Anki

- **"Anki non è raggiungibile"**: avvia Anki sul computer. In autonomo, Anki ha bisogno dell'add-on
  AnkiConnect.
- **"Nessun profilo aperto in Anki"**: apri il profilo del figlio, poi invia di nuovo.
- **Un avviso su un altro profilo**: la lezione è di un figlio diverso da quello del profilo aperto
  in Anki. Apri il profilo giusto, o conferma.
- **Le carte non arrivano sul telefono**: il messaggio dice "nessuna sincronizzazione con AnkiWeb"
  quando il profilo non è collegato ad AnkiWeb. Fai clic una volta su **Sincronizza** in Anki per
  accedere, poi invia di nuovo. Sul telefono, sincronizza AnkiDroid o AnkiMobile.
- **Carte senza audio**: il servizio vocale non ha risposto (serve Internet). Invia di nuovo la
  lezione più tardi: l'audio mancante viene aggiunto.

## Ancora non funziona?

Segnala il bug su GitHub, con il [modulo Bug](https://github.com/cchabanois/notosaurus/issues/new?template=bug.yml) (serve un account GitHub, gratuito). Incolla le
righe di **Strumenti → Notosaurus → Registro del server** attorno al problema, e la versione (in
fondo alla pagina delle impostazioni). La issue è pubblica: mai la foto di un quaderno né il nome di
un bambino.

## Disinstallare l'add-on

In Anki, **Strumenti → Add-on**, seleziona Notosaurus, **Elimina**. I suoi componenti e **la sua
cartella dati (lezioni, foto, impostazioni) vengono eliminati anch'essi**: copia prima la cartella
dati se vuoi tenerli (vedi [Privacy e sicurezza sul computer](../privacy/#dove-sono-i-dati)). Le
carte già inviate restano in Anki.
