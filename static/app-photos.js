// The photos of a lesson: added (a PDF's pages picked), turned, partly hidden, removed, seen in full.
// Methods of the page's Alpine component (app.js), as `this`.

// A canvas as a file (JPEG, or a PNG mask). Not canvas.toBlob: in Android's WebView it
// waits for idle time, 4 to 13 s for a photo; toDataURL does the same in ~0.2 s.
function canvasBlob(canvas, type = "image/jpeg") {
  const data = atob(canvas.toDataURL(type, JPEG_QUALITY).split(",")[1]);
  const bytes = new Uint8Array(data.length);
  for (let i = 0; i < data.length; i++) bytes[i] = data.charCodeAt(i);
  return new Blob([bytes], { type });
}

// Shrinks a phone photo (3–5 MB) to ~1600 px JPEG before upload.
async function resize(file) {
  const bitmap = await createImageBitmap(file, { imageOrientation: "from-image" });
  const scale = Math.min(1, MAX_SIDE / Math.max(bitmap.width, bitmap.height));
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(bitmap.width * scale);
  canvas.height = Math.round(bitmap.height * scale);
  canvas.getContext("2d").drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  bitmap.close();
  return canvasBlob(canvas);
}

// A photo turned a quarter turn clockwise (JPEG; a hidden areas' mask: PNG).
async function rotateBlob(blob, type = "image/jpeg") {
  const bitmap = await createImageBitmap(blob);
  const canvas = document.createElement("canvas");
  canvas.width = bitmap.height;
  canvas.height = bitmap.width;
  const ctx = canvas.getContext("2d");
  ctx.translate(canvas.width, 0);
  ctx.rotate(Math.PI / 2);
  ctx.drawImage(bitmap, 0, 0);
  bitmap.close();
  return canvasBlob(canvas, type);
}

// Hiding part of a photo before it is sent (a name, a school…): blacked out with a finger,
// un-blacked the same way. The photo keeps its original and the mask of what is hidden, so
// it can be changed until it is sent; only the blacked-out photo goes to the server.
const HIDE_BRUSH = 0.035;  // the brush's width, of the photo's longer side
let hideEdit = null;  // { bitmap, mask, canvas, last }: the editor's canvases (out of Alpine's proxies)

// The mask made sharp (a stroke's soft edges, an un-blacked one's faint outline: black or
// nothing); whether anything is hidden.
function hardenMask(mask) {
  const ctx = mask.getContext("2d");
  const image = ctx.getImageData(0, 0, mask.width, mask.height);
  let used = false;
  for (let i = 3; i < image.data.length; i += 4) {
    image.data[i] = image.data[i] >= 128 ? 255 : 0;
    used ||= image.data[i] > 0;
  }
  ctx.putImageData(image, 0, 0);
  return used;
}

// PDFs: each page drawn as a photo (pdf.js, loaded the first time a PDF is chosen),
// so masks, frames, thumbnails and every AI service work the same as with photos.
// pdf.js 6.4.299, shipped with the page (vendor/pdfjs/README.md): a blocked CDN made PDFs unreadable
const PDFJS = "vendor/pdfjs/";  // next to the page
const PDF_THUMB = 240;  // px: the page picker's thumbnails
let pdfjs = null;
let pdfTask = null;  // loading it (destroyed when done: frees the worker's memory)
let openPdf = null;  // the PDF being picked from (pdf.js objects stay out of Alpine's proxies)
let pdfPicked = null;  // resolves when its pages are picked (or not)

const isPdf = (file) => file.type === "application/pdf" || /\.pdf$/i.test(file.name);

async function loadPdf(file) {
  if (!pdfjs) {
    const base = new URL(PDFJS, document.baseURI).href;
    pdfjs = await import(`${base}pdf.min.mjs`);
    pdfjs.GlobalWorkerOptions.workerSrc = `${base}pdf.worker.min.mjs`;
  }
  pdfTask = pdfjs.getDocument({ data: new Uint8Array(await file.arrayBuffer()) });
  return pdfTask.promise;
}

// A page as a JPEG at most `side` px, on white (a PDF page may be transparent).
async function renderPdfPage(doc, n, side = MAX_SIDE) {
  const page = await doc.getPage(n);
  const base = page.getViewport({ scale: 1 });
  const viewport = page.getViewport({ scale: side / Math.max(base.width, base.height) });
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(viewport.width);
  canvas.height = Math.round(viewport.height);
  await page.render({ canvas, viewport, background: "white" }).promise;
  page.cleanup();
  return canvasBlob(canvas);
}

// A page's text, as the PDF holds it (none in a scan): sent to the AI with the page,
// for the exact words. Lines kept; spaces trimmed.
async function pdfPageText(doc, n) {
  const page = await doc.getPage(n);
  const content = await page.getTextContent();
  page.cleanup();
  return content.items
    .map((item) => (item.str ?? "") + (item.hasEOL ? "\n" : ""))
    .join("")
    .replace(/[ \t]+/g, " ")
    .replace(/ *\n */g, "\n")
    .trim();
}

const photosPart = {
  // --- Photos ---------------------------------------------------------
  async addPhotos(event) {
    await this.addFiles([...event.target.files]);
    event.target.value = "";  // allows picking the same photo again
  },

  // Photos or PDFs dragged from the computer onto "Gallery" or "PDF": each goes where its
  // type says (a PDF dropped on "Gallery" is read as a PDF all the same)
  dragOver(event, tile) {
    if (!event.dataTransfer?.types?.includes("Files") || this.readOnly()) return;
    event.preventDefault();
    event.dataTransfer.dropEffect = "copy";
    this.dropTile = tile;
  },

  // A file let go anywhere else: not opened by the browser (the page and its lesson would go)
  ignoreDrop(event) {
    if (!event.dataTransfer?.types?.includes("Files")) return;  // text dragged into a field: as usual
    event.preventDefault();
    if (event.type === "drop") this.dropTile = "";
  },

  async dropFiles(event) {
    this.dropTile = "";
    if (!event.dataTransfer?.files?.length || this.readOnly()) return;
    event.preventDefault();
    await this.addFiles([...event.dataTransfer.files]);
  },

  async addFiles(files) {
    this.error = "";
    for (const file of files) {
      if (isPdf(file)) {
        await this.addPdf(file);
        continue;
      }
      try {
        const blob = await resize(file);
        this.photos.push({ blob, url: URL.createObjectURL(blob) });
        this.photosEdited = Boolean(this.lessonId);
      } catch {
        this.error = t("app.photos.unreadable", { name: file.name });
      }
    }
  },

  // A PDF: its pages as photos. More pages than places left: the user picks them
  // (never cut silently).
  async addPdf(file) {
    const free = this.maxPhotos - this.photos.length;
    if (free <= 0) {
      this.error = t("app.pdf.full", { max: this.maxPhotos });
      return;
    }
    this.pdfBusy = true;
    try {
      openPdf = await loadPdf(file);
      const count = openPdf.numPages;
      let chosen = Array.from({ length: count }, (_, i) => i + 1);
      if (count > free) chosen = await this.pickPdfPages(file.name, count, free);
      for (const n of chosen) {
        const blob = await renderPdfPage(openPdf, n);
        const text = await pdfPageText(openPdf, n).catch(() => "");
        this.photos.push({ blob, url: URL.createObjectURL(blob), text });
        this.photosEdited = Boolean(this.lessonId);
      }
    } catch (e) {
      this.error = t(e?.name === "PasswordException" ? "app.pdf.protected" : "app.photos.unreadable", { name: file.name });
    } finally {
      this.pdfBusy = false;
      this.closePdfPicker();
      await pdfTask?.destroy();
      pdfTask = openPdf = null;
    }
  },

  // The page picker: every page's thumbnail, drawn one after the other; at most `free`.
  pickPdfPages(name, count, free) {
    this.pdf = { open: true, name, free, pages: Array.from({ length: count }, (_, i) => ({ n: i + 1, url: "", chosen: false })) };
    (async () => {
      for (const page of this.pdf.pages) {
        if (!this.pdf.open || !openPdf) return;
        try {
          page.url = URL.createObjectURL(await renderPdfPage(openPdf, page.n, PDF_THUMB));
        } catch {
          return;  // closed meanwhile
        }
      }
    })();
    return new Promise((resolve) => { pdfPicked = resolve; });
  },

  pdfChosen() {
    return this.pdf.pages.filter((p) => p.chosen).map((p) => p.n);
  },

  // "Add" (the pages chosen) or closed (none)
  donePdfPicker(add) {
    pdfPicked?.(add ? this.pdfChosen() : []);
    pdfPicked = null;
    this.closePdfPicker();
  },

  closePdfPicker() {
    this.pdf.pages.forEach((p) => p.url && URL.revokeObjectURL(p.url));
    this.pdf = { open: false, name: "", free: 0, pages: [] };
  },

  // A quarter turn clockwise, when a photo (or the AI's guess) is sideways. In a saved
  // lesson the server turns the photo and its diagram masks; before, just the photo here.
  async rotatePhoto(i) {
    this.error = "";
    try {
      if (!this.lessonId) {
        const photo = this.photos[i];
        const turned = { ...photo, blob: await rotateBlob(photo.blob) };  // its text kept
        if (photo.original) {  // what it hides turns with it
          turned.original = await rotateBlob(photo.original);
          turned.mask = await rotateBlob(photo.mask, "image/png");
        }
        URL.revokeObjectURL(photo.url);
        this.photos.splice(i, 1, { ...turned, url: URL.createObjectURL(turned.blob) });
        return;
      }
      if (this.saveTimer) await this.saveNow();
      const lesson = await (await api(`/api/lessons/${this.lessonId}/photos/${i + 1}/rotate`, { method: "POST" })).json();
      await this.loadPhotos(lesson);
      lesson.cards.forEach((card, n) => { if (this.cards[n]) this.cards[n].mask = card.mask; });
      this.frames = lesson.frames ?? [];
      this.lastSaved = this.snapshot();  // already saved by the server
    } catch (e) {
      this.error = e.message;
    }
  },

  // --- Hiding part of a photo, before it is sent -------------------------
  async openHide(i) {
    const photo = this.photos[i];
    const bitmap = await createImageBitmap(photo.original ?? photo.blob);
    const mask = document.createElement("canvas");
    mask.width = bitmap.width;
    mask.height = bitmap.height;
    if (photo.mask) {
      const hidden = await createImageBitmap(photo.mask);
      mask.getContext("2d").drawImage(hidden, 0, 0);
      hidden.close();
    }
    this.hiding = { open: true, index: i, erase: false, pdf: Boolean(photo.pdfText ?? photo.text) };
    await this.$nextTick();
    const canvas = this.$refs.hideCanvas;
    canvas.width = bitmap.width;
    canvas.height = bitmap.height;
    hideEdit = { bitmap, mask, canvas, last: null };
    this.drawHidden();
  },

  drawHidden() {
    const { bitmap, mask, canvas } = hideEdit;
    const ctx = canvas.getContext("2d");
    ctx.drawImage(bitmap, 0, 0);
    ctx.drawImage(mask, 0, 0);
  },

  // The finger (or the mouse) down, moved, up: a stroke on the mask
  hideStroke(event) {
    if (!hideEdit) return;
    if (event.type === "pointerdown") {
      event.target.setPointerCapture(event.pointerId);
      hideEdit.last = null;
    } else if (event.type === "pointermove") {
      if (!hideEdit.last) return;  // not pressed
    } else {
      hideEdit.last = null;  // up, or cancelled
      return;
    }
    const { canvas, mask } = hideEdit;
    const box = canvas.getBoundingClientRect();
    const point = [(event.clientX - box.left) * (canvas.width / box.width), (event.clientY - box.top) * (canvas.height / box.height)];
    const from = hideEdit.last ?? point;
    const ctx = mask.getContext("2d");
    ctx.globalCompositeOperation = this.hiding.erase ? "destination-out" : "source-over";
    ctx.strokeStyle = "#000";
    ctx.lineCap = ctx.lineJoin = "round";
    ctx.lineWidth = Math.max(mask.width, mask.height) * HIDE_BRUSH * (this.hiding.erase ? 1.25 : 1);  // un-blacked: no outline left
    ctx.beginPath();
    ctx.moveTo(...from);
    ctx.lineTo(point[0] + 0.01, point[1]);  // a tap leaves a dot
    ctx.stroke();
    hideEdit.last = point;
    this.drawHidden();
  },

  clearHidden() {
    const { mask } = hideEdit;
    mask.getContext("2d").clearRect(0, 0, mask.width, mask.height);
    this.drawHidden();
  },

  // "Done": the photo as it will be sent (its original and mask kept, to change it again);
  // nothing hidden: the original back. A PDF page's text holds what is hidden too: not sent then.
  async doneHide(keep) {
    const { bitmap, mask, canvas } = hideEdit;
    const i = this.hiding.index;
    const photo = this.photos[i];
    try {
      if (keep) {
        const original = photo.original ?? photo.blob;
        const pdfText = photo.pdfText ?? photo.text;
        const used = hardenMask(mask);
        this.drawHidden();
        const changed = used
          ? { blob: canvasBlob(canvas), original, mask: canvasBlob(mask, "image/png"), text: "", pdfText }
          : { blob: original, text: pdfText };
        URL.revokeObjectURL(photo.url);
        this.photos.splice(i, 1, { ...changed, url: URL.createObjectURL(changed.blob) });
        this.photosEdited = Boolean(this.lessonId);
      }
    } finally {
      bitmap.close();
      hideEdit = null;
      this.hiding = { open: false, index: -1, erase: false, pdf: false };
    }
  },

  // --- Viewer: a photo (or a card's picture) in full ---------------------
  openViewer(list, index) {
    this.viewer = { open: true, list, index, zoomed: false, touchX: 0 };
  },

  moveViewer(step) {
    const n = this.viewer.list.length;
    this.viewer.index = (this.viewer.index + step + n) % n;
    this.viewer.zoomed = false;
  },

  swipeViewer(x) {
    const dx = x - this.viewer.touchX;
    if (Math.abs(dx) > 50 && this.viewer.list.length > 1) this.moveViewer(dx < 0 ? 1 : -1);
  },

  removePhoto(i) {
    URL.revokeObjectURL(this.photos[i].url);
    this.photos.splice(i, 1);
    this.photosEdited = Boolean(this.lessonId);
  },
};
