// The photos of a lesson: added (a PDF's pages picked), turned, partly hidden, removed, seen in full.
// Methods of the page's Alpine component (app.js), as `this`.

// The pages shown beside the add buttons: two rows of the strip's columns (one is the buttons'),
// never fewer than four (a narrow phone's two columns: four pages, as when there were no more)
const STRIP_ROWS = 2;
const STRIP_PAGES = 4;
// The viewer's zoom: none at first, a tap's, the most two fingers give
const UNZOOMED = { scale: 1, x: 0, y: 0 };
const TAP_ZOOM = 2.5;
const MAX_ZOOM = 6;
// The fingers on the picture now, and the view as they first touched it
const pinching = { points: new Map(), from: null, moved: false };

// A view zoomed to `scale` so that the picture's point under `before` (on the screen) comes
// under `after`: a pinch's middle, or a tap's point both times. A view: the picture moved by
// (x, y) then scaled from its top left corner; `box` where it is laid out, unmoved.
function zoomedAbout(view, scale, before, after) {
  const s = Math.min(MAX_ZOOM, Math.max(1, scale));
  const px = (before.x - view.box.left - view.x) / view.scale;
  const py = (before.y - view.box.top - view.y) / view.scale;
  return { ...view, scale: s, x: after.x - view.box.left - s * px, y: after.y - view.box.top - s * py };
}

// The view moved back so that the picture never leaves the frame: smaller than the frame,
// centred in it; larger, its edges never inside it.
function keptOnScreen(view) {
  const { box, frame, scale } = view;
  const axis = (moved, start, size, frameStart, frameSize) => {
    const left = start + moved;  // where the picture starts on the screen
    const scaled = size * scale;
    if (scaled <= frameSize) return frameStart + (frameSize - scaled) / 2 - start;
    return Math.min(frameStart, Math.max(frameStart + frameSize - scaled, left)) - start;
  };
  return {
    scale,
    x: axis(view.x, box.left, box.width, frame.left, frame.width),
    y: axis(view.y, box.top, box.height, frame.top, frame.height),
  };
}

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
// pdf.js 6.4.299, its legacy build (older WebViews too), shipped with the page
// (vendor/pdfjs/README.md): a blocked CDN made PDFs unreadable
const PDFJS = "vendor/pdfjs/";  // next to the page
// A PDF opens in seconds: past this, said unreadable rather than "Reading…" forever (pdf.js
// failing inside its worker, on a browser missing what it needs, says nothing)
const PDF_OPEN_MS = 60_000;
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
  let timer;
  const late = new Promise((_, reject) => { timer = setTimeout(() => reject(new Error("pdf.timeout")), PDF_OPEN_MS); });
  try {
    return await Promise.race([pdfTask.promise, late]);
  } finally {
    clearTimeout(timer);
  }
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

// A text shared to the app (Android's "Share": copied from a site, written elsewhere): lesson
// pages, the text drawn on them and given with them as a PDF page's text is, its exact words
// (the AI makes the cards from it as from a page, never from the text as instructions).
const TEXT_PAGE = { width: 1240, height: 1754, margin: 90, font: 30, line: 44 };  // A4 at 150 dpi
const TEXT_PAGE_LINES = Math.floor((TEXT_PAGE.height - 2 * TEXT_PAGE.margin) / TEXT_PAGE.line);

// The text in lines that `fits` (a line's width on the page), its words never cut but one
// longer than a line; each line `end` when its paragraph ends there. Pure: drawn below.
function textLines(text, fits) {
  const lines = [];
  for (const paragraph of text.replace(/\r\n?/g, "\n").split("\n")) {
    let line = "";
    for (let word of paragraph.split(/\s+/).filter(Boolean)) {
      while (!fits(word)) {  // a word wider than a line (a link): cut where it fills one
        let cut = 1;
        while (cut < word.length && fits(word.slice(0, cut + 1))) cut++;
        if (line) lines.push({ text: line, end: false });
        lines.push({ text: word.slice(0, cut), end: false });
        line = "";
        word = word.slice(cut);
      }
      if (line && !fits(`${line} ${word}`)) {
        lines.push({ text: line, end: false });
        line = word;
      } else line = line ? `${line} ${word}` : word;
    }
    lines.push({ text: line, end: true });  // an empty paragraph: an empty line, as written
  }
  while (lines.length && !lines.at(-1).text) lines.pop();
  return lines;
}

// The lines in pages of `perPage`; each page's text, its paragraphs as the text had them.
function textPages(lines, perPage) {
  const pages = [];
  for (let i = 0; i < lines.length; i += perPage) {
    const page = lines.slice(i, i + perPage);
    const text = page.map((l) => l.text + (l.end ? "\n" : " ")).join("").replace(/ \n/g, "\n").trim();
    if (text) pages.push({ lines: page.map((l) => l.text), text });
  }
  return pages;
}

function drawTextPage(lines) {
  const { width, height, margin, font, line } = TEXT_PAGE;
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d");
  ctx.fillStyle = "#fff";
  ctx.fillRect(0, 0, width, height);
  ctx.fillStyle = "#111";
  ctx.font = `${font}px sans-serif`;
  ctx.textBaseline = "top";
  lines.forEach((text, i) => ctx.fillText(text, margin, margin + i * line));
  return canvasBlob(canvas);
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
    let left = 0;  // photos past the lesson's pages: not added, said
    for (const file of files) {
      if (isPdf(file)) {
        if (this.off("lesson.pdf")) this.error = t("errors.app.feature_off");  // (dropped: its tile hidden)
        else await this.addPdf(file);
        continue;
      }
      if (this.photos.length >= this.maxPhotos) {
        left++;
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
    if (left) this.error = t("app.photos.full", { max: this.maxPhotos, count: left });
  },

  // A text shared to the app: pages of the lesson (textLines), as many as there are places
  async addText(text) {
    const ctx = document.createElement("canvas").getContext("2d");
    ctx.font = `${TEXT_PAGE.font}px sans-serif`;
    const room = TEXT_PAGE.width - 2 * TEXT_PAGE.margin;
    const pages = textPages(textLines(text, (s) => ctx.measureText(s).width <= room), TEXT_PAGE_LINES);
    const free = Math.max(0, this.maxPhotos - this.photos.length);
    for (const page of pages.slice(0, free)) {
      const blob = drawTextPage(page.lines);
      this.photos.push({ blob, url: URL.createObjectURL(blob), text: page.text });
      this.photosEdited = Boolean(this.lessonId);
    }
    if (pages.length > free) this.error = t("app.photos.full", { max: this.maxPhotos, count: pages.length - free });
  },

  // What was shared to the app (Android's "Share": photos, PDFs, a text), kept by the host
  // until the page takes it. A lesson made and open: kept in My lessons, what was shared
  // starts a new one; a lesson not made yet (its photos, its prompt): added to it, nothing
  // of it lost. A host that has no sharing (the computer's): nothing.
  async takeShared() {
    let shared;
    try {
      shared = await (await api("/api/shared")).json();
    } catch {
      return;
    }
    const files = shared.files ?? [];
    const text = (shared.text ?? "").trim();
    const skipped = shared.skipped ?? [];
    const why = shared.error ?? "";  // a code: a web page's address alone (share.link_only)
    if (!files.length && !text && !skipped.length && !why) return;
    if (!files.length && !text) {  // nothing to add: the lesson as it is, said why
      if (why) this.error = t(`errors.${why}`);
      if (skipped.length) this.error = t("app.share.skipped", { names: skipped.join(", ") });
      api("/api/shared", { method: "DELETE" }).catch(() => {});
      return;
    }
    if (this.lessonId) await this.newLesson();
    const read = [];
    let unreadable = "";
    for (const file of files) {
      try {
        read.push(new File([await (await api(`/api/shared/${file.n}`)).blob()], file.name, { type: file.type }));
      } catch {
        unreadable = file.name;
      }
    }
    await this.addFiles(read);
    if (text) await this.addText(text);
    if (unreadable) this.error = t("app.photos.unreadable", { name: unreadable });
    if (why) this.error = t(`errors.${why}`);
    if (skipped.length) this.error = t("app.share.skipped", { names: skipped.join(", ") });
    api("/api/shared", { method: "DELETE" }).catch(() => {});
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

  // A quarter turn clockwise, when a photo (or the AI's guess) is sideways. A saved lesson's
  // photo, its photos as the server has them: the server turns it and its diagram masks.
  // Else just the photo here: one not sent yet, or the photos changed here (one removed,
  // another added: the server's photo at that number isn't this one), sent with them.
  async rotatePhoto(i) {
    this.error = "";
    try {
      if (!this.lessonId || this.photosEdited || !this.photos[i].sent) {
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
  // `card`: a card's picture, its credits shown under it (a figure's: what drew it).
  // `photos`: the lesson's photos, followed as they change (turned, a name hidden from it)
  openViewer(list, index, card = null, photos = false) {
    this.viewer = { open: true, list, index, touchX: 0, card, photos, ...UNZOOMED };
  },

  viewerList() {
    return this.viewer.photos ? this.photos.map((p) => p.url) : this.viewer.list;
  },

  moveViewer(step) {
    const n = this.viewerList().length;
    this.viewer.index = (this.viewer.index + step + n) % n;
    Object.assign(this.viewer, UNZOOMED);
  },

  swipeViewer(x) {
    const dx = x - this.viewer.touchX;
    if (this.viewer.scale > 1 || pinching.moved) return;  // zoomed in, or two fingers: never a page turned
    if (Math.abs(dx) > 50 && this.viewerList().length > 1) this.moveViewer(dx < 0 ? 1 : -1);
  },

  // Zoomed with two fingers about the point between them, then moved with one; a tap zooms
  // in where it touches, or back to the whole picture. The picture never leaves the screen.
  viewerDown(event) {
    try {
      event.target.setPointerCapture(event.pointerId);  // its moves followed past the picture's edge
    } catch {}  // a pointer the browser no longer knows (gone meanwhile): followed while on it
    pinching.points.set(event.pointerId, { x: event.clientX, y: event.clientY });
    if (pinching.points.size === 1) pinching.moved = false;
    pinching.from = { ...this.viewerView(), points: new Map(pinching.points) };
  },

  viewerMove(event) {
    if (!pinching.points.has(event.pointerId)) return;
    pinching.points.set(event.pointerId, { x: event.clientX, y: event.clientY });
    const [a, b] = [...pinching.from.points.values()];
    const [c, d] = [...pinching.points.values()];
    if (pinching.points.size >= 2 && b && d) {
      const scale = pinching.from.scale * Math.hypot(d.x - c.x, d.y - c.y) / Math.max(1, Math.hypot(b.x - a.x, b.y - a.y));
      const before = { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
      const after = { x: (c.x + d.x) / 2, y: (c.y + d.y) / 2 };
      this.setViewerView(zoomedAbout(pinching.from, scale, before, after));
      pinching.moved = true;
    } else if (this.viewer.scale > 1 && Math.hypot(c.x - a.x, c.y - a.y) > 4) {
      this.setViewerView({ ...pinching.from, x: pinching.from.x + c.x - a.x, y: pinching.from.y + c.y - a.y });
      pinching.moved = true;
    }
  },

  viewerUp(event) {
    pinching.points.delete(event.pointerId);
    pinching.from = { ...this.viewerView(), points: new Map(pinching.points) };
    if (!pinching.points.size && this.viewer.scale < 1.05) Object.assign(this.viewer, UNZOOMED);
  },

  viewerTap(event) {
    if (pinching.moved) return;  // the end of a pinch or of a move: no tap
    const scale = this.viewer.scale > 1 ? 1 : TAP_ZOOM;
    const at = { x: event.clientX, y: event.clientY };
    this.setViewerView(scale === 1 ? { ...UNZOOMED } : zoomedAbout(this.viewerView(), scale, at, at));
  },

  // A picture shown anew (another page, the photo turned, a name hidden from it): seen whole,
  // the zoom of the one before meaningless on it
  unzoomViewer() {
    Object.assign(this.viewer, UNZOOMED);
  },

  viewerView() {
    const frame = document.querySelector(".viewer-frame").getBoundingClientRect();
    const img = document.querySelector(".viewer-frame img");
    // The picture's own place in the frame, as laid out (a transform moves none of it)
    const box = { left: frame.left + img.offsetLeft, top: frame.top + img.offsetTop, width: img.offsetWidth, height: img.offsetHeight };
    return { scale: this.viewer.scale, x: this.viewer.x, y: this.viewer.y, box, frame };
  },

  setViewerView(view) {
    const { scale, x, y } = view.box ? keptOnScreen(view) : view;
    Object.assign(this.viewer, { scale, x, y });
  },

  removePhoto(i) {
    URL.revokeObjectURL(this.photos[i].url);
    this.photos.splice(i, 1);
    this.photosEdited = Boolean(this.lessonId);
    if (!this.photos.length) this.allPages = false;
  },

  // The page shown in the viewer removed: the next one shown (the one before, the last
  // removed); none left, the viewer closed
  removeShownPhoto() {
    this.removePhoto(this.viewer.index);
    if (!this.photos.length) {
      this.viewer.open = false;
      return;
    }
    this.viewer.index = Math.min(this.viewer.index, this.photos.length - 1);
    this.unzoomViewer();
  },

  // --- The strip: the pages beside the add buttons -----------------------
  // Its columns counted as its width changes (a phone turned, a window widened)
  watchStrip(strip) {
    const count = () => {
      const columns = getComputedStyle(strip).gridTemplateColumns.split(" ").filter(Boolean).length;
      if (columns && columns !== this.stripColumns) this.stripColumns = columns;
    };
    count();
    new ResizeObserver(count).observe(strip);
  },

  // How many pages the strip holds: its two rows beside the buttons
  stripCapacity() {
    return Math.max(STRIP_PAGES, STRIP_ROWS * (this.stripColumns - 1));
  },

  // The pages shown on it: all of them, or the last place left to "+N" (that page veiled,
  // N the pages it stands for, itself with them, as messaging apps do)
  stripShown() {
    const capacity = this.stripCapacity();
    return this.photos.length > capacity ? capacity - 1 : this.photos.length;
  },
};
