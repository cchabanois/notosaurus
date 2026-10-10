// The cards of the open lesson: corrected by the AI, edited, their diagram labels, formulas and pictures.
// Methods of the page's Alpine component (app.js), as `this`.

const cardsPart = {
  // --- AI correction --------------------------------------------------
  async revise() {
    const instruction = this.revision.text.trim();
    if (!instruction || this.revision.busy || !this.lessonId || this.readOnly()) return;
    this.error = "";
    this.revision.busy = true;
    const before = { deck: this.deck, cards: this.cards.map((c) => ({ ...c, _state: undefined })) };
    try {
      const res = await (await api(`/api/lessons/${this.lessonId}/revise`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...this.payload(), instruction }),
      })).json();
      const { cards, stats } = this.compareCards(before.cards, res.lesson.cards);
      clearTimeout(this.saveTimer);
      this.saveTimer = null;
      this.deck = res.lesson.deck;
      this.cards = cards;
      this.lastSaved = this.snapshot();  // the server already saved the revision
      this.saveState = "saved";
      this.revision = { text: "", busy: false, summary: res.summary, stats, undo: before };
      this.loadLessons();
      this.drawPictures();  // a card added by the correction may ask for one
    } catch (e) {
      this.error = e.message;
      this.revision.busy = false;
    }
  },

  // Keep the keys of unchanged cards and flag new or modified ones.
  compareCards(oldCards, newCards) {
    const same = (a, b) => ["front", "back", "info", "subdeck"].every((f) => (a[f] ?? "") === (b[f] ?? ""));
    const unused = [...oldCards];
    let added = 0, modified = 0;
    const cards = newCards.map((card) => {
      const exact = unused.findIndex((o) => same(o, card));
      if (exact !== -1) return { ...card, key: unused.splice(exact, 1)[0].key };
      const sameFront = unused.findIndex((o) => o.front === card.front);
      if (sameFront !== -1) {
        modified++;
        return { ...withKey(card), key: unused.splice(sameFront, 1)[0].key, _state: "modified" };
      }
      added++;
      return { ...withKey(card), _state: "new" };
    });
    const parts = [];
    if (added) parts.push(t("app.revise.added", { count: added }));
    if (modified) parts.push(t("app.revise.modified", { count: modified }));
    if (unused.length) parts.push(t("app.revise.removed", { count: unused.length }));
    return { cards, stats: parts.join(" · ") || t("app.revise.noChange") };
  },

  // The lesson as it was, for "Undo" after a regeneration (a correction only needs
  // the deck and cards)
  undoState() {
    return {
      deck: this.deck,
      cards: this.cards.map((c) => ({ ...c, _state: undefined })),
      frames: this.frames,
      lessonPrompt: this.lessonPrompt,
      lessonChoice: this.lessonChoice,
      voice: this.voice,
      reverse: this.reverse,
      typing: this.typing,
      dictation: this.dictation,
    };
  },

  undoRevision() {
    const { deck, cards, voice, ...rest } = this.revision.undo;
    this.deck = deck;
    this.cards = cards;  // autosave sends the restored version
    if (voice !== undefined) this.voice = voice;
    Object.assign(this, rest);  // after a regeneration: frames, prompt, options
    this.revision = { text: "", busy: false, summary: t("app.revise.undone"), stats: "", undo: null };
  },

  clearRevision() {
    this.cards.forEach((c) => { c._state = undefined; });
    this.revision = { ...this.revision, summary: "", stats: "", undo: null };
  },

  // --- Review ---------------------------------------------------------
  // Photos + prompt, or the prompt alone (see "Generate from the prompt alone")
  sheetOpen() {
    return this.lessonsOpen || this.pdf.open || this.picker.open || this.editor.open || this.removal.open;
  },

  canGenerate() {
    return this.form.text.trim() !== "" && !this.loading && !this.dictating("prompt") && !this.tidy.busy;
  },

  bottomBar() {
    return !this.unpaired;  // always visible: it is the main call to action
  },

  removeCard(card) {
    this.cards = this.cards.filter((c) => c !== card);
  },

  // --- Diagram labels (masks on a photo) ---------------------------------
  photoFor(card) {
    return this.photos[card.mask.page - 1]?.url ?? null;
  },

  hasMasks() {
    return this.cards.some((c) => c.mask);
  },

  // Every mask on the same photo: all of them are hidden on the card's image.
  masksOnPage(card) {
    return this.cards.filter((c) => c.mask && c.mask.page === card.mask.page);
  },

  // What Anki shows of the photo: the diagram's frame stretched to hold every mask
  // with a margin, so it never cuts a label (same as diagrams.crop on the server).
  // No frame: the whole photo.
  cropFor(card) {
    const frame = this.frames.find((f) => f.page === card.mask.page);
    if (!frame) return { box: [0, 0, 1, 1] };
    const m = 0.03;
    const masks = this.masksOnPage(card).map(({ mask: { box: b } }) => [b[0] - m, b[1] - m, b[2] + m, b[3] + m]);
    const boxes = [frame.box, ...masks];
    const clamp = (v) => Math.min(1, Math.max(0, v));
    return {
      box: [
        clamp(Math.min(...boxes.map((b) => b[0]))), clamp(Math.min(...boxes.map((b) => b[1]))),
        clamp(Math.max(...boxes.map((b) => b[2]))), clamp(Math.max(...boxes.map((b) => b[3]))),
      ],
    };
  },

  // Drag a corner of the frame ("nw", "ne", "sw", "se"). It starts from what is shown,
  // and can't go inside the masks: the crop stretches back to hold them.
  startCrop(event, card, corner) {
    if (this.readOnly()) return;
    event.preventDefault();
    const rect = event.currentTarget.closest(".diagram").getBoundingClientRect();
    let frame = this.frames.find((f) => f.page === card.mask.page);
    if (!frame) {
      frame = { page: card.mask.page, box: [0, 0, 1, 1] };
      this.frames.push(frame);
    }
    frame.box = [...this.cropFor(card).box];
    const start = { x: event.clientX, y: event.clientY, box: [...frame.box] };
    const clamp = (v, min, max) => Math.min(max, Math.max(min, v));
    const move = (e) => {
      const dx = (e.clientX - start.x) / rect.width;
      const dy = (e.clientY - start.y) / rect.height;
      let [x0, y0, x1, y1] = start.box;
      if (corner.includes("w")) x0 = clamp(x0 + dx, 0, x1 - 0.05);
      if (corner.includes("e")) x1 = clamp(x1 + dx, x0 + 0.05, 1);
      if (corner.includes("n")) y0 = clamp(y0 + dy, 0, y1 - 0.05);
      if (corner.includes("s")) y1 = clamp(y1 + dy, y0 + 0.05, 1);
      frame.box = [x0, y0, x1, y1].map((v) => Math.round(v * 10000) / 10000);
    };
    const stop = () => {
      frame.box = [...this.cropFor(card).box];  // what is shown: pushed inside a mask, it stops there
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", stop);
      window.removeEventListener("pointercancel", stop);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", stop);
    window.addEventListener("pointercancel", stop);
  },

  maskStyle(mask) {
    const [x0, y0, x1, y1] = mask.box.map((v) => v * 100);
    return `left: ${x0}%; top: ${y0}%; width: ${x1 - x0}%; height: ${y1 - y0}%`;
  },

  // Drag the mask (mode "move") or its corner ("resize"), with a finger or a mouse.
  // Boxes are fractions of the photo, like on the server.
  startDrag(event, card, mode) {
    if (this.readOnly()) return;
    event.preventDefault();
    const frame = event.currentTarget.closest(".diagram").getBoundingClientRect();
    const start = { x: event.clientX, y: event.clientY, box: [...card.mask.box] };
    const clamp = (v, min, max) => Math.min(max, Math.max(min, v));
    const move = (e) => {
      const dx = (e.clientX - start.x) / frame.width;
      const dy = (e.clientY - start.y) / frame.height;
      let [x0, y0, x1, y1] = start.box;
      if (mode === "move") {
        const [w, h] = [x1 - x0, y1 - y0];
        x0 = clamp(x0 + dx, 0, 1 - w);
        y0 = clamp(y0 + dy, 0, 1 - h);
        [x1, y1] = [x0 + w, y0 + h];
      } else {
        x1 = clamp(x1 + dx, x0 + 0.02, 1);
        y1 = clamp(y1 + dy, y0 + 0.02, 1);
      }
      card.mask.box = [x0, y0, x1, y1].map((v) => Math.round(v * 10000) / 10000);
    };
    const stop = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", stop);
      window.removeEventListener("pointercancel", stop);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", stop);
    window.addEventListener("pointercancel", stop);
  },

  subdecks() {
    return [...new Set(this.cards.map((c) => c.subdeck).filter(Boolean))];
  },

  addCard() {
    const last = this.cards.at(-1);
    this.cards.push(withKey({ id: newId(), front: "", back: "", subdeck: last?.subdeck ?? "" }));
  },

  // --- Formulas --------------------------------------------------------
  hasMath(text) {
    return HAS_MATH.test(text ?? "");
  },

  // A front, a back, an info grow with their text (a sentence with gaps is long). CSS does it where
  // `field-sizing` is known; elsewhere, its height follows the text it holds, and
  // is measured again when it shows or its width changes.
  watchHeight(el) {
    if (!CSS.supports("field-sizing", "content")) new ResizeObserver(() => this.fitHeight(el)).observe(el);
  },
  fitHeight(el) {
    if (CSS.supports("field-sizing", "content") || !el.offsetParent) return; // hidden: no height to measure
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
  },

  isCloze(text) {
    return CLOZE.test(text ?? "");
  },

  // The text as Anki will show it: formulas drawn (KaTeX), gaps marked with their
  // number (each number is a card), line breaks kept, the rest escaped.
  previewHtml(text) {
    text = text ?? "";
    const plain = (t) =>
      escapeHtml(t)
        .replace(GAP_START, (_, n) => `<span class="gap"><sup>${n}</sup>`)
        .replace(GAP_END, "</span>")
        .replaceAll("\n", "<br>");
    if (!this.katexReady) return plain(text);
    let html = "", last = 0;
    for (const m of text.matchAll(MATH)) {
      html += plain(text.slice(last, m.index));
      const display = m[2] !== undefined;
      html += katex.renderToString(m[1] ?? m[2], { displayMode: display, throwOnError: false });
      last = m.index + m[0].length;
    }
    return html + plain(text.slice(last));
  },

  // --- Pictures ("front: the picture of the word") ------------------------
  pictureUrl(card) {
    return `/api/lessons/${this.lessonId}/pictures/${card.picture}`;
  },

  // A card's picture panel: what to draw (the AI's subject, else the answer), redraw,
  // the user's own photo, or no picture.
  togglePicturePanel(card) {
    card._panel = !card._panel;
    if (card._panel) card._subject = card.figure || card.picture_prompt || card.back;
  },

  async pictureAction(card, request) {
    if (this.saveTimer) await this.saveNow();  // the server must know the card
    card._drawing = true;
    this.pictureJobs++;
    this.error = "";
    try {
      const res = await (await api(`/api/lessons/${this.lessonId}/cards/${card.id}/picture${request.path ?? ""}`, request)).json();
      card.picture = res.card.picture;
      card.picture_source = res.card.picture_source ?? null;
      card.picture_prompt = res.card.picture_prompt;
      card.figure = res.card.figure;
      if (!card.picture) card._panel = false;
    } catch (e) {
      this.error = e.message;
    } finally {
      card._drawing = false;
      this.pictureJobs--;
    }
  },

  redrawPicture(card) {
    return this.pictureAction(card, {
      path: "/draw",
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ subject: card._subject ?? null }),
    });
  },

  async uploadPicture(card, event) {
    const file = event.target.files[0];
    event.target.value = "";
    if (!file) return;
    const body = new FormData();
    body.append("photo", await resize(file), "photo.jpg");
    return this.pictureAction(card, { method: "POST", body });
  },

  // "🔎 Find a picture": free pictures of the subject to choose from (previews come as data)
  async searchPictures(card) {
    const subject = card._subject?.trim();
    if (!subject || card._searching) return;
    card._searching = true;
    card._found = null;
    this.error = "";
    try {
      const res = await api("/api/pictures/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ subject }),
      });
      card._found = (await res.json()).results;
    } catch (e) {
      this.error = e.message;
    } finally {
      card._searching = false;
    }
  },

  // Where the card's picture comes from, said in its panel ("" when it isn't known)
  pictureSourceText(card) {
    const origin = card.picture_source;
    if (!origin) return "";
    if (origin.source === "photo") return t("app.pictures.sourcePhoto");
    if (origin.source === "drawn") return origin.model ? t("app.pictures.sourceDrawnBy", { model: origin.model }) : t("app.pictures.sourceDrawn");
    const names = { commons: "Wikimedia Commons", openverse: "Openverse", pixabay: "Pixabay" };
    return t("app.pictures.sourceFound", { source: names[origin.source] ?? origin.source, licence: origin.licence });
  },

  // The sources of the pictures found, as their credit line says them
  foundSources(card) {
    const names = { commons: "Wikimedia Commons", openverse: "Openverse", pixabay: "Pixabay" };
    return [...new Set((card._found ?? []).map((f) => names[f.source]))].join(", ");
  },

  async chooseFound(card, found) {
    await this.pictureAction(card, {
      path: "/found",
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source: found.source, id: found.id }),
    });
    if (card.picture) card._found = null;
  },

  removePicture(card) {
    return this.pictureAction(card, { method: "DELETE" });
  },

  async drawPictures() {
    if (this.readOnly() || !this.cards.some((c) => (c.picture_prompt || c.figure) && !c.picture)) return;
    if (this.saveTimer) await this.saveNow();
    this.drawing = true;
    const lessonId = this.lessonId;
    try {
      const res = await (await api(`/api/lessons/${lessonId}/pictures`, { method: "POST" })).json();
      if (this.lessonId !== lessonId) return;  // another lesson opened meanwhile
      // With where each comes from: the next save would drop it otherwise
      const drawn = new Map(res.lesson.cards.map((c) => [c.id, c]));
      this.cards.forEach((c) => {
        const made = drawn.get(c.id);
        if (!c.picture && made?.picture) Object.assign(c, { picture: made.picture, picture_source: made.picture_source ?? null });
      });
      if (res.failures) {
        this.error = t("app.pictures.failed", { count: res.failures }) + (res.error ? ` ${errorMessage(res.error)}` : "");
      }
    } catch (e) {
      this.error = e.message;
    } finally {
      this.drawing = false;
    }
  },
};
