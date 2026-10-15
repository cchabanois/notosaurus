// The open lesson corrected by the AI: the cards compared with the ones before, and the
// correction undone (a regeneration too).
// Methods of the page's Alpine component (app.js), as `this`.

const revisionPart = {
  async revise() {
    const instruction = this.revision.text.trim();
    if (!instruction || this.revision.busy || !this.lessonId || this.readOnly()) return;
    this.error = "";
    this.revision.busy = true;
    const before = {
      deck: this.deck, cards: this.cards.map((c) => ({ ...c, _state: undefined })),
      reverse: this.reverse, typing: this.typing, dictation: this.dictation, dictationOnly: this.dictationOnly,
    };
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
      // How the cards are asked, if the correction changed it ("both ways")
      this.reverse = res.lesson.reverse;
      this.typing = res.lesson.typing ?? false;
      this.dictation = res.lesson.dictation ?? false;
      this.dictationOnly = res.lesson.dictation_only ?? false;
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

  clearRevision() {
    this.cards.forEach((c) => { c._state = undefined; });
    this.revision = { ...this.revision, summary: "", stats: "", undo: null };
  },
};
