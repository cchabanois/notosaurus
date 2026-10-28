---
title: "Enviar a Anki en el ordenador"
description: "Desde el complemento o en autónomo: enviar las tarjetas directamente a Anki en el ordenador o descargar un archivo .apkg, y hacer llegar las tarjetas al móvil."
---

Con el complemento (o en autónomo), una vez revisadas, las tarjetas van a Anki en el ordenador con
un toque, o como archivo. En la aplicación Android, van directas a AnkiDroid: consulta
[La aplicación y AnkiDroid](../app-ankidroid/).

## Añadir a Anki

**📥 Añadir a Anki** escribe las tarjetas directamente en el **perfil abierto en Anki**, en el mazo
de la lección, con su audio y sus imágenes. Un mensaje dice lo que se ha hecho, por ejemplo «✓ En
Anki: 9 tarjetas añadidas. Sincronizado con AnkiWeb.» Si las imágenes y figuras aún se están
dibujando, el botón las espera y dice cuántas están listas («⏳ Imágenes y figuras: 2 / 5
listas…»).

![Las tarjetas enviadas a Anki](../../../assets/screenshots/en/sent.png)

- Con el **complemento**, Notosaurus escribe en Anki él mismo: no hay nada más que instalar.
- Notosaurus **en autónomo** (sin el complemento) necesita Anki abierto en el ordenador con el
  complemento [AnkiConnect](https://ankiweb.net/shared/info/2055492159).
- Si la lección es de otro hijo que el del perfil abierto en Anki, Notosaurus pregunta antes de
  escribirla en la colección equivocada (consulta [Varios hijos](../several-children/)).

## Enviar una lección de nuevo

Una vez enviada la lección, y mientras nada cambie, el botón dice **✓ Al día en Anki** (aun así
vuelve a enviar la lección si hace falta). En cuanto algo de lo que recibe Anki cambia (una
tarjeta, su imagen, el mazo, la voz, las opciones), pasa a **🔄 Actualizar en Anki**: una lección
corregida y enviada de nuevo actualiza sus tarjetas en Anki, con el historial, en vez de
duplicarlas. Consulta [Las tarjetas en Anki](../cards-in-anki/).

## El archivo .apkg

**⬇️ .apkg** descarga el mazo como archivo, con su audio y sus imágenes, sin necesidad de tener
Anki abierto:

- **en un ordenador**, haz doble clic en él: Anki lo importa;
- **en Android**, abre el archivo descargado y elige **AnkiDroid**. Si no aparece AnkiDroid,
  comparte el archivo con AnkiDroid, o usa **Importar** en el menú de AnkiDroid;
- **en un iPhone**, ábrelo con **AnkiMobile** desde el menú de compartir.

Importar un `.apkg` más reciente de la misma lección también actualiza sus tarjetas en vez de
duplicarlas.

Con el **complemento Notosaurus**, una lección enviada con **📥 Añadir a Anki** y su `.apkg` hacen
las mismas tarjetas: puedes mezclar las dos cosas, en el ordenador y en el móvil. Con
**AnkiConnect**, elige una sola vía por perfil de Anki: un `.apkg` importado donde la lección ya se
envió directamente (o en un perfil sincronizado con él) añadiría cada tarjeta una segunda vez.

## Hacer llegar las tarjetas al móvil

Tras **Añadir a Anki**, Notosaurus **sincroniza el perfil con AnkiWeb** (la opción **Sincronizar
con AnkiWeb después del envío**, en los ajustes). Las tarjetas llegan entonces a AnkiDroid o
AnkiMobile en su próxima sincronización. Si el perfil no tiene sesión iniciada en AnkiWeb, las
tarjetas se añaden a Anki en el ordenador, y el mensaje dice que no se ha sincronizado.

Sin cuenta de AnkiWeb, el archivo `.apkg` abierto en el móvil pone el mazo directamente en
AnkiDroid, pero los repasos se quedan entonces solo en ese móvil.
