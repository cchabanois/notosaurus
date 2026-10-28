---
title: "In Anki sul computer"
description: "L'add-on in Anki sul computer: il suo menu Strumenti → Notosaurus e la sua configurazione."
---

Con l'add-on, Notosaurus gira dentro Anki sul computer: si avvia con Anki, si ferma con lui, e
scrive le carte direttamente nel profilo aperto.

## Il menu Strumenti → Notosaurus

![Il menu Notosaurus in Anki](../../../assets/screenshots/en/anki-menu.png)

- **Apri Notosaurus** apre Notosaurus nel browser del computer.
- **Apri sul telefono…** mostra un codice QR per aprire Notosaurus sul telefono, e i tre passaggi
  per arrivarci (vedi [Sul telefono](../phone/)).
- **Configurazione guidata** apre la procedura: l'IA e la sua chiave, poi il telefono (vedi
  [Primi passi con l'add-on](../getting-started/#2-la-procedura-guidata)). La prima volta, Anki la
  propone da solo quando nessuna IA è ancora configurata.
- **Impostazioni** apre le impostazioni (servizio di IA e chiave, voci, figli…) nel browser del
  computer. Si aprono solo sul computer: il telefono non può cambiarle.
- **Stato del server…** dice se Notosaurus è in esecuzione, i suoi indirizzi (sul telefono e su
  questo computer), e dove sono i suoi file e le tue lezioni.
- **Riavvia il server** ferma e riavvia Notosaurus: dopo aver cambiato la configurazione
  dell'add-on, o quando qualcosa è bloccato.
- **Registro del server** mostra cosa ha fatto Notosaurus di recente. È la prima cosa da guardare
  quando qualcosa va storto (vedi [Risolvere i problemi dell'add-on](../troubleshooting/)).
- **Aiuto** apre questa documentazione, nella lingua di Anki.
- **Sostieni Notosaurus…** apre la sua pagina [Ko-fi](https://ko-fi.com/notosaurus), per fare una
  donazione se ti piace. Notosaurus resta gratuito.

![Il codice QR per aprire Notosaurus sul telefono](../../../assets/screenshots/en/anki-phone.png)

Cambiare profilo in Anki lascia Notosaurus in esecuzione: le carte vanno allora nel profilo aperto
(vedi [Più figli](../several-children/)).

## La configurazione dell'add-on

Alcune opzioni tecniche sono in **Strumenti → Add-on**, seleziona **Notosaurus**, poi
**Configura**:

- `autostart`: avviare Notosaurus con Anki (`true` di default). Con `false`, si avvia la prima
  volta che usi il menu.
- `host`: `0.0.0.0` (default) permette al telefono di raggiungere Notosaurus sulla stessa Wi-Fi;
  `127.0.0.1` lo limita a questo computer.
- `port`: `8000` di default. Cambialo se un altro programma usa già quella porta.
- `source`, `python`, `data`: lasciali vuoti. Servono solo per sviluppare Notosaurus.

Dopo una modifica: **Strumenti → Notosaurus → Riavvia il server**.

I mazzi che crea Notosaurus e come appaiono le sue carte in Anki, sul computer e sui telefoni: vedi
[Le carte in Anki](../cards-in-anki/).
