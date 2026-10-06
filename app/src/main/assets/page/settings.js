// The Android app's settings (admin.html): the licence and its account at the relay,
// AnkiDroid, the standing instructions, the lessons on the phone. Texts: "android" in
// the web page's i18n files; errors as the web page shows them (errorMessage).

const SAVE_DELAY = 800;  // ms: saved shortly after the last change

async function api(path, options = {}) {
  const res = await fetch(path, options);
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail ?? detail; } catch {}
    throw new Error(errorMessage(detail));
  }
  return res.json();
}

const json = (method, body) => ({ method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

document.addEventListener("alpine:init", () => {
  Alpine.data("settings", () => ({
    form: null,       // the settings (the key masked)
    account: null,    // the relay's answer for the key
    anki: null,       // { installed, permitted }
    data: null,       // { lessons, bytes }
    newKey: "",
    checking: false,
    saveState: "saved",
    saveTimer: null,
    error: "",
    notice: "",

    async init() {
      await i18nReady;
      try {
        this.form = await api("/api/admin/settings");
      } catch (e) {
        this.error = e.message;
        return;
      }
      this.loadAnki();
      this.loadData();
      if (this.form.has_key) this.loadAccount();
      // Back from AnkiDroid's permission dialog, or from installing it
      document.addEventListener("visibilitychange", () => {
        if (document.visibilityState === "visible") this.loadAnki();
      });
    },

    formatDate(iso) {
      Alpine.store("i18n").version;
      return new Date(iso).toLocaleDateString(I18N.locale, { day: "numeric", month: "long" });
    },

    async loadAccount() {
      this.account = null;
      try {
        this.account = await api("/api/admin/account");
      } catch (e) {
        this.error = e.message;
      }
    },

    async loadAnki() {
      try { this.anki = await api("/api/admin/anki"); } catch {}
    },

    async loadData() {
      try { this.data = await api("/api/admin/data"); } catch {}
    },

    // A new key: saved, then checked with the relay
    async saveKey() {
      if (!this.newKey.trim()) return;
      this.checking = true;
      try {
        this.form = await api("/api/admin/settings", json("PUT", { key: this.newKey.trim() }));
        this.newKey = "";
        await this.loadAccount();
      } catch (e) {
        this.error = e.message;
      } finally {
        this.checking = false;
      }
    },

    scheduleSave() {
      this.saveState = "pending";
      clearTimeout(this.saveTimer);
      this.saveTimer = setTimeout(() => this.saveNow(), SAVE_DELAY);
    },

    async saveNow() {
      clearTimeout(this.saveTimer);
      this.saveState = "saving";
      const { relay, instructions, card_helps } = this.form;
      try {
        const saved = await api("/api/admin/settings", json("PUT", { relay, instructions, card_helps }));
        this.form.relay = saved.relay;
        this.saveState = "saved";
      } catch (e) {
        this.saveState = "error";
        this.error = e.message;
      }
    },

    async allowAnki() {
      try { await api("/api/admin/anki/permission", { method: "POST" }); } catch (e) { this.error = e.message; }
    },

    async deleteLessons() {
      if (!confirm(t("android.data.confirm"))) return;
      try {
        await api("/api/admin/lessons", { method: "DELETE" });
        this.notice = t("android.data.deleted");
        this.loadData();
      } catch (e) {
        this.error = e.message;
      }
    },
  }));
});
