// The cards of the open lesson: reviewed, edited, their formulas and gaps previewed. The AI
// correction: app-revision.js; the diagram labels: app-diagram.js; the pictures: app-pictures.js.
// Methods of the page's Alpine component (app.js), as `this`.

const cardsPart = {
  // How the lesson's cards are asked, in a line: "↔ both ways · ⌨️ typed answer"; "" none
  askedHow() {
    const said = [];
    if (this.reverse) said.push(t("app.review.options.reverse"));
    if (this.typing) said.push(t("app.review.options.typing"));
    if (this.dictation) said.push(t(this.dictationOnly ? "app.review.options.dictationOnly" : "app.review.options.dictation"));
    return said.join(" · ");
  },

  // --- Review ---------------------------------------------------------
  // Photos + prompt, or the prompt alone (see "Generate from the prompt alone")
  sheetOpen() {
    return this.lessonsOpen || this.pdf.open || this.allPages || this.picker.open || this.editor.open || this.removal.open || this.asking.open;
  },

  canGenerate() {
    return this.form.text.trim() !== "" && !this.loading && !this.dictating("prompt") && !this.tidy.busy;
  },

  bottomBar() {
    return !this.unpaired;  // always visible: it is the main call to action
  },

  removeCard(card) {
    if (this.editing === card.key) this.editing = "";
    this.cards = this.cards.filter((c) => c !== card);
  },

  // --- One card edited at a time ---------------------------------------
  // The others shown as Anki will show them (formulas drawn, no fields). A touch on one of its
  // texts, ✏️ or ✨ edits a card; done with it (✓, Escape, another card edited, the lesson
  // corrected or sent): saved, its correction no longer undoable, and the pictures no card
  // uses then removed: a correction's old picture is kept only while it can be undone.
  isEditing(card) {
    return !this.readOnly() && this.editing === card.key;
  },

  // `field`: the text touched, shown as typed (its LaTeX), the cursor in it ("front", "back",
  // "info", "fun_fact", "explanation", "mnemonic", "subdeck", "choice:<n>"); none: the card
  // edited, its texts still drawn (✨: what is asked of the AI), its empty ones offered by their
  // placeholder. `all`: every field shown (a card just added, empty).
  editCard(card, field = "", { all = false } = {}) {
    if (this.readOnly()) return;
    if (this.editing !== card.key) {
      this.doneEditing();
      this.editing = card.key;
    }
    if (all) card._allFields = true;
    if (!field) return;
    card._editing = field;
    const [name, n] = field.split(":");
    const selector = name === "choice" ? `.choice:nth-of-type(${Number(n) + 1}) textarea`
      : name === "subdeck" ? "input.subdeck" : `textarea.${name}`;
    this.$nextTick(() => document.querySelector(`[data-card="${card.key}"] ${selector}`)?.focus());
  },

  // The edited card left: its correction (and the lesson's) no longer undoable, so the
  // pictures they replaced can go
  doneEditing() {
    const card = this.cards.find((c) => c.key === this.editing);
    this.editing = "";
    if (card) {
      this.cancelFix(card);
      Object.assign(card, { _fixed: null, _allFields: false, _editing: "" });
    }
    this.revision = { ...this.revision, undo: null };
    this.prunePictures();
  },

  // The pictures no saved card uses removed (POST …/pictures/prune), once nothing can bring
  // them back: no card edited, no correction to undo, the lesson saved as shown. Not while
  // the server draws (a picture it writes is in no card yet): the next time, or the next open.
  async prunePictures() {
    if (!this.lessonId || this.readOnly() || this.editing || this.revision.undo) return;
    if (this.drawingHere() || this.pictureJobs) return;
    const id = this.lessonId;
    if (this.saveTimer || this.snapshot() !== this.lastSaved) await this.saveNow();
    if (this.lessonId !== id || this.editing || this.snapshot() !== this.lastSaved || this.saveState !== "saved") return;
    try {
      await api(`/api/lessons/${id}/pictures/prune`, { method: "POST" });
    } catch {}  // the next time
  },

  // The AI's correction of a lesson that looked wrong, taken: the card corrected, the doubt gone
  fixDoubt(card) {
    Object.assign(card, { front: card.doubt.front, back: card.doubt.back, doubt: null });
  },

  subdecks() {
    return [...new Set(this.cards.map((c) => c.subdeck).filter(Boolean))];
  },

  // A card still empty is the one to fill: no second one added while it waits; either way
  // its front is where the typing goes
  addCard() {
    const last = this.cards.at(-1);
    let card = this.cards.find((c) => !(c.front ?? "").trim() && !(c.back ?? "").trim());
    if (!card) {
      card = withKey({ id: newId(), front: "", back: "", subdeck: last?.subdeck ?? "" });
      this.cards.push(card);
    }
    this.editCard(card, "", { all: true });  // empty: its fields to write in
    const key = card.key;
    this.$nextTick(() => {
      const front = document.querySelector(`[data-card="${key}"] textarea.front`);
      front?.scrollIntoView({ block: "center", behavior: "smooth" });
      front?.focus({ preventScroll: true });
    });
  },

  // --- Formulas --------------------------------------------------------
  // A text as the card shows it, formulas drawn and gaps marked, unless the card is edited and
  // this text touched (or all of them asked, ✏️): then as typed, its LaTeX (editCard)
  renderedOnly(card, field) {
    return !(this.isEditing(card) && (card._allFields || card._editing === field));
  },

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

  // The text as Anki will show it: formulas drawn (MathJax, as Anki), gaps marked with their
  // number (each number is a card), line breaks kept, the rest escaped.
  previewHtml(text) {
    text = text ?? "";
    const plain = (t) =>
      escapeHtml(t)
        .replace(GAP_START, (_, n) => `<span class="gap"><sup>${n}</sup>`)
        .replace(GAP_END, "</span>")
        .replaceAll("\n", "<br>");
    if (!this.mathReady) return plain(text);
    let html = "", last = 0, drawn = false;
    for (const m of text.matchAll(MATH)) {
      html += plain(text.slice(last, m.index));
      html += MathJax.tex2chtml(m[1] ?? m[2], { display: m[2] !== undefined }).outerHTML;
      last = m.index + m[0].length;
      drawn = true;
    }
    // the styles of what was just drawn (its characters' fonts), added to the page's
    if (drawn) {
      MathJax.startup.document.clear();
      MathJax.startup.document.updateDocument();
    }
    return html + plain(text.slice(last));
  },
};
