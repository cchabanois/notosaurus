---
title: "Os cartões no Anki"
description: "Onde o Notosaurus põe os cartões no Anki, como eles ficam, como uma lição enviada de novo os atualiza, e ✎ Notosaurus para corrigir um a partir do Anki."
---

Venham do app (para o AnkiDroid) ou do computador (para o Anki), os cartões são os mesmos: os
mesmos baralhos, os mesmos tipos de cartão, as mesmas atualizações. Como enviá-los: veja
[O app e o AnkiDroid](../app-ankidroid/) ou [Enviar para o Anki](../send-to-anki/).

## Os baralhos

Cada lição tem o seu baralho, por exemplo `Inglês::Unit 3 - At school`: `::` cria um baralho
dentro de outro, então as lições de uma matéria ficam agrupadas. Os cartões com uma seção
(Vocabulário, Quiz…) vão para um subbaralho do baralho da lição.

![Os baralhos do Notosaurus no Anki](../../../assets/screenshots/en/anki-decks.png)

Para revisar uma matéria inteira, clique no baralho dela: o Anki pega os cartões de todos os
baralhos que estão dentro dele.

## Enviar uma lição de novo

Depois que a lição é enviada, o botão diz **✓ Atualizado no Anki**, depois **🔄 Atualizar no
Anki** assim que algo muda. Você pode corrigir uma lição e enviá-la de novo quantas vezes quiser:

- os cartões dela são **atualizados** no Anki, **não duplicados**, e cada cartão mantém o
  histórico de revisão, mesmo que você tenha corrigido a frente;
- se você mudou o baralho da lição, os cartões dela são **movidos** para lá, com o histórico;
- os cartões adicionados desde o último envio são adicionados;
- os cartões excluídos da lição ficam no Anki: depois do envio, o Notosaurus os lista e oferece
  excluí-los (com o histórico de revisão), nunca sem perguntar.

Excluir uma lição inteira no Notosaurus oferece excluir também os cartões dela no Anki, com o
histórico de revisão.

No computador, mudar uma opção de cartão (o cartão invertido, a resposta digitada) em uma lição
já enviada move os cartões dela para o tipo de nota correspondente, com o histórico.

No Anki, as notas de cada lição levam uma etiqueta `notosaurus::<lição>`: útil para encontrá-las
no navegador.

## Corrigir um cartão a partir do Anki

Abaixo de cada resposta, um pequeno **✎ Notosaurus** abre o cartão no Notosaurus para corrigi-lo:
no app no Android (o AnkiDroid abre antes uma pequena página web, cujo botão abre o app), na
página no computador (Anki aberto, Notosaurus na porta de sempre). Nada se perde: a correção
atualiza a mesma nota, o histórico de revisão fica. O link só sabe onde a lição mora: uma lição
feita no computador abre lá, uma feita no app abre no app. O AnkiWeb e o AnkiMobile não o mostram.

Até o AnkiDroid 2.25.2, ative antes **Configurações → Avançado → Allow cards to launch other
apps**: sem isso, o AnkiDroid bloqueia todos os links de um cartão ("Security: Card blocked from
launching another app"). A partir do AnkiDroid 2.25.3, os links para uma página web passam sem
isso.

## Como eles ficam

Veja como ficam os [tipos de cartão](../card-types/) durante uma revisão no Anki do computador. O
AnkiDroid e o AnkiMobile mostram os mesmos cartões.

**Pergunta e resposta**: uma palavra com o áudio (▶) e uma nota.

![Um cartão de vocabulário no Anki](../../../assets/screenshots/en/anki-vocab.png)

**Lacunas**: a pergunta esconde a palavra, a resposta a mostra.

![Um cartão com lacuna: a pergunta](../../../assets/screenshots/en/anki-cloze-q.png)

![Um cartão com lacuna: a resposta](../../../assets/screenshots/en/anki-cloze-a.png)

**Múltipla escolha**: a resposta marca a opção certa com ✔ e dá a explicação.

![Um cartão de múltipla escolha: a pergunta](../../../assets/screenshots/en/anki-quiz-q.png)

![Um cartão de múltipla escolha: a resposta](../../../assets/screenshots/en/anki-quiz-a.png)

**Esquemas**: a foto da lição com legendas numeradas; um cartão por legenda a nomear.

![Um cartão de esquema no Anki](../../../assets/screenshots/en/anki-diagram.png)

**Imagens**: um desenho a nomear no idioma estudado, com o áudio.

![Um cartão com imagem no Anki](../../../assets/screenshots/en/anki-picture.png)

**Figuras**: a figura desenhada pelo Notosaurus acompanha a pergunta.

![Um cartão com uma figura no Anki](../../../assets/screenshots/en/anki-figure.png)
