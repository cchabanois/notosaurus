---
title: "Solução de problemas do app"
description: "O que fazer quando o app Android diz que não há créditos, que o teste ou a assinatura terminou, que o AnkiDroid não aceita os cartões ou que o computador não responde."
---

As mensagens abaixo são as que o app mostra.

## A assinatura

| Mensagem | O que fazer |
|---|---|
| "Sem créditos este mês" | Eles voltam na próxima renovação: **🔑 Assinatura**, nas configurações, diz quando. |
| "Seu teste grátis terminou" | Assine nas Configurações (**🔑 Assinatura**) para continuar. |
| "No momento não há novos testes grátis…" | Os novos testes grátis estão suspensos por enquanto: assine nas Configurações, ou tente de novo amanhã. Um teste já iniciado continua. |
| "Sua assinatura terminou" | Assine de novo no app. |
| "Pagamento pendente" | O Google Play não conseguiu renovar a assinatura: atualize o seu método de pagamento no Google Play (**Configurações → Gerenciar a assinatura**). |
| "O teste grátis só é possível com o app instalado pelo Google Play, em um celular de verdade" | Instale o app pelo Google Play; o teste não é oferecido em um emulador. |
| "Nenhuma assinatura encontrada nesta conta do Google" (**Já tenho uma assinatura**) | Confira se o celular usa a conta do Google com a qual a assinatura foi feita. |

Veja [A assinatura](../app-subscription/).

## AnkiDroid

| Mensagem | O que fazer |
|---|---|
| "O Notosaurus não tem permissão para adicionar cartões ao AnkiDroid" | **Configurações → 📥 AnkiDroid → Permitir**, depois adicione os cartões de novo. Recusado de vez (o Android não pergunta mais): permita nas configurações do Android, **Apps → Notosaurus → Permissões**. |
| "O AnkiDroid não está instalado" / "O AnkiDroid não aceitou os cartões" | Instale o AnkiDroid, **abra-o uma vez** (ele cria a sua coleção), depois adicione os cartões de novo. |

**✎ Notosaurus não faz nada no AnkiDroid** ("Security: Card blocked from launching another
app"): até o AnkiDroid 2.25.2, ative no AnkiDroid **Configurações → Avançado → Allow cards to
launch other apps**, ou atualize o AnkiDroid (a partir do 2.25.3, o link passa sem isso).

**Cartões sem som**: as vozes do serviço Notosaurus não responderam (o celular precisa de
internet). Os cartões são enviados sem o som, e a mensagem diz quantos. Adicione a lição ao Anki
de novo mais tarde: os sons que faltam são acrescentados.

Veja [O app e o AnkiDroid](../app-ankidroid/).

## Com o seu computador

| Mensagem | O que fazer |
|---|---|
| "💻 Seu computador não responde" | O Anki precisa estar aberto no computador com o complemento, e o celular na mesma Wi-Fi. **Tentar de novo**, ou **Escanear o QR code de novo** se o endereço do computador mudou. |

Veja [Com o seu computador](../app-with-computer/).

## Os cartões

**Os cartões estão errados ou faltam alguns.** Confira a foto (veja [Fotos e PDFs](../photos/)),
seja mais preciso nas instruções, ou corrija-os com a IA (veja [Revisar os cartões](../review/)).

**Relate.** Um cartão que não está certo (uma palavra mal lida, uma resposta errada, uma figura
torta, uma imagem inadequada): **⋯ → ⚑ Relatar** nele, com uma palavra sobre o que você
esperava. Cada relato é lido, e é assim que esses erros são corrigidos. Veja
[Relatar um problema](../review/#relatar-um-problema).

## Um PDF não pode ser adicionado

- **"Já há 10 páginas: remova algumas antes de adicionar um PDF."** Uma lição comporta 10 páginas:
  remova as fotos de que não precisa (o botão **Remover esta página**, ✕, em cada uma), ou faça
  duas lições.
- **"… está protegido por senha: salve-o sem senha e adicione-o de novo."** Abra o PDF, salve-o
  sem a senha (ou imprima-o em um novo PDF), depois adicione-o de novo.
- **Palavras mal lidas em um PDF**: um PDF digitalizado tem só imagens, lidas como fotos. Um PDF
  feito em um computador dá à IA o texto exato.
