---
title: "Le carte in Anki"
description: "Dove Notosaurus mette le carte in Anki, come appaiono, come una lezione inviata di nuovo le aggiorna, e ✎ Notosaurus per correggerne una da Anki."
---

Che arrivino dall'app (in AnkiDroid) o dal computer (in Anki), le carte sono le stesse: gli stessi
mazzi, gli stessi tipi di carta, gli stessi aggiornamenti. Come inviarle: vedi
[L'app e AnkiDroid](../app-ankidroid/) o [Inviare ad Anki](../send-to-anki/).

## I mazzi

Ogni lezione ha il suo mazzo, per esempio `Inglese::Unit 3 - At school`: `::` crea un mazzo
dentro un altro, così le lezioni di una materia sono raggruppate. Le carte con una sezione
(Vocabolario, Quiz…) vanno in un sotto-mazzo del mazzo della lezione.

![I mazzi di Notosaurus in Anki](../../../assets/screenshots/en/anki-decks.png)

Per ripassare una materia intera, fai clic sul suo mazzo: Anki prende le carte di tutti i mazzi
che contiene.

## Inviare di nuovo una lezione

Una volta inviata la lezione, il pulsante dice **✓ Aggiornato in Anki**, poi **🔄 Aggiorna in
Anki** appena qualcosa cambia. Puoi correggere una lezione e inviarla di nuovo tutte le volte che
vuoi:

- le sue carte vengono **aggiornate** in Anki, **non duplicate**, e ogni carta conserva la sua
  cronologia di ripasso, anche se ne hai corretto il fronte;
- se hai cambiato il mazzo della lezione, le sue carte vengono **spostate** lì, con la loro
  cronologia;
- le carte aggiunte dall'ultimo invio vengono aggiunte;
- le carte eliminate dalla lezione restano in Anki: dopo l'invio, Notosaurus le elenca e propone
  di eliminarle (con la loro cronologia), mai senza chiedere.

Eliminare un'intera lezione in Notosaurus propone di eliminare anche le sue carte in Anki, con la
loro cronologia di ripasso.

Sul computer, cambiare un'opzione di carta (la carta inversa, la risposta scritta) su una lezione
già inviata sposta le sue carte nel tipo di nota corrispondente, cronologia mantenuta.

In Anki, le note di ogni lezione portano un'etichetta `notosaurus::<lezione>`: comoda per
trovarle nel browser.

## Correggere una carta da Anki

Sotto ogni risposta, un piccolo **✎ Notosaurus** apre la carta in Notosaurus per correggerla:
nell'app su Android (AnkiDroid apre prima una breve pagina web, il cui pulsante apre l'app),
nella pagina sul computer (Anki aperto, Notosaurus sulla sua porta abituale). Non si perde nulla:
la correzione aggiorna la stessa nota, la sua cronologia di ripasso resta. Il link sa solo dove
vive la lezione: una lezione fatta sul computer si apre lì, una fatta nell'app si apre nell'app.
AnkiWeb e AnkiMobile non lo mostrano.

Fino ad AnkiDroid 2.25.2, attiva prima **Impostazioni → Avanzate → Allow cards to launch other
apps**: senza, AnkiDroid blocca ogni link su una carta ("Security: Card blocked from launching
another app"). Da AnkiDroid 2.25.3, i link a una pagina web passano anche senza.

## Come appaiono

Ecco come appaiono i [tipi di carta](../card-types/) durante un ripasso in Anki sul computer.
AnkiDroid e AnkiMobile mostrano le stesse carte.

**Domanda e risposta**: una parola con il suo audio (▶) e una nota.

![Una carta di vocabolario in Anki](../../../assets/screenshots/en/anki-vocab.png)

**Testo da completare**: la domanda nasconde la parola, la risposta la mostra.

![Una carta da completare: la domanda](../../../assets/screenshots/en/anki-cloze-q.png)

![Una carta da completare: la risposta](../../../assets/screenshots/en/anki-cloze-a.png)

**Scelta multipla**: la risposta segna la scelta giusta con ✔ e dà la spiegazione.

![Una carta a scelta multipla: la domanda](../../../assets/screenshots/en/anki-quiz-q.png)

![Una carta a scelta multipla: la risposta](../../../assets/screenshots/en/anki-quiz-a.png)

**Schemi**: la foto della lezione con nomi numerati; una carta per nome da indicare.

![Una carta di schema in Anki](../../../assets/screenshots/en/anki-diagram.png)

**Immagini**: un disegno da nominare nella lingua studiata, con il suo audio.

![Una carta con immagine in Anki](../../../assets/screenshots/en/anki-picture.png)

**Figure**: la figura disegnata da Notosaurus accompagna la domanda.

![Una carta con una figura in Anki](../../../assets/screenshots/en/anki-figure.png)
