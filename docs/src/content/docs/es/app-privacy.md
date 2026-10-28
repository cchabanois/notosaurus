---
title: "Política de privacidad de la aplicación Android"
description: "Los datos que tratan la aplicación Android de Notosaurus y su servicio, por qué, dónde, durante cuánto tiempo, y tus derechos."
---

*Última actualización: 21 de octubre de 2026.*

Esta página trata de **la aplicación Notosaurus para Android** y del **servicio Notosaurus** que
usa para leer las fotos y hacer las tarjetas y las voces. Notosaurus en un ordenador (el
complemento de Anki) funciona de otra manera: consulta [Privacidad y seguridad](../privacy/).

**Responsable del tratamiento**: CHABANOIS Cédric.
**Contacto**: notosaurus.app@gmail.com

**Quién usa la aplicación**: un **padre o una madre** (un adulto), que prepara el repaso de sus
hijos. La aplicación no está hecha para que la use un niño.

## En resumen

- Tus **lecciones se quedan en tu móvil**: fotos, tarjetas, instrucciones, sonidos.
- Lo que la IA debe leer (fotos, instrucciones, dictados) **pasa por el servicio** mientras se
  hacen las tarjetas, **y no se guarda allí**.
- La IA (**Gemini de Google**) y las voces se **procesan en la Unión Europea**. Google no los usa
  para entrenar sus modelos.
- **Sin publicidad, sin estadísticas, sin seguimiento**, y no se vende nada.
- El servicio solo guarda tu **licencia** (su huella, tu plan y tus créditos), y lo que
  **denuncias** con ⚑, si lo haces.

## Lo que se queda en tu móvil

Las lecciones (fotos de las páginas, tarjetas, instrucciones, imágenes de las tarjetas, sonidos),
tus instrucciones guardadas y tus ajustes, incluida tu clave de licencia, se guardan **en el
almacenamiento privado de la aplicación** en tu móvil. Otras aplicaciones no pueden acceder a
ellos. Se borran cuando eliminas una lección, o la aplicación.

Las tarjetas enviadas a **AnkiDroid** se escriben en él en tu móvil. Su sincronización con AnkiWeb
depende de AnkiDroid y de tu cuenta de AnkiWeb, no de Notosaurus.

## Lo que pasa por el servicio Notosaurus

Cuando lo pides, la aplicación envía al servicio, por HTTPS:

| Qué | Para qué |
|---|---|
| Las **fotos** de las páginas y su texto (PDF), la **instrucción**, tus instrucciones permanentes, tus nombres de mazo | Hacer o completar las tarjetas de la lección |
| Las **tarjetas** de una lección y tu corrección | Corregirlas, explicar una tarjeta, poner en limpio una instrucción |
| Una **grabación de tu voz** (🎤) | Escribirla como texto (dictar una instrucción o una corrección) |
| El **reverso** de una tarjeta | Leerlo en voz alta (las voces de las tarjetas) |
| La **descripción** de una imagen, o unas **palabras clave** | Dibujar la imagen de una tarjeta, o buscar una libre |
| Tu **clave de licencia** | Comprobar tu licencia y contar tus créditos |
| Si te suscribes: el **token de tu compra** en Google Play | Comprobar la suscripción con Google Play y convertirla en tu licencia |
| Para la **prueba gratuita**: una **huella del teléfono** (calculada por la aplicación, nunca su identificador) y la certificación **Play Integrity** de Google | Ofrecer la prueba una sola vez por teléfono, a la aplicación instalada desde Google Play en un teléfono real |

El servicio pasa estos contenidos a los encargados del tratamiento de abajo, devuelve el
resultado a la aplicación y **no los guarda**: ninguna foto, tarjeta, grabación o texto de lección
se almacena ni se escribe en sus registros. Salvo una **denuncia**: ver más abajo.

Una página de cuaderno suele mostrar el **nombre del niño**. Antes de enviar una foto puedes
**ocultarlo**: 🖍️ en la foto, y luego tápalo con el dedo. Solo la foto tapada sale y se queda en la
lección.

## Lo que guarda el servicio

- **Tu licencia**: la huella de su clave (no la clave), tu plan, tus créditos restantes, su fecha
  de renovación, lo usado ese día, y una nota breve para el soporte (un número de pedido, por
  ejemplo). Se guarda mientras es válida, luego **12 meses** después de que termine (para
  responder a una pregunta o una reclamación), y después se borra.
- **Lo que denuncias** con ⚑ (una tarjeta hecha por la IA, con su explicación si se muestra y su
  imagen, salvo una foto que hayas hecho tú; ofensiva o incorrecta), si lo haces: exactamente lo
  que la aplicación te muestra antes de enviarlo, el motivo, tu comentario, las instrucciones de la
  lección, el idioma y un identificador corto de licencia. Nunca las fotos de la lección ni el
  nombre del niño. Lo lee Notosaurus para mejorar el contenido de la IA, se guarda **180 días**, y
  luego se borra.
- **Tus correos al soporte**, si los hay: se guardan **12 meses** tras el último intercambio.
- **Registros técnicos**, guardados **30 días** para hacer funcionar el servicio y detectar fallos
  y abusos: la hora, la acción pedida («hacer una lección»…), su duración, su resultado, el modelo
  de IA y los créditos usados, la versión de la aplicación, un identificador corto de licencia y,
  como en cualquier sitio web, la **dirección IP** de la petición. Nunca el contenido de las
  lecciones.

## Encargados del tratamiento

| Servicio | Lo que recibe | Dónde |
|---|---|---|
| **Google Cloud**: Vertex AI (Gemini) | Fotos, instrucciones, tarjetas, dictados, descripciones de imágenes | Unión Europea |
| **Google Cloud**: Cloud Run, Firestore, registros | El servicio en sí, las licencias, los registros | Bélgica (europe-west1) |
| **Google Cloud**: Text-to-Speech | El texto que leer (el reverso de una tarjeta) | Unión Europea |
| **Wikimedia Commons**, **Openverse**, **Pixabay** | Unas palabras clave en inglés («dog»), nunca una foto | Sus servidores |
| **Google Play**: suscripciones, Play Integrity | El token de una compra; la certificación de la prueba gratuita | Sus servidores |
| **GitHub** (GitHub Pages) | Al iniciarse, la aplicación lee ahí la dirección del servicio: GitHub ve tu dirección IP | Sus servidores |

Google actúa como encargado del tratamiento, según las condiciones de Google Cloud, y no usa
estos datos para entrenar sus modelos. Para detectar abusos, Google puede sin embargo guardar las
peticiones enviadas a Gemini **hasta 90 días**, según sus condiciones, sin usarlas para nada más.

### Transferencias fuera de la Unión Europea

El tratamiento se hace en la Unión Europea, pero Google, GitHub, la Fundación Wikimedia y
Openverse son organizaciones estadounidenses, que pueden acceder a él. Estas transferencias están
cubiertas por las **cláusulas contractuales tipo** de la Comisión Europea y, para las empresas
certificadas como Google, por el **Marco de Privacidad de Datos UE-EE. UU.**. Pixabay es una
empresa de la UE.

## Por qué: las bases jurídicas

| Tratamiento | Base jurídica |
|---|---|
| Hacer, completar, corregir y explicar tarjetas; dictado; voces; imágenes | **Prestar el servicio** que pides |
| Comprobar tu licencia y contar tus créditos | **Ejecutar el contrato** (tu licencia) |
| Registros técnicos, seguridad, lucha contra el abuso | El **interés legítimo** en hacer funcionar un servicio seguro |
| La prueba gratuita una sola vez por teléfono (Play Integrity) | El **interés legítimo** en evitar el abuso de la prueba |
| Tus denuncias del contenido de la IA | Tu **solicitud**, y el interés legítimo en una IA que haga contenido adecuado |
| El micrófono | Tu **consentimiento**, pedido en el primer dictado y revocable en los ajustes del teléfono |
| Responder a tus correos | Tu **solicitud** |

Notosaurus no toma **ninguna decisión automatizada** sobre ti y no hace **ninguna elaboración de
perfiles**. Sin tu licencia no se puede prestar el servicio; todo lo demás solo se envía cuando lo
pides.

## El modo «Con mi ordenador»

Cuando la aplicación abre Notosaurus en tu ordenador (el complemento de Anki), el móvil habla
directamente con el ordenador, en la wifi de casa: entonces no pasa nada por el servicio
Notosaurus. Se aplica la página [Privacidad y seguridad](../privacy/).

## Los permisos de la aplicación

- **Internet**: para llegar al servicio.
- **Micrófono**, pedido la primera vez que tocas 🎤, y usado solo mientras dictas.
- **AnkiDroid**, para añadirle las tarjetas, pedido en el primer envío.
- Las fotos se hacen con la cámara del móvil o se eligen en la galería, cuando tú lo haces. La
  aplicación no necesita acceso a todas tus fotos.

## Los niños

La aplicación la usa **un padre o una madre**, no el niño. Pero las fotos de cuaderno pueden
contener datos del niño (su nombre, su letra): oculta el nombre con 🖍️ antes de enviar, y no pongas
nada personal en las instrucciones.

## Tus derechos

Escribiendo a **notosaurus.app@gmail.com**, puedes:

- **acceder** a tus datos y obtener una copia (**portabilidad**);
- hacer que se **rectifiquen** o se **supriman**;
- **limitar** su tratamiento, u **oponerte** al tratamiento basado en el interés legítimo;
- **retirar tu consentimiento** (el micrófono) en cualquier momento, sin efecto sobre lo hecho
  antes.

Las lecciones están en tu móvil: las borras tú mismo en la aplicación. Recibes una respuesta en
el plazo de un mes. También puedes reclamar ante tu autoridad de protección de datos (en Francia,
la CNIL: cnil.fr).

## Seguridad

Todos los intercambios con el servicio usan **HTTPS**. El servicio solo guarda la huella de tu
clave de licencia. En tu móvil, la clave se queda en el almacenamiento privado de la aplicación, y
los ajustes solo muestran sus últimos caracteres.

## Cambios

Si esta política cambia, la fecha de arriba de la página también cambia.
