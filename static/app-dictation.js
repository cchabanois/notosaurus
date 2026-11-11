// Dictation (the app's 🎤): what the user says, written into the instructions or the
// correction. Heard by the phone's own speech recognition ("live"): its text shows in the
// field as it comes ("✨ Tidy up" cleans it after). A phone without one: recorded, then
// written by the AI, which hears the recording (the relay). Only where the server can
// listen: the Android app.
// Methods of the page's Alpine component (app.js), as `this`.

const DICTATION_MAX = 120_000;  // ms: the recording stops by itself after 2 minutes
const HEARD_EVERY = 300;  // ms: what the phone heard, asked this often while it listens

// While listening, a tap anywhere else stops it as ⏹ does (the text written), and does only
// that: "Correct" tapped then doesn't send a request whose text isn't there yet. A "click",
// not a touch: none comes after a finger scrolling the page. The app gone to the background
// (a call, the home screen) stops it too.
let stopElsewhere = null;

// Said after what was already there, on a line of its own
const joinDictated = (before, text) => (before.trim() ? `${before.trimEnd()}\n${text}` : text);

// A dictated field's text (`kind`: dictate's), and its text set
function dictatedText(app, kind) {
  if (kind === "prompt") return app.form.text;
  if (kind.startsWith("card:")) return app.cards.find((c) => `card:${c.key}` === kind)?._fix?.text ?? "";
  return app.revision.text;
}

function setDictated(app, kind, text) {
  if (kind === "prompt") app.form.text = text;
  else if (kind.startsWith("card:")) {
    const card = app.cards.find((c) => `card:${c.key}` === kind);
    if (card?._fix) card._fix.text = text;
  } else app.revision.text = text;
}

// The dictated text shown: the field scrolled to its end, where it was added (a long prompt
// kept it out of sight). Not focused: no keyboard opened over it.
function showDictated(kind) {
  const field = document.querySelector(`textarea[data-dictated="${CSS.escape(kind)}"]`);
  if (field) field.scrollTop = field.scrollHeight;
}

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
      const started = await (await api("/api/dictation/start", { method: "POST" })).json();
      this.mic.listening = kind;
      this.mic.before = dictatedText(this, kind);
      this.mic.timer = setTimeout(() => this.stopDictation(), DICTATION_MAX);
      this.watchElsewhere();
      if (started.live) this.followHeard(kind);
    } catch (e) {
      this.error = e.message;
    }
  },

  // The phone's text shown in the field as it hears it, after what was there
  followHeard(kind) {
    const ask = async () => {
      if (this.mic.listening !== kind) return;
      try {
        const heard = await (await api("/api/dictation/heard")).json();
        if (this.mic.listening !== kind) return;
        if (heard.text) {
          setDictated(this, kind, joinDictated(this.mic.before, heard.text));
          this.$nextTick(() => showDictated(kind));
        }
        if (heard.error) return this.stopDictation();  // said by the stop
      } catch {}  // the next one, then
      this.mic.heard = setTimeout(ask, HEARD_EVERY);
    };
    this.mic.heard = setTimeout(ask, HEARD_EVERY);
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
    clearTimeout(this.mic.heard);
    this.mic.listening = "";
    this.mic.busy = kind;
    const before = this.mic.before ?? dictatedText(this, kind);
    let text = "";
    try {
      const res = await api("/api/dictation/stop", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ kind: kind.startsWith("card:") ? "correction" : kind }),
      });
      text = ((await res.json()).text ?? "").trim();
      if (!text) this.error = t("app.dictation.nothing");
    } catch (e) {
      this.error = e.message;
    } finally {
      this.mic.busy = "";
      this.mic.before = null;
    }
    // Shown as heard while listening: now as said in full (nothing, or an error: as it was)
    setDictated(this, kind, text ? joinDictated(before, text) : before);
    if (text) this.$nextTick(() => showDictated(kind));
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
