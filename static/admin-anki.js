// Anki: its status (profile, AnkiWeb), the connection tested.
// Methods of the settings page's Alpine component (admin.js), as `this`.

const ankiPart = {
  async loadAnkiStatus() {
    try {
      this.ankiStatus = await (await fetch("/api/anki/status")).json();
    } catch {
      this.ankiStatus = null;
    }
  },

  // In the add-on, Notosaurus talks to its own bridge (which mimics AnkiConnect):
  // don't mention AnkiConnect there. The open profile tells it's the right one.
  ankiOk(r) {
    if (!r.profile) return t("admin.anki.testNoProfile");
    return t(this.saved.embedded ? "admin.anki.testOkAddon" : "admin.anki.testOk", r);
  },

  async testAnki() {
    this.ankiResult = null;
    if (!(await this.flush())) return;
    this.testingAnki = true;
    try {
      const r = await (await fetch("/api/anki/status")).json();
      this.ankiStatus = r;
      this.ankiResult = r.available
        ? { ok: true, text: this.ankiOk(r) }
        : { ok: false, text: `✗ ${errorMessage(r.error)}` };
    } catch {
      this.ankiResult = { ok: false, text: `✗ ${t("errors.unreachable")}` };
    } finally {
      this.testingAnki = false;
    }
  },
};
