---
title: "Privacidade e segurança no computador"
description: "O que sai do seu computador, onde o Notosaurus guarda os dados, quem pode usá-lo, e como fazer backup."
---

Esta página trata do Notosaurus em um computador. Para o app Android e o serviço dele, veja a
[política de privacidade do app](../app-privacy/).

Em um computador, o Notosaurus não tem conta nem servidor próprio: ele roda no seu computador. Uma
lição muitas vezes mostra a letra de uma criança, às vezes o nome dela: veja aqui para onde isso
vai.

## O que sai do seu computador

- **As fotos e as instruções** vão para o **serviço de IA escolhido nas configurações**, para fazer
  e corrigir os cartões. O texto de um PDF digital vai junto com a página. Com elas vão a série da
  criança e as suas instruções para ela, **nunca o nome dela**.
- **Os versos dos cartões** vão para o serviço de síntese de voz da Microsoft, para fazer o áudio,
  quando uma voz é escolhida.
- **A descrição de uma imagem** vai para o serviço que a desenha, para "Idioma: vocabulário em
  imagens".
- **As palavras de uma busca de imagem** (algumas palavras em inglês: "dog", "Storming of the
  Bastille painting") vão para o Wikimedia Commons e o Openverse, para encontrar imagens livres;
  nunca as fotos.

As páginas em si não carregam nada de outro lugar: os scripts e as fontes delas vêm com o
Notosaurus (sem Google Fonts, sem CDN).

Mais nada: sem estatísticas, sem rastreamento. Com um modelo em casa (veja
[Serviços de IA](../ai-services/#um-modelo-em-casa)), nem as fotos saem de casa.

:::caution[Níveis gratuitos]
Os níveis gratuitos costumam permitir que o serviço de IA use o que você envia para melhorar os
modelos dele. Para os cadernos das crianças, prefira uma chave paga. Antes de tirar a foto, você
também pode cobrir um nome escrito na página.
:::

## Onde ficam os dados

Tudo fica guardado em arquivos simples, na **pasta de dados** do Notosaurus: as lições (fotos,
cartões, áudio), as instruções e as configurações.

- No **complemento**, ela fica na pasta do complemento, em `user_files/data`. **Ferramentas →
  Notosaurus → Estado do servidor…** mostra onde. Ela é mantida quando o complemento é atualizado,
  e removida com ele.
- **No modo autônomo**, é a pasta `data/` (ou `NOTOSAURUS_DATA`).

As **chaves de API** ficam nessa pasta, em `settings.json`, legíveis só pela sua conta de usuário.
Elas nunca são enviadas de volta a um celular ou a um navegador: as configurações só mostram os
quatro últimos caracteres delas.

**Para fazer backup do Notosaurus**, copie a pasta de dados. Os cartões em si estão no Anki, com
backup feito pelo Anki e, com uma conta, pelo AnkiWeb.

## Quem pode usar o Notosaurus

- **Só os aparelhos pareados.** Pela Wi-Fi, só o próprio computador e os aparelhos que escanearam o
  QR code (**Configurações → Celulares**) podem usar o Notosaurus: os outros não podem gastar os
  seus créditos de IA nem excluir lições. **Desconectar todos os celulares** desfaz o pareamento de
  todos, por exemplo depois que um celular foi perdido ou emprestado.
- **Configurações só no computador.** No complemento, as configurações só abrem no próprio
  computador: as crianças não podem mudar o serviço de IA nem ver as chaves pelo celular. No modo
  autônomo, elas são protegidas por uma senha.
- **Uma lição pertence a um perfil.** Uma lição só pode ser alterada pelo perfil do Anki em que foi
  feita; outro filho recebe a própria cópia (**⧉ Copiar para…**).

## A Wi-Fi

O Notosaurus fala com os celulares em HTTP simples, na sua rede local. O pareamento mantém longe os
curiosos e outros sites, mas não alguém que espione o tráfego da Wi-Fi: mantenha a sua Wi-Fi
protegida (WPA2 ou WPA3).

O Notosaurus foi feito para casa: os celulares o usam na mesma Wi-Fi que o computador. **Nunca
exponha o Notosaurus** (nem o AnkiConnect) **à internet.**
