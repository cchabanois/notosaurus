---
title: "Informativa sulla privacy dell'app Android"
description: "I dati che l'app Android di Notosaurus e il suo servizio trattano, perché, dove, per quanto tempo, e i tuoi diritti."
---

*Ultimo aggiornamento: 11 novembre 2026.*

Questa pagina riguarda **l'app Notosaurus per Android** e **il servizio Notosaurus** che usa per
leggere le foto e fare le carte e le voci. Notosaurus su un computer (l'add-on di Anki) funziona
in modo diverso: vedi [Privacy e sicurezza](../privacy/).

**Titolare del trattamento**: CHABANOIS Cédric.
**Contatto**: notosaurus.app@gmail.com

**Chi usa l'app**: un **genitore** (un adulto), che prepara il ripasso dei propri figli. L'app non
è fatta per essere usata da un bambino.

## In breve

- Le tue **lezioni restano sul tuo telefono**: foto, carte, istruzioni, suoni.
- Ciò che l'IA deve leggere (foto, istruzioni) **passa dal servizio** mentre si fanno le
  carte, **e lì non viene conservato**.
- Un **dettato** (🎤) è ascoltato **dal riconoscimento vocale del tuo telefono** (quello scelto
  nelle impostazioni di Android, di solito quello di Google): la tua voce non passa dal servizio.
- L'IA (**Gemini di Google**) è trattata sui server di Google, **che possono trovarsi fuori
  dall'Unione europea**; le voci sono trattate nell'Unione europea. Google non le usa per
  addestrare i suoi modelli.
- **Niente pubblicità, niente statistiche, niente tracciamento**, e niente viene venduto.
- Il servizio conserva solo la tua **licenza** (la sua impronta, il tuo piano e i tuoi crediti), e
  ciò che **segnali** con ⚑, se lo fai.

## Cosa resta sul tuo telefono

Le lezioni (foto delle pagine, carte, istruzioni, immagini delle carte, suoni), le tue istruzioni
salvate e le tue impostazioni, compresa la tua chiave di licenza, sono conservate **nella memoria
privata dell'app** sul tuo telefono. Le altre app non possono accedervi. Vengono eliminate quando
elimini una lezione, o l'app.

Le carte inviate ad **AnkiDroid** vi sono scritte sul tuo telefono. La loro sincronizzazione con
AnkiWeb dipende da AnkiDroid e dal tuo account AnkiWeb, non da Notosaurus.

Le schede dei tuoi figli (nome, classe, mazzi, istruzioni) restano anch'esse sul tuo telefono: solo la classe e le istruzioni di un bambino partono con le sue lezioni, mai il suo nome.

Quando **salvi una copia delle tue lezioni** (💾 nelle impostazioni), il file va dove scegli tu (Drive, la scheda SD, Download…) e segue poi le regole di quel posto.

## Cosa passa dal servizio Notosaurus

Quando lo chiedi, l'app invia al servizio, tramite HTTPS:

| Cosa | Per cosa |
|---|---|
| Le **foto** delle pagine e il loro testo (PDF), l'**istruzione**, le tue istruzioni permanenti, i tuoi nomi di mazzo | Creare o completare le carte della lezione, e ritagliare i disegni delle sue pagine |
| La **classe** del bambino a cui è destinata la lezione, e le istruzioni date per lui (mai il suo nome) | Carte adatte al suo livello |
| Le **carte** di una lezione e la tua correzione | Correggerle, spiegare una carta, mettere in ordine un'istruzione |
| Una **registrazione della tua voce** (🎤), solo su un telefono senza riconoscimento vocale | Scriverla come testo (dettare un'istruzione o una correzione) |
| Il **retro** di una carta | Leggerlo ad alta voce (le voci delle carte) |
| La **descrizione** di un'immagine, o qualche **parola chiave** | Disegnare l'immagine di una carta, o cercarne una libera |
| La tua **chiave di licenza** | Verificare la tua licenza e contare i tuoi crediti |
| Se ti abboni: il **token del tuo acquisto** su Google Play | Verificare l'abbonamento con Google Play e farne la tua licenza |
| Per la **prova gratuita**: un'**impronta del telefono** (calcolata dall'app, mai il suo identificativo) e l'attestazione **Play Integrity** di Google | Offrire la prova una sola volta per telefono, all'app installata da Google Play su un vero telefono |

Il servizio passa questi contenuti ai responsabili del trattamento qui sotto, rimanda il risultato
all'app e **non li conserva**: nessuna foto, carta, registrazione o testo di lezione viene
memorizzato o scritto nei suoi registri. Tranne una **segnalazione**: vedi sotto.

Una pagina di quaderno mostra spesso il **nome del bambino**. Prima di inviare una foto puoi
**nasconderlo**: 🖍️ sulla foto a schermo intero, poi anneriscilo con il dito. Solo la foto annerita esce e resta
nella lezione.

## Cosa conserva il servizio

- **La tua licenza**: l'impronta della sua chiave (non la chiave stessa), il tuo piano, i tuoi
  crediti rimasti, la loro data di rinnovo, ciò che è stato usato quel giorno, e una breve nota per
  l'assistenza (un numero d'ordine, per esempio). Conservata finché è valida, poi **12 mesi** dopo
  la fine (per rispondere a una domanda o a un reclamo), poi eliminata.
- **Ciò che segnali** con ⚑ (una carta fatta dall'IA, con la sua spiegazione se mostrata e la sua
  immagine, tranne una foto scattata da te; offensiva o sbagliata), se lo fai: esattamente ciò che
  l'app ti mostra prima dell'invio, il motivo, il tuo commento, le istruzioni della lezione, la
  lingua e un breve identificativo di licenza. Mai le foto della lezione né il nome del bambino.
  Letto da Notosaurus per migliorare i contenuti dell'IA, conservato **180 giorni**, poi eliminato.
- **Le tue email all'assistenza**, se ce ne sono: conservate **12 mesi** dopo l'ultimo scambio.
- **Registri tecnici**, conservati **30 giorni** per far funzionare il servizio e individuare
  guasti e abusi: l'ora, l'azione richiesta ("fare una lezione"…), la sua durata, il suo esito, il
  modello di IA e i crediti usati, la versione dell'app, un breve identificativo di licenza e, come
  per qualsiasi sito web, l'**indirizzo IP** della richiesta. Mai il contenuto delle lezioni.

## Responsabili del trattamento

| Servizio | Cosa riceve | Dove |
|---|---|---|
| **Google Cloud**: Vertex AI (Gemini) | Foto, istruzioni, carte, dettati, descrizioni di immagini | I suoi server, nel mondo (anche fuori dall'Unione europea) |
| **Google Cloud**: Cloud Run, Firestore, registri | Il servizio stesso, le licenze, i registri | Belgio (europe-west1) |
| **Google Cloud**: Text-to-Speech | Il testo da leggere (il retro di una carta) | Unione europea |
| **Wikimedia Commons**, **Openverse**, **Pixabay** | Qualche parola chiave in inglese ("dog"), mai una foto | I loro server |
| **Google Play**: abbonamenti, Play Integrity | Il token di un acquisto; l'attestazione della prova gratuita | I suoi server |
| **GitHub** (GitHub Pages) | All'avvio, l'app vi legge l'indirizzo del servizio: GitHub vede il tuo indirizzo IP | I suoi server |

Google agisce come responsabile del trattamento, secondo le condizioni di Google Cloud, e non usa
questi dati per addestrare i suoi modelli. Per individuare abusi, Google può tuttavia conservare le
richieste inviate a Gemini **fino a 90 giorni**, secondo le sue condizioni, senza usarle per
nient'altro.

### Trasferimenti al di fuori dell'Unione europea

L'IA (Gemini) può trattare le tue foto, istruzioni e dettati fuori dall'Unione europea, sui server
di Google; il resto avviene nell'Unione europea, ma Google, GitHub, la Wikimedia Foundation e
Openverse sono organizzazioni statunitensi, che possono accedervi. Questi trasferimenti sono coperti dalle
**clausole contrattuali tipo** della Commissione europea e, per le aziende certificate come
Google, dal **Quadro UE-USA per la protezione dei dati personali**. Pixabay è un'azienda dell'UE.

## Perché: le basi giuridiche

| Trattamento | Base giuridica |
|---|---|
| Fare, completare, correggere e spiegare carte; dettatura; voci; immagini | **Fornire il servizio** che chiedi |
| Verificare la tua licenza e contare i tuoi crediti | **Eseguire il contratto** (la tua licenza) |
| Registri tecnici, sicurezza, lotta agli abusi | Il **legittimo interesse** a far funzionare un servizio sicuro |
| La prova gratuita una sola volta per telefono (Play Integrity) | Il **legittimo interesse** a prevenire l'abuso della prova |
| Le tue segnalazioni sui contenuti dell'IA | La tua **richiesta**, e il legittimo interesse a un'IA che faccia contenuti adatti |
| Il microfono | Il tuo **consenso**, chiesto alla prima dettatura e revocabile nelle impostazioni del telefono |
| Rispondere alle tue email | La tua **richiesta** |

Notosaurus non prende **alcuna decisione automatizzata** su di te e non fa **alcuna
profilazione**. Senza la tua licenza il servizio non può essere fornito; tutto il resto viene
inviato solo quando lo chiedi.

## La modalità "Con il mio computer"

Quando l'app apre Notosaurus sul tuo computer (l'add-on di Anki), il telefono parla direttamente
con il computer, sulla Wi-Fi di casa: allora niente passa dal servizio Notosaurus. Vale la pagina
[Privacy e sicurezza](../privacy/).

## Le autorizzazioni dell'app

- **Internet**: per raggiungere il servizio.
- **Microfono**, chiesto la prima volta che tocchi 🎤, e usato solo durante la dettatura: la tua
  voce è ascoltata dal riconoscimento vocale del telefono (quello di Android, di solito quello di
  Google, sul telefono o sui suoi server, secondo le sue impostazioni) o, su un telefono che non
  ne ha, scritta dall'IA del servizio.
- **AnkiDroid**, per aggiungervi le carte, chiesto al primo invio.
- Le foto vengono scattate con la fotocamera del telefono o scelte nella galleria, quando lo fai
  tu. L'app non ha bisogno di accedere a tutte le tue foto.
- **Notifiche**: nessuna autorizzazione richiesta. Mentre una lezione viene creata o inviata, l'app può continuare qualche minuto in background; dove le notifiche sono consentite, ne mostra una nel frattempo.
- Il **codice QR** del computer viene letto dal lettore di codici dei servizi Google Play, sul telefono: l'app riceve solo l'indirizzo letto, mai l'immagine della fotocamera.

## I bambini

L'app è usata da **un genitore**, non dal bambino. Ma le foto del quaderno possono contenere dati
del bambino (il suo nome, la sua scrittura): nascondi il nome con 🖍️ prima dell'invio, e non
mettere nulla di personale nelle istruzioni.

## I tuoi diritti

Scrivendo a **notosaurus.app@gmail.com**, puoi:

- **accedere** ai tuoi dati e ottenerne una copia (**portabilità**);
- farli **rettificare** o **cancellare**;
- **limitarne** il trattamento, o **opporti** al trattamento basato sul legittimo interesse;
- **revocare il tuo consenso** (il microfono) in qualsiasi momento, senza effetto su ciò che è
  stato fatto prima.

Le lezioni sono sul tuo telefono: le elimini tu stesso nell'app. Ricevi una risposta entro un
mese. Puoi anche presentare reclamo alla tua autorità per la protezione dei dati (in Francia, la
CNIL: cnil.fr).

## Sicurezza

Ogni scambio con il servizio usa **HTTPS**. Il servizio conserva solo l'impronta della tua chiave
di licenza. Sul tuo telefono, la chiave resta nella memoria privata dell'app, e le impostazioni ne
mostrano solo gli ultimi caratteri.

## Eliminare i tuoi dati

Perché il servizio Notosaurus elimini ciò che conserva di te:

1. Scrivi a **notosaurus.app@gmail.com**, oggetto «Elimina i miei dati».
2. Indica gli ultimi caratteri della tua chiave di licenza (⚙️ → 🔑 Abbonamento li mostra), o il
   numero d'ordine Google Play se sei abbonato. Se sei abbonato, disdici prima l'abbonamento in
   Google Play.
3. Li eliminiamo e te lo confermiamo, entro un mese.

**Eliminati**: la tua licenza (l'impronta della sua chiave, il tuo piano, i tuoi crediti), ciò che
hai segnalato con ⚑ e le nostre email. **Mai conservati dal servizio**: le tue lezioni, foto,
registrazioni e carte. I suoi log tecnici si cancellano da soli dopo 30 giorni. Google Play
conserva le tracce dei tuoi pagamenti secondo le proprie condizioni. Le tue lezioni sul telefono le
elimini tu, nell'app o disinstallandola.

## Modifiche

Se questa informativa cambia, cambia anche la data in cima alla pagina.
