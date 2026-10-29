---
title: "Configurações e serviços de IA"
description: "As configurações do complemento no computador; qual serviço de IA escolher, como obter a chave de API passo a passo, o modelo, os modelos locais, e quanto custa uma lição."
---

O Notosaurus não tem IA própria: ele usa o serviço que você escolher, com **a sua própria
chave**. Você paga o serviço diretamente, pelo que usar: sem assinatura.

## As configurações

No computador, **Ferramentas → Notosaurus → Configurações** as abre no navegador. Elas só abrem no
próprio computador: um celular não pode alterá-las nem ver as chaves. Em modo autônomo ou com
Docker, a página de configurações (`/admin.html`) é acessível pela rede, protegida por uma
**🔐 Senha de administrador** criada na primeira visita.

O que só o computador tem:

- **Serviço de IA**, **Acesso** (as chaves de API) e **Modelo**: veja abaixo.
- **Imagens nos cartões**: o **Serviço que as desenha** (o dos cartões quando ele sabe desenhar:
  Gemini, OpenAI, OpenRouter; o Claude e os modelos locais não) e o seu **Modelo de imagem**, com
  **🖼️ Testar: desenhar uma girafa**. Veja [Tipos de cartões](../card-types/#imagens).
- **📥 Enviar direto para o Anki**: o AnkiConnect, o modo autônomo, e a sincronização com o
  AnkiWeb. Veja [Enviar para o Anki](../send-to-anki/).
- **📱 Celulares**: o QR code que abre o Notosaurus em um celular e o autoriza, e **Desconectar
  todos os celulares**. Veja [No celular](../phone/) e [Privacidade e segurança](../privacy/).
- **Lições**: de quem é cada lição, quanto custou, excluí-la (veja [Quanto custa](#quanto-custa)).

![Configurações: os celulares, por QR code](../../../assets/screenshots/en/settings-phones.png)

**📝 Instruções para a IA** e **Vozes dos cartões** também estão nas configurações do app Android:
veja [Instruções](../instructions/#instruções-permanentes) e [Vozes](../voices/).

## Qual serviço?

| Serviço | Para quem | Custo de uma lição |
|---|---|---|
| **Gemini** (Google) | o padrão: rápido, barato, lê bem; um nível gratuito para experimentar | uma fração de centavo |
| **Claude** (Anthropic) | entre as melhores leituras de letra manuscrita, e o mais rápido (Sonnet) | alguns centavos |
| **OpenAI** (GPT) | se você já tem uma conta da OpenAI | alguns centavos |
| **OpenRouter** | uma chave para Gemini, Claude, GPT, Mistral…; o custo exato de cada lição | o preço do modelo escolhido |
| **Outro serviço compatível com a OpenAI** | um modelo em casa (Ollama, LM Studio), ou outro serviço | grátis em casa |

Troque de serviço quando quiser em **Configurações → Serviço de IA**: as lições já feitas ficam
como estão.

![Configurações: escolher o serviço de IA](../../../assets/screenshots/en/settings-ai.png)

## Obter uma chave

Crie a chave no site do serviço, depois cole-a em **Configurações → Acesso** e toque em
**🔌 Testar**: o Notosaurus verifica se o modelo lê uma imagem e responde no formato certo. Na
primeira vez, o [assistente de configuração](../getting-started/#2-o-assistente-de-configuração) faz
o mesmo em duas etapas.

![Configurações: a chave de API e o modelo](../../../assets/screenshots/en/settings-key.png)

### Gemini

1. Abra [aistudio.google.com/apikey](https://aistudio.google.com/apikey) e entre com uma conta do
   Google.
2. **Create API key**, depois copie-a.
3. O nível gratuito basta para experimentar o Notosaurus, mas os limites dele são baixos (algumas
   dezenas de requisições por dia nos melhores modelos) e o Google pode usar o que você envia para
   melhorar os seus produtos. Para os cadernos dos seus filhos, ative o faturamento do projeto da
   chave no Google AI Studio: você paga então uma fração de centavo por lição e, segundo os termos
   do Google, os seus dados não são usados para melhorar os produtos dele.

### Claude

1. Abra [console.anthropic.com](https://console.anthropic.com) e crie uma conta.
2. Em **Billing**, adicione um pouco de crédito: poucos euros duram muito.
3. Em **Settings → API keys**, **Create key**, depois copie-a.

### OpenAI

1. Abra [platform.openai.com](https://platform.openai.com) e crie uma conta.
2. Adicione um pouco de crédito nas configurações de faturamento.
3. Em **API keys**, crie uma chave secreta, depois copie-a.

### OpenRouter

1. Abra [openrouter.ai](https://openrouter.ai) e entre.
2. Compre créditos: o OpenRouter acrescenta uma pequena taxa a cada compra, então prefira uma
   compra de 15 $ ou mais a várias pequenas.
3. Em **Keys**, crie uma chave, depois copie-a.

Uma chave do OpenRouter dá acesso ao Gemini, Claude, GPT e muitos outros: útil para compará-los.
Por padrão, o Notosaurus usa o Gemini Flash pelo OpenRouter.

## O modelo

- **O Notosaurus escolhe por você**: com o campo **Modelo** vazio, cada serviço usa o seu padrão,
  o marcado com ⭐.
- **Recomendados, segundo nossos testes**, abaixo de **Modelo**, lista os modelos que aconselhamos
  para esse serviço, do melhor custo-benefício ao mais caro, com o custo de uma lição. Toque em um
  para escolhê-lo, ou digite qualquer outro modelo do serviço; com os serviços compatíveis com a
  OpenAI, **📋 Carregar os modelos do serviço** lista só os modelos que aceitam imagens.
- **Como os escolhemos**, e os modelos a evitar: veja [Qual modelo?](../which-model/).

O Gemini também tem **modelos reserva**, testados em ordem quando o principal está sobrecarregado
ou não está incluído no plano da chave (uma chave gratuita não tem o modelo mais recente: usa então
um mais antigo).

## Um modelo em casa

Com **Outro serviço compatível com a OpenAI**, o Notosaurus pode usar um modelo que roda no seu
computador, com o [Ollama](https://ollama.com) ou o [LM Studio](https://lmstudio.ai). O endereço
costuma terminar em `/v1` (Ollama: `http://localhost:11434/v1`). Nada sai de casa e nada é pago,
mas:

- o modelo precisa **aceitar imagens** (um modelo de "visão"): **📋 Carregar os modelos do
  serviço** os lista;
- ele precisa de uma **boa placa de vídeo** (ou um Mac recente com bastante memória);
- ele lê **a letra manuscrita bem pior** que o Gemini ou o Claude;
- com o Ollama, as correções precisam de um contexto maior que o padrão: defina
  `OLLAMA_CONTEXT_LENGTH` (por exemplo para 16384) antes de iniciá-lo.

## Quanto custa

**Configurações → Lições** mostra quanto a IA custou, no total, por perfil e por lição, com cada
geração, correção e imagem.

![Configurações: o custo de cada lição](../../../assets/screenshots/en/settings-costs.png)

Esses números são estimados a partir dos preços públicos dos serviços (o OpenRouter dá o custo
exato). Com uma chave gratuita do Gemini, nada é cobrado de fato. Por exemplo, a lição de
vocabulário destas capturas custou cerca de 2 centavos de dólar para gerar com o Claude Sonnet, e o
mesmo para a correção. As imagens custam de menos de um centavo a alguns centavos cada; as figuras,
menos de um centavo (desenhadas rápido, alguns segundos cada, enquanto você revisa os cartões).
Ficou em dúvida sobre uma figura? "🔍", embaixo dela, faz a IA olhar para ela; se encontrar algo
errado, você escolhe se ela é redesenhada, com o erro indicado: rápido (alguns segundos), depois,
se continuar errada, com cuidado, com o raciocínio do modelo (até um minuto).
