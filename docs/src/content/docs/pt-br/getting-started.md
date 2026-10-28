---
title: "Primeiros passos com o complemento"
description: "Instalar o Notosaurus no Anki, configurá-lo com o assistente, conectar o celular e fazer o seu primeiro baralho a partir de uma foto."
---

O complemento do Anki roda o Notosaurus no seu computador, dentro do Anki, de graça, com a sua
própria chave de IA. Você o usa pelo navegador do celular, ou pelo app Android, na mesma Wi-Fi.
Prefere o app sozinho? Veja [Qual Notosaurus?](../which-notosaurus/).

## Do que você precisa

- **O Anki** em um computador (Windows, macOS ou Linux), uma versão recente.
- **Um celular** na mesma Wi-Fi que o computador.
- **Uma chave de um serviço de IA.** O Gemini é o mais barato e tem um nível gratuito para
  experimentar o Notosaurus; o Claude e o GPT também funcionam bem. Uma lição custa de uma fração
  de centavo a alguns centavos.

:::caution[Níveis gratuitos e privacidade]
Os níveis gratuitos costumam permitir que o provedor de IA use o que você envia para melhorar os
modelos dele. Para os cadernos dos seus filhos, prefira uma chave paga: poucos euros duram muito.
:::

## 1. Instalar o complemento

1. Baixe `notosaurus-<version>.ankiaddon` da
   [versão mais recente](https://github.com/cchabanois/notosaurus/releases/latest).
2. Clique duas vezes no arquivo (ou no Anki: **Ferramentas → Extensões → Instalar de um
   arquivo...**), depois reinicie o Anki.
3. Na primeira abertura, o Notosaurus pergunta antes de instalar os seus componentes (cerca de
   300 MB). Leva alguns minutos, uma vez só.

## 2. O assistente de configuração

Depois de instalados os componentes, o Anki oferece **"Configurar agora?"**: o assistente abre no
navegador do computador. Duas etapas, alguns minutos. Ele fica sempre em **Ferramentas →
Notosaurus → Assistente de configuração**, e enquanto nenhuma IA estiver configurada, a página do
Notosaurus mostra **"Falta uma etapa"** com um botão para iniciá-lo.

**A IA.** Escolha o serviço que lê as lições. O **Gemini** é recomendado: o melhor custo-benefício
nos nossos testes, cerca de 1 centavo de dólar por lição (veja
[Configurações e serviços de IA](../ai-services/) para os outros).

![O assistente: escolher a IA](../../../assets/screenshots/en/setup-start.png)

Para o Gemini, o assistente explica como obter a chave em três passos. Cole-a e toque em
**🔌 Verificar a chave**: o Notosaurus verifica se o modelo lê uma imagem e responde no formato
certo. **Próximo** aparece quando passa.

![O assistente: a chave do Gemini, verificada](../../../assets/screenshots/en/setup-ai.png)

**O celular.** Escaneie o QR code com a câmera do celular e abra o link. O assistente espera o
celular, depois mostra **"✓ O celular está conectado."** Em seguida, adicione a página à tela
inicial: ela abre como um app (veja [No celular](../phone/) para cada navegador). **Mais tarde**
pula esta etapa: o QR code continua em **Ferramentas → Notosaurus → Abrir no celular…** e nas
configurações.

![O assistente: o QR code para o celular](../../../assets/screenshots/en/setup-phone.png)

**Pronto!** Abra o Notosaurus, ou todas as configurações: imagens dos cartões, vozes, instruções
por filho… As configurações só abrem no computador: as crianças não podem mudá-las pelo celular.

![O assistente: o Notosaurus está pronto](../../../assets/screenshots/en/setup-done.png)

:::tip
Só os aparelhos que escanearam este QR code podem usar o Notosaurus. Se um celular for perdido ou
emprestado: **Configurações → Celulares → Desconectar todos os celulares**.
:::

## 3. Sua primeira lição

1. Em **Fotos da lição**, tire uma foto da página (ou de várias páginas), ou adicione um PDF: veja
   [Fotos e PDFs](../photos/).
2. Em **Instruções**, escolha o que fazer: vocabulário, perguntas, lacunas, um esquema para
   completar… **Automático** escolhe conforme a lição. Veja [Instruções](../instructions/).

   ![Uma foto da lição e as instruções](../../../assets/screenshots/en/instructions.png)

3. Toque em **Gerar os cartões** e espere alguns segundos.
4. Confira os cartões. Edite-os, exclua alguns, ou peça à IA para corrigi-los com suas palavras:
   veja [Revisar os cartões](../review/).

   ![Os cartões, prontos para revisar](../../../assets/screenshots/en/review.png)

   ![Pedir uma correção à IA](../../../assets/screenshots/en/correction.png)

5. Toque em **Adicionar ao Anki**.

A lição fica salva: você pode reabri-la mais tarde pela lista de lições, corrigi-la e enviá-la de
novo. Os cartões dela são atualizados no Anki, não duplicados.

Com as instruções **Esquema ou mapa para completar**, as legendas de um esquema ficam escondidas
atrás de números: cada cartão pergunta por uma delas.

![Um esquema com as legendas escondidas](../../../assets/screenshots/en/diagram.png)

## 4. Revisar no celular

Para revisar no celular, use o **AnkiDroid** (Android) ou o **AnkiMobile** (iPhone) com uma conta
do **AnkiWeb**: o Notosaurus sincroniza o Anki depois de enviar os cartões. Com vários filhos, veja
[Vários filhos](../several-children/).
