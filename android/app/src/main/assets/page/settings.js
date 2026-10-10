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
  // whole: the settings page; false: only the settings themselves (unreachable.html)
  Alpine.data("settings", (whole = true) => ({
    form: null,       // the settings (the key masked)
    account: null,    // the relay's answer for the key
    anki: null,       // { installed, permitted }
    data: null,       // { lessons, bytes }
    newKey: "",
    checking: false,
    computerAddress: "",
    connecting: false,
    pairing: false,   // connecting a computer: its QR code (or address) asked for
    typing: false,    // its address typed rather than scanned
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
      if (!whole) return;
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
      const { relay, instructions, card_helps, tts_rate } = this.form;
      try {
        const saved = await api("/api/admin/settings", json("PUT", { relay, instructions, card_helps, tts_rate }));
        this.form.relay = saved.relay;
        this.saveState = "saved";
      } catch (e) {
        this.saveState = "error";
        this.error = e.message;
      }
    },

    // The add-on's Notosaurus: its QR code (or address) checked, then its page instead of ours
    async scanComputer() {
      await this.connect(() => api("/api/admin/computer/scan", { method: "POST" }));
    },

    async connectComputer() {
      await this.connect(() => api("/api/admin/computer", json("PUT", { address: this.computerAddress })));
    },

    async connect(request) {
      this.connecting = true;
      this.error = "";
      try {
        const answer = await request();
        if (answer.url) location.href = answer.url;
      } catch (e) {
        this.error = e.message;
      } finally {
        this.connecting = false;
      }
    },

    async useComputer() {
      try {
        location.href = (await api("/api/admin/mode", json("POST", { mode: "computer" }))).url;
      } catch (e) {
        this.error = e.message;
      }
    },

    onPhone() {
      return this.form?.mode !== "computer";
    },

    // "On this phone": back to it, or no computer to connect after all
    choosePhone() {
      if (this.onPhone()) this.pairing = this.typing = false;
      else this.usePhone();
    },

    // "On my computer": the known one, or connecting one
    chooseComputer() {
      if (this.form?.computer) this.useComputer();
      else this.pairing = true;
    },

    // The page these settings came from: the computer's in that mode, else the phone's
    back() {
      location.href = this.form?.mode === "computer" ? this.form.computer : "./";
    },

    async usePhone() {
      try {
        location.href = (await api("/api/admin/mode", json("POST", { mode: "phone" }))).url;
      } catch (e) {
        this.error = e.message;
      }
    },

    async allowAnki() {
      try {
        await api("/api/admin/anki/permission", { method: "POST" });
        this.loadAnki();
      } catch (e) {
        this.error = e.message;
      }
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
