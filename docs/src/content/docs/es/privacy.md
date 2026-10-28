---
title: "Privacidad y seguridad en el ordenador"
description: "Lo que sale de tu ordenador, dónde guarda Notosaurus sus datos, quién puede usarlo, y cómo hacer una copia de seguridad."
---

Esta página trata de Notosaurus en un ordenador. Para la aplicación Android y su servicio, consulta
la [política de privacidad de la aplicación](../app-privacy/).

En un ordenador, Notosaurus no tiene cuenta ni servidor propio: funciona en tu ordenador. Una
lección suele mostrar la letra de un niño, a veces su nombre: aquí está a dónde va.

## Lo que sale de tu ordenador

- **Las fotos y las instrucciones** van al **servicio de IA elegido en los ajustes**, para hacer y
  corregir las tarjetas. El texto de un PDF digital va con su página. Con ellas van el curso del
  niño y tus instrucciones para él, **nunca su nombre**.
- **Los reversos de las tarjetas** van al servicio de síntesis de voz de Microsoft, para hacer el
  audio, cuando se elige una voz.
- **La descripción de una imagen** va al servicio que la dibuja, para «Idioma: vocabulario en
  imágenes».
- **Las palabras de una búsqueda de imagen** (unas palabras en inglés: «dog», «Storming of the
  Bastille painting») van a Wikimedia Commons y Openverse, para encontrar imágenes libres; nunca
  las fotos.

Las páginas en sí no cargan nada de otro sitio: sus scripts y fuentes vienen con Notosaurus (sin
Google Fonts, sin CDN).

Nada más: sin estadísticas, sin seguimiento. Con un modelo en casa (consulta
[Servicios de IA](../ai-services/#un-modelo-en-casa)), las fotos tampoco salen de casa.

:::caution[Niveles gratuitos]
Los niveles gratuitos suelen permitir al servicio de IA usar lo que envías para mejorar sus
modelos. Para los cuadernos de los niños, mejor una clave de pago. Antes de hacer la foto, también
puedes tapar un nombre escrito en la página.
:::

## Dónde están los datos

Todo se guarda como archivos simples, en la **carpeta de datos** de Notosaurus: las lecciones
(fotos, tarjetas, audio), las instrucciones y los ajustes.

- En el **complemento**, está en la carpeta del complemento, en `user_files/data`. **Herramientas
  → Notosaurus → Estado del servidor…** muestra dónde. Se conserva cuando se actualiza el
  complemento, y se elimina con él.
- **En autónomo**, es la carpeta `data/` (o `NOTOSAURUS_DATA`).

Las **claves de API** se guardan en esa carpeta, en `settings.json`, legibles solo por tu cuenta de
usuario. Nunca se devuelven a un móvil ni a un navegador: los ajustes solo muestran sus cuatro
últimos caracteres.

**Para hacer una copia de seguridad de Notosaurus**, copia la carpeta de datos. Las tarjetas en sí
están en Anki, respaldadas por Anki y, con una cuenta, por AnkiWeb.

## Quién puede usar Notosaurus

- **Solo los dispositivos emparejados.** Por la wifi, solo el propio ordenador y los dispositivos
  que han escaneado el código QR (**Ajustes → Móviles**) pueden usar Notosaurus: otros no pueden
  gastar tus créditos de IA ni eliminar lecciones. **Desconectar todos los móviles** los
  desempareja a todos, por ejemplo después de perder o prestar un móvil.
- **Los ajustes solo en el ordenador.** En el complemento, los ajustes solo se abren en el propio
  ordenador: los niños no pueden cambiar el servicio de IA ni ver las claves desde un móvil. En
  autónomo, están protegidos por una contraseña.
- **Una lección pertenece a un perfil.** Una lección solo se puede cambiar desde el perfil de Anki
  en el que se hizo; otro hijo recibe su propia copia (**⧉ Copiar para…**).

## La wifi

Notosaurus habla con los móviles en HTTP simple, en tu red local. El emparejamiento mantiene fuera
a los curiosos y a otros sitios web, pero no a alguien que espíe el tráfico de la wifi: mantén tu
wifi protegida (WPA2 o WPA3).

Notosaurus está hecho para casa: los móviles lo usan en la misma wifi que el ordenador. **Nunca
expongas Notosaurus** (ni AnkiConnect) **a Internet.**
