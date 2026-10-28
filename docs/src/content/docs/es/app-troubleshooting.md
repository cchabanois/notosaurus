---
title: "Solucionar problemas de la aplicación"
description: "Qué hacer cuando la aplicación Android dice que no quedan créditos, que la prueba o la suscripción han terminado, que AnkiDroid no acepta las tarjetas o que el ordenador no responde."
---

Los mensajes de abajo son los que muestra la aplicación.

## La suscripción

| Mensaje | Qué hacer |
|---|---|
| «No quedan créditos este mes» | Vuelven con la próxima renovación: **🔑 Suscripción**, en los ajustes, dice cuándo. |
| «Tu prueba gratuita ha terminado» | Suscríbete en los Ajustes (**🔑 Suscripción**) para continuar. |
| «Ahora no hay nuevas pruebas gratuitas…» | Las nuevas pruebas gratuitas están en pausa por el momento: suscríbete en los Ajustes, o vuelve a intentarlo mañana. Una prueba ya empezada continúa. |
| «Tu suscripción ha terminado» | Vuelve a suscribirte en la aplicación. |
| «Pago pendiente» | Google Play no ha podido renovar la suscripción: actualiza tu método de pago en Google Play (**Ajustes → Gestionar la suscripción**). |
| «La prueba gratuita solo es posible con la app instalada desde Google Play, en un teléfono real» | Instala la aplicación desde Google Play; la prueba no se ofrece en un emulador. |
| «No se ha encontrado ninguna suscripción en esta cuenta de Google» (**Ya tengo una suscripción**) | Comprueba que el teléfono usa la cuenta de Google con la que se hizo la suscripción. |

Consulta [La suscripción](../app-subscription/).

## AnkiDroid

| Mensaje | Qué hacer |
|---|---|
| «Notosaurus no tiene permiso para añadir tarjetas a AnkiDroid» | **Ajustes → 📥 AnkiDroid → Permitir**, y vuelve a añadir las tarjetas. Rechazado para siempre (Android ya no pregunta): permítelo en los ajustes de Android, **Aplicaciones → Notosaurus → Permisos**. |
| «AnkiDroid no está instalado» / «AnkiDroid no aceptó las tarjetas» | Instala AnkiDroid, **ábrelo una vez** (crea su colección), y vuelve a añadir las tarjetas. |

**✎ Notosaurus no hace nada en AnkiDroid** («Security: Card blocked from launching another
app»): hasta AnkiDroid 2.25.2, activa en AnkiDroid **Configuración → Avanzado → Allow cards to
launch other apps**, o actualiza AnkiDroid (desde 2.25.3, el enlace pasa sin eso).

**Tarjetas sin sonido**: las voces del servicio Notosaurus no han respondido (el teléfono necesita
Internet). Las tarjetas se envían sin su sonido, y el mensaje dice cuántas. Vuelve a añadir la
lección a Anki más tarde: se añaden los sonidos que faltan.

Consulta [La aplicación y AnkiDroid](../app-ankidroid/).

## Con tu ordenador

| Mensaje | Qué hacer |
|---|---|
| «💻 Tu ordenador no responde» | Anki debe estar abierto en el ordenador con el complemento, y el móvil en la misma wifi. **Reintentar**, o **Escanear de nuevo el código QR** si ha cambiado la dirección del ordenador. |

Consulta [Con tu ordenador](../app-with-computer/).

## Las tarjetas

**Las tarjetas están mal o faltan algunas.** Revisa la foto (consulta [Fotos y PDF](../photos/)),
precisa más las instrucciones, o corrígelas con la IA (consulta [Revisar las tarjetas](../review/)).

**Señálalo.** Una tarjeta que no está bien (una palabra mal leída, una respuesta incorrecta, una
figura torcida, una imagen inadecuada): **⋯ → ⚑ Denunciar** en ella, con unas palabras sobre lo
que esperabas. Leemos cada aviso, y así se corrigen esos errores. Consulta
[Señalar un problema](../review/#señalar-un-problema).

## No se puede añadir un PDF

- **«Ya hay 10 páginas: quita alguna antes de añadir un PDF.»** Una lección admite 10 páginas:
  quita las fotos que no necesites (el botón **Quitar esta página**, ✕, en cada una), o haz dos
  lecciones.
- **«… está protegido con contraseña: guárdalo sin contraseña y vuelve a añadirlo.»** Abre el PDF,
  guárdalo sin su contraseña (o imprímelo en un PDF nuevo), y vuelve a añadirlo.
- **Palabras mal leídas en un PDF**: un PDF escaneado solo contiene imágenes, leídas como fotos.
  Un PDF hecho en un ordenador da a la IA su texto exacto.
