---
title: "Política de privacidade do app Android"
description: "Os dados que o app Android do Notosaurus e o seu serviço tratam, por quê, onde, por quanto tempo, e os seus direitos."
---

*Última atualização: 11 de novembro de 2026.*

Esta página trata do **app Notosaurus para Android** e do **serviço Notosaurus** que ele usa para
ler as fotos e fazer os cartões e as vozes. O Notosaurus em um computador (o complemento do Anki)
funciona de outro jeito: veja [Privacidade e segurança](../privacy/).

**Controlador dos dados**: CHABANOIS Cédric.
**Contato**: notosaurus.app@gmail.com

**Quem usa o app**: um **pai ou uma mãe** (um adulto), que prepara a revisão dos filhos. O app não
foi feito para ser usado por uma criança.

## Em resumo

- As suas **lições ficam no seu celular**: fotos, cartões, instruções, sons.
- O que a IA precisa ler (fotos, instruções) **passa pelo serviço** enquanto os cartões
  são feitos, **e não fica guardado lá**.
- Um **ditado** (🎤) é ouvido pelo **reconhecimento de voz do seu celular** (o escolhido nas
  configurações do Android, em geral o do Google): a sua voz não passa pelo serviço.
- A IA (**o Gemini do Google**) é processada nos servidores do Google, **que podem ficar fora da
  União Europeia**; as vozes são processadas na União Europeia. O Google não as usa para treinar
  os seus modelos.
- **Sem anúncios, sem estatísticas, sem rastreamento**, e nada é vendido.
- O serviço só guarda a sua **licença** (a impressão digital dela, o seu plano e os seus créditos),
  e o que você **relata** com ⚑, se o fizer.

## O que fica no seu celular

As lições (fotos das páginas, cartões, instruções, imagens dos cartões, sons), as suas instruções
salvas e as suas configurações, incluindo a sua chave de licença, ficam **no armazenamento
privado do app** no seu celular. Outros apps não conseguem acessá-los. Eles são apagados quando
você exclui uma lição, ou o app.

Os cartões enviados ao **AnkiDroid** são escritos nele, no seu celular. A sincronização deles com
o AnkiWeb depende do AnkiDroid e da sua conta do AnkiWeb, não do Notosaurus.

As fichas dos seus filhos (nome, série, baralhos, instruções) também ficam no seu celular: só a série e as instruções de uma criança vão com as lições dela, nunca o nome.

Quando você **faz um backup das suas lições** (💾 nas configurações), o arquivo vai para onde você escolher (Drive, o cartão SD, Downloads…) e segue então as regras desse lugar.

## O que passa pelo serviço Notosaurus

Quando você pede, o app envia ao serviço, por HTTPS:

| O quê | Para quê |
|---|---|
| As **fotos** das páginas e o texto delas (PDF), a **instrução**, as suas instruções permanentes, os seus nomes de baralho | Criar ou completar os cartões da lição, e recortar os desenhos das páginas dela |
| A **série** da criança a quem a lição se destina, e as instruções dadas para ela (nunca o nome dela) | Cartões adequados ao nível dela |
| Os **cartões** de uma lição e a sua correção | Corrigi-los, explicar um cartão, passar uma instrução a limpo |
| Uma **gravação da sua voz** (🎤), só num celular sem reconhecimento de voz | Escrevê-la como texto (ditar uma instrução ou uma correção) |
| O **verso** de um cartão | Lê-lo em voz alta (as vozes dos cartões) |
| A **descrição** de uma imagem, ou algumas **palavras-chave** | Desenhar a imagem de um cartão, ou procurar uma livre |
| A sua **chave de licença** | Verificar a sua licença e contar os seus créditos |
| Se você assinar: o **token da sua compra** no Google Play | Verificar a assinatura com o Google Play e transformá-la na sua licença |
| Para o **teste grátis**: uma **impressão digital do celular** (calculada pelo app, nunca o identificador dele) e o atestado **Play Integrity** do Google | Oferecer o teste uma só vez por celular, ao app instalado pelo Google Play em um celular de verdade |

O serviço repassa esses conteúdos aos operadores abaixo, devolve o resultado ao app e **não os
guarda**: nenhuma foto, cartão, gravação ou texto de lição é armazenado ou escrito nos seus logs.
Exceto um **relato**: veja abaixo.

Uma página de caderno muitas vezes mostra o **nome da criança**. Antes de enviar uma foto você
pode **ocultá-lo**: 🖍️ na foto em tela cheia, depois tape com o dedo. Só a foto tapada sai e fica na lição.

## O que o serviço guarda

- **A sua licença**: a impressão digital da chave (não a chave em si), o seu plano, os seus
  créditos restantes, a data de renovação, o que foi usado naquele dia, e uma nota curta para o
  suporte (um número de pedido, por exemplo). Guardada enquanto é válida, depois **12 meses** após
  o fim (para responder a uma pergunta ou reclamação), depois apagada.
- **O que você relata** com ⚑ (um cartão feito pela IA, com a explicação quando mostrada e a
  imagem, a não ser que seja uma foto tirada por você; chocante ou errado), se o fizer: exatamente
  o que o app mostra antes do envio, o motivo, o seu comentário, as instruções da lição, o idioma
  e um identificador curto da licença. Nunca as fotos da lição nem o nome da criança. Lido pelo
  Notosaurus para melhorar o conteúdo da IA, guardado **180 dias**, depois apagado.
- **Os seus e-mails ao suporte**, se houver: guardados **12 meses** após a última troca.
- **Logs técnicos**, guardados **30 dias** para fazer o serviço funcionar e detectar falhas e
  abusos: a hora, a ação pedida ("fazer uma lição"…), a duração, o resultado, o modelo de IA e os
  créditos usados, a versão do app, um identificador curto da licença e, como em qualquer site, o
  **endereço IP** da requisição. Nunca o conteúdo das lições.

## Operadores

| Serviço | O que recebe | Onde |
|---|---|---|
| **Google Cloud**: Vertex AI (Gemini) | Fotos, instruções, cartões, ditados, descrições de imagens | Os seus servidores, no mundo (fora da União Europeia também) |
| **Google Cloud**: Cloud Run, Firestore, logs | O próprio serviço, as licenças, os logs | Bélgica (europe-west1) |
| **Google Cloud**: Text-to-Speech | O texto a ler (o verso de um cartão) | União Europeia |
| **Wikimedia Commons**, **Openverse**, **Pixabay** | Algumas palavras-chave em inglês ("dog"), nunca uma foto | Os servidores deles |
| **Google Play**: assinaturas, Play Integrity | O token de uma compra; o atestado do teste grátis | Os servidores dele |
| **GitHub** (GitHub Pages) | Ao abrir, o app lê ali o endereço do serviço: o GitHub vê o seu endereço IP | Os servidores dele |

O Google atua como operador, segundo os termos do Google Cloud, e não usa esses dados para
treinar os seus modelos. Para detectar abusos, o Google pode, porém, guardar as requisições
enviadas ao Gemini **por até 90 dias**, segundo os seus termos, sem usá-las para mais nada.

### Transferências para fora da União Europeia

A IA (o Gemini) pode processar as suas fotos, instruções e ditados fora da União Europeia, nos
servidores do Google; o resto acontece na União Europeia, mas o Google, o GitHub, a Wikimedia
Foundation e o Openverse são organizações dos EUA, que podem ter acesso a ele. Essas transferências são cobertas
pelas **cláusulas contratuais-padrão** da Comissão Europeia e, para empresas certificadas como o
Google, pelo **EU–US Data Privacy Framework**. O Pixabay é uma empresa da UE.

## Por quê: as bases legais

| Tratamento | Base legal |
|---|---|
| Fazer, completar, corrigir e explicar cartões; ditado; vozes; imagens | **Prestar o serviço** que você pede |
| Verificar a sua licença e contar os seus créditos | **Executar o contrato** (a sua licença) |
| Logs técnicos, segurança, combate ao abuso | O **legítimo interesse** em manter um serviço seguro |
| O teste grátis uma só vez por celular (Play Integrity) | O **legítimo interesse** em evitar o abuso do teste |
| Os seus relatos sobre o conteúdo da IA | O seu **pedido**, e o legítimo interesse em uma IA que faça conteúdo adequado |
| O microfone | O seu **consentimento**, pedido no primeiro ditado e revogável nas configurações do celular |
| Responder aos seus e-mails | O seu **pedido** |

O Notosaurus não toma **nenhuma decisão automatizada** sobre você e não faz **nenhuma criação de
perfil**. Sem a sua licença o serviço não pode ser prestado; todo o resto só é enviado quando você
pede.

## O modo "Com meu computador"

Quando o app abre o Notosaurus no seu computador (o complemento do Anki), o celular fala
diretamente com o computador, na Wi-Fi de casa: nada passa então pelo serviço Notosaurus. Vale a
página [Privacidade e segurança](../privacy/).

## As permissões do app

- **Internet**: para chegar ao serviço.
- **Microfone**, pedido na primeira vez que você toca em 🎤, e usado só durante o ditado: a sua
  voz é ouvida pelo reconhecimento de voz do celular (o do Android, em geral o do Google, no
  celular ou nos servidores dele, conforme as configurações) ou, num celular sem ele, escrita
  pela IA do serviço.
- **AnkiDroid**, para adicionar os cartões a ele, pedido no primeiro envio.
- As fotos são tiradas pela câmera do celular ou escolhidas na galeria, quando você faz isso. O
  app não precisa de acesso a todas as suas fotos.
- **Notificações**: nenhuma permissão pedida. Enquanto uma lição é criada ou enviada, o app pode continuar alguns minutos em segundo plano; onde as notificações são permitidas, mostra uma enquanto isso.
- O **QR code** do computador é lido pelo leitor de códigos dos serviços do Google Play, no celular: o app recebe só o endereço lido, nunca a imagem da câmera.

## As crianças

O app é usado por **um pai ou uma mãe**, não pela criança. Mas as fotos do caderno podem conter
dados da criança (o nome, a letra): oculte o nome com 🖍️ antes de enviar, e não ponha nada pessoal
nas instruções.

## Os seus direitos

Escrevendo para **notosaurus.app@gmail.com**, você pode:

- **acessar** os seus dados e obter uma cópia deles (**portabilidade**);
- pedir que sejam **corrigidos** ou **apagados**;
- **limitar** o tratamento deles, ou **se opor** ao tratamento baseado no legítimo interesse;
- **retirar o seu consentimento** (o microfone) a qualquer momento, sem efeito sobre o que foi
  feito antes.

As lições estão no seu celular: você mesmo as apaga no app. Você recebe uma resposta em até um
mês. Também pode reclamar à sua autoridade de proteção de dados (na França, a CNIL:
cnil.fr).

## Segurança

Toda troca com o serviço usa **HTTPS**. O serviço só guarda a impressão digital da sua chave de
licença. No seu celular, a chave fica no armazenamento privado do app, e as configurações só
mostram os últimos caracteres dela.

## Excluir os seus dados

Para que o serviço Notosaurus exclua o que guarda de você:

1. Escreva para **notosaurus.app@gmail.com**, assunto "Excluir meus dados".
2. Informe os últimos caracteres da sua chave de licença (⚙️ → 🔑 Assinatura os mostra), ou o
   número do seu pedido no Google Play se você for assinante. Se for assinante, cancele antes a
   assinatura no Google Play.
3. Nós os excluímos e confirmamos para você, em até um mês.

**Excluídos**: a sua licença (a impressão digital da chave, o seu plano, os seus créditos), o que
você relatou com ⚑ e os nossos e-mails. **Nunca guardados pelo serviço**: as suas lições, fotos,
gravações e cartões. Os registros técnicos dele se apagam sozinhos após 30 dias. O Google Play
guarda os registros dos seus pagamentos segundo os próprios termos. As suas lições no celular você
mesmo exclui, no app ou desinstalando-o.

## Alterações

Se esta política mudar, a data no alto da página também muda.
