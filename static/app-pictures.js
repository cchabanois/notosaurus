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
    card._check = null;  // about the picture it had
    this.pictureJobs++;
    this.error = "";
    try {
      // Its steps shown on it as they begin (drawing, checked, drawn again…), as the batch's
      const asked = { ...request, headers: { ...(request.headers ?? {}), Accept: "application/x-ndjson" } };
      const res = await resultAsItComes(
        await api(`/api/lessons/${this.lessonId}/cards/${card.id}/picture${request.path ?? ""}`, asked),
        (step) => Object.assign(card, { _step: step.step, _problem: step.problem ?? "", _first: step.first ?? "" }),
      );
      card.picture = res.card.picture;
      card.picture_source = res.card.picture_source ?? null;
      card.picture_prompt = res.card.picture_prompt;
      card.picture_search = res.card.picture_search ?? "";
      card.figure = res.card.figure;
      card.figure_kind = res.card.figure_kind ?? "";
      return res;
    } catch (e) {
      this.error = e.message;
      return null;
    } finally {
      Object.assign(card, { _drawing: false, _step: "", _problem: "", _first: "" });
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

  // "🔍 Check": the figure looked at by the AI against its description, on demand (never on
  // its own: a figure is drawn at once); something wrong, the user decides to draw it again
  async checkFigure(card) {
    Object.assign(card, { _check: null, _checking: true });
    this.error = "";
    try {
      const res = await api(`/api/lessons/${this.lessonId}/cards/${card.id}/picture/check`, { method: "POST" });
      card._check = await res.json();
    } catch (e) {
      this.error = e.message;
    } finally {
      card._checking = false;
    }
  },

  // Drawn again with the model's thinking, told what the check found; the figure it replaces
  // shown faded meanwhile
  async redrawFigure(card) {
    const problem = card._check?.problem ?? "";
    Object.assign(card, { _check: null, _replacing: this.pictureUrl(card) });
    try {
      await this.pictureAction(card, {
        path: "/draw",
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ problem }),
      });
    } finally {
      card._replacing = "";
    }
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

  // The open lesson's pictures are being drawn (not another's, left while they were)
  drawingHere() {
    return this.drawingLessons.includes(this.lessonId);
  },

  // The pictures the cards ask for: figures drawn, free pictures found; those none fits are
  // drawn by the image model only when the user says yes (`draw`: the banner's "Draw them")
  async drawPictures(draw = false) {
    if (this.readOnly() || !this.cards.some((c) => (c.picture_prompt || c.figure) && !c.picture)) return;
    if (this.saveTimer) await this.saveNow();
    const lessonId = this.lessonId;
    this.drawingLessons.push(lessonId);
    this.toDraw = [];
    try {
      const res = await this.pictureSteps(lessonId, await api(`/api/lessons/${lessonId}/pictures`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/x-ndjson" },
        body: JSON.stringify({ draw }),
      }));
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
      this.drawingLessons.splice(this.drawingLessons.indexOf(lessonId), 1);
      if (this.lessonId === lessonId) this.cards.forEach((c) => Object.assign(c, { _step: "", _problem: "", _first: "" }));
    }
  },

  // The pictures' answer, each card's steps shown on it as they begin (application/x-ndjson):
  // a figure drawn, checked, redrawn when wrong (its first one shown meanwhile, faded); a
  // picture looked for, drawn. A server answering all at once (an older one): its answer
  async pictureSteps(lessonId, res) {
    if (!(res.headers.get("Content-Type") ?? "").includes("ndjson")) return res.json();
    for await (const item of ndjsonItems(res)) {
      if (item.result) return item.result;
      if (item.error) throw itemError(item.error);
      const card = this.lessonId === lessonId && item.step && this.cards.find((c) => c.id === item.card);
      if (!card) continue;
      if (item.step === "ready") {  // its picture, shown at once: not when the others are done
        if (!card.picture) {
          Object.assign(card, {
            picture: item.picture, picture_source: item.picture_source ?? null, figure: item.figure ?? card.figure,
            figure_kind: item.figure_kind ?? card.figure_kind ?? "",
            picture_prompt: item.picture_prompt ?? card.picture_prompt, picture_search: item.picture_search ?? card.picture_search,
          });
        }
        Object.assign(card, { _step: "", _problem: "", _first: "" });
      } else Object.assign(card, { _step: item.step, _problem: item.problem ?? "", _first: item.first ?? "" });
    }
    throw new Error(t("errors.unreachable"));
  },

  // What a card's picture is being made by, on it ("drawing…", "checked…", "drawn again…")
  pictureStepText(card) {
    const figure = Boolean(card.figure);
    const key = {
      deciding: "deciding", searching: "searching", checking: "checking", redrawing: "redrawing",
      drawing: figure ? "drawingFigure" : "drawing",
    }[card._step];
    if (key) return t(`app.pictures.steps.${key}`);
    // Others already under way, not this one: its turn to come (a few at a time)
    if (!card._drawing && this.drawingHere() && this.cards.some((c) => c._step)) return t("app.pictures.steps.waiting");
    return t(figure ? "app.pictures.drawingFigure" : "app.pictures.drawing");
  },

  // Roughly how long, in seconds: a figure quick then checked; drawn again with thinking, longer
  pictureExpected(card) {
    if (card._step === "redrawing") return 40;
    return card.figure ? 10 : 15;
  },

  // The figure found wrong, shown faded while it's drawn again (never kept): the one being
  // replaced (redrawFigure), or a first one the server sent
  firstFigureUrl(card) {
    if (card._replacing) return card._replacing;
    return card._first ? `data:image/svg+xml;charset=utf-8,${encodeURIComponent(card._first)}` : "";
  },
};
