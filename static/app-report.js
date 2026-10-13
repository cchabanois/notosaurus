// Content the AI made, reported by the user (Google Play's policy on generated content): a
// card, its explanation or its picture, sent to Notosaurus with a reason. Only what the sheet
// shows goes: never the lesson's photos, nor the child's name. Where a host relays it
// (/api/config "report": the app).
// Methods of the page's Alpine component (app.js), as `this`.

const reportPart = {
  // What of the card can be reported: the card, its explanation (shown), its picture (not the user's photo)
  reportKinds(card) {
    const kinds = ["card"];
    if (card._explain?.blocks?.length) kinds.push("explanation");
    if (card.picture && card.picture_source?.source !== "photo") kinds.push("picture");
    return kinds;
  },

  openReport(card) {
    this.report = { open: true, card, kind: "card", reason: "", comment: "", sending: false, sent: false, error: "" };
  },

  // The content sent, as text (for Notosaurus to read: the fields' names in English)
  reportContent() {
    const { card, kind } = this.report;
    if (!card) return "";
    const lines = [`Front: ${card.front}`, `Back: ${card.back}`];
    if (kind === "explanation") {
      for (const block of card._explain?.blocks ?? []) lines.push(`${block.kind}: ${block.text}`);
    } else if (kind === "picture") {
      const origin = card.picture_source;
      lines.push(`Picture: ${card.figure || card.picture_prompt}`);
      if (origin) lines.push(`Source: ${[origin.source, origin.model, origin.page].filter(Boolean).join(" · ")}`);
    } else {
      if (card.choices.length) lines.push(`Choices: ${card.choices.join(" | ")}`);
      const helps = { info: card.info, fun_fact: card.fun_fact, explanation: card.explanation, mnemonic: card.mnemonic };
      for (const [name, text] of Object.entries(helps)) if (text) lines.push(`${name}: ${text}`);
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
      const picture = report.kind === "picture" ? await this.reportPicture() : "";
      await api(`/api/lessons/${this.lessonId}/report`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ kind: report.kind, reason: report.reason, comment: report.comment.trim(), content: this.reportContent(), picture }),
      });
      report.sent = true;
    } catch (e) {
      report.error = e.message;
    } finally {
      report.sending = false;
    }
  },

  // Sent: the card removed, if the user wants (the picture: removed from it)
  async dropReported() {
    const { card, kind } = this.report;
    this.report.open = false;
    if (kind === "picture") await this.removePicture(card);
    else if (kind === "card") this.removeCard(card);
  },
};
