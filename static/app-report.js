// Content the AI made, reported by the user (Google Play's policy on generated content): the
// whole card as seen (its texts, its explanation, its picture), sent to Notosaurus with a reason. Only what the sheet
// shows goes: never the lesson's photos, nor the child's name. Where a host relays it
// (/api/config "report": the app).
// Methods of the page's Alpine component (app.js), as `this`.

const reportPart = {
  // The card's picture, if it goes with the report: the AI's or a free one, never the user's photo
  reportedPicture(card) {
    return Boolean(card?.picture) && card.picture_source?.source !== "photo";
  },

  openReport(card) {
    this.report = { open: true, card, reason: "", comment: "", sending: false, sent: false, error: "" };
  },

  // The content sent, as text (for Notosaurus to read: the fields' names in English): the
  // whole card as the user sees it, its explanation if shown, its picture's description
  reportContent() {
    const { card } = this.report;
    if (!card) return "";
    const lines = [`Front: ${card.front}`, `Back: ${card.back}`];
    if (card.choices.length) lines.push(`Choices: ${card.choices.join(" | ")}`);
    const helps = { info: card.info, fun_fact: card.fun_fact, explanation: card.explanation, mnemonic: card.mnemonic };
    for (const [name, text] of Object.entries(helps)) if (text) lines.push(`${name}: ${text}`);
    for (const block of card._explain?.blocks ?? []) lines.push(`${block.kind}: ${block.text}`);
    if (card.figure || card.picture_prompt) lines.push(`Picture: ${card.figure || card.picture_prompt}`);
    const origin = card.picture_source;
    if (origin && this.reportedPicture(card)) {
      lines.push(`Source: ${[origin.source, origin.model, origin.page].filter(Boolean).join(" · ")}`);
    }
    return lines.join("\n");
  },

  // The picture as a data URL (a reported picture: it goes with the report)
  async reportPicture() {
    const blob = await (await fetch(this.pictureUrl(this.report.card))).blob();
    return await new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result);
      reader.onerror = () => reject(reader.error);
      reader.readAsDataURL(blob);
    });
  },

  async sendReport() {
    const report = this.report;
    report.sending = true;
    report.error = "";
    try {
      const picture = this.reportedPicture(report.card) ? await this.reportPicture() : "";
      await api(`/api/lessons/${this.lessonId}/report`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ kind: "card", reason: report.reason, comment: report.comment.trim(), content: this.reportContent(), picture }),
      });
      report.sent = true;
    } catch (e) {
      report.error = e.message;
    } finally {
      report.sending = false;
    }
  },

  // Sent: the card removed, or only its picture, if the user wants
  async dropReported(what) {
    const { card } = this.report;
    this.report.open = false;
    if (what === "picture") await this.removePicture(card);
    else this.removeCard(card);
  },
};
