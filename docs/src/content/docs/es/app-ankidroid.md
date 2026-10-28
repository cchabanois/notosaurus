---
title: "La aplicación y AnkiDroid"
description: "Cómo pone la aplicación las tarjetas en AnkiDroid: su permiso, actualizaciones sin duplicados, abrir AnkiDroid, corregir una tarjeta desde AnkiDroid, y el mazo filtrado de un examen."
---

En este teléfono, las tarjetas van a **AnkiDroid**, la aplicación gratuita de Anki para Android:
sin `.apkg`, sin ordenador, sin esperar a la sincronización.

## La primera vez

1. **Instala AnkiDroid** desde Google Play, si no está: la aplicación abre su página cuando falta.
2. **Abre AnkiDroid una vez**, para que cree su colección.
3. En el primer **📥 Añadir a Anki**, AnkiDroid pregunta si Notosaurus puede añadirle tarjetas (el
   propio diálogo de AnkiDroid): permítelo.

**📥 AnkiDroid**, en los ajustes de la aplicación, dice cómo están las cosas: **✓ AnkiDroid está
instalado y Notosaurus puede añadirle tarjetas.**, o un botón para **Instalar AnkiDroid** o para
**Permitir**.

![AnkiDroid pregunta si Notosaurus puede acceder a notas, tarjetas, tipos de nota y mazos y crearlos](../../../assets/screenshots/en/app-ankidroid-permission.png)

## Enviar las tarjetas

**📥 Añadir a Anki** escribe las tarjetas en AnkiDroid, en el mazo de la lección, con sus sonidos
e imágenes. Como en el ordenador:

- **Enviada de nuevo**, una lección **actualiza** sus tarjetas en vez de duplicarlas, y su
  historial de repaso se queda.
- **Las tarjetas eliminadas de la lección** se quedan en AnkiDroid: tras el envío, la aplicación
  las lista y ofrece eliminarlas (con su historial de repaso), nunca sin preguntar.
- **Eliminar una lección** ofrece eliminar también sus tarjetas en AnkiDroid.

AnkiDroid sincroniza las tarjetas con AnkiWeb como siempre, si tiene una cuenta conectada: llegan
entonces a Anki en un ordenador, o a otro teléfono.

## Abrir AnkiDroid

**Abrir AnkiDroid**, arriba de la página y al final, lo abre con un toque, para repasar las
tarjetas recién enviadas.

![Los mazos de AnkiDroid tras enviar lecciones desde la aplicación: un mazo por asignatura, un submazo por lección](../../../assets/screenshots/en/app-ankidroid-decks.png)

## Corregir una tarjeta desde AnkiDroid

Bajo cada respuesta en AnkiDroid, un pequeño **✎ Notosaurus** abre la tarjeta en la aplicación
para corregirla (AnkiDroid abre antes una pequeña página web, cuyo botón abre la aplicación). La
corrección actualiza la misma nota: su historial de repaso se queda. Una lección hecha con el
ordenador ([Con tu ordenador](../app-with-computer/)) se abre en el ordenador, no en la
aplicación.

Hasta **AnkiDroid 2.25.2**, activa antes en AnkiDroid **Configuración → Avanzado → Allow cards to
launch other apps**: sin eso, AnkiDroid bloquea todos los enlaces de una tarjeta («Security: Card
blocked from launching another app»). Desde AnkiDroid 2.25.3, los enlaces a una página web pasan
sin eso.

![Una tarjeta en AnkiDroid con su sonido y, bajo la respuesta, ✎ Notosaurus](../../../assets/screenshots/en/app-ankidroid-card.png)

## El mazo filtrado de un examen

Un examen que preparar reúne tarjetas de varias lecciones bajo una etiqueta (consulta
[Preparar un examen](../tests/)). En su ventana, **Abrir en AnkiDroid** abre las tarjetas del
examen en el explorador de tarjetas de AnkiDroid, estén en el mazo que estén; luego **⋮ → Crear
mazo filtrado → Construir** (con más de 100 tarjetas, sube antes **Limitar a**). AnkiDroid no deja
que otra aplicación cree por sí sola un mazo filtrado.

¿Algo va mal? Consulta [Solucionar problemas de la aplicación](../app-troubleshooting/).
