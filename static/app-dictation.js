// Dictation (the app's 🎤): what the user says, written into the instructions or the
// correction by the AI, which hears the recording (the relay). Only where the server
// can transcribe: the Android app.
// Methods of the page's Alpine component (app.js), as `this`.

const DICTATION_MAX = 120_000;  // ms: the recording stops by itself after 2 minutes

// While listening, a tap anywhere else stops it as ⏹ does (the text written), and does only
// that: "Correct" tapped then doesn't send a request whose text isn't there yet. A "click",
// not a touch: none comes after a finger scrolling the page. The app gone to the background
// (a call, the home screen) stops it too.
let stopElsewhere = null;

// Said after what was already there, on a line of its own
const joinDictated = (before, text) => (before.trim() ? `${before.trimEnd()}\n${text}` : text);

const dictationPart = {
  // `kind`: "prompt" (the instructions), "correction" (the AI correction's field) or
  // "card:<key>" (a card's own correction, heard as a correction).
  // Once to start listening, again to stop: the text then comes into the field.
  async dictate(kind) {
    if (this.mic.busy) return;
    if (this.mic.listening === kind) return this.stopDictation();
    if (this.mic.listening) return;  // the other field is listening
    this.error = "";
    try {
      await api("/api/dictation/start", { method: "POST" });
      this.mic.listening = kind;
      this.mic.timer = setTimeout(() => this.stopDictation(), DICTATION_MAX);
      this.watchElsewhere();
    } catch (e) {
      this.error = e.message;
    }
  },

  watchElsewhere() {
    const tapped = (e) => {
      if (e.target.closest?.(".mic")) return;  // ⏹ itself
      e.preventDefault();
      e.stopPropagation();
      this.stopDictation();
    };
    const hidden = () => document.hidden && this.stopDictation();
    document.addEventListener("click", tapped, true);
    document.addEventListener("visibilitychange", hidden);
    stopElsewhere = () => {
      document.removeEventListener("click", tapped, true);
      document.removeEventListener("visibilitychange", hidden);
    };
  },

  async stopDictation() {
    const kind = this.mic.listening;
    if (!kind) return;
    stopElsewhere?.();
    stopElsewhere = null;
    clearTimeout(this.mic.timer);
    this.mic.listening = "";
    this.mic.busy = kind;
    try {
      const res = await api("/api/dictation/stop", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ kind: kind.startsWith("card:") ? "correction" : kind }),
      });
      const text = ((await res.json()).text ?? "").trim();
      if (!text) {
        this.error = t("app.dictation.nothing");
      } else if (kind === "prompt") {
        this.form.text = joinDictated(this.form.text, text);
      } else if (kind.startsWith("card:")) {
        const card = this.cards.find((c) => `card:${c.key}` === kind);
        if (card?._fix) card._fix.text = joinDictated(card._fix.text, text);
      } else {
        this.revision.text = joinDictated(this.revision.text, text);
      }
    } catch (e) {
      this.error = e.message;
    } finally {
      this.mic.busy = "";
    }
  },

  // The field waits for its text (listening, then written down): not typed into meanwhile
  dictating(kind) {
    return this.mic.listening === kind || this.mic.busy === kind;
  },

  // What the field is waiting for, said under it ("" when nothing)
  dictationStep(kind) {
    if (this.mic.listening === kind) return "app.dictation.listening";
    return this.mic.busy === kind ? "app.dictation.busy" : "";
  },

  // The 🎤's name (an i18n key, translated by the page with $t: it follows the language)
  micKey(kind) {
    if (this.mic.listening === kind) return "app.dictation.stop";
    return this.mic.busy === kind ? "app.dictation.busy" : "app.dictation.start";
  },
};
