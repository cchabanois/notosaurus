// The open lesson corrected by the AI: the cards compared with the ones before, and the
// correction undone (a regeneration too).
// Methods of the page's Alpine component (app.js), as `this`.

// How long the AI usually takes, as measured (gemini-3.8-flash, 2026-11-11: one page 12-15 s
// quick, 14-17 s careful, about 3 s or 2.5 s more a page, whatever the route): what the
// waiting card says, not a promise ("slow" says when it is late)
function lessonSeconds(quick, pages) {
  const n = Math.max(1, pages);  // the instructions alone: as a page
  return quick ? 10 + 3 * n : 15 + 2.5 * n;
}

// A lesson's correction: the AI writes every card again, so by its cards, and its pages
// (2026-11-19: 4 to 16 cards, none to 2 pages, 8-24 s careful, about 30 % less quick)
function revisionSeconds(quick, cards, pages) {
  return (quick ? 0.7 : 1) * (6 + cards + 2 * pages);
}

// "About 15 seconds", rounded to 5; a minute or more: in minutes
function about(seconds) {
  if (seconds < 60) return t("app.loading.aboutSeconds", { count: Math.max(5, Math.round(seconds / 5) * 5) });
  return t("app.loading.aboutMinutes", { count: Math.round(seconds / 60) });
}

const revisionPart = {
  // As the lesson is made: quick unless the user chose careful ("careful": once more carefully)
  async revise({ careful = false } = {}) {
    const instruction = this.revision.text.trim();
    if (!instruction || this.revision.busy || !this.lessonId || this.readOnly()) return;
    this.doneEditing();  // one correction undoable at a time: the lesson's now
    const quick = (this.quick && !careful) || this.off("ai.careful");
    this.error = "";
    this.revision.busy = true;
    Object.assign(this, { loadingQuick: quick, loadingPages: this.photos.length, loadingCards: this.cards.length });
    const before = {
      deck: this.deck, cards: this.cards.map((c) => ({ ...c, _state: undefined })),
      reverse: this.reverse, typing: this.typing, dictation: this.dictation, dictationOnly: this.dictationOnly,
    };
    this.aiStep = "";
    const job = newJob();  // "Cancel" in the waiting card stops it
    this.generating = job;
    this.cancelling = false;
    try {
      const res = await resultAsItComes(await api(`/api/lessons/${this.lessonId}/revise?job=${job}`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/x-ndjson" },
        body: JSON.stringify({ ...this.payload(), instruction, quick }),
      }), (step) => { this.aiStep = step.step; });
      if (!res) {  // cancelled: the cards as they were, the instruction kept to change it
        this.revision.busy = false;
        return;
      }
      const { cards, stats } = this.compareCards(before.cards, res.lesson.cards);
      // A card whose picture is drawn again (what it shows changed): its old one shown faded meanwhile
      const was = new Map(before.cards.map((c) => [c.key, c]));
      cards.forEach((c) => {
        const old = was.get(c.key);
        if (old?.picture && !c.picture && (c.figure || c.picture_prompt)) c._replacing = this.pictureUrl(old);
      });
      clearTimeout(this.saveTimer);
      this.saveTimer = null;
      this.deck = res.lesson.deck;
      this.cards = cards;
      // How the cards are asked, if the correction changed it ("both ways")
      this.reverse = res.lesson.reverse;
      this.typing = res.lesson.typing ?? false;
      this.dictation = res.lesson.dictation ?? false;
      this.dictationOnly = res.lesson.dictation_only ?? false;
      this.lastSaved = this.snapshot();  // the server already saved the revision
      this.saveState = "saved";
      this.revision = { text: "", busy: false, summary: res.summary, stats, undo: before, instruction, quick };
      this.loadLessons();
      this.drawPictures();  // a card added by the correction may ask for one
    } catch (e) {
      if (!this.cancelling) this.error = e.message;
      this.revision.busy = false;
    } finally {
      this.aiStep = "";
      this.generating = "";
      this.cancelling = false;
    }
  },

  // --- One card corrected by the AI ("✨ Correct this card") ----------------
  // card._fix: its field ({ text, busy, blank }); card._fixed: what changed ({ summary,
  // before }), until undone or corrected again. A card still empty (just added) is written.
  // Its field focused only with a mouse: on a touch screen, focus opens the keyboard over the
  // card, when the 🎙️ beside it is often simpler; touching the field opens it.
  openFix(card) {
    this.editCard(card);  // its correction undoable while the card is edited; its field there
    card._menu = false;
    if (!matchMedia("(pointer: fine)").matches) return;
    this.$nextTick(() => document.querySelector(`[data-card="${card.key}"] .card-fix textarea`)?.focus());
  },

  async fixCard(card, { careful = false } = {}) {
    const fix = card._fix;
    const instruction = fix?.text.trim();
    if (!instruction || fix.busy || !this.lessonId || this.readOnly()) return;
    const quick = (this.quick && !careful) || this.off("ai.careful");
    this.error = "";
    fix.busy = true;
    fix.job = newJob();  // its "Cancel" stops it while the AI writes
    fix.cancelling = false;
    const plain = (c) => Object.fromEntries(Object.entries(c).filter(([k]) => k !== "key" && !k.startsWith("_")));
    const lessonId = this.lessonId;
    try {
      const res = await (await api(`/api/lessons/${lessonId}/fix-card?job=${fix.job}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ card: plain(card), instruction, quick, others: this.cards.filter((c) => c !== card).map((c) => c.front) }),
      })).json();
      if (fix.cancelling) return;  // cancelled as it came: the card as it was
      const i = this.cards.indexOf(card);
      if (this.lessonId !== lessonId || i === -1) return;  // another lesson opened, or the card removed, meanwhile
      const fixed = { ...res.card, key: card.key, _state: "modified", _fixed: { summary: res.summary, before: plain(card), instruction, quick } };
      fixed._fix = this.newFix(fixed);  // the field ready for the next one
      if (card.picture && !fixed.picture) fixed._replacing = this.pictureUrl(card);  // shown faded until drawn again
      this.cards.splice(i, 1, fixed);
      await this.saveNow();  // its picture is drawn from the saved lesson
      if (res.figure_problem) {
        // The request was about its figure as drawn: drawn again, told what is wrong in it (as
        // the check's problem), the one it replaces shown faded meanwhile
        const drawn = this.cards[i];
        drawn._check = { ok: false, problem: res.figure_problem };
        await this.redrawFigure(drawn);
      } else if ((fixed.figure || fixed.picture_prompt) && !fixed.picture) this.drawPictures();
    } catch (e) {
      if (!fix.cancelling) this.error = e.message;  // cancelled: nothing to say
      fix.busy = false;
    }
  },

  // A card's correction field, empty: what is asked of the AI ("blank": a card still empty, written)
  newFix(card) {
    return { text: "", busy: false, blank: this.blankCard(card) };
  },

  // The card's "Cancel" (or Escape) while the AI corrects it: this correction dropped, the card
  // as it was, its field empty again (gone once the card is done with); the AI writing it is
  // stopped, the microphone listening for it too (what it heard dropped).
  cancelFix(card) {
    const fix = card._fix;
    if (!fix) return;
    if (fix.busy && !fix.cancelling) {
      fix.cancelling = true;
      cancelJob(fix.job);
    }
    const listening = this.mic.listening === `card:${card.key}`;
    card._fix = this.isEditing(card) ? this.newFix(card) : null;
    // Once its field is gone (stopping changes what the field shows)
    if (listening) this.$nextTick(() => this.stopDictation({ keep: false }));
  },

  // Nothing written on it yet: the AI writes it ("✨ Write with the AI")
  blankCard(card) {
    return !(card.front ?? "").trim() && !(card.back ?? "").trim();
  },

  // "🎯 Again, carefully": the quick correction undone, asked again with the model's thinking
  fixCarefully(card) {
    const { instruction } = card._fixed;
    const i = this.cards.indexOf(card);
    this.undoFix(card);
    const restored = this.cards[i];
    restored._fix = { text: instruction, busy: false, blank: this.blankCard(restored) };
    return this.fixCard(restored, { careful: true });
  },

  undoFix(card) {
    const i = this.cards.indexOf(card);
    if (i === -1 || !card._fixed) return;
    const restored = { ...card._fixed.before, key: card.key };  // autosave sends it
    restored._fix = this.newFix(restored);
    this.cards.splice(i, 1, restored);
  },

  // The waiting card's title: what is being done, now (the cards counted as they come)
  loadingTitle() {
    Alpine.store("i18n").version;  // computed again once the texts are read
    if (this.revision.busy) return t("app.loading.revising");
    if (this.aiStep === "figures") return t("app.loading.figures");
    if (this.coming.length) return t("app.loading.writingCards", { count: this.coming.length });
    return t(this.photos.length ? "app.loading.reading" : "app.loading.writing");
  },

  // Under it: how long it usually takes; the AI slow to answer, or another model asked
  loadingNote() {
    Alpine.store("i18n").version;  // (else the key itself, when made before the texts came)
    if (this.aiStep === "fallback") return t("app.loading.fallback");
    if (this.aiStep === "slow" && !this.coming.length) return t("app.loading.slow");
    if (this.batch && !this.revision.busy) return t("app.loading.batch", this.batch);  // pages 11 to 20 of 30
    return about(this.revision.busy
      ? revisionSeconds(this.loadingQuick, this.loadingCards, this.loadingPages)
      : lessonSeconds(this.loadingQuick, this.loadingPages));
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
      rate: this.rate,
      reverse: this.reverse,
      typing: this.typing,
      dictation: this.dictation,
      dictationOnly: this.dictationOnly,
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

  // "🎯 Again, carefully": the quick correction undone, asked again with the model's thinking
  reviseCarefully() {
    const { instruction } = this.revision;
    this.undoRevision();
    this.revision.text = instruction;
    return this.revise({ careful: true });
  },

  clearRevision() {
    this.cards.forEach((c) => { c._state = undefined; });
    this.revision = { ...this.revision, summary: "", stats: "", undo: null };
  },
};
