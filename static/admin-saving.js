// The settings saved as they change: what differs from the saved ones, when it is sent.
// Methods of the settings page's Alpine component (admin.js), as `this`.

const savingPart = {
  // What differs from the saved settings. `keys: false` leaves out API keys being
  // typed (a cleared key is always in: the 🗑 button is a deliberate action).
  changes({ keys = true } = {}) {
    const changes = {};
    const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
    for (const k of EDITABLE) if (!same(this.form[k], this.saved[k])) changes[k] = this.form[k];
    for (const [k, v] of Object.entries(this.keys)) {
      if (v === null) changes[k] = "";                        // clear
      else if (keys && v.trim()) changes[k] = v.trim();       // replace
    }
    return changes;
  },

  dirty(options) {
    return Boolean(this.form) && Object.keys(this.changes(options)).length > 0;
  },

  scheduleSave(delay = 900) {
    this.saveState = "pending";
    clearTimeout(this.saveTimer);
    this.saveTimer = setTimeout(() => this.flush({ keys: false }), delay);
  },

  // Save now what changed (with the typed keys unless `keys: false`).
  async flush({ keys = true } = {}) {
    clearTimeout(this.saveTimer);
    this.saveTimer = null;
    if (!this.dirty({ keys })) {
      if (this.saveState !== "error") this.saveState = "saved";
      return true;
    }
    return this.save({ keys });
  },

  // An API key is saved when its field is left (or Enter), never half-typed.
  commitKey(field) {
    if (this.keys[field]?.trim()) this.flush();
  },

  async save({ keys = true } = {}) {
    this.error = "";
    this.saving = true;
    this.saveState = "saving";
    const typed = { ...this.keys };
    try {
      const sent = this.changes({ keys });
      this.show(await this.request("/api/admin/settings", { method: "PUT", body: JSON.stringify(sent) }));
      if (!keys) {  // keys still being typed stay in their fields
        for (const [k, v] of Object.entries(typed)) if (v !== null && !(k in sent)) this.keys[k] = v;
      }
      this.saveState = this.dirty({ keys: false }) ? "pending" : "saved";
      this.autoLoadModels();  // a key or an address just saved
      this.autoLoadPictureModels();  // or the drawing service changed
      return true;
    } catch (e) {
      this.error = e.message;  // e.g. an address without http://: not saved, said here
      this.saveState = "error";
      return false;
    } finally {
      this.saving = false;
    }
  },
};
