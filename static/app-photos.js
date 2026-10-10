// The photos of a lesson: added (a PDF's pages picked), turned, removed, seen in full.
// Methods of the page's Alpine component (app.js), as `this`.

// Shrinks a phone photo (3–5 MB) to ~1600 px JPEG before upload.
async function resize(file) {
  const bitmap = await createImageBitmap(file, { imageOrientation: "from-image" });
  const scale = Math.min(1, MAX_SIDE / Math.max(bitmap.width, bitmap.height));
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(bitmap.width * scale);
  canvas.height = Math.round(bitmap.height * scale);
  canvas.getContext("2d").drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  bitmap.close();
  return new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", JPEG_QUALITY));
}

// A photo turned a quarter turn clockwise (JPEG).
async function rotateBlob(blob) {
  const bitmap = await createImageBitmap(blob);
  const canvas = document.createElement("canvas");
  canvas.width = bitmap.height;
  canvas.height = bitmap.width;
  const ctx = canvas.getContext("2d");
  ctx.translate(canvas.width, 0);
  ctx.rotate(Math.PI / 2);
  ctx.drawImage(bitmap, 0, 0);
  bitmap.close();
  return new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", JPEG_QUALITY));
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
  return new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", JPEG_QUALITY));
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
        const blob = await rotateBlob(this.photos[i].blob);
        URL.revokeObjectURL(this.photos[i].url);
        this.photos.splice(i, 1, { ...this.photos[i], blob, url: URL.createObjectURL(blob) });  // its text kept
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
