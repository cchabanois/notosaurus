// The tests to prepare ("Contrôles", app/exams.py): lessons, whole or some of their
// cards, gathered under one tag on their notes in Anki, to revise together with Anki's
// custom study (by tag). Methods of the page's Alpine component (app.js), as `this`;
// it holds `exams`, `examSheet` and `examPick`.

const JSON_BODY = { "Content-Type": "application/json" };

const examsPart = {
  async loadExams() {
    try {
      this.exams = await (await api("/api/exams")).json();
    } catch {
      this.exams = [];
    }
  },

  examDate(exam) {
    if (!exam.date) return "";
    const date = new Date(exam.date + "T12:00:00");
    return date.toLocaleDateString(I18N.locale, { weekday: "long", day: "numeric", month: "long" });
  },

  examPast(exam) {
    return Boolean(exam.date) && exam.date < new Date().toISOString().slice(0, 10);
  },

  // The open lesson's part in a test (null: not in it)
  examPart(exam, lessonId = this.lessonId) {
    return exam.lessons.find((p) => p.lesson === lessonId) ?? null;
  },

  // As the lessons' sheet names a lesson: its deck's parts
  examLessonTitle(part) {
    return deckParts(part.deck).join(" › ") || t("app.lessons.noDeck");
  },

  // The review's button: the tests the open lesson is in, or "Test…"
  examButtonLabel() {
    const names = this.exams.filter((e) => this.examPart(e)).map((e) => e.name);
    return names.length ? t("app.exams.buttonIn", { names: names.join(", ") }) : t("app.exams.button");
  },

  // An id for a new test, from its name (as the lessons' folders: ASCII, dashes), unused
  examId(name) {
    const base = name.normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase()
      .replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 32).replace(/-+$/, "") || "exam";
    let id = base;
    for (let n = 2; this.exams.some((e) => e.id === id); n++) id = `${base}-${n}`;
    return id;
  },

  // The sheet: every test, with the open lesson's place in each; or one test's detail
  // `alone`: from the lessons' list, not about the open lesson (a new test starts empty)
  async openExams(exam = null, alone = false) {
    this.examSheet = {
      open: true, view: exam ? "detail" : "list", exam, alone, draft: { name: "", date: "" }, busy: false, error: "",
      copied: false, reviewed: "", sendingLeft: 0, adding: { query: "", chosen: [] },
    };
    await this.loadExams();
    if (exam) this.examSheet.exam = this.exams.find((e) => e.id === exam.id) ?? exam;
  },

  showExam(exam) {
    this.examSheet = { ...this.examSheet, exam, view: "detail", error: "", reviewed: "" };
  },

  backToExams() {
    this.examSheet = { ...this.examSheet, exam: null, view: "list", error: "" };
  },

  // The test saved (made, or its lessons changed): the list and the sheet follow
  async saveExam(exam, lessons) {
    const sheet = this.examSheet;
    sheet.busy = true;
    sheet.error = "";
    try {
      const body = { name: exam.name, date: exam.date, lessons: lessons.map(({ lesson, cards }) => ({ lesson, cards })) };
      const saved = await (await api(`/api/exams/${exam.id}`, { method: "PUT", headers: JSON_BODY, body: JSON.stringify(body) })).json();
      this.exams = this.exams.some((e) => e.id === exam.id) ? this.exams.map((e) => (e.id === exam.id ? saved : e)) : [...this.exams, saved];
      if (sheet.exam?.id === exam.id) sheet.exam = saved;
      if (saved.anki === false && saved.lessons.some((p) => p.in_anki)) this.notify(t("app.exams.ankiClosed"));
      return saved;
    } catch (e) {
      sheet.error = e.message;
      return null;
    } finally {
      sheet.busy = false;
    }
  },

  // A new test from the sheet's form, with the open lesson (whole) when there is one
  async createExam() {
    const draft = this.examSheet.draft;
    const name = draft.name.trim();
    if (!name) return;
    const lessons = this.lessonId && !this.examSheet.alone ? [{ lesson: this.lessonId, cards: null }] : [];
    const saved = await this.saveExam({ id: this.examId(name), name, date: draft.date }, lessons);
    if (saved) {
      this.examSheet.draft = { name: "", date: "" };
      this.showExam(saved);
    }
  },

  // Lessons added to the test from its sheet, whole (some cards: "Open and pick the cards"):
  // the child's lessons not in it yet, found by their name
  addable(exam) {
    const query = fold(this.examSheet.adding.query.trim());
    const inIt = new Set(exam.lessons.map((p) => p.lesson));
    return this.visibleLessons()
      .filter((l) => !inIt.has(l.id))
      .map((l) => ({ id: l.id, title: this.examLessonTitle(l) }))
      .filter((l) => !query || fold(l.title).includes(query));
  },

  startAdding() {
    this.examSheet = { ...this.examSheet, view: "add", adding: { query: "", chosen: [] }, error: "" };
  },

  toggleAdding(id) {
    const chosen = this.examSheet.adding.chosen;
    this.examSheet.adding.chosen = chosen.includes(id) ? chosen.filter((c) => c !== id) : [...chosen, id];
  },

  async finishAdding() {
    const exam = this.examSheet.exam;
    const added = this.examSheet.adding.chosen.map((lesson) => ({ lesson, cards: null }));
    const saved = await this.saveExam(exam, [...exam.lessons, ...added]);
    if (saved) this.showExam(saved);
  },

  // The open lesson in the test, whole, or out of it
  async toggleExamLesson(exam) {
    const part = this.examPart(exam);
    const lessons = part ? exam.lessons.filter((p) => p.lesson !== this.lessonId) : [...exam.lessons, { lesson: this.lessonId, cards: null }];
    await this.saveExam(exam, lessons);
  },

  async removeExamLesson(exam, part) {
    await this.saveExam(exam, exam.lessons.filter((p) => p.lesson !== part.lesson));
  },

  // Choosing the open lesson's cards for the test: a checkbox on each card, a bar to finish
  startPick(exam) {
    const part = this.examPart(exam);
    const selected = new Set(part ? (part.cards ?? this.cards.map((c) => c.id)) : []);
    this.examPick = { id: exam.id, name: exam.name, selected };
    this.examSheet.open = false;
  },

  // A lesson of the test that isn't open: opened, then its cards chosen
  async pickIn(exam, part) {
    this.examSheet.open = false;
    await this.openLesson(part.lesson);
    this.startPick(exam);
  },

  togglePick(card) {
    const selected = new Set(this.examPick.selected);
    if (selected.has(card.id)) selected.delete(card.id);
    else selected.add(card.id);
    this.examPick = { ...this.examPick, selected };
  },

  pickAll() {
    this.examPick = { ...this.examPick, selected: new Set(this.cards.map((c) => c.id)) };
  },

  cancelPick() {
    this.examPick = null;
  },

  async finishPick() {
    const pick = this.examPick;
    const exam = this.exams.find((e) => e.id === pick.id);
    if (!exam) {
      this.examPick = null;
      return;
    }
    if (this.saveTimer) await this.saveNow(); // every card has its id once saved
    const chosen = this.cards.map((c) => c.id).filter((id) => pick.selected.has(id));
    const others = exam.lessons.filter((p) => p.lesson !== this.lessonId);
    const whole = chosen.length === this.cards.length;
    const lessons = chosen.length ? [...others, { lesson: this.lessonId, cards: whole ? null : chosen }] : others;
    const saved = await this.saveExam(exam, lessons);
    this.examPick = null;
    // Not in Anki yet: sending it is the next step, offered on the message
    const next = this.anki.available && !this.off("anki.send") && !this.lessonExported ? "send" : false;
    if (saved) this.notify(t("app.exams.picked", { count: chosen.length, name: exam.name }), next);
  },

  async deleteExam(exam) {
    if (!(await this.askConfirm(t("app.exams.confirmDelete", { name: exam.name })))) return;
    try {
      await api(`/api/exams/${exam.id}`, { method: "DELETE" });
      this.exams = this.exams.filter((e) => e.id !== exam.id);
      this.backToExams();
    } catch (e) {
      this.examSheet.error = e.message;
    }
  },

  // The computer, Anki open: a filtered deck of the test's cards, made and shown in Anki
  async reviewExam(exam) {
    const sheet = this.examSheet;
    sheet.busy = true;
    sheet.error = "";
    sheet.reviewed = "";
    try {
      const body = JSON.stringify({ deck: t("app.exams.filteredDeck", { name: exam.name }) });
      const made = await (await api(`/api/exams/${exam.id}/review`, { method: "POST", headers: JSON_BODY, body })).json();
      sheet.reviewed = t("app.exams.reviewed", { count: made.count, deck: made.deck });
    } catch (e) {
      sheet.error = e.message;
    } finally {
      sheet.busy = false;
    }
  },

  // A test's lessons not (all) in Anki yet, sent from its sheet one after the other: the open
  // lesson as it stands (its unsaved edits too), the others as saved
  unsentLessons(exam) {
    return (exam?.lessons ?? []).filter((p) => p.in_anki < p.total);
  },

  async sendExamLessons(exam, parts) {
    const sheet = this.examSheet;
    sheet.busy = true;
    sheet.error = "";
    sheet.sendingLeft = parts.length;
    try {
      for (const p of parts) {
        const open = p.lesson === this.lessonId;
        if (open) await this.picturesDone();
        const lesson = open ? this.payload() : await (await api(`/api/lessons/${p.lesson}`)).json();
        const body = {
          deck: lesson.deck, cards: lesson.cards, voice: lesson.voice, rate: lesson.rate, reverse: lesson.reverse,
          typing: lesson.typing, dictation: lesson.dictation, dictation_only: lesson.dictation && lesson.dictation_only,
          frames: lesson.frames, lesson_id: p.lesson,
        };
        await api("/api/anki/send", { method: "POST", headers: JSON_BODY, body: JSON.stringify(body) });
        if (open) {
          this.lessonExported = true;
          this.lastSaved = this.snapshot();  // sending also saves the lesson
        }
        sheet.sendingLeft--;
      }
    } catch (e) {
      sheet.error = e.message;
    } finally {
      sheet.busy = false;
      sheet.sendingLeft = 0;
      await this.loadExams();  // how many of its cards are in Anki now
      sheet.exam = this.exams.find((e) => e.id === exam.id) ?? sheet.exam;
      this.loadLessons();
    }
  },

  // AnkiDroid's browser opened on the test's cards: its menu makes their filtered deck
  async browseExam(exam) {
    this.examSheet.error = "";
    try {
      await api("/api/anki/browse", { method: "POST", headers: JSON_BODY, body: JSON.stringify({ search: exam.search }) });
    } catch (e) {
      this.examSheet.error = e.message;
    }
  },

  async copyExamSearch(exam) {
    try {
      await navigator.clipboard.writeText(exam.search);
      this.examSheet.copied = true;
      setTimeout(() => { this.examSheet.copied = false; }, 1500);
    } catch {
      this.examSheet.error = exam.search; // no clipboard (plain http on some phones): shown to copy by hand
    }
  },
};
