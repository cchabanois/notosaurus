// The cards of the open lesson: reviewed, edited, their formulas and gaps previewed. The AI
// correction: app-revision.js; the diagram labels: app-diagram.js; the pictures: app-pictures.js.
// Methods of the page's Alpine component (app.js), as `this`.

// The screen after the last card, edited as a card is (its key): the lesson looked over
const LESSON_END = "end";

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
  // texts or ✨ edits a card, full screen, its correction's field at the bottom; done with it
  // (✕, Escape, Android's back, ‹ › to another, the lesson corrected or sent): saved, its
  // correction no longer undoable, and the pictures no card uses then removed: a correction's
  // old picture is kept only while it can be undone.
  isEditing(card) {
    return !this.readOnly() && this.editing === card.key;
  },

  // Shown as when edited: the card edited, or the one beside it while a finger drags it (its
  // placeholders, its correction's field), so that it looks the same once it is
  shownEdited(card) {
    return this.isEditing(card) || this.peek === card.key;
  },

  // The card beside the edited one (its key; the lesson's end, LESSON_END), while a finger drags
  // it (none: null): its correction's field there as it will be; the one it was before, not
  // edited, without it again
  setPeek(key) {
    const old = this.cards.find((c) => c.key === this.peek);
    if (old && old.key !== key && !this.isEditing(old)) old._fix = null;
    this.peek = key ?? "";
    const card = this.cards.find((c) => c.key === key);
    if (card && this.lessonId) card._fix ??= this.newFix(card);
  },

  // The cards looked over one by one, then the lesson's end: their keys
  reviewKeys() {
    return [...this.cards.map((c) => c.key), LESSON_END];
  },

  // A card of the list touched: open full screen, as Anki shows it (nothing focused: no keyboard
  // over it on a phone); a touch on one of its texts there edits it
  openCard(card) {
    this.editCard(card);
    this.$nextTick(() => document.querySelector(`[data-card="${card.key}"]`)?.scrollTo({ top: 0 }));
  },

  // ＋ in the card open (or at the lesson's end): an empty card just after it, in its sub-deck,
  // open, its front ready to type
  addCardAfter(card) {
    const after = card ?? this.cards.at(-1);
    const at = this.cards.indexOf(after);
    const added = withKey({ id: newId(), front: "", back: "", subdeck: after?.subdeck ?? "" });
    this.doneEditing();  // first: the one it leaves, empty, goes (the new one then in its place)
    const now = this.cards.indexOf(after);
    this.cards.splice(now === -1 ? at : now + 1, 0, added);
    this.editCard(added, "", { all: true });
    this.$nextTick(() => document.querySelector(`[data-card="${added.key}"] textarea.front`)?.focus());
  },

  // `field`: the text touched, shown as typed (its LaTeX), the cursor in it ("front", "back",
  // "info", "fun_fact", "explanation", "mnemonic", "subdeck", "choice:<n>"); none: the card
  // edited, its texts still drawn (✨: what is asked of the AI), its empty ones offered by their
  // placeholder. `all`: every field shown (a card just added, empty).
  editCard(card, field = "", { all = false } = {}) {
    if (this.readOnly()) return;
    this.slide = 0;
    if (this.editing !== card.key) {
      this.doneEditing();
      this.editing = card.key;
      card._fix ??= this.lessonId ? this.newFix(card) : null;
    }
    if (all) card._allFields = true;
    if (!field) return;
    card._editing = field;
    const [name, n] = field.split(":");
    const selector = name === "choice" ? `.choice:nth-of-type(${Number(n) + 1}) textarea`
      : name === "subdeck" ? "input.subdeck" : `textarea.${name}`;
    // Focused once shown: x-show shows it at the next frame (a hidden field takes no focus)
    this.$nextTick(() => requestAnimationFrame(() => document.querySelector(`[data-card="${card.key}"] ${selector}`)?.focus()));
  },

  // A finger swiped across the card edited: the card follows it, sideways, the next one (to the
  // left) or the previous one beside it, moved with it; let go far enough, they go on and the
  // other one is edited, else they come back. Only a stroke sideways (a scroll up or down moves
  // nothing), from anywhere on the card, a field or a diagram's photo too (a quick stroke selects
  // no text: that takes a long press), but what a finger drags there (a diagram's mask, its
  // handles, its frame's corners); past the first or the last card, it hardly moves.
  touchCard(event) {
    const el = event.currentTarget, t = event.changedTouches[0];
    if (event.type === "touchstart") {
      const dragged = event.target.closest?.(".diagram :is(.mask.editable, .handle, .crop-handle)");
      this.cardTouch = event.touches.length === 1 && !dragged ? { x: t.clientX, y: t.clientY, way: "" } : null;
      return;
    }
    const touch = this.cardTouch;
    if (!touch) return;
    const dx = t.clientX - touch.x, dy = t.clientY - touch.y;
    const keys = this.reviewKeys();
    const step = dx < 0 ? 1 : -1, next = keys[keys.indexOf(this.editing) + step];  // a key may be 0
    const beside = () => this.peek !== "" && document.querySelector(`[data-card="${this.peek}"]`);
    const place = (card, transform, transition = "none") => {
      if (card) Object.assign(card.style, { transform, transition });
    };
    if (event.type === "touchmove") {
      if (!touch.way && Math.hypot(dx, dy) > 10) touch.way = Math.abs(dx) > Math.abs(dy) ? "side" : "scroll";
      if (touch.way !== "side") return;
      if (this.peek !== (next ?? "")) {  // the one beside it: on the side the finger goes
        place(beside(), "");
        this.setPeek(next);
      }
      place(el, `translateX(${next !== undefined ? dx : dx / 4}px)`);
      place(beside(), `translateX(calc(${dx}px + ${step * 100}%))`);
      return;
    }
    this.cardTouch = null;
    const sideways = touch.way ? touch.way === "side" : Math.abs(dx) > 2 * Math.abs(dy);
    const far = Math.abs(dx) > Math.min(80, el.offsetWidth / 4);
    if (event.type === "touchend" && !event.touches.length && sideways && far && next !== undefined) {
      if (this.peek !== next) this.setPeek(next);  // let go without a move seen: there all the same
      this.$nextTick(() => {
        place(el, `translateX(${-step * 100}%)`, "transform .15s ease-out");
        place(beside(), "translateX(0)", "transform .15s ease-out");
      });
      setTimeout(() => {
        place(el, "", "");
        place(beside(), "", "");
        this.moveEditing(step, { slide: false });  // already in its place
        this.setPeek(null);
      }, 170);
      return;
    }
    place(el, "", "transform .2s ease-out");  // back where they were
    place(beside(), `translateX(${step * 100}%)`, "transform .2s ease-out");
    setTimeout(() => {
      place(el, "", "");
      place(beside(), "", "");
      this.setPeek(null);
    }, 200);
  },

  // The edited card left: its correction (and the lesson's) no longer undoable, so the
  // pictures they replaced can go
  doneEditing() {
    const card = this.cards.find((c) => c.key === this.editing);
    this.editing = "";
    if (card) {
      this.cancelFix(card);
      Object.assign(card, { _fixed: null, _allFields: false, _editing: "" });
      if (this.blankCard(card) && !card.mask && !card.picture) this.removeCard(card);  // added, left empty
      // The list where the card is (‹ › may have gone far from where it was opened)
      this.$nextTick(() => document.querySelector(`[data-card="${card.key}"]`)?.scrollIntoView({ block: "nearest" }));
    }
    this.revision = { ...this.revision, undo: null };
    this.prunePictures();
  },

  // ‹ ›: the previous or the next card edited, this one done with; after the last, the lesson's end
  moveEditing(step, { slide = true } = {}) {
    const keys = this.reviewKeys();
    const key = keys[keys.indexOf(this.editing) + step];
    if (key === undefined) return;  // (a card's key may be 0)
    if (key === LESSON_END) {
      this.doneEditing();
      this.editing = LESSON_END;
    } else {
      this.editCard(this.cards.find((c) => c.key === key));
    }
    if (slide) this.slide = step;
    this.$nextTick(() => document.querySelector(`[data-card="${key}"]`)?.scrollTo({ top: 0 }));
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
