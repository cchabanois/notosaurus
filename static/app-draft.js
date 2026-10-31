// The lesson in progress, kept by the host as the page changes it (app/draft.py; the Android
// app's Draft.kt): found again when the page opens again, back from the settings or a link,
// or the phone having closed the app meanwhile. Before the lesson is made: its photos and
// its prompt; once made (saved with its photos): which lesson is open.

const DRAFT_WAIT_MS = 500;  // a pause in the typing: sent then (on the same machine: quick)

const draftPart = {
  draftTimer: null,
  draftSent: "",        // what the host has of it (draftText)
  draftPhotosSent: "",  // its photos' addresses: sent again only when they change
  draftKept: false,     // kept from the start on (keepDraft): until then, found again first

  // What the host keeps, besides the photos: the open lesson, or the prompt (with its form:
  // a free one, or one changed for this time) and the photos' texts (a PDF's)
  draftText() {
    if (this.lessonId) return JSON.stringify({ lesson: this.lessonId });
    const prompt = { selected: this.selectedId, chosen: this.promptChosen, form: this.form };
    return JSON.stringify({ lesson: null, prompt, texts: this.photos.map((p) => p.text ?? "") });
  },

  draftPhotos() {
    return this.lessonId ? [] : this.photos;
  },

  // Nothing to find again: no lesson open, no photo, the prompt as it is saved
  draftEmpty() {
    return !this.lessonId && !this.photos.length && (this.selectedId === null ? !this.form.text.trim() : !this.isModified());
  },

  async saveDraft() {
    clearTimeout(this.draftTimer);
    this.draftTimer = null;
    const text = this.draftText();
    const photos = this.draftPhotos();
    const sig = photos.map((p) => p.url).join(" ");
    if (text === this.draftSent && sig === this.draftPhotosSent) return;
    try {
      if (this.draftEmpty()) {
        await api("/api/draft", { method: "DELETE" });
      } else {
        const body = new FormData();
        body.append("draft", text);
        if (sig !== this.draftPhotosSent) {
          body.append("photos_sent", "true");
          photos.forEach((p, i) => body.append("photos", p.blob, `photo-${i + 1}.jpg`));
        }
        await api("/api/draft", { method: "PUT", body });
      }
      [this.draftSent, this.draftPhotosSent] = [text, sig];
    } catch {}  // tried again at the next change
  },

  // Once the page has started (found again first): each change kept, a moment later; at
  // once when the page is left (the settings, another app)
  keepDraft() {
    this.draftKept = true;
    Alpine.effect(() => {
      this.draftText();
      this.draftPhotos().map((p) => p.url);
      clearTimeout(this.draftTimer);
      this.draftTimer = setTimeout(() => this.saveDraft(), DRAFT_WAIT_MS);
    });
    document.addEventListener("visibilitychange", () => {
      if (document.visibilityState === "hidden" && this.draftTimer) this.saveDraft();
    });
    // A link to another page of Notosaurus (⚙️, "Subscribe"): followed once it is kept
    document.addEventListener("click", async (e) => {
      const link = e.target.closest?.("a[href]");
      if (!link || !this.draftTimer || link.target || e.defaultPrevented) return;
      if (new URL(link.href, location.href).origin !== location.origin) return;
      e.preventDefault();
      await this.saveDraft();
      location.href = link.href;
    });
  },

  // The page opening: the lesson left in progress, as it was
  async restoreDraft() {
    let draft = {};
    try {
      draft = await (await api("/api/draft")).json();
    } catch {
      return;
    }
    if (draft.lesson) {
      if (this.lessons.some((l) => l.id === draft.lesson)) await this.openLesson(draft.lesson);
    } else if (draft.prompt || draft.photos) {
      if (draft.prompt) {
        this.selectedId = draft.prompt.selected ?? null;
        this.promptChosen = Boolean(draft.prompt.chosen);
        this.form = { ...this.form, ...draft.prompt.form };
      }
      for (let n = 1; n <= (draft.photos ?? 0); n++) {
        try {
          const blob = await (await api(`/api/draft/photos/${n}`)).blob();
          this.photos.push({ blob, url: URL.createObjectURL(blob), text: draft.texts?.[n - 1] ?? "" });
        } catch {}  // one missing: the others
      }
    }
    // What the host has: not sent again as a change
    this.draftSent = this.draftText();
    this.draftPhotosSent = this.draftPhotos().map((p) => p.url).join(" ");
  },
};
