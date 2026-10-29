---
title: "O app e o AnkiDroid"
description: "Como o app põe os cartões no AnkiDroid: a permissão, atualizações sem duplicatas, abrir o AnkiDroid, corrigir um cartão a partir do AnkiDroid, e o baralho filtrado de uma prova."
---

Neste celular, os cartões vão para o **AnkiDroid**, o app gratuito do Anki para Android: sem
`.apkg`, sem computador, sem esperar sincronização.

## Na primeira vez

1. **Instale o AnkiDroid** pelo Google Play, se ele não estiver lá: o app abre a página dele
   quando falta.
2. **Abra o AnkiDroid uma vez**, para que ele crie a sua coleção.
3. No primeiro **📥 Adicionar ao Anki**, o AnkiDroid pergunta se o Notosaurus pode adicionar
   cartões a ele (a janela do próprio AnkiDroid): permita.

**📥 AnkiDroid**, nas configurações do app, diz como estão as coisas: **✓ O AnkiDroid está
instalado e o Notosaurus pode adicionar cartões a ele.**, ou um botão para **Instalar o AnkiDroid**
ou para **Permitir**.

![O AnkiDroid pergunta se o Notosaurus pode acessar e criar notas, cartões, tipos de nota e baralhos](../../../assets/screenshots/en/app-ankidroid-permission.png)

## Enviar os cartões

**📥 Adicionar ao Anki** escreve os cartões no AnkiDroid, no baralho da lição, com os sons e as
imagens. Como no computador:

- **Enviada de novo**, uma lição **atualiza** os cartões em vez de duplicá-los, e o histórico de
  revisão fica.
- **Os cartões excluídos da lição** ficam no AnkiDroid: depois do envio, o app os lista e oferece
  excluí-los (com o histórico de revisão), nunca sem perguntar.
- **Excluir uma lição** oferece excluir também os cartões dela no AnkiDroid.

O AnkiDroid sincroniza os cartões com o AnkiWeb como sempre, se estiver conectado a uma conta:
eles chegam então ao Anki em um computador, ou a outro celular.

## Abrir o AnkiDroid

**Abrir o AnkiDroid**, no alto da página e no fim dela, o abre com um toque, para revisar os
cartões que acabaram de ser enviados.

![Os baralhos do AnkiDroid depois de enviar lições pelo app: um baralho por matéria, um subbaralho por lição](../../../assets/screenshots/en/app-ankidroid-decks.png)

## Corrigir um cartão a partir do AnkiDroid

Abaixo de cada resposta no AnkiDroid, um pequeno **✎ Notosaurus** abre o cartão no app para
corrigi-lo (o AnkiDroid abre antes uma pequena página web, cujo botão abre o app). A correção
atualiza a mesma nota: o histórico de revisão fica. Uma lição feita com o computador
([Com o seu computador](../app-with-computer/)) abre no computador, não no app.

Até o **AnkiDroid 2.25.2**, ative antes no AnkiDroid **Configurações → Avançado → Allow cards to
launch other apps**: sem isso, o AnkiDroid bloqueia todos os links de um cartão ("Security: Card
blocked from launching another app"). A partir do AnkiDroid 2.25.3, os links para uma página web
passam sem isso.

![Um cartão no AnkiDroid com o som e, abaixo da resposta, ✎ Notosaurus](../../../assets/screenshots/en/app-ankidroid-card.png)

## O baralho filtrado de uma prova

Uma prova a preparar junta cartões de várias lições sob uma etiqueta (veja
[Preparar uma prova](../tests/)). Na janela dela, **Abrir no AnkiDroid** abre os cartões da prova
no navegador de cartões do AnkiDroid, seja qual for o baralho; depois **⋮ → Criar baralho com
filtros → Criar** (com mais de 100 cartões, aumente antes **Limitar a**). O AnkiDroid não deixa
outro app criar sozinho um baralho filtrado.

Algo deu errado? Veja [Solução de problemas do app](../app-troubleshooting/).
