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
    return this.canSendDictated("prompt", this.form.text) && !this.loading && !this.tidy.busy;
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
  // open, ready to write (focusAdded)
  addCardAfter(card) {
    const after = card ?? this.cards.at(-1);
    const at = this.cards.indexOf(after);
    const added = withKey({ id: newId(), front: "", back: "", subdeck: after?.subdeck ?? "" });
    this.doneEditing();  // first: the one it leaves, empty, goes (the new one then in its place)
    const now = this.cards.indexOf(after);
    this.cards.splice(now === -1 ? at : now + 1, 0, added);
    this.editCard(added, "", { all: true });
    this.focusAdded(added.key);
  },

  // A card just added, ready to write. On a touch screen nothing focused: focus opens the
  // keyboard over the card, when « Que doit demander cette carte ? » (the AI writes it), often
  // dictated by its 🎙️, is what is mostly used; touching a field opens it. With a mouse, that
  // field focused; its front when there is none (a lesson not saved yet: no AI on it). Once
  // shown: x-show shows the fields at the next frame. A field of the card clicked meanwhile (a
  // busy machine, a quick hand) keeps the focus: what is typed there stays there
  focusAdded(key) {
    if (!matchMedia("(pointer: fine)").matches) return;
    this.$nextTick(() => requestAnimationFrame(() => {
      const card = document.querySelector(`[data-card="${key}"]`);
      if (!card || card.contains(document.activeElement)) return;
      (card.querySelector(".card-fix textarea") ?? card.querySelector("textarea.front"))?.focus({ preventScroll: true });
    }));
  },

  // `field`: the text touched, shown as typed (its LaTeX), the cursor in it ("front", "back",
  // "info", "fun_fact", "explanation", "mnemonic", "choice:<n>"); none: the card
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
    const selector = name === "choice" ? `.choice:nth-of-type(${Number(n) + 1}) textarea` : `textarea.${name}`;
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
      // Not what a finger drags (a mask, a handle), nor the diagram edited full screen (#721),
      // nor the picture's page
      const dragged = event.target.closest?.(".diagram :is(.mask.editable, .handle, .crop-handle), .diagram-clip.open, .picture-panel");
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

  // Another lesson shown (or a new one): nothing of the one before left full screen (a card
  // edited, its diagram or picture, the lesson's end), nor half dragged
  leaveCards() {
    Object.assign(this, { editing: "", diagramOpen: "", pictureOpen: "", peek: "", slide: 0, cardTouch: null });
  },

  // The edited card left: its correction (and the lesson's) no longer undoable, so the
  // pictures they replaced can go
  doneEditing() {
    const card = this.cards.find((c) => c.key === this.editing);
    this.editing = "";
    this.diagramOpen = "";
    this.pictureOpen = "";
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
  // the server draws (a picture it writes is in no card yet), nor while a figure a correction
  // replaced is still to be drawn again from (previousFigure: its sources go with it): the next
  // time, or the next open.
  async prunePictures() {
    if (!this.lessonId || this.readOnly() || this.editing !== "" || this.revision.undo) return;
    if (this.drawingHere() || this.pictureJobs || this.cards.some((c) => c._previous && !c.picture)) return;
    const id = this.lessonId;
    if (this.saveTimer || this.snapshot() !== this.lastSaved) await this.saveNow();
    if (this.lessonId !== id || this.editing !== "" || this.snapshot() !== this.lastSaved || this.saveState !== "saved") return;
    try {
      await api(`/api/lessons/${id}/pictures/prune`, { method: "POST" });
    } catch {}  // the next time
  },

  // The AI's correction of a lesson that looked wrong, taken: the card corrected, the doubt gone
  fixDoubt(card) {
    Object.assign(card, { front: card.doubt.front, back: card.doubt.back, doubt: null });
  },

  // The card's deck in Anki, its levels (app/anki.py: _deck_name): the lesson's, then its part,
  // one named as the deck's last level not again; shown at the open card's top, as Anki's
  deckPath(card) {
    const base = this.deck.trim(), part = (card.subdeck || "").trim();
    const last = base.split("::").pop().trim().toLowerCase();
    const name = !part || last === part.toLowerCase() ? base : `${base}::${part}`;
    return name.split("::").map((level) => level.trim()).filter(Boolean);
  },

  // --- A card's sub-deck, chosen ---------------------------------------
  // Touched, a list the page draws: none, the lesson's sub-decks (how many cards each), or a
  // new one typed. Not a field's suggestions (<datalist>): Android's WebView shows them barely or
  // not at all, its ▼ promising a list it doesn't give.
  subdeckCounts() {
    const counts = new Map();
    for (const c of this.cards) if (c.subdeck) counts.set(c.subdeck, (counts.get(c.subdeck) ?? 0) + 1);
    return [...counts];
  },

  openSubdecks(card) {
    if (this.readOnly()) return;
    if (this.editing !== card.key) this.editCard(card);
    card._subdecks = { fresh: "" };
    // Focused (not its field: no keyboard over it on a phone); Escape closes it alone wherever
    // the focus is (the card's own Escape leaves it to the list while it is open)
    this.$nextTick(() => document.querySelector(`[data-card="${card.key}"] .subdeck-picker`)?.focus({ preventScroll: true }));
  },

  pickSubdeck(card, name) {
    card.subdeck = name.trim();
    card._subdecks = null;
  },

  // A card still empty is the one to fill: no second one added while it waits; either way
  // it is opened ready to write (focusAdded)
  addCard() {
    const last = this.cards.at(-1);
    let card = this.cards.find((c) => !(c.front ?? "").trim() && !(c.back ?? "").trim());
    if (!card) {
      card = withKey({ id: newId(), front: "", back: "", subdeck: last?.subdeck ?? "" });
      this.cards.push(card);
    }
    this.editCard(card, "", { all: true });  // empty: its fields to write in
    const key = card.key;
    this.$nextTick(() => document.querySelector(`[data-card="${key}"] textarea.front`)?.scrollIntoView({ block: "center", behavior: "smooth" }));
    this.focusAdded(key);
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
