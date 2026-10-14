// The phones: the link in their QR code, unpaired all at once.
// Methods of the settings page's Alpine component (admin.js), as `this`.

const phonesPart = {
  async loadPhone() {
    try {
      this.phone = await this.request("/api/admin/phone");
    } catch {}  // the section stays hidden
  },

  // A new token: every phone must scan the QR code again (one was lost or lent)
  async unpairPhones() {
    if (!(await this.askConfirm(t("admin.phones.confirmUnpair"), { ok: t("admin.phones.unpair") }))) return;
    try {
      this.phone = await this.request("/api/admin/phone/unpair", { method: "POST" });
      this.notice = t("admin.phones.unpaired");
    } catch (e) {
      this.error = e.message;
    }
  },
};
