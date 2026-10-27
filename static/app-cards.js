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
    return this.lessonsOpen || this.pdf.open || this.picker.open || this.editor.open || this.removal.open || this.asking.open;
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

  // The AI's correction of a lesson that looked wrong, taken: the card corrected, the doubt gone
  fixDoubt(card) {
    Object.assign(card, { front: card.doubt.front, back: card.doubt.back, doubt: null });
  },

  subdecks() {
    return [...new Set(this.cards.map((c) => c.subdeck).filter(Boolean))];
  },

  addCard() {
    const last = this.cards.at(-1);
    this.cards.push(withKey({ id: newId(), front: "", back: "", subdeck: last?.subdeck ?? "" }));
  },

  // --- Formulas --------------------------------------------------------
  // A formula or gaps not being edited: only as the card shows them (their text: a click away)
  renderedOnly(card, field) {
    const special = this.hasMath(card[field]) || (field === "front" && this.isCloze(card.front));
    return special && card._editing !== field;
  },

  // A click on a formula: its text to edit, the cursor in it
  editField(card, field, el) {
    if (this.readOnly()) return;
    card._editing = field;
    this.$nextTick(() => el.closest(".flash")?.querySelector(`textarea.${field}`)?.focus());
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
};
