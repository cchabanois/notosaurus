---
title: "Solucionar problemas del complemento"
description: "Qué hacer cuando el complemento no arranca, el móvil no se conecta, la IA falla o las tarjetas no llegan a Anki."
---

Los mensajes de abajo son los que muestra Notosaurus. Cuando algo va mal en el complemento,
**Herramientas → Notosaurus → Registro del servidor** muestra lo que ha pasado, y **Reiniciar el
servidor** a menudo lo arregla.

## Notosaurus no arranca

**«Notosaurus no se ha iniciado.»** Rechazaste la instalación de sus componentes en el primer
inicio. Para instalarlos: **Herramientas → Notosaurus → Abrir Notosaurus**.

**«No se ha podido descargar uv de GitHub»** o **«No se han podido instalar las dependencias de
Notosaurus».** El primer inicio descarga unos 300 MB: comprueba la conexión a Internet, y luego
**Herramientas → Notosaurus → Reiniciar el servidor**. El registro dice qué ha fallado.

**El servidor se detiene justo después de arrancar.** Puede que otro programa use el puerto 8000,
por ejemplo un Notosaurus arrancado en autónomo a la vez. Detenlo, o elige otro puerto en la
configuración del complemento (**Herramientas → Complementos → Notosaurus → Configuración**,
`port`), y reinicia Anki.

## El móvil no puede abrir Notosaurus

Consulta también [En el móvil](../phone/).

- El móvil y el ordenador deben estar en la **misma wifi**. Una red de «invitados» suele mantener
  separados sus dispositivos: usa la principal.
- En Windows, permite Anki (o Python) cuando el **cortafuegos** pregunte, la primera vez.
- Si ha cambiado la dirección del ordenador (tras reiniciar el router), **vuelve a escanear el
  código QR**: **Herramientas → Notosaurus → Abrir en el móvil…**.
- **«El servidor solo escucha en este ordenador»**: pon `host` a `0.0.0.0` en la configuración del
  complemento.
- **«Este dispositivo todavía no está autorizado»**: el móvil no ha escaneado el código QR, o se
  desconectaron todos los móviles. Vuelve a escanearlo.

## Los ajustes no se abren en el móvil

**«Los ajustes se abren desde Anki, en el ordenador.»** Es a propósito: en el complemento, los
ajustes (y las claves de API) solo son accesibles en el propio ordenador. Ábrelos con
**Herramientas → Notosaurus → Ajustes**.

## La IA falla

| Mensaje | Qué hacer |
|---|---|
| «Falta la clave» / «Clave de … no válida» | Vuelve a pegar la clave en **Ajustes → Acceso**, y luego **🔌 Probar**. |
| «… está saturado en este momento» | Frecuente con Gemini: vuelve a intentarlo dentro de un minuto. Los modelos de reserva toman el relevo automáticamente. |
| «Cuota de … alcanzada» | Se ha alcanzado el límite de una clave gratuita: espera, o activa la facturación. |
| «Respuesta cortada: demasiadas tarjetas a la vez» | Envía menos páginas a la vez, o pide menos tarjetas. |
| «El modelo no ha devuelto tarjetas válidas» | Vuelve a intentarlo; si sigue pasando, elige otro modelo. |
| El modelo «no parece ver la imagen» (Probar) | El modelo no lee imágenes: elige un modelo con visión. |

## Las tarjetas están mal o faltan algunas

Revisa la foto (consulta [Fotos y PDF](../photos/)), precisa más las instrucciones, o corrígelas
con la IA (consulta [Revisar las tarjetas](../review/)). Con letra manuscrita, Claude lee mejor:
consulta [Ajustes y servicios de IA](../ai-services/).

## No se puede añadir un PDF

- **«Ya hay 10 páginas: quita alguna antes de añadir un PDF.»** Una lección admite 10 páginas:
  quita las fotos que no necesites (el botón **Quitar esta página**, ✕, en cada una), o haz dos
  lecciones.
- **«… está protegido con contraseña: guárdalo sin contraseña y vuelve a añadirlo.»** Abre el PDF,
  guárdalo sin su contraseña (o imprímelo en un PDF nuevo), y vuelve a añadirlo.
- **Palabras mal leídas en un PDF**: un PDF escaneado solo contiene imágenes, leídas como fotos.
  Un PDF hecho en un ordenador da a la IA su texto exacto.

## Las tarjetas no llegan a Anki

- **«No se puede contactar con Anki»**: abre Anki en el ordenador. En autónomo, Anki necesita el
  complemento AnkiConnect.
- **«Ningún perfil abierto en Anki»**: abre el perfil del hijo, y vuelve a enviar.
- **Un aviso sobre otro perfil**: la lección es de otro hijo que el del perfil abierto en Anki.
  Abre el perfil correcto, o confirma.
- **Las tarjetas no llegan al móvil**: el mensaje dice «sin sincronización con AnkiWeb» cuando el
  perfil no tiene sesión iniciada en AnkiWeb. Haz clic una vez en **Sincronizar** en Anki para
  iniciar sesión, y vuelve a enviar. En el móvil, sincroniza AnkiDroid o AnkiMobile.
- **Tarjetas sin sonido**: el servicio de voz no ha respondido (necesita Internet). Vuelve a enviar
  la lección más tarde: se añade el audio que falta.

## ¿Sigue sin funcionar?

Informa del error en GitHub, con el [formulario Bug](https://github.com/cchabanois/notosaurus/issues/new?template=bug.yml) (hace falta una cuenta de GitHub,
gratuita). Pega las líneas de **Herramientas → Notosaurus → Registro del servidor** alrededor del
problema, y la versión (al final de la página de ajustes). La issue es pública: nunca la foto de un
cuaderno ni el nombre de un niño.

## Desinstalar el complemento

En Anki, **Herramientas → Complementos**, selecciona Notosaurus, **Eliminar**. Sus componentes y
**su carpeta de datos (lecciones, fotos, ajustes) se eliminan también**: copia antes la carpeta de
datos si quieres conservarlos (consulta
[Privacidad y seguridad en el ordenador](../privacy/#dónde-están-los-datos)). Las tarjetas ya
enviadas se quedan en Anki.
