// The prompts: chosen, edited, saved, copied, deleted.
// Methods of the page's Alpine component (app.js), as `this`.

// A Notosaurus prompt works without a photo once something to learn is written in it (a list
// of words, a topic): words added to its own text, a few at least; a comma put right, a word
// changed, isn't that. In any language: words counted, never their meaning.
const WORDS_WITHOUT_PHOTO = 3;

function addedWords(original, text) {
  const words = (t) => t.toLocaleLowerCase().match(/[\p{L}\p{N}]+/gu) ?? [];
  const left = new Map();
  for (const w of words(original)) left.set(w, (left.get(w) ?? 0) + 1);
  let added = 0;
  for (const w of words(text)) {
    if (left.get(w)) left.set(w, left.get(w) - 1);
    else added++;
  }
  return added;
}

const promptsPart = {
  // --- Prompts ---------------------------------------------------------
  // `initial`: the page's first load, which comes after the settings: a prompt chosen or
  // text written meanwhile stays (it was replaced by the last prompt used)
  async loadPrompts(selectId, initial = false) {
    try {
      this.prompts = await (await api("/api/prompts")).json();
    } catch (e) {
      this.error = t("app.prompt.unavailable", { message: e.message });
      return;
    }
    if (initial && (this.promptChosen || this.form.text.trim())) return;
    // Ids: the user's are numbers, Notosaurus's "notosaurus:…" (stored as text in the browser)
    const found = this.prompts.find((c) => String(c.id) === String(selectId)) ?? this.prompts[0];
    this.selectedId = found?.id ?? null;
    this.selectPrompt();
  },

  // Again, the selection kept (the free prompt too). The text shown follows the
  // prompt (now in the page's language) unless it was changed for this time.
  async reloadPrompts() {
    const keepText = this.selectedId === null || this.isModified();
    try {
      this.prompts = await (await api("/api/prompts")).json();
    } catch {
      return;  // the old list stays
    }
    if (this.selectedId !== null && !this.current()) this.selectedId = this.prompts[0]?.id ?? null;  // deleted meanwhile
    if (!keepText) this.selectPrompt();
  },

  current() {
    return this.prompts.find((c) => c.id === this.selectedId);
  },

  // The prompt can make cards without a photo: the free one with a text, the user's own
  // (what they wrote), a built-in one only once something was written in it (as is, it
  // has a lesson to read, not words: "Automatique", "Dictée"…)
  worksWithoutPhoto() {
    const prompt = this.current();
    if (!prompt) return this.form.text.trim() !== "";
    return !prompt.builtin || addedWords(prompt.text, this.form.text) >= WORDS_WITHOUT_PHOTO;
  },

  // What the big button at the bottom does now: make the cards from the photos, from the
  // prompt alone (it says what to learn), or take the lesson's photo first
  nextAction() {
    if (this.photos.length) return "generate";
    return this.worksWithoutPhoto() ? "prompt" : "photo";
  },

  // Most recently used prompts first (never used: oldest first), always
  // including the selected one.
  recentPrompts() {
    // Never used: in the server's order (Notosaurus's prompts as it lists them, then
    // the user's, oldest first). Not by id: ids are numbers or "notosaurus:…" strings.
    const order = new Map(this.prompts.map((c, i) => [c, i]));
    const byUse = [...this.prompts].sort(
      (a, b) => (b.used_at ?? "").localeCompare(a.used_at ?? "") || order.get(a) - order.get(b));
    const recent = byUse.slice(0, RECENT_PROMPTS);
    const selected = this.current();
    if (selected && !recent.includes(selected)) recent.splice(RECENT_PROMPTS - 1, 1, selected);
    return recent;
  },

  filteredPrompts() {
    const words = normalize(this.picker.query).split(/\s+/).filter(Boolean);
    return this.prompts
      .filter((c) => words.every((w) => normalize(`${c.name} ${c.text}`).includes(w)))
      .sort((a, b) => a.name.localeCompare(b.name, I18N.locale, { sensitivity: "base" }));
  },

  openPicker() {
    this.picker = { open: true, query: "" };
    this.$nextTick(() => this.$refs.pickerSearch.focus());
  },

  // "✏️ Free": a prompt for this time only (kept with the lesson, not in the list).
  // Voice "auto": a voice only when the backs are in a language being learned.
  chooseFree() {
    this.promptChosen = true;
    if (this.selectedId !== null) {
      this.selectedId = null;
      this.form = { name: "", text: "", deck: "", voice: "auto", typing: false, dictation: false, dictation_only: false };
    }
    this.$nextTick(() => this.$refs.promptText.focus());
  },

  choose(id) {
    this.promptChosen = true;
    this.selectedId = id;
    this.selectPrompt();
    this.picker.open = false;
  },

  selectPrompt() {
    const c = this.current();
    this.form = c
      ? { name: c.name, text: c.text, deck: c.deck, voice: c.voice, typing: c.typing, dictation: c.dictation, dictation_only: c.dictation_only ?? false }
      : { name: "", text: "", deck: "", voice: "", typing: false, dictation: false, dictation_only: false };
    if (c) storage("set", c.id);
  },

  // Text differing from the selected saved prompt (or no prompt selected, e.g. a
  // reopened lesson's own prompt): it can become a new saved prompt.
  canSaveAsNew() {
    const c = this.current();
    return this.form.text.trim() !== "" && (!c || c.text !== this.form.text);
  },

  isModified() {
    const c = this.current();
    return c && c.text !== this.form.text;
  },

  // Editor sheet: "new" = empty form, "edit" = the selected prompt,
  // "copy" = a new prompt starting from the text tweaked for this time.
  openEditor(mode) {
    const c = this.current();
    const base = mode === "new"
      ? { name: "", text: "", deck: "" }
      : { ...this.form };
    if (mode === "copy") base.name = "";
    // Notosaurus's prompts open read-only: "Duplicate" makes a copy to change
    const builtin = mode === "edit" && Boolean(c?.builtin);
    if (builtin) Object.assign(base, { name: c.name, text: c.text, deck: c.deck });
    this.editor = { open: true, id: mode === "edit" ? c.id : null, builtin, error: "", ...base };
    this.$nextTick(() => {
      if (!this.editor.name) this.$refs.editorName.focus();
    });
  },

  async saveEditor() {
    const { id, name, text, deck } = this.editor;
    if (!name.trim() || !text.trim()) {
      this.editor.error = t("app.editor.required");
      return;
    }
    try {
      const saved = await (await api(id ? `/api/prompts/${id}` : "/api/prompts", {
        method: id ? "PUT" : "POST",
        headers: { "Content-Type": "application/json" },
        // The voice and options: what the AI reads in the text, at each lesson
        body: JSON.stringify({
          name: name.trim(), text: text.trim(), deck: deck.trim(), voice: "auto",
          typing: false, dictation: false, dictation_only: false,
        }),
      })).json();
      this.editor.open = false;
      await this.loadPrompts(saved.id);
    } catch (e) {
      this.editor.error = t("common.failed", { message: e.message });
    }
  },

  // A copy of any prompt (Notosaurus's included), opened in the editor to be changed.
  async duplicatePrompt(prompt) {
    try {
      const copy = await (await api(`/api/prompts/${encodeURIComponent(prompt.id)}/duplicate`, { method: "POST" })).json();
      this.picker.open = false;
      await this.loadPrompts(copy.id);
      this.openEditor("edit");
    } catch (e) {
      this.error = t("common.failed", { message: e.message });
    }
  },

  // From the editor (the prompt being edited) or from the list of all prompts.
  async deletePrompt(prompt = null) {
    const inEditor = prompt === null;
    const { id, name } = inEditor ? this.editor : prompt;
    if (!id || !(await this.askConfirm(t("app.editor.confirmDelete", { name })))) return;
    try {
      await api(`/api/prompts/${id}`, { method: "DELETE" });
      if (inEditor) this.editor.open = false;
      await this.loadPrompts(id === this.selectedId ? null : this.selectedId);
    } catch (e) {
      const message = t("common.failed", { message: e.message });
      if (inEditor) this.editor.error = message;
      else this.error = message;
    }
  },

  // "✨ Tidy up": the instructions rewritten clear and short by the AI, every intention
  // kept and none added (typed in a hurry, or dictated); "↩" brings back the text
  // before, as long as the tidied one isn't changed.
  async tidyPrompt() {
    const before = this.form.text;
    if (!before.trim() || this.tidy.busy) return;
    this.tidy.busy = true;
    this.error = "";
    try {
      const res = await api("/api/prompt/rephrase", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: before }),
      });
      const { text } = await res.json();
      this.form.text = text;
      Object.assign(this.tidy, { before, after: text });
    } catch (e) {
      this.error = e.message;
    } finally {
      this.tidy.busy = false;
    }
  },

  // Offered for instructions someone wrote (free, one's own, or Notosaurus's once changed):
  // Notosaurus's own, as they are, are tidy already
  canTidy() {
    if (!this.form.text.trim()) return false;
    return !(this.current()?.builtin && !this.isModified());
  },

  canUntidy() {
    return this.tidy.before !== null && this.form.text === this.tidy.after;
  },

  untidyPrompt() {
    this.form.text = this.tidy.before;
    this.tidy.before = null;
  },
};
