// The Android app's settings (admin.html): the licence and its account at the relay,
// AnkiDroid, the standing instructions, the lessons on the phone. Texts: "android" in
// the web page's i18n files; errors as the web page shows them (errorMessage).

const SAVE_DELAY = 800;  // ms: saved shortly after the last change

async function api(path, options = {}) {
  const res = await fetch(path, options);
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail ?? detail; } catch {}
    throw Object.assign(new Error(errorMessage(detail)), { code: detail?.code });
  }
  return res.json();
}

const json = (method, body) => ({ method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

document.addEventListener("alpine:init", () => {
  // whole: the settings page; false: only the settings themselves (unreachable.html)
  Alpine.data("settings", (whole = true) => ({
    ...voiceChoicePart,
    ...askConfirmPart,
    form: null,       // the settings (the key masked)
    account: null,    // the relay's answer for the key
    offers: [],       // the base plans Google Play offers ({ plan, price, trial_days }); none: not on sale
    trial: false,     // the free trial (no card) offered, by the first lesson: Google Play is there
    lapsed: "",       // the subscription ended, or on hold (a payment failed): the relay's code
    buying: false,
    anki: null,       // { installed, permitted }
    data: null,       // { lessons, bytes }
    transferring: "",  // "export" or "import" while the lessons' file is made or taken in
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
    asking: { open: false, message: "", ok: "", cancel: "", answer: null },  // a yes/no (ask-confirm.js)
    voiceList: [],    // the relay's voices, to choose one per language (voice-choice.js)

    async init() {
      await i18nReady;
      this.loadVoiceList();  // not waited for: only offered
      try {
        this.form = await api("/api/admin/settings");
      } catch (e) {
        this.error = e.message;
        return;
      }
      if (!whole) return;
      this.loadAnki();
      this.loadData();
      await this.loadSubscription();
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

    // What an ended subscription, or one on hold, asks of the parent (in the page's language)
    lapsedText() {
      Alpine.store("i18n").version;
      return this.lapsed ? errorMessage({ code: this.lapsed }) : "";
    },

    async loadAccount() {
      this.account = null;
      this.lapsed = "";
      try {
        this.account = await api("/api/admin/account");
        // Past its end: on hold (a payment to fix in Google Play), or ended
        if (this.account.ends_at && new Date(this.account.ends_at) <= new Date()) {
          this.lapsed = this.account.plan === "free_trial" ? "relay.trial_ended"
            : this.account.on_hold ? "relay.payment_pending" : "relay.subscription_ended";
        }
      } catch (e) {
        this.error = e.message;
        // Ended: subscribing again; on hold: Google Play's page, where the payment is fixed
        if (["relay.subscription_ended", "relay.payment_pending", "relay.trial_ended"].includes(e.code)) this.lapsed = e.code;
        // Unknown or ended (one mistyped): the app no longer keeps it, subscribing offered again
        if (e.code === "relay.invalid_key") {
          this.error = t("android.licence.refused");  // not "check it in the settings": they are open
          try { this.form = await api("/api/admin/settings"); } catch {}
        }
      }
    },

    // What Google Play offers; without a key, a subscription of this Google account restored
    async loadSubscription() {
      try {
        const found = await api("/api/admin/subscription");
        this.offers = found.offers;
        this.trial = found.trial;
        if (found.restored) {
          this.form = await api("/api/admin/settings");
          this.notice = t("android.subscription.restored");
        }
      } catch {}
    },

    // Google Play's purchase screen; bought, the relay's licence (its key kept by the app)
    async subscribe(plan) { await this.buy("/api/admin/subscription/subscribe", { plan }); },
    async restore() { await this.buy("/api/admin/subscription/restore"); },

    async buy(path, body = {}) {
      this.buying = true;
      this.error = "";
      try {
        const answer = await api(path, json("POST", body));
        if (answer.cancelled) return;
        if (answer.pending) {  // paid later: restored as the settings open once Google Play has it
          this.notice = t("android.subscription.pending");
          return;
        }
        this.account = answer;
        this.lapsed = "";
        this.form = await api("/api/admin/settings");
        this.notice = t("android.subscription.done");
      } catch (e) {
        this.error = e.message;
      } finally {
        this.buying = false;
      }
    },

    async manage() {
      try { await api("/api/admin/subscription/manage", { method: "POST" }); } catch {}
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

    // A debug build: the real relay or the test one, in one tap (each keeps its own licence)
    async useRelay(url) {
      if (url === this.form.relay) return;
      try {
        this.form = await api("/api/admin/settings", json("PUT", { relay: url }));
        this.account = null;
        if (this.form.has_key) await this.loadAccount();
      } catch (e) {
        this.error = e.message;
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
      const { relay, instructions, helps, tts_rate, voices } = this.form;
      try {
        const saved = await api("/api/admin/settings", json("PUT", { relay, instructions, helps, tts_rate, voices }));
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

    // The lessons in one file (LessonsTransfer): written where the user chooses, or taken in
    async exportLessons() {
      this.error = this.notice = "";
      this.transferring = "export";
      try {
        const r = await api("/api/admin/transfer/export", { method: "POST" });
        if (!r.cancelled) this.notice = t("admin.transfer.exported", { name: r.name });
      } catch (e) {
        this.error = e.message;
      } finally {
        this.transferring = "";
      }
    },

    async importLessons(event) {
      const file = event.target.files?.[0];
      event.target.value = "";  // the same file can be chosen again
      if (!file) return;
      this.error = this.notice = "";
      this.transferring = "import";
      try {
        const body = new FormData();
        body.append("file", file);
        this.notice = t("admin.transfer.imported", await api("/api/admin/transfer", { method: "POST", body }));
        this.loadData();
      } catch (e) {
        this.error = e.message;
      } finally {
        this.transferring = "";
      }
    },

    async deleteLessons() {
      if (!(await this.askConfirm(t("android.data.confirm")))) return;
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
