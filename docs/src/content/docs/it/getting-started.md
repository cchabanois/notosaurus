---
title: "Primi passi con l'add-on"
description: "Installare Notosaurus in Anki, configurarlo con la procedura guidata, collegare il telefono e fare il primo mazzo da una foto."
---

L'add-on di Anki fa girare Notosaurus sul tuo computer, dentro Anki, gratis, con la tua chiave IA.
Lo usi dal browser del telefono, o dall'app Android, sulla stessa Wi-Fi. Preferisci l'app da sola?
Vedi [Quale Notosaurus?](../which-notosaurus/).

## Cosa ti serve

- **Anki** su un computer (Windows, macOS o Linux), una versione recente.
- **Un telefono** sulla stessa Wi-Fi del computer.
- **Una chiave per un servizio di IA.** Gemini è il più economico e ha un livello gratuito per
  provare Notosaurus; anche Claude e GPT funzionano bene. Una lezione costa da una frazione di
  centesimo a qualche centesimo.

:::caution[Livelli gratuiti e privacy]
I livelli gratuiti di solito permettono al fornitore di IA di usare ciò che invii per migliorare i
suoi modelli. Per i quaderni dei tuoi figli, meglio una chiave a pagamento: pochi euro durano a
lungo.
:::

## 1. Installare l'add-on

1. Scarica `notosaurus-<version>.ankiaddon` dall'[ultima versione](https://github.com/cchabanois/notosaurus/releases/latest).
2. Fai doppio clic sul file (o in Anki: **Strumenti → Add-on → Installa da file...**), poi
   riavvia Anki.
3. Al primo avvio, Notosaurus chiede prima di installare i suoi componenti (circa 300 MB). Ci
   vogliono pochi minuti, una volta sola.

## 2. La procedura guidata

Una volta installati i componenti, Anki propone **"Configurarlo ora?"**: la procedura si apre nel
browser del computer. Due passaggi, pochi minuti. È sempre in **Strumenti → Notosaurus →
Configurazione guidata**, e finché nessuna IA è configurata, la pagina di Notosaurus mostra
**"Manca un passaggio"** con un pulsante per avviarla.

**L'IA.** Scegli il servizio che legge le lezioni. Si consiglia **Gemini**: il miglior rapporto
qualità/prezzo nei nostri test, circa 1 centesimo di dollaro per lezione (vedi
[Impostazioni e servizi di IA](../ai-services/) per gli altri).

![La procedura: scegliere l'IA](../../../assets/screenshots/en/setup-start.png)

Per Gemini, la procedura spiega in tre passaggi come ottenere la chiave. Incollala, poi tocca
**🔌 Verifica la chiave**: Notosaurus verifica che il modello legga un'immagine e risponda nel
formato giusto. **Avanti** compare quando la verifica riesce.

![La procedura: la chiave Gemini, verificata](../../../assets/screenshots/en/setup-ai.png)

**Il telefono.** Inquadra il codice QR con la fotocamera del telefono e apri il link. La procedura
aspetta il telefono, poi mostra **"✓ Il telefono è connesso."** Poi aggiungi la pagina alla
schermata Home: si apre come un'app (vedi [Sul telefono](../phone/) per ogni browser). **Più
tardi** salta questo passaggio: il codice QR resta in **Strumenti → Notosaurus → Apri sul
telefono…** e nelle impostazioni.

![La procedura: il codice QR per il telefono](../../../assets/screenshots/en/setup-phone.png)

**Pronto!** Apri Notosaurus, o tutte le impostazioni: immagini delle carte, voci, istruzioni per
figlio… Le impostazioni si aprono solo sul computer: i bambini non possono cambiarle da un telefono.

![La procedura: Notosaurus è pronto](../../../assets/screenshots/en/setup-done.png)

:::tip
Solo i dispositivi che hanno scansionato questo codice QR possono usare Notosaurus. Se un telefono
viene perso o prestato: **Impostazioni → Telefoni → Disconnetti tutti i telefoni**.
:::

## 3. La tua prima lezione

1. In **Foto della lezione**, fotografa la pagina (o più pagine), oppure aggiungi un PDF: vedi
   [Foto e PDF](../photos/).
2. In **Istruzioni**, scegli cosa fare: vocabolario, domande, testo da completare, uno schema da
   completare… **Automatiche** sceglie in base alla lezione. Vedi [Istruzioni](../instructions/).

   ![Una foto della lezione e le istruzioni](../../../assets/screenshots/en/instructions.png)

3. Tocca **Genera le carte** e aspetta qualche secondo.
4. Controlla le carte. Modificale, eliminane qualcuna, o chiedi all'IA di correggerle con parole
   tue: vedi [Rileggere le carte](../review/).

   ![Le carte, pronte da rileggere](../../../assets/screenshots/en/review.png)

   ![Chiedere una correzione all'IA](../../../assets/screenshots/en/correction.png)

5. Tocca **Aggiungi ad Anki**.

La lezione viene salvata: puoi riaprirla più tardi dall'elenco delle lezioni, correggerla e
inviarla di nuovo. Le sue carte vengono aggiornate in Anki, non duplicate.

Con le istruzioni **Schema o carta da completare**, i nomi di uno schema sono nascosti dietro
numeri: ogni carta ne chiede uno.

![Uno schema con i nomi nascosti](../../../assets/screenshots/en/diagram.png)

## 4. Ripassare sul telefono

Per ripassare sul telefono, usa **AnkiDroid** (Android) o **AnkiMobile** (iPhone) con un account
**AnkiWeb**: Notosaurus sincronizza Anki dopo aver inviato le carte. Con più figli, vedi
[Più figli](../several-children/).
