// The pictures of the open lesson's cards ("front: the picture of the word"): drawn, found
// among free pictures, the user's own photo; where each comes from.
// Methods of the page's Alpine component (app.js), as `this`.

const picturesPart = {
  pictureUrl(card) {
    return `/api/lessons/${this.lessonId}/pictures/${card.picture}`;
  },

  // A card's picture panel: what it should show (its own description; empty when it has
  // none: the AI then decides from the card), draw, find, the user's own photo, or none.
  togglePicturePanel(card) {
    card._panel = !card._panel;
    if (card._panel) card._subject = card.figure || card.picture_prompt || "";
  },

  async pictureAction(card, request) {
    if (this.saveTimer) await this.saveNow();  // the server must know the card
    card._drawing = true;
    this.pictureJobs++;
    this.error = "";
    try {
      const res = await (await api(`/api/lessons/${this.lessonId}/cards/${card.id}/picture${request.path ?? ""}`, request)).json();
      card.picture = res.card.picture;
      card.picture_source = res.card.picture_source ?? null;
      card.picture_prompt = res.card.picture_prompt;
      card.picture_search = res.card.picture_search ?? "";
      card.figure = res.card.figure;
      return res;
    } catch (e) {
      this.error = e.message;
      return null;
    } finally {
      card._drawing = false;
      this.pictureJobs--;
    }
  },

  // "✨ Image", the cheapest first: the AI decides from what was written (any language; none:
  // the card); a figure is drawn (cheap). A picture: free ones looked for, sorted by the AI;
  // one fits, it is the card's; several, the user picks (the AI's choice first); none, the
  // user is asked before the image model draws one (it costs)
  async makePicture(card) {
    card._found = null;
    card._ask = false;
    const had = card.picture_source?.page ?? "";  // "Change": not the one it has
    const res = await this.pictureAction(card, {
      path: "/make",
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ subject: card._subject ?? null }),
    });
    if (!res) return;
    card._subject = card.figure || card.picture_prompt;
    if (!res.search) return;  // a figure: drawn
    if (!this.off("pictures.search")) await this.searchPictures(card, res.search);
    const found = (card._found ?? []).filter((f) => !had || f.page !== had);
    if (found.length === 1) return this.chooseFound(card, found[0]);
    card._found = found.length ? found : null;
    if (!found.length) {
      if (this.off("pictures.draw")) this.error = t("app.pictures.none");
      else card._ask = true;
    }
  },

  // The user said yes: drawn by the image model (a figure: drawn again)
  async drawPicture(card) {
    card._ask = false;
    await this.pictureAction(card, { path: "/draw", method: "POST" });
  },

  // What a picture drawn by the image model costs, about (for `count` of them): "" when unknown
  drawingCost(count = 1) {
    if (this.drawingCredits) return t("app.pictures.costCredits", { count: this.drawingCredits * count });
    if (this.drawingUsd) return t("app.pictures.costUsd", { amount: (this.drawingUsd * count).toFixed(2) });
    return "";
  },

  async uploadPicture(card, event) {
    const file = event.target.files[0];
    event.target.value = "";
    if (!file) return;
    const body = new FormData();
    body.append("photo", await resize(file), "photo.jpg");
    return this.pictureAction(card, { method: "POST", body });
  },

  // Free pictures of the card's picture (its description, its search words: makePicture),
  // sorted by the AI, each source's as it answers (previews come as data)
  async searchPictures(card, words = "") {
    if (card._searching) return;
    const context = `${(card.front ?? "").trim()} → ${(card.back ?? "").trim()}`;
    const subject = (card.picture_prompt?.trim() || card._subject?.trim() || context).slice(0, 200);
    card._searching = true;
    card._found = [];  // each source's, as it answers
    this.error = "";
    try {
      const res = await api("/api/pictures/search", {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/x-ndjson" },
        body: JSON.stringify({ subject, context, words }),
      });
      if (!(res.headers.get("Content-Type") ?? "").includes("ndjson")) {
        card._found = (await res.json()).results;
        return;
      }
      for await (const item of ndjsonItems(res)) {
        if (item.error) throw itemError(item.error);
        if (item.found) card._found = [...card._found, ...item.found];
      }
    } catch (e) {
      this.error = e.message;
    } finally {
      card._searching = false;
    }
  },

  // Where the card's picture comes from, said in its panel ("" when it isn't known)
  pictureSourceText(card) {
    const origin = card.picture_source;
    if (!origin) return "";
    if (origin.source === "photo") return t("app.pictures.sourcePhoto");
    if (origin.source === "drawn") return origin.model ? t("app.pictures.sourceDrawnBy", { model: origin.model }) : t("app.pictures.sourceDrawn");
    const names = { commons: "Wikimedia Commons", openverse: "Openverse", pixabay: "Pixabay" };
    return t("app.pictures.sourceFound", { source: names[origin.source] ?? origin.source, licence: origin.licence });
  },

  // The sources of the pictures found, as their credit line says them
  foundSources(card) {
    const names = { commons: "Wikimedia Commons", openverse: "Openverse", pixabay: "Pixabay" };
    return [...new Set((card._found ?? []).map((f) => names[f.source]))].join(", ");
  },

  async chooseFound(card, found) {
    await this.pictureAction(card, {
      path: "/found",
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source: found.source, id: found.id }),
    });
    if (card.picture) card._found = null;
  },

  removePicture(card) {
    return this.pictureAction(card, { method: "DELETE" });
  },

  // The pictures the cards ask for: figures drawn, free pictures found; those none fits are
  // drawn by the image model only when the user says yes (`draw`: the banner's "Draw them")
  async drawPictures(draw = false) {
    if (this.readOnly() || !this.cards.some((c) => (c.picture_prompt || c.figure) && !c.picture)) return;
    if (this.saveTimer) await this.saveNow();
    this.drawing = true;
    this.toDraw = [];
    const lessonId = this.lessonId;
    try {
      const res = await (await api(`/api/lessons/${lessonId}/pictures`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ draw }),
      })).json();
      if (this.lessonId !== lessonId) return;  // another lesson opened meanwhile
      // With where each comes from: the next save would drop it otherwise
      const drawn = new Map(res.lesson.cards.map((c) => [c.id, c]));
      this.cards.forEach((c) => {
        const made = drawn.get(c.id);
        if (!c.picture && made?.picture) Object.assign(c, { picture: made.picture, picture_source: made.picture_source ?? null });
      });
      this.toDraw = res.to_draw ?? [];
      if (res.failures) {
        this.error = t("app.pictures.failed", { count: res.failures }) + (res.error ? ` ${errorMessage(res.error)}` : "");
      }
    } catch (e) {
      this.error = e.message;
    } finally {
      this.drawing = false;
    }
  },
};
