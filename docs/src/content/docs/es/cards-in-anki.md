---
title: "Las tarjetas en Anki"
description: "Dónde pone Notosaurus las tarjetas en Anki, cómo se ven, cómo las actualiza una lección enviada de nuevo, y ✎ Notosaurus para corregir una desde Anki."
---

Vengan de la aplicación (a AnkiDroid) o del ordenador (a Anki), las tarjetas son las mismas: los
mismos mazos, los mismos tipos de tarjeta, las mismas actualizaciones. Cómo enviarlas: consulta
[La aplicación y AnkiDroid](../app-ankidroid/) o [Enviar a Anki](../send-to-anki/).

## Los mazos

Cada lección tiene su mazo, por ejemplo `Inglés::Unit 3 - At school`: `::` crea un mazo dentro de
otro, así las lecciones de una asignatura quedan agrupadas. Las tarjetas con una sección
(Vocabulario, Test…) van a un submazo del mazo de la lección.

![Los mazos de Notosaurus en Anki](../../../assets/screenshots/en/anki-decks.png)

Para repasar una asignatura entera, haz clic en su mazo: Anki toma las tarjetas de todos los
mazos que contiene.

## Enviar una lección de nuevo

Una vez enviada la lección, el botón dice **✓ Al día en Anki**, y luego **🔄 Actualizar en Anki**
en cuanto algo cambia. Puedes corregir una lección y enviarla de nuevo tantas veces como quieras:

- sus tarjetas se **actualizan** en Anki, **no se duplican**, y cada tarjeta conserva su historial
  de repaso, aunque hayas corregido su anverso;
- si has cambiado el mazo de la lección, sus tarjetas se **mueven** allí, con su historial;
- las tarjetas añadidas desde el último envío se añaden;
- las tarjetas eliminadas de la lección se quedan en Anki: tras el envío, Notosaurus las lista y
  ofrece eliminarlas (con su historial de repaso), nunca sin preguntar.

Eliminar una lección entera en Notosaurus ofrece eliminar también sus tarjetas en Anki, con su
historial de repaso.

En el ordenador, cambiar una opción de tarjeta (la tarjeta inversa, la respuesta escrita) en una
lección ya enviada mueve sus tarjetas al tipo de nota correspondiente, con el historial.

En Anki, las notas de cada lección llevan una etiqueta `notosaurus::<lección>`: útil para
encontrarlas en el explorador.

## Corregir una tarjeta desde Anki

Bajo cada respuesta, un pequeño **✎ Notosaurus** abre la tarjeta en Notosaurus para corregirla:
en la aplicación en Android (AnkiDroid abre antes una pequeña página web, cuyo botón abre la
aplicación), en la página en el ordenador (Anki abierto, Notosaurus en su puerto habitual). No se
pierde nada: la corrección actualiza la misma nota, su historial de repaso se queda. El enlace
solo sabe dónde vive la lección: una lección hecha en el ordenador se abre allí, una hecha en la
aplicación se abre en la aplicación. AnkiWeb y AnkiMobile no lo muestran.

Hasta AnkiDroid 2.25.2, activa antes **Configuración → Avanzado → Allow cards to launch other
apps**: sin eso, AnkiDroid bloquea todos los enlaces de una tarjeta («Security: Card blocked from
launching another app»). Desde AnkiDroid 2.25.3, los enlaces a una página web pasan sin eso.

## Cómo se ven

Así se ven los [tipos de tarjeta](../card-types/) durante un repaso en Anki en el ordenador.
AnkiDroid y AnkiMobile muestran las mismas tarjetas.

**Pregunta y respuesta**: una palabra con su audio (▶) y una nota.

![Una tarjeta de vocabulario en Anki](../../../assets/screenshots/en/anki-vocab.png)

**Texto con huecos**: la pregunta oculta la palabra, la respuesta la muestra.

![Una tarjeta con huecos: la pregunta](../../../assets/screenshots/en/anki-cloze-q.png)

![Una tarjeta con huecos: la respuesta](../../../assets/screenshots/en/anki-cloze-a.png)

**Opción múltiple**: la respuesta marca la opción correcta con ✔ y da la explicación.

![Una tarjeta de opción múltiple: la pregunta](../../../assets/screenshots/en/anki-quiz-q.png)

![Una tarjeta de opción múltiple: la respuesta](../../../assets/screenshots/en/anki-quiz-a.png)

**Esquemas**: la foto de la lección con rótulos numerados; una tarjeta por rótulo que nombrar.

![Una tarjeta de esquema en Anki](../../../assets/screenshots/en/anki-diagram.png)

**Imágenes**: un dibujo que nombrar en el idioma que se aprende, con su audio.

![Una tarjeta de imagen en Anki](../../../assets/screenshots/en/anki-picture.png)

**Figuras**: la figura dibujada por Notosaurus acompaña a la pregunta.

![Una tarjeta con una figura en Anki](../../../assets/screenshots/en/anki-figure.png)
