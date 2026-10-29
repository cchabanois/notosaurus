---
title: "Solução de problemas do complemento"
description: "O que fazer quando o complemento não inicia, o celular não se conecta, a IA falha ou os cartões não chegam ao Anki."
---

As mensagens abaixo são as que o Notosaurus mostra. Quando algo dá errado no complemento,
**Ferramentas → Notosaurus → Log do servidor** mostra o que aconteceu, e **Reiniciar o servidor**
muitas vezes resolve.

## O Notosaurus não inicia

**"O Notosaurus não foi iniciado."** Você recusou a instalação dos componentes dele na primeira
abertura. Para instalá-los: **Ferramentas → Notosaurus → Abrir o Notosaurus**.

**"Não foi possível baixar o uv do GitHub"** ou **"Não foi possível instalar os componentes do
Notosaurus".** A primeira abertura baixa cerca de 300 MB: confira a conexão com a internet, depois
**Ferramentas → Notosaurus → Reiniciar o servidor**. O log diz o que falhou.

**O servidor para logo depois de iniciar.** Outro programa pode estar usando a porta 8000, por
exemplo um Notosaurus iniciado no modo autônomo ao mesmo tempo. Pare-o, ou escolha outra porta na
configuração do complemento (**Ferramentas → Extensões → Notosaurus → Configurar**, `port`), depois
reinicie o Anki.

## O celular não consegue abrir o Notosaurus

Veja também [No celular](../phone/).

- O celular e o computador precisam estar na **mesma Wi-Fi**. Uma rede de "convidados" costuma
  manter os aparelhos separados: use a principal.
- No Windows, permita o Anki (ou o Python) quando o **firewall** perguntar, na primeira vez.
- Se o endereço do computador mudou (depois de reiniciar o roteador), **escaneie o QR code de
  novo**: **Ferramentas → Notosaurus → Abrir no celular…**.
- **"O servidor só escuta neste computador"**: coloque `host` em `0.0.0.0` na configuração do
  complemento.
- **"Este aparelho ainda não está autorizado"**: o celular não escaneou o QR code, ou todos os
  celulares foram desconectados. Escaneie-o de novo.

## As configurações não abrem no celular

**"As configurações são abertas pelo Anki, no computador."** É de propósito: no complemento, as
configurações (e as chaves de API) só são acessíveis no próprio computador. Abra-as com
**Ferramentas → Notosaurus → Configurações**.

## A IA falha

| Mensagem | O que fazer |
|---|---|
| "Falta a chave" / "Chave do … inválida" | Cole a chave de novo em **Configurações → Acesso**, depois **🔌 Testar**. |
| "… está sobrecarregado agora" | Comum com o Gemini: tente de novo daqui a um minuto. Os modelos reserva assumem automaticamente. |
| "Cota do … atingida" | O limite de uma chave gratuita foi atingido: espere, ou ative o faturamento. |
| "Resposta cortada: cartões demais de uma vez" | Envie menos páginas por vez, ou peça menos cartões. |
| "O modelo não retornou cartões válidos" | Tente de novo; se continuar acontecendo, escolha outro modelo. |
| O modelo "parece não ver a imagem" (Testar) | O modelo não lê imagens: escolha um modelo com visão. |

## Os cartões estão errados ou faltam alguns

Confira a foto (veja [Fotos e PDFs](../photos/)), seja mais preciso nas instruções, ou corrija-os
com a IA (veja [Revisar os cartões](../review/)). Com letra manuscrita, o Claude lê melhor: veja
[Configurações e serviços de IA](../ai-services/).

## Um PDF não pode ser adicionado

- **"Já há 10 páginas: remova algumas antes de adicionar um PDF."** Uma lição comporta 10 páginas:
  remova as fotos de que não precisa (o botão **Remover esta página**, ✕, em cada uma), ou faça
  duas lições.
- **"… está protegido por senha: salve-o sem senha e adicione-o de novo."** Abra o PDF, salve-o
  sem a senha (ou imprima-o em um novo PDF), depois adicione-o de novo.
- **Palavras mal lidas em um PDF**: um PDF digitalizado tem só imagens, lidas como fotos. Um PDF
  feito em um computador dá à IA o texto exato.

## Os cartões não chegam ao Anki

- **"Não foi possível acessar o Anki"**: abra o Anki no computador. No modo autônomo, o Anki
  precisa do complemento AnkiConnect.
- **"Nenhum perfil aberto no Anki"**: abra o perfil do filho, depois envie de novo.
- **Um aviso sobre outro perfil**: a lição é de outro filho que não o do perfil aberto no Anki.
  Abra o perfil certo, ou confirme.
- **Os cartões não chegam ao celular**: a mensagem diz "sem sincronização com o AnkiWeb" quando o
  perfil não está conectado ao AnkiWeb. Clique uma vez em **Sincronizar** no Anki para entrar,
  depois envie de novo. No celular, sincronize o AnkiDroid ou o AnkiMobile.
- **Cartões sem som**: o serviço de voz não respondeu (ele precisa de internet). Envie a lição de
  novo mais tarde: o áudio que falta é acrescentado.

## Ainda não funciona?

Relate o bug no GitHub, com o [formulário Bug](https://github.com/cchabanois/notosaurus/issues/new?template=bug.yml) (é preciso uma conta do GitHub, gratuita).
Cole as linhas de **Ferramentas → Notosaurus → Log do servidor** em volta do problema, e a versão
(no fim da página de configurações). A issue é pública: nunca a foto de um caderno nem o nome de
uma criança.

## Desinstalar o complemento

No Anki, **Ferramentas → Extensões**, selecione o Notosaurus, **Excluir**. Os componentes dele e
**a pasta de dados (lições, fotos, configurações) também são excluídos**: copie antes a pasta de
dados se quiser guardá-los (veja
[Privacidade e segurança no computador](../privacy/#onde-ficam-os-dados)). Os cartões já enviados
ficam no Anki.
