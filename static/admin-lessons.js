// The lessons: who they belong to, their access, deleted; what their AI calls cost.
// Methods of the settings page's Alpine component (admin.js), as `this`.

const lessonsPart = {
  // --- Lessons: who they belong to ------------------------------------------
  async loadLessons() {
    try {
      this.lessons = await this.request("/api/admin/lessons");
    } catch (e) {
      this.error = e.message;
    }
  },

  // Owner not among Anki's profiles (renamed or deleted): nobody can change the lesson.
  ownerMissing(l) {
    return Boolean(l.owner && this.lessons.profiles && !this.lessons.profiles.includes(l.owner));
  },

  // The lessons by owner (the Anki profiles in Anki's order, then those gone from Anki,
  // then the lessons without owner), then by subject: the deck's first level, as in
  // the app ("anglais" and "Anglais" together). The lessons themselves, not copies:
  // a change of access updates them in place.
  lessonTree() {
    const profiles = this.lessons?.profiles ?? [];
    const owners = new Map();
    for (const l of this.lessons?.lessons ?? []) {
      const owner = l.owner ?? "";
      if (!owners.has(owner)) owners.set(owner, { key: `owner:${owner}`, owner, count: 0, cost: null, subjects: new Map() });
      const group = owners.get(owner);
      group.count += 1;
      const cost = this.lessonCost(l);
      if (cost !== null) group.cost = (group.cost ?? 0) + cost;
      const name = deckParts(l.deck)[0] ?? t("app.lessons.noDeck");
      const subject = name.toLocaleLowerCase();
      if (!group.subjects.has(subject)) group.subjects.set(subject, { key: `subject:${subject}`, name, lessons: [] });
      group.subjects.get(subject).lessons.push(l);
    }
    const rank = (g) => (!g.owner ? 2 : profiles.includes(g.owner) || !this.lessons?.profiles ? 0 : 1);
    const order = (g) => (profiles.includes(g.owner) ? profiles.indexOf(g.owner) : profiles.length);
    return [...owners.values()]
      .sort((a, b) => rank(a) - rank(b) || order(a) - order(b) || a.owner.localeCompare(b.owner))
      .map((g) => ({ ...g, missing: this.ownerMissing(g), subjects: [...g.subjects.values()] }));
  },

  // A lesson under its subject: the rest of its deck name ("Leçon 2 › Phrases")
  lessonTitle(l) {
    const [head, ...rest] = deckParts(l.deck);
    return rest.length ? rest.join(" › ") : head ?? t("app.lessons.noDeck");
  },

  ownerChoices(l) {
    const profiles = this.lessons.profiles ?? [];
    return l.owner && !profiles.includes(l.owner) ? [l.owner, ...profiles] : profiles;
  },

  async setAccess(l, changes) {
    this.error = this.notice = "";
    try {
      Object.assign(l, await this.request(`/api/admin/lessons/${l.id}`, {
        method: "PUT", body: JSON.stringify(changes),
      }));
      this.notice = t("admin.lessons.changed", { deck: l.deck });
    } catch (e) {
      this.error = e.message;
      await this.loadLessons();  // show what is really saved
    }
  },

  // Its cards in Anki go only when confirmed (asked when the open profile has some)
  async deleteLesson(l) {
    if (!(await this.askConfirm(t("admin.lessons.confirmDelete", { deck: l.deck })))) return;
    this.error = this.notice = "";
    try {
      let count = 0;
      try {
        count = (await this.request(`/api/admin/lessons/${l.id}/anki-notes`)).count;
      } catch {}  // Anki unknown: the lesson alone
      const anki = count > 0 && (await this.askConfirm(t("admin.lessons.alsoAnki", { count }), {
        ok: t("admin.lessons.deleteCards"), cancel: t("admin.lessons.keepCards"),
      }));
      const r = await this.request(`/api/admin/lessons/${l.id}?anki=${anki}`, { method: "DELETE" });
      if (r.anki_deleted) this.notice = t("app.lessons.deletedInAnki", { count: r.anki_deleted });
      this.lessons.lessons = this.lessons.lessons.filter((x) => x.id !== l.id);
    } catch (e) {
      this.error = e.message;
    }
  },

  // --- AI costs (US dollars) --------------------------------------------
  formatCost(usd) {
    Alpine.store("i18n").version;
    if (usd === null || usd === undefined) return "—";
    if (usd < 1) {  // AI calls cost cents: "2.7 ¢" says more than "$0.03"
      const cents = (usd * 100).toLocaleString(I18N.locale, { maximumSignificantDigits: 2 });
      return t("admin.costs.cents", { cents });  // US cents: "¢" alone reads as euro cents
    }
    return usd.toLocaleString(I18N.locale, { style: "currency", currency: "USD" });
  },

  lessonCost(l) {
    const known = l.ai_calls.filter((c) => c.cost !== null);
    return known.length ? known.reduce((sum, c) => sum + c.cost, 0) : null;
  },

  // "1.4 ¢ · gemini-3.8-flash · 1 generation + 2 corrections"
  costLine(l) {
    const models = [...new Set(l.ai_calls.map((c) => c.model))].join(", ");
    const count = (kind) => l.ai_calls.filter((c) => c.kind === kind).length;
    const [extract, revise, picture] = [count("extract"), count("revise"), count("picture")];
    const estimate = l.ai_calls.some((c) => !c.exact && c.cost) ? "≈ " : "";
    const counts = [t("admin.costs.extracts", { count: extract })];
    if (revise) counts.push(t("admin.costs.revisions", { count: revise }));
    if (picture) counts.push(t("admin.costs.pictures", { count: picture }));
    return `💰 ${estimate}${this.formatCost(this.lessonCost(l))} · ${models} · ${counts.join(" + ")}`;
  },

  callLine(call) {
    const tokens = call.input_tokens === null ? "" : ` · ${t("admin.costs.tokens", {
      input: call.input_tokens.toLocaleString(I18N.locale), output: (call.output_tokens ?? 0).toLocaleString(I18N.locale),
    })}`;
    const cost = call.cost === null ? t("admin.costs.unknown") : (call.exact ? "" : "≈ ") + this.formatCost(call.cost);
    return `${this.formatDate(call.at)} · ${t(`admin.costs.kind.${call.kind}`)} · ${call.provider} · ${call.model}${tokens} · ${cost}`;
  },

  formatDate(iso) {
    Alpine.store("i18n").version;  // re-render when the language changes
    return new Date(iso).toLocaleDateString(I18N.locale, { day: "numeric", month: "short", year: "numeric" });
  },
};
