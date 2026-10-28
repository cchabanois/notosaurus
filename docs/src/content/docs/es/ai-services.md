---
title: "Ajustes y servicios de IA"
description: "Los ajustes del complemento en el ordenador; qué servicio de IA elegir, cómo conseguir su clave de API paso a paso, el modelo, los modelos locales, y lo que cuesta una lección."
---

Notosaurus no tiene IA propia: usa el servicio que elijas, con **tu propia clave**. Pagas al
servicio directamente, por lo que usas: sin suscripción.

## Los ajustes

En el ordenador, **Herramientas → Notosaurus → Ajustes** los abre en el navegador. Solo se abren
en el propio ordenador: un móvil no puede cambiarlos ni ver las claves. En autónomo o con Docker,
la página de ajustes (`/admin.html`) es accesible desde la red, protegida por una **🔐 Contraseña
de administrador** creada en la primera visita.

Lo que solo tiene el ordenador:

- **Servicio de IA**, **Acceso** (las claves de API) y **Modelo**: ver abajo.
- **Imágenes de las tarjetas**: el **Servicio que las dibuja** (el de las tarjetas cuando sabe
  dibujar: Gemini, OpenAI, OpenRouter; Claude y los modelos locales no) y su **Modelo de imagen**,
  con **🖼️ Probar: dibujar una jirafa**. Consulta [Tipos de tarjetas](../card-types/#imágenes).
- **📥 Enviar directamente a Anki**: AnkiConnect, el modo autónomo, y la sincronización con
  AnkiWeb. Consulta [Enviar a Anki](../send-to-anki/).
- **📱 Móviles**: el código QR que abre Notosaurus en un móvil y lo autoriza, y **Desconectar todos
  los móviles**. Consulta [En el móvil](../phone/) y [Privacidad y seguridad](../privacy/).
- **Lecciones**: de quién es cada lección, cuánto costó, eliminarla (consulta
  [Lo que cuesta](#lo-que-cuesta)).

![Ajustes: los móviles, por código QR](../../../assets/screenshots/en/settings-phones.png)

**📝 Instrucciones para la IA** y **Voces de las tarjetas** también están en los ajustes de la
aplicación Android: consulta [Instrucciones](../instructions/#instrucciones-permanentes) y
[Voces](../voices/).

## ¿Qué servicio?

| Servicio | Para quién | Coste de una lección |
|---|---|---|
| **Gemini** (Google) | el predeterminado: rápido, barato, lee bien; un nivel gratuito para probar | una fracción de céntimo |
| **Claude** (Anthropic) | de las mejores lecturas de letra manuscrita, y el más rápido (Sonnet) | unos céntimos |
| **OpenAI** (GPT) | si ya tienes una cuenta de OpenAI | unos céntimos |
| **OpenRouter** | una clave para Gemini, Claude, GPT, Mistral…; el coste exacto de cada lección | el precio del modelo elegido |
| **Otro servicio compatible con OpenAI** | un modelo en casa (Ollama, LM Studio), u otro servicio | gratis en casa |

Cambia de servicio cuando quieras en **Ajustes → Servicio de IA**: las lecciones ya hechas se
quedan como están.

![Ajustes: elegir el servicio de IA](../../../assets/screenshots/en/settings-ai.png)

## Conseguir una clave

Crea la clave en el sitio del servicio, pégala en **Ajustes → Acceso** y toca **🔌 Probar**:
Notosaurus comprueba que el modelo lee una imagen y responde en el formato correcto. La primera
vez, el [asistente de configuración](../getting-started/#2-el-asistente-de-configuración) hace lo
mismo en dos pasos.

![Ajustes: la clave de API y el modelo](../../../assets/screenshots/en/settings-key.png)

### Gemini

1. Abre [aistudio.google.com/apikey](https://aistudio.google.com/apikey) e inicia sesión con una
   cuenta de Google.
2. **Create API key**, y luego cópiala.
3. El nivel gratuito basta para probar Notosaurus, pero sus límites son bajos (unas decenas de
   peticiones al día con los mejores modelos) y Google puede usar lo que envías para mejorar sus
   productos. Para los cuadernos de tus hijos, activa la facturación del proyecto de la clave en
   Google AI Studio: pagas entonces una fracción de céntimo por lección y, según las condiciones de
   Google, tus datos no se usan para mejorar sus productos.

### Claude

1. Abre [console.anthropic.com](https://console.anthropic.com) y crea una cuenta.
2. En **Billing**, añade algo de saldo: unos euros duran mucho.
3. En **Settings → API keys**, **Create key**, y luego cópiala.

### OpenAI

1. Abre [platform.openai.com](https://platform.openai.com) y crea una cuenta.
2. Añade algo de saldo en los ajustes de facturación.
3. En **API keys**, crea una clave secreta, y luego cópiala.

### OpenRouter

1. Abre [openrouter.ai](https://openrouter.ai) e inicia sesión.
2. Compra créditos: OpenRouter añade una pequeña comisión a cada compra, así que mejor una compra
   de 15 $ o más que varias pequeñas.
3. En **Keys**, crea una clave, y luego cópiala.

Una clave de OpenRouter da acceso a Gemini, Claude, GPT y muchos otros: útil para compararlos. Por
defecto, Notosaurus usa Gemini Flash a través de OpenRouter.

## El modelo

- **Notosaurus elige por ti**: con el campo **Modelo** vacío, cada servicio usa su
  predeterminado, el marcado con ⭐.
- **Recomendados, según nuestras pruebas**, bajo **Modelo**, lista los modelos que aconsejamos para
  ese servicio, del de mejor relación calidad-precio al más caro, con lo que cuesta una lección.
  Toca uno para elegirlo, o escribe cualquier otro modelo del servicio; con los servicios
  compatibles con OpenAI, **📋 Cargar los modelos del servicio** lista solo los modelos que aceptan
  imágenes.
- **Cómo los elegimos**, y los modelos que evitar: consulta [¿Qué modelo?](../which-model/).

Gemini también tiene **modelos de reserva**, probados por orden cuando el principal está
sobrecargado o no está incluido en el plan de la clave (una clave gratuita no tiene el modelo más
reciente: usa entonces uno anterior).

## Un modelo en casa

Con **Otro servicio compatible con OpenAI**, Notosaurus puede usar un modelo que funcione en tu
ordenador, con [Ollama](https://ollama.com) o [LM Studio](https://lmstudio.ai). La dirección suele
terminar en `/v1` (Ollama: `http://localhost:11434/v1`). Nada sale de casa y no se paga nada,
pero:

- el modelo debe **aceptar imágenes** (un modelo de «visión»): **📋 Cargar los modelos del
  servicio** los lista;
- necesita una **buena tarjeta gráfica** (o un Mac reciente con mucha memoria);
- lee **la letra manuscrita mucho peor** que Gemini o Claude;
- con Ollama, las correcciones necesitan un contexto más largo que el predeterminado: define
  `OLLAMA_CONTEXT_LENGTH` (por ejemplo a 16384) antes de iniciarlo.

## Lo que cuesta

**Ajustes → Lecciones** muestra lo que ha costado la IA, en total, por perfil y por lección, con
cada generación, corrección e imagen.

![Ajustes: el coste de cada lección](../../../assets/screenshots/en/settings-costs.png)

Estas cifras se estiman a partir de los precios públicos de los servicios (OpenRouter da el coste
exacto). Con una clave gratuita de Gemini, en realidad no se cobra nada. Como ejemplo, la lección
de vocabulario de estas capturas costó unos 2 céntimos de dólar al generarla con Claude Sonnet, y
otro tanto su corrección. Las imágenes cuestan de menos de un céntimo a unos céntimos cada una; las
figuras, menos de un céntimo (dibujadas rápido, unos segundos cada una, mientras revisas las
tarjetas). ¿Dudas de una figura? «🔍», debajo, hace que la IA la mire; si encuentra algo mal,
eliges si se vuelve a dibujar, indicándole el error: rápido (unos segundos) y luego, si sigue mal,
con cuidado, con el razonamiento del modelo (hasta un minuto).
