---
title: "Privacy e sicurezza sul computer"
description: "Cosa esce dal tuo computer, dove Notosaurus tiene i suoi dati, chi può usarlo, e come farne un backup."
---

Questa pagina riguarda Notosaurus su un computer. Per l'app Android e il suo servizio, vedi
l'[informativa sulla privacy dell'app](../app-privacy/).

Su un computer, Notosaurus non ha un account né un server proprio: gira sul tuo computer. Una
lezione mostra spesso la scrittura di un bambino, a volte il suo nome: ecco dove va.

## Cosa esce dal tuo computer

- **Le foto e le istruzioni** vanno al **servizio di IA scelto nelle impostazioni**, per fare e
  correggere le carte. Il testo di un PDF digitale va con la sua pagina. Con loro vanno la classe
  del bambino e le tue istruzioni per lui, **mai il suo nome**.
- **I retro delle carte** vanno al servizio di sintesi vocale di Microsoft, per fare l'audio,
  quando è scelta una voce.
- **La descrizione di un'immagine** va al servizio che la disegna, per "Lingua: lessico per
  immagini".
- **Le parole di una ricerca di immagini** (qualche parola in inglese: "dog", "Storming of the
  Bastille painting") vanno a Wikimedia Commons e Openverse, per trovare immagini libere; mai le
  foto.

Le pagine stesse non caricano niente da altrove: i loro script e caratteri vengono con Notosaurus
(niente Google Fonts, niente CDN).

Nient'altro: niente statistiche, niente tracciamento. Con un modello a casa (vedi
[Servizi di IA](../ai-services/#un-modello-a-casa)), nemmeno le foto escono di casa.

:::caution[Livelli gratuiti]
I livelli gratuiti di solito permettono al servizio di IA di usare ciò che invii per migliorare i
suoi modelli. Per i quaderni dei bambini, meglio una chiave a pagamento. Prima di scattare la foto,
puoi anche coprire un nome scritto sulla pagina.
:::

## Dove sono i dati

Tutto è conservato come semplici file, nella **cartella dati** di Notosaurus: le lezioni (foto,
carte, audio), le istruzioni e le impostazioni.

- Nell'**add-on**, è nella cartella dell'add-on, in `user_files/data`. **Strumenti → Notosaurus →
  Stato del server…** mostra dove. Viene conservata quando l'add-on si aggiorna, ed eliminata con
  lui.
- **In autonomo**, è la cartella `data/` (o `NOTOSAURUS_DATA`).

Le **chiavi API** sono salvate in quella cartella, in `settings.json`, leggibili solo dal tuo
account utente. Non vengono mai rimandate a un telefono o a un browser: le impostazioni ne mostrano
solo gli ultimi quattro caratteri.

**Per fare un backup di Notosaurus**, copia la cartella dati. Le carte stesse sono in Anki, salvate
da Anki e, con un account, da AnkiWeb.

## Chi può usare Notosaurus

- **Solo i dispositivi associati.** Tramite la Wi-Fi, solo il computer stesso e i dispositivi che
  hanno scansionato il codice QR (**Impostazioni → Telefoni**) possono usare Notosaurus: gli altri
  non possono spendere i tuoi crediti di IA né eliminare lezioni. **Disconnetti tutti i telefoni**
  li dissocia tutti, per esempio dopo che un telefono è stato perso o prestato.
- **Impostazioni solo sul computer.** Nell'add-on, le impostazioni si aprono solo sul computer
  stesso: i bambini non possono cambiare il servizio di IA né vedere le chiavi da un telefono. In
  autonomo, sono protette da una password.
- **Una lezione appartiene a un profilo.** Una lezione si può modificare solo dal profilo Anki in
  cui è stata fatta; un altro figlio riceve la sua copia (**⧉ Copia per…**).

## La Wi-Fi

Notosaurus parla con i telefoni in HTTP semplice, sulla tua rete locale. L'associazione tiene
fuori i curiosi e gli altri siti web, ma non qualcuno che spia il traffico della Wi-Fi: tieni la tua
Wi-Fi protetta (WPA2 o WPA3).

Notosaurus è fatto per la casa: i telefoni lo usano sulla stessa Wi-Fi del computer. **Non esporre
mai Notosaurus** (né AnkiConnect) **su Internet.**
