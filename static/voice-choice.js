// The voice chosen per language variety, in the settings (the computer's and the app's):
// "es-ES" → Álvaro rather than Elvira. Without a choice, the language's usual voice
// (tts.voice_for, Speech.voiceFor). The voices are the service's: edge-tts on the computer,
// the relay's in the app (/api/voices). Methods of the settings page's component, as
// `this`; it holds form.voices ({locale: voice}) and voiceList.

let listening = null;  // the voice being heard

const voiceChoicePart = {
  async loadVoiceList() {
    try {
      const res = await fetch("/api/voices");
      this.voiceList = res.ok ? await res.json() : [];
    } catch {
      this.voiceList = [];  // offline: no choice offered
    }
  },

  // The varieties a voice can be chosen for, those chosen already left out
  voiceLocales() {
    const chosen = Object.keys(this.form?.voices ?? {});
    return [...new Set(this.voiceList.map((v) => v.locale))].filter((l) => !chosen.includes(l)).sort();
  },

  voicesOf(locale) {
    return this.voiceList.filter((v) => v.locale === locale);
  },

  // "Elvira · femme": its name without its locale and its service's words
  voiceLabel(v) {
    const name = v.voice.slice(v.locale.length + 1).replace(/Neural$/, "").split("-").pop();
    return `${name} · ${t(v.gender === "Female" ? "admin.voice.female" : "admin.voice.male")}`;
  },

  // "espagnol (Espagne)", in the page's language
  localeName(locale, lang = I18N.lang) {
    try {
      return new Intl.DisplayNames([lang], { type: "language" }).of(locale) ?? locale;
    } catch {
      return locale;
    }
  },

  addVoice(locale) {
    const first = this.voicesOf(locale)[0];
    if (first) this.form.voices = { ...this.form.voices, [locale]: first.voice };
  },

  setVoice(locale, voice) {
    this.form.voices = { ...this.form.voices, [locale]: voice };
  },

  removeVoice(locale) {
    const { [locale]: _, ...rest } = this.form.voices;
    this.form.voices = rest;
  },

  // Heard saying its language's name, in that language ("español (España)"). Played at
  // once (the tap allows the sound); a failure said, its reason asked again (the relay's
  // credits used up, unreachable…): an <audio> doesn't give the server's answer.
  listenVoice(locale, voice) {
    const url = `/api/tts?${new URLSearchParams({ text: this.localeName(locale, locale), voice })}`;
    const audio = new Audio(url);
    listening?.pause();  // one voice at a time
    listening = audio;
    audio.addEventListener("error", async () => {
      let message = t("app.audio.failed");
      try {
        const res = await fetch(url);
        if (!res.ok) message = errorMessage((await res.json()).detail) || message;
      } catch {}
      this.error = message;
    });
    audio.play().catch((e) => {
      if (e.name === "NotAllowedError") this.error = t("app.audio.blocked");
    });
  },
};
