---
title: "Primeros pasos con el complemento"
description: "Instalar Notosaurus en Anki, configurarlo con el asistente, conectar tu móvil y hacer tu primer mazo a partir de una foto."
---

El complemento de Anki hace funcionar Notosaurus en tu ordenador, dentro de Anki, gratis, con tu
propia clave de IA. Lo usas desde el navegador del móvil, o desde la aplicación Android, en la
misma wifi. ¿Prefieres la aplicación por sí sola? Consulta [¿Qué Notosaurus?](../which-notosaurus/).

## Lo que necesitas

- **Anki** en un ordenador (Windows, macOS o Linux), una versión reciente.
- **Un móvil** en la misma wifi que el ordenador.
- **Una clave para un servicio de IA.** Gemini es el más barato y tiene un nivel gratuito para
  probar Notosaurus; Claude y GPT también funcionan bien. Una lección cuesta de una fracción de
  céntimo a unos céntimos.

:::caution[Niveles gratuitos y privacidad]
Los niveles gratuitos suelen permitir al proveedor de IA usar lo que envías para mejorar sus
modelos. Para los cuadernos de tus hijos, mejor una clave de pago: unos euros duran mucho.
:::

## 1. Instalar el complemento

1. Descarga `notosaurus-<version>.ankiaddon` de la
   [última versión](https://github.com/cchabanois/notosaurus/releases/latest).
2. Haz doble clic en el archivo (o en Anki: **Herramientas → Complementos → Instalar desde
   archivo…**), y luego reinicia Anki.
3. En el primer inicio, Notosaurus pregunta antes de instalar sus componentes (unos 300 MB).
   Tarda unos minutos, una sola vez.

## 2. El asistente de configuración

Una vez instalados los componentes, Anki ofrece **«¿Configurarlo ahora?»**: el asistente se abre
en el navegador del ordenador. Dos pasos, unos minutos. Siempre está en **Herramientas →
Notosaurus → Asistente de inicio**, y mientras no haya ninguna IA configurada, la página de
Notosaurus muestra **«Falta un paso»** con un botón para iniciarlo.

**La IA.** Elige el servicio que lee las lecciones. Se recomienda **Gemini**: la mejor relación
calidad-precio en nuestras pruebas, alrededor de 1 céntimo de dólar por lección (consulta
[Ajustes y servicios de IA](../ai-services/) para los demás).

![El asistente: elegir la IA](../../../assets/screenshots/en/setup-start.png)

Para Gemini, el asistente explica cómo conseguir la clave en tres pasos. Pégala y toca
**🔌 Comprobar la clave**: Notosaurus comprueba que el modelo lee una imagen y responde en el
formato correcto. **Siguiente** aparece cuando pasa la prueba.

![El asistente: la clave de Gemini, comprobada](../../../assets/screenshots/en/setup-ai.png)

**El móvil.** Escanea el código QR con la cámara del móvil y abre el enlace. El asistente espera
al móvil y luego muestra **«✓ El móvil está conectado.»** Después añade la página a la pantalla de
inicio: se abre como una aplicación (consulta [En el móvil](../phone/) para cada navegador). **Más
tarde** se salta este paso: el código QR sigue en **Herramientas → Notosaurus → Abrir en el
móvil…** y en los ajustes.

![El asistente: el código QR para el móvil](../../../assets/screenshots/en/setup-phone.png)

**¡Listo!** Abre Notosaurus, o todos los ajustes: imágenes de las tarjetas, voces, instrucciones
por hijo… Los ajustes solo se abren en el ordenador: los niños no pueden cambiarlos desde un móvil.

![El asistente: Notosaurus está listo](../../../assets/screenshots/en/setup-done.png)

:::tip
Solo los dispositivos que han escaneado este código QR pueden usar Notosaurus. Si se pierde o se
presta un móvil: **Ajustes → Móviles → Desconectar todos los móviles**.
:::

## 3. Tu primera lección

1. En **Fotos de la lección**, haz una foto de la página (o de varias páginas), o añade un PDF:
   consulta [Fotos y PDF](../photos/).
2. En **Instrucciones**, elige qué hacer: vocabulario, preguntas, texto con huecos, un esquema
   que completar… **Automático** elige según la lección. Consulta [Instrucciones](../instructions/).

   ![Una foto de la lección y las instrucciones](../../../assets/screenshots/en/instructions.png)

3. Toca **Generar las tarjetas** y espera unos segundos.
4. Revisa las tarjetas. Edítalas, elimina algunas, o pide a la IA que las corrija con tus
   palabras: consulta [Revisar las tarjetas](../review/).

   ![Las tarjetas, listas para revisar](../../../assets/screenshots/en/review.png)

   ![Pedir una corrección a la IA](../../../assets/screenshots/en/correction.png)

5. Toca **Añadir a Anki**.

La lección se guarda: puedes volver a abrirla más tarde desde la lista de lecciones, corregirla y
enviarla de nuevo. Sus tarjetas se actualizan en Anki, no se duplican.

Con las instrucciones **Esquema o mapa mudo**, los rótulos de un esquema se ocultan tras números:
cada tarjeta pregunta por uno de ellos.

![Un esquema con los rótulos ocultos](../../../assets/screenshots/en/diagram.png)

## 4. Repasar en el móvil

Para repasar en el móvil, usa **AnkiDroid** (Android) o **AnkiMobile** (iPhone) con una cuenta de
**AnkiWeb**: Notosaurus sincroniza Anki tras enviar las tarjetas. Con varios hijos, consulta
[Varios hijos](../several-children/).
