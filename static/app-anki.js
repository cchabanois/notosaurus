// What goes to Anki: the cards' audio, the direct send (AnkiConnect, AnkiDroid), a card explained, the .apkg.
// Methods of the page's Alpine component (app.js), as `this`.

const ankiPart = {
  // --- Audio ----------------------------------------------------------
  // A voice ("es-ES-ElviraNeural" on the computer, "es-ES-Chirp3-HD-Aoede" in the
  // Android app) → mp3 in the cards; Anki locale ("es_ES") → the device reads it aloud.
  isVoice(voice) {
    return /^[a-z]{2,3}-[A-Z]{2}-[\w-]+$/.test(voice);
  },

  hasAudio() {
    return this.isVoice(this.voice);
  },

  // What a card's sound says (as tts.spoken): its back; a dictation's sentence with a blank:
  // the sentence with the word, then the word, each on its line
  // (read on its own: tts.lines)
  spokenText(card) {
    const back = (card.back ?? "").trim();
    const sentence = (card.front ?? "").replace(/\s*\([^)]*\)/g, "").trim();
    const blank = /…|\.{3}|_{3,}/;
    if (!this.dictation || back.includes("\n") || !blank.test(sentence)) return back;
    const said = sentence.replace(blank, () => back);
    return `${said}${/[.!?]$/.test(said) ? "" : "."}\n${back}`;
  },

  play(text, voice = this.voice) {
    if (!text.trim()) return;
    const params = new URLSearchParams({ text, voice });
    if (this.lessonId) params.set("lesson", this.lessonId);  // kept in the lesson, reused on export
    if (this.rate) params.set("rate", this.rate);
    const audio = new Audio(`/api/tts?${params}`);
    // One voice at a time: listening again, or to another card, stops the one playing
    sounding?.pause();
    sounding = audio;
    // Only a load failure means the sound is really missing. play() may also
    // reject when playback start is interrupted (e.g. AbortError) while the
    // sound still plays, so its rejection alone is not an error for the user.
    audio.addEventListener("error", () => {
      this.error = t("app.audio.failed");
    });
    audio.play().catch((e) => {
      if (e.name === "NotAllowedError") this.error = t("app.audio.blocked");
      else console.warn("audio.play()", e);
    });
  },

  // --- Direct send (AnkiConnect) -------------------------------------
  async checkAnki() {
    const before = this.anki.profile;
    try {
      this.anki = await (await api("/api/anki/status")).json();
    } catch {
      this.anki = { available: false };
    }
    const now = this.anki.profile;
    // Another Anki profile opened (not at page load, not on the profile screen)
    if (before && now && now !== before) this.profileToApply = now;
    if (this.profileToApply) await this.applyProfile();
    this.followProfile();
    if (this.reviewInAnki && !this.ankiIcon) this.loadAnkiIcon();
  },

  // The app: AnkiDroid's own icon, as installed on this phone, for "Open AnkiDroid" (🎓 until
  // it is installed; asked again at most once a minute, so it appears once it is)
  async loadAnkiIcon() {
    if (Date.now() - this.ankiIconAsked < 60_000) return;
    this.ankiIconAsked = Date.now();
    try {
      const res = await fetch("/api/anki/icon", { headers: { "X-Notosaurus-Lang": I18N.lang } });
      if (res.ok) this.ankiIcon = URL.createObjectURL(await res.blob());
    } catch {}
  },

  // Follow an Anki profile switch: a lesson of the previous profile is saved and
  // closed, so nothing gets sent to the wrong collection. Waits for a generation,
  // correction or send in progress to finish, so their result isn't lost.
  async applyProfile() {
    if (this.loading || this.revision.busy || this.sending || this.exporting) return;
    const profile = this.profileToApply;
    this.profileToApply = null;
    this.loadLessons();  // the new profile's lessons
    if (this.lessonId && this.lessonOwner && !this.lessonShared && this.lessonOwner !== profile) {
      if (this.saveTimer) await this.saveNow();
      await this.newLesson();
    }
    const child = this.profileChild(profile);  // a profile per child: said with the child's name
    this.notify(child ? t("app.profile.switchedChild", { child: child.name }) : t("app.profile.switched", { profile }));
  },

  // Pictures being drawn or changed: the cards sent must have them
  async picturesDone() {
    while (this.drawing || this.pictureJobs) await new Promise((resolve) => setTimeout(resolve, 300));
  },

  async sendToAnki() {
    this.error = this.success = "";
    this.sending = true;
    try {
      await this.picturesDone();
      const r = await this.sendSteps(await api("/api/anki/send", {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/x-ndjson" },
        body: JSON.stringify({ ...this.payload(), lesson_id: this.lessonId }),
      }));
      this.lastSaved = this.snapshot();  // sending also saves the lesson
      this.lessonExported = true;
      clearTimeout(this.saveTimer);
      this.saveTimer = null;
      this.saveState = "saved";
      this.loadLessons();
      const parts = [];
      if (r.added) parts.push(t("app.send.added", { count: r.added }));
      if (r.updated) parts.push(t("app.send.updated", { count: r.updated }));
      if (r.converted) parts.push(t("app.send.converted", { count: r.converted }));
      if (r.moved) parts.push(t("app.send.moved", { count: r.moved }));
      let message = t("app.send.done", { parts: parts.join(", ") || t("app.send.nothing") });
      if (r.synced) message += " " + t("app.send.synced");
      this.notify(message, true);
      const warnings = [];
      if (r.sync_error) warnings.push(t("app.send.noSync", { reason: errorMessage(r.sync_error) }));
      if (r.audio_failures) warnings.push(t("app.send.noSound", { count: r.audio_failures }));
      if (r.conversion_unsupported) warnings.push(t("app.send.oldAnkiConnect"));
      // A note type gained a field or a card: Anki asks which side to keep at the next sync
      if (r.restructured?.length) warnings.push(t("app.send.restructured", { names: r.restructured.join(", ") }));
      if (warnings.length) this.error = t("app.send.butWarning", { warnings: warnings.join(" ; ") });
      // The lesson's notes no card has any more (deleted, or remade): delete them? (asked)
      if (r.leftovers?.length) this.leftovers = { open: true, notes: r.leftovers, lesson: this.lessonId, busy: false };
    } catch (e) {
      this.error = e.message;
      // The app without AnkiDroid: install it from the message (Google Play only when asked)
      if (e.detail?.code === "anki.android_missing") this.errorAction = { for: e.message, kind: "installAnki" };
      this.checkAnki();
    } finally {
      this.sending = false;
      this.sendStep = "";
    }
  },

  // The send's answer, its steps said on the button as they come (application/x-ndjson):
  // the backs' sounds made (most of the wait), then the cards; a server answering all at
  // once (an older one): its answer
  async sendSteps(res) {
    if (!(res.headers.get("Content-Type") ?? "").includes("ndjson")) return res.json();
    for await (const item of ndjsonItems(res)) {
      if (item.result) return item.result;
      if (item.error) throw itemError(item.error);
      if (item.step === "sounds") this.sendStep = t("app.actions.sendingSounds", { done: item.done, total: item.total });
      else if (item.step === "cards") this.sendStep = t("app.actions.sendingCards");
    }
    throw new Error(t("errors.unreachable"));
  },

  // AnkiDroid opened on its own screen (the app); missing: the message offers to install it
  async openAnkiDroid() {
    this.error = "";
    try {
      await api("/api/anki/open", { method: "POST" });
    } catch (e) {
      this.error = e.message;
      if (e.detail?.code === "anki.android_missing") this.errorAction = { for: e.message, kind: "installAnki" };
    }
  },

  // AnkiDroid's Google Play page; then "Add to Anki" again once it's installed and opened
  async installAnki() {
    this.error = "";
    try {
      await api("/api/anki/install", { method: "POST" });
    } catch (e) {
      this.error = e.message;
    }
  },

  // The lesson's deck opened in AnkiDroid, to review it now
  async reviewLesson() {
    this.success = "";
    try {
      await api("/api/anki/review", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ deck: this.deck }),
      });
    } catch (e) {
      this.error = e.message;
    }
  },

  // Changed here: kept on this device, whatever the settings' default
  // --- Explaining a card (💬) ------------------------------------------
  // The explanation first; then the follow-ups (an example, a way to remember it, why
  // the answer is right) the AI said would help with this card, one after the other.
  // A second 💬 just hides or shows what was already explained.
  // The welcome accepted: a parent, the privacy policy (saved by the app, with its version)
  async acceptWelcome() {
    this.welcome.busy = true;
    try {
      await api("/api/welcome", { method: "POST" });
      this.welcome.open = false;
    } catch (e) {
      this.error = e.message;
    } finally {
      this.welcome.busy = false;
    }
  },

  // "Delete from Anki" in the leftovers' dialog: their review history goes with them
  async deleteLeftovers() {
    const { lesson, notes } = this.leftovers;
    this.leftovers.busy = true;
    try {
      const r = await (await api(`/api/lessons/${lesson}/anki-notes/delete`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ids: notes.map((n) => n.id) }),
      })).json();
      this.leftovers.open = false;
      this.notify(t("app.lessons.deletedInAnki", { count: r.deleted }) + (r.synced ? " " + t("app.send.synced") : ""));
      if (r.sync_error) this.error = t("app.lessons.deletedNoSync", { reason: errorMessage(r.sync_error) });
    } catch (e) {
      this.leftovers.busy = false;
      this.error = e.message;
    }
  },

  async explain(card, kind = "explain") {
    card._explain ??= { open: false, blocks: [], more: [], loading: "", error: "", kept: false };
    const ex = card._explain;
    if (kind === "explain" && ex.blocks.length) {
      ex.open = !ex.open;
      return;
    }
    Object.assign(ex, { open: true, loading: kind, error: "" });
    const shown = Object.fromEntries(Object.entries(card).filter(([k]) => k !== "key" && !k.startsWith("_")));
    try {
      const r = await (await api(`/api/lessons/${this.lessonId}/explain`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ card: shown, kind }),
      })).json();
      ex.blocks.push({ kind, text: r.text });
      ex.kept = false;
      ex.more = kind === "explain" ? r.more : ex.more.filter((k) => k !== kind);
    } catch (e) {
      ex.error = e.message;
    } finally {
      ex.loading = "";
    }
  },

  // Kept in the card's info: on its back in Anki (saved as any edit)
  keepExplanation(card) {
    const text = card._explain.blocks.map((b) => b.text.trim()).join(" ");
    card.info = [card.info.trim(), text].filter(Boolean).join(" — ");
    card._explain.kept = true;
  },

  // --- Export ---------------------------------------------------------
  async exportApkg() {
    this.error = "";
    this.exporting = true;
    try {
      await this.picturesDone();
      const res = await api("/api/export", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...this.payload(), lesson_id: this.lessonId }),
      });
      this.lastSaved = this.snapshot();  // exporting also saves the lesson
      this.lessonExported = true;
      clearTimeout(this.saveTimer);
      this.saveTimer = null;
      this.saveState = "saved";
      this.loadLessons();
      // AnkiDroid opens the downloaded file by its type
      const url = URL.createObjectURL(new Blob([await res.blob()], { type: "application/apkg" }));
      const a = document.createElement("a");
      a.href = url;
      a.download = `${this.deck.replace(/[\\/:*?"<>|]+/g, " - ")}.apkg`;
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 10_000);
      const failures = Number(res.headers.get("X-Notosaurus-Audio-Failures") || 0);
      if (failures) this.error = t("app.export.noSound", { count: failures });
      else this.notify(t("app.export.done"), true);
    } catch (e) {
      this.error = e.message;
    } finally {
      this.exporting = false;
    }
  },
};
