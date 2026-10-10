// The settings' password: created, changed.
// Methods of the settings page's Alpine component (admin.js), as `this`.

const passwordPart = {
  async setPassword(current) {
    if (this.pw.new !== this.pw.confirm) {
      this.error = t("admin.mismatch");
      return false;
    }
    try {
      await this.request("/api/admin/password", {
        method: "POST",
        body: JSON.stringify({ current, new: this.pw.new }),
      });
    } catch (e) {
      this.error = e.message;
      return false;
    }
    const password = this.pw.new;
    this.pw.new = this.pw.confirm = "";
    return password;
  },

  async createPassword() {
    this.error = "";
    const password = await this.setPassword(null);
    if (!password) return;
    this.status.password_set = true;
    await this.load(password);
  },

  async changePassword() {
    this.error = "";
    const password = await this.setPassword(this.password);
    if (!password) return;
    this.password = password;
    session("set", password);
    this.notice = t("admin.changed");
  },
};
