---
title: "No Anki do computador"
description: "O complemento no Anki do computador: o menu Ferramentas → Notosaurus e a configuração dele."
---

Com o complemento, o Notosaurus roda dentro do Anki no computador: ele inicia com o Anki, para com
ele, e escreve os cartões direto no perfil que está aberto.

## O menu Ferramentas → Notosaurus

![O menu Notosaurus no Anki](../../../assets/screenshots/en/anki-menu.png)

- **Abrir o Notosaurus** abre o Notosaurus no navegador do computador.
- **Abrir no celular…** mostra um QR code para abrir o Notosaurus no celular, e os três passos para
  chegar lá (veja [No celular](../phone/)).
- **Assistente de configuração** abre o assistente: a IA e a chave dela, depois o celular (veja
  [Primeiros passos com o complemento](../getting-started/#2-o-assistente-de-configuração)). Na
  primeira vez, o Anki o oferece sozinho quando nenhuma IA está configurada ainda.
- **Configurações** abre as configurações (serviço de IA e chave, vozes, filhos…) no navegador do
  computador. Elas só abrem no computador: o celular não pode alterá-las.
- **Estado do servidor…** diz se o Notosaurus está rodando, os endereços dele (no celular e neste
  computador), e onde ficam os arquivos dele e as suas lições.
- **Reiniciar o servidor** para e inicia de novo o Notosaurus: depois de mudar a configuração do
  complemento, ou quando algo travou.
- **Log do servidor** mostra o que o Notosaurus fez por último. É a primeira coisa a olhar quando
  algo dá errado (veja [Solução de problemas do complemento](../troubleshooting/)).
- **Ajuda** abre esta documentação, no idioma do Anki.
- **Apoiar o Notosaurus…** abre a página dele no [Ko-fi](https://ko-fi.com/notosaurus), para fazer
  uma doação se você gostar. O Notosaurus continua gratuito.

![O QR code para abrir o Notosaurus no celular](../../../assets/screenshots/en/anki-phone.png)

Trocar de perfil no Anki mantém o Notosaurus rodando: os cartões vão então para o perfil que está
aberto (veja [Vários filhos](../several-children/)).

## A configuração do complemento

Algumas opções técnicas ficam em **Ferramentas → Extensões**, selecione **Notosaurus**, depois
**Configurar**:

- `autostart`: iniciar o Notosaurus com o Anki (`true` por padrão). Com `false`, ele inicia na
  primeira vez que você usa o menu.
- `host`: `0.0.0.0` (padrão) deixa o celular chegar ao Notosaurus na mesma Wi-Fi; `127.0.0.1` o
  limita a este computador.
- `port`: `8000` por padrão. Mude-o se outro programa já usa essa porta.
- `source`, `python`, `data`: deixe-os vazios. Servem só para desenvolver o Notosaurus.

Depois de uma mudança: **Ferramentas → Notosaurus → Reiniciar o servidor**.

Os baralhos que o Notosaurus cria e como os cartões dele ficam no Anki, no computador e nos
celulares: veja [Os cartões no Anki](../cards-in-anki/).
