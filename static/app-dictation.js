// Dictation (the app's 🎤): what the user says, written into the instructions or the
// correction by the AI, which hears the recording (the relay). Only where the server
// can transcribe: the Android app.
// Methods of the page's Alpine component (app.js), as `this`.

const DICTATION_MAX = 120_000;  // ms: the recording stops by itself after 2 minutes

// Said after what was already there, on a line of its own
const joinDictated = (before, text) => (before.trim() ? `${before.trimEnd()}\n${text}` : text);

const dictationPart = {
  // `kind`: "prompt" (the instructions) or "correction" (the AI correction's field).
  // Once to start listening, again to stop: the text then comes into the field.
  async dictate(kind) {
    if (this.dictation.busy) return;
    if (this.dictation.listening === kind) return this.stopDictation();
    if (this.dictation.listening) return;  // the other field is listening
    this.error = "";
    try {
      await api("/api/dictation/start", { method: "POST" });
      this.dictation.listening = kind;
      this.dictation.timer = setTimeout(() => this.stopDictation(), DICTATION_MAX);
    } catch (e) {
      this.error = e.message;
    }
  },

  async stopDictation() {
    const kind = this.dictation.listening;
    if (!kind) return;
    clearTimeout(this.dictation.timer);
    this.dictation.listening = "";
    this.dictation.busy = kind;
    try {
      const res = await api("/api/dictation/stop", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ kind }),
      });
      const text = ((await res.json()).text ?? "").trim();
      if (!text) {
        this.error = t("app.dictation.nothing");
      } else if (kind === "prompt") {
        this.form.text = joinDictated(this.form.text, text);
      } else {
        this.revision.text = joinDictated(this.revision.text, text);
      }
    } catch (e) {
      this.error = e.message;
    } finally {
      this.dictation.busy = "";
    }
  },

  // The field waits for its text (listening, then written down): not typed into meanwhile
  dictating(kind) {
    return this.dictation.listening === kind || this.dictation.busy === kind;
  },

  // What the field is waiting for, said under it ("" when nothing)
  dictationStep(kind) {
    if (this.dictation.listening === kind) return "app.dictation.listening";
    return this.dictation.busy === kind ? "app.dictation.busy" : "";
  },

  // The 🎤's name (an i18n key, translated by the page with $t: it follows the language)
  micKey(kind) {
    if (this.dictation.listening === kind) return "app.dictation.stop";
    return this.dictation.busy === kind ? "app.dictation.busy" : "app.dictation.start";
  },
};
