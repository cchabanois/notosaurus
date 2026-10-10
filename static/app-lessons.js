// A lesson made from the photos (extraction), and the saved lessons: opened, saved, deleted.
// Methods of the page's Alpine component (app.js), as `this`.

const lessonsPart = {
  // --- Extraction -----------------------------------------------------
  // A lesson open and ours: generating again replaces its cards (no second lesson).
  // Someone else's: a new lesson of our own.
  regeneratesInPlace() {
    return Boolean(this.lessonId) && !this.readOnly();
  },

  // `careful`: made again carefully ("Careful, again"), whatever the choice above
  async extract({ careful = false } = {}) {
    const quick = this.quick && !careful;
    this.error = "";
    this.loading = true;
    this.loadingQuick = quick;
    this.coming = [];
    // Its id, for "Cancel" (not crypto.randomUUID: a phone opens the page over plain http)
    const job = Math.random().toString(36).slice(2) + Date.now().toString(36);
    this.generating = job;
    this.cancelling = false;
    if (this.saveTimer) await this.saveNow();
    const inPlace = this.regeneratesInPlace();
    // What "Undo" brings back; not when the photos changed (the old ones are gone)
    const before = inPlace && !this.photosEdited ? this.undoState() : null;
    const body = new FormData();
    this.photos.forEach((p, i) => body.append("images", p.blob, `page-${i + 1}.jpg`));
    body.append("prompt", this.form.text);
    body.append("deck", this.form.deck);
    body.append("voice", this.form.voice);
    // The PDF pages' text, one per photo ("" for a photo): the exact words for the AI
    if (this.photos.some((p) => p.text)) body.append("page_texts", JSON.stringify(this.photos.map((p) => p.text ?? "")));
    // Generated again: the options set in the review stay, the prompt's are added
    body.append("typing", Boolean(this.form.typing || (inPlace && this.typing)));
    body.append("dictation", Boolean(this.form.dictation || (inPlace && this.dictation)));
    if (this.funFacts) body.append("fun_facts", "true");
    if (this.helps) body.append("helps", "true");
    if (quick) body.append("quick", "true");
    body.append("job", job);
    if (this.selectedId) body.append("prompt_id", this.selectedId);
    try {
      const url = inPlace ? `/api/lessons/${this.lessonId}/regenerate` : "/api/extract";
      const res = await api(url, { method: "POST", body, headers: { Accept: "application/x-ndjson" } });
      const lesson = await lessonAsItComes(res, (card) => {
        if (card) this.coming.push({ front: plainCardText(card.front), back: plainCardText(card.back) });
        else this.coming = [];
      });
      if (!lesson) return;  // cancelled: the page as it was (the photos, the prompt)
      const used = this.current();
      if (used) used.used_at = new Date().toISOString();  // moves it to the front of the chips
      await this.loadPhotos(lesson);  // as saved: the server turns sideways photos upright
      this.show(lesson);
      this.madeQuick = quick;
      if (inPlace) {
        this.revision = { text: "", busy: false, summary: t("app.prompt.regenerated"), stats: "", undo: before };
      }
      this.loadLessons();
      if (!this.cards.length) this.error = t("app.review.noCards");
      this.drawPictures();  // the cards show now, their pictures when drawn
    } catch (e) {
      if (!this.cancelling) this.error = e.message;  // cancelled: no error to show
    } finally {
      this.loading = false;
      this.generating = "";
      this.cancelling = false;
    }
  },

  // "Cancel" while waiting: the AI stops, no lesson is saved (generated again: the old one stays)
  async cancelGeneration() {
    if (!this.generating || this.cancelling) return;
    this.cancelling = true;
    try {
      await api(`/api/generations/${encodeURIComponent(this.generating)}/cancel`, { method: "POST" });
    } catch {}  // gone already: its answer comes anyway
  },

  // Decks that already exist (Anki's, the lessons'), offered when the deck is edited
  async loadDecks() {
    try {
      this.decks = await (await api("/api/decks")).json();
    } catch {}  // only suggestions
  },

  // --- Saved lessons ---------------------------------------------------
  async loadLessons() {
    try {
      this.lessons = await (await api("/api/lessons")).json();
    } catch {}  // history is optional for creating a lesson
  },

  formatDate(iso) {
    Alpine.store("i18n").version;  // re-render dates when the language changes
    return formatDate(iso);
  },

  // Lessons of the open Anki profile, shared lessons, lessons without owner (the server
  // sends no others; filtered here too, so a profile switch shows at once).
  visibleLessons() {
    const profile = this.anki.profile;
    if (!profile) return this.lessons;
    return this.lessons.filter((l) => l.shared || !l.owner || l.owner === profile);
  },

  manyLessons() {
    return this.visibleLessons().length > MANY_LESSONS;
  },

  // The lessons sheet, in sections. By subject, the deck's first level ("Anglais" for
  // "Anglais::Leçon 1"), each lesson shown by the rest of its name; in the list's order
  // (the most recent first): the subject worked on last comes first. Anki doesn't tell
  // decks apart by case: neither does this. With many lessons: the recent ones first,
  // the subjects folded but the open lesson's (opened or closed by hand, kept on this
  // device); a search shows the lessons found instead.
  lessonSections() {
    const all = this.visibleLessons();
    const many = all.length > MANY_LESSONS;
    const named = (l) => ({ ...l, title: deckParts(l.deck).join(" › ") || t("app.lessons.noDeck") });
    const query = fold(this.lessonQuery.trim());
    if (many && query) {
      const found = all.filter((l) => fold(deckParts(l.deck).join(" ")).includes(query)).map(named);
      return [{ key: "found", name: t("app.lessons.found"), count: found.length, open: true, lessons: found }];
    }
    const subjects = new Map();
    for (const l of all) {
      const [head, ...rest] = deckParts(l.deck);
      const name = head ?? t("app.lessons.noDeck");
      const subject = name.toLocaleLowerCase();
      if (!subjects.has(subject)) subjects.set(subject, { key: `subject:${subject}`, subject, name, lessons: [] });
      subjects.get(subject).lessons.push({ ...l, title: rest.length ? rest.join(" › ") : name });
    }
    const sections = [...subjects.values()].map((g) => ({
      ...g,
      count: g.lessons.length,
      foldable: many,
      open: !many || (this.openSubjects[g.subject] ?? g.lessons.some((l) => l.id === this.lessonId)),
    }));
    if (many) {
      const recent = all.slice(0, RECENT_LESSONS).map(named);
      sections.unshift({ key: "recent", name: t("app.lessons.recent"), open: true, lessons: recent });
    }
    return sections;
  },

  toggleSubject(section) {
    this.openSubjects = { ...this.openSubjects, [section.subject]: !section.open };
    storage("set", JSON.stringify(this.openSubjects), OPEN_SUBJECTS);
  },

  // Only the lesson's creator decides to share it
  canShare() {
    return Boolean(this.lessonOwner) && this.anki.profile === this.lessonOwner;
  },

  // Someone else's lesson (shared, or seen with "All profiles"): it can be read,
  // sent to Anki and exported, not changed. Lessons without owner are everyone's.
  readOnly() {
    return Boolean(this.lessonOwner) && this.anki.profile !== this.lessonOwner;
  },

  canDelete(l) {
    return !l.owner || l.owner === this.anki.profile;
  },

  // Shows a lesson coming from the server (fresh generation or reopened).
  show(lesson) {
    this.madeQuick = false;
    clearTimeout(this.saveTimer);
    this.saveTimer = null;
    this.lessonId = lesson.id;
    this.lessonOwner = lesson.owner ?? "";
    this.lessonShared = lesson.shared ?? false;
    this.lessonPrompt = lesson.prompt ?? "";
    this.lessonChoice = lesson.choice ?? "";
    this.lessonExported = Boolean(lesson.exported_at);
    this.photosEdited = false;
    this.frames = lesson.frames ?? [];
    this.deck = lesson.deck;
    this.cards = lesson.cards.map(withKey);
    this.reverse = lesson.reverse;
    this.typing = lesson.typing ?? false;
    this.dictation = lesson.dictation ?? false;
    this.voice = lesson.voice;
    this.lastSaved = this.snapshot();
    this.saveState = "saved";
    this.revision = { text: "", busy: false, summary: "", stats: "", undo: null };
    this.$nextTick(() => this.$refs.review?.scrollIntoView({ behavior: "smooth" }));
  },

  async openLesson(id) {
    this.error = "";
    if (this.saveTimer) await this.saveNow();
    try {
      const lesson = await (await api(`/api/lessons/${id}`)).json();
      await this.loadPhotos(lesson);
      this.show(lesson);
      this.usePromptOf(lesson);
    } catch (e) {
      this.error = t("app.lessons.openFailed", { message: e.message });
    }
  },

  // A reopened lesson brings back the prompt it was generated with, so "Generate
  // again" starts from it; the saved prompt with that exact text is selected, if any.
  usePromptOf(lesson) {
    if (!lesson.prompt) return;
    const saved = this.prompts.find((c) => c.text === lesson.prompt);
    this.selectedId = saved?.id ?? null;
    this.form = saved
      ? { name: saved.name, text: saved.text, deck: saved.deck, voice: saved.voice, typing: saved.typing, dictation: saved.dictation }
      : { name: "", text: lesson.prompt, deck: "", voice: lesson.voice, typing: lesson.typing, dictation: lesson.dictation };
  },

  // The lesson's photos from the server, as blobs, so a generation can be run again.
  async loadPhotos(lesson) {
    const photos = [];
    for (let n = 1; n <= lesson.photo_count; n++) {
      const blob = await (await api(`/api/lessons/${lesson.id}/photos/${n}`)).blob();
      photos.push({ blob, url: URL.createObjectURL(blob), text: lesson.page_texts?.[n - 1] ?? "" });
    }
    this.clearPhotos();
    this.photos = photos;
  },

  async newLesson() {
    if (this.saveTimer) await this.saveNow();
    const left = this.lessonId && this.cards.length ? this.deck : "";
    this.clearPhotos();
    this.lessonId = null;
    this.lessonOwner = "";
    this.lessonShared = false;
    this.deck = "";
    this.cards = [];
    this.reverse = false;
    this.voice = "";
    this.typing = false;
    this.dictation = false;
    this.saveState = "";
    this.lessonPrompt = "";
    this.lessonChoice = "";
    this.lessonExported = false;
    this.photosEdited = false;
    this.frames = [];
    // Back to the saved prompt picked last (a reopened lesson may have left its own text)
    if (!this.current()) {
      this.selectedId = (this.prompts.find((c) => String(c.id) === storage("get")) ?? this.prompts[0])?.id ?? null;
    }
    this.selectPrompt();  // restores the selected prompt's text and voice
    window.scrollTo({ top: 0, behavior: "smooth" });
    if (left) this.notify(t("app.lessonKept", { deck: left }));
  },

  // A success message, gone after a while; `next`: it offers to start a new lesson
  notify(message, next = false) {
    this.success = message;
    this.successNext = next;
    setTimeout(() => { if (this.success === message) this.success = ""; }, next ? 12000 : 6000);
  },

  // Asks first; its cards in Anki only go when ticked (their review history goes with them)
  async deleteLesson(l) {
    this.removal = { open: true, lesson: l, checking: true, available: false, count: 0, anki: false, busy: false };
    try {
      const found = await (await api(`/api/lessons/${l.id}/anki-notes`)).json();
      if (this.removal.lesson?.id === l.id) Object.assign(this.removal, found);  // still this lesson's dialog
    } catch {}  // Anki unknown: the lesson alone
    if (this.removal.lesson?.id === l.id) this.removal.checking = false;
  },

  async confirmDeleteLesson() {
    const { lesson: l, anki } = this.removal;
    this.removal.busy = true;
    try {
      const r = await (await api(`/api/lessons/${l.id}?anki=${anki}`, { method: "DELETE" })).json();
      this.removal.open = false;
      if (r.anki_deleted) {
        this.notify(t("app.lessons.deletedInAnki", { count: r.anki_deleted }) + (r.synced ? " " + t("app.send.synced") : ""));
      }
      if (r.sync_error) this.error = t("app.lessons.deletedNoSync", { reason: errorMessage(r.sync_error) });
      if (l.id === this.lessonId) {
        clearTimeout(this.saveTimer);
        this.saveTimer = null;
        this.lessonId = null;
        await this.newLesson();
      }
      await this.loadLessons();
    } catch (e) {
      this.error = e.message;
    }
  },

  clearPhotos() {
    this.photos.forEach((p) => URL.revokeObjectURL(p.url));
    this.photos = [];
  },

  payload() {
    return {
      deck: this.deck,
      // Without the page's own fields: key, and _state, _panel, _subject, _drawing…
      cards: this.cards.map((card) =>
        Object.fromEntries(Object.entries(card).filter(([k]) => k !== "key" && !k.startsWith("_")))),
      voice: this.voice,
      reverse: this.reverse,
      typing: this.typing,
      dictation: this.dictation,
      shared: this.lessonShared,
      frames: this.frames,
      prompt: this.lessonPrompt,
      choice: this.lessonChoice,
    };
  },

  snapshot() {
    return JSON.stringify(this.payload());
  },

  scheduleSave() {
    this.saveState = "pending";
    clearTimeout(this.saveTimer);
    this.saveTimer = setTimeout(() => this.saveNow(), SAVE_DELAY);
  },

  async saveNow(keepalive = false) {
    clearTimeout(this.saveTimer);
    this.saveTimer = null;
    if (!this.lessonId || this.readOnly()) return;
    if (this.drawing || this.pictureJobs) return this.scheduleSave();  // after: the server is changing pictures
    const body = this.snapshot();
    // Before the request: otherwise clearing saveTimer re-runs the autosave effect,
    // which would see an unsaved snapshot and schedule the same save again.
    this.lastSaved = body;
    this.saveState = "saving";
    try {
      await api(`/api/lessons/${this.lessonId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body,
        keepalive,  // lets the request complete even if the page closes
      });
      this.saveState = this.snapshot() === body ? "saved" : "pending";
      this.loadLessons();
    } catch (e) {
      if (e.detail?.code === "lesson.read_only") {
        // Another Anki profile was opened just before this save: show the saved lesson.
        await this.openLesson(this.lessonId);
        return;
      }
      this.saveState = "error";  // not retried in a loop; the next edit saves again
    }
  },
};
