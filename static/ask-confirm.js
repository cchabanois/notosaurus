// A yes/no asked in the page's own sheet, not the browser's confirm() (which shows the
// page's address): the app's, the settings page's and the Android app's settings, each
// with the "asking" sheet in its HTML. Methods of the page's component, as `this`; it
// holds `asking`.

const askConfirmPart = {
  // Resolves true on the confirming button, false when cancelled or closed (a question
  // still open is answered no).
  askConfirm(message, { ok = t("common.delete"), cancel = t("common.cancel") } = {}) {
    this.asking.answer?.(false);
    return new Promise((resolve) => {
      this.asking = { open: true, message, ok, cancel, answer: resolve };
    });
  },

  answerConfirm(yes) {
    const answer = this.asking.answer;
    this.asking = { ...this.asking, open: false, answer: null };  // the text stays while it slides away
    answer?.(yes);
  },
};
