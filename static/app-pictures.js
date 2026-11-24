// The pictures of the open lesson's cards ("front: the picture of the word"): drawn, found
// among free pictures, the user's own photo; where each comes from.
// Methods of the page's Alpine component (app.js), as `this`.

// A card's picture fields, as the server tells them (core's pictures.READY): its answer to a
// card's picture, a "ready" step, a lesson's cards (takePicture)
const PICTURE_FIELDS = ["picture", "picture_source", "figure", "figure_kind", "picture_prompt", "picture_search", "picture_on_back"];
// The free pictures' sources, as their credit line says them
const SOURCE_NAMES = { commons: "Wikimedia Commons", openverse: "Openverse", pixabay: "Pixabay" };

const picturesPart = {
  pictureUrl(card) {
    return `/api/lessons/${this.lessonId}/pictures/${card.picture}`;
  },

  // A card's picture panel: what it should show (its own description; empty when it has
  // none: the AI then decides from the card), draw, find, the user's own photo, or none.
  // The card's picture touched: in the card edited, its page full screen (what it shows, where it
  // comes from, changed, a photo of one's own, none), as a diagram's is, until « Terminé »;
  // elsewhere (a lesson read only), only shown large. A card without one: ⋯ → its page.
  openPicture(card) {
    if (!this.isEditing(card) || !this.lessonId) return this.openViewer([this.pictureUrl(card)], 0, card);
    card._menu = false;
    card._subject = card.figure || card.picture_prompt || "";
    this.pictureOpen = card.key;
  },

  async pictureAction(card, request) {
    if (this.saveTimer) await this.saveNow();  // the server must know the card
    card._drawing = true;
    card._check = null;  // about the picture it had
    card._triedQuick = false;  // (redrawFigure sets it again after a quick redraw)
    this.pictureJobs++;
    this.error = "";
    try {
      // Its steps shown on it as they begin (drawing, checked, drawn again…), as the batch's
      const asked = { ...request, headers: { ...(request.headers ?? {}), Accept: "application/x-ndjson" } };
      const res = await resultAsItComes(
        await api(`/api/lessons/${this.lessonId}/cards/${card.id}/picture${request.path ?? ""}`, asked),
        (step) => Object.assign(card, { _step: step.step, _problem: step.problem ?? "", _first: step.first ?? "" }),
      );
      if (!res) return null;  // cancelled: the card as it was
      this.takePicture(card, res.card);
      if (card.picture) card._previous = null;  // the figure a correction replaced: no longer drawn from
      return res;
    } catch (e) {
      this.error = e.message;
      return null;
    } finally {
      Object.assign(card, { _drawing: false, _step: "", _problem: "", _first: "" });
      this.pictureJobs--;
    }
  },

  // A card's picture fields taken from the server's (`from`): one an older server leaves out
  // kept as the card has it; no picture_source said, where it comes from isn't known
  takePicture(card, from) {
    for (const field of PICTURE_FIELDS) card[field] = from[field] ?? (field === "picture_source" ? null : card[field]);
    card.figure_kind ??= "";
    card.picture_search ??= "";
  },

  // "✨ Image", the cheapest first: the AI decides from what was written (any language; none:
  // the card); a figure is drawn (cheap). A picture: free ones looked for, sorted by the AI;
  // one fits, it is the card's; several, the user picks (the AI's choice first); none, the
  // user is asked before the image model draws one (it costs). A figure the AI turns into a
  // picture: the card keeps its figure until a picture replaces it (the search given up, it
  // is still the figure), the picture's fields kept in `_decided`, sent with the one chosen.
  // A figure a correction replaced, not drawn again since (its automatic drawing failed, or
  // not done yet): drawn again from it (`previous`, as drawPictures'), until one is drawn
  async makePicture(card) {
    card._found = null;
    card._ask = false;
    card._decided = null;
    const had = card.picture_source?.page ?? "";  // "Change": not the one it has
    const previous = card._previous && !card.picture ? { previous: card._previous } : {};
    const res = await this.pictureAction(card, {
      path: "/make",
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ subject: card._subject ?? null, ...previous }),
    });
    if (!res) return;
    card._decided = res.decided ?? null;
    // Decided for a figure, from nothing written (a figure stays one when it is): left as it
    // was, the card still the figure (written, the picture's description would be drawn as one)
    if (!card._decided) card._subject = card.figure || card.picture_prompt;
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
    const decided = this.pendingPicture(card);
    const res = await this.pictureAction(card, card._decided
      ? { path: "/draw", method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(decided) }
      : { path: "/draw", method: "POST" });
    if (res) card._decided = null;
  },

  // The picture makePicture decided for a figure, still to be chosen: sent with the one chosen
  // (found, drawn, one's own), the figure then replaced; {} when there is none
  pendingPicture(card) {
    return card._decided ? { decided: card._decided } : {};
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

  // Drawn again, told what the check found: quickly first (told the problem, it mostly gets
  // it right, four times faster), with the model's thinking from then on when found wrong
  // again; the figure it replaces shown faded meanwhile
  async redrawFigure(card) {
    const problem = card._check?.problem ?? "";
    const careful = Boolean(card._triedQuick) && !this.off("ai.careful");
    Object.assign(card, { _check: null, _replacing: this.pictureUrl(card) });
    try {
      const res = await this.pictureAction(card, {
        path: "/draw",
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ problem, careful }),
      });
      if (res) card._triedQuick = true;  // a careful one too: once thinking was paid for, never less
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
    if (card._decided) body.append("decided", JSON.stringify(card._decided));
    const res = await this.pictureAction(card, { method: "POST", body });
    if (res) card._decided = null;
    return res;
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
    if (origin.source === "lesson") return t("app.pictures.sourceLesson");
    if (origin.source === "drawn") return origin.model ? t("app.pictures.sourceDrawnBy", { model: origin.model }) : t("app.pictures.sourceDrawn");
    return t("app.pictures.sourceFound", { source: SOURCE_NAMES[origin.source] ?? origin.source, licence: origin.licence });
  },

  // The picture's page at its source, as a link: an https: address only (a lesson imported
  // or shared could hold anything there)
  pictureSourcePage(card) {
    const page = card?.picture_source?.page ?? "";
    return /^https:\/\//i.test(page) ? page : "";
  },

  // What the figures are drawn with, each with its licence and its page: the relay's on the
  // phone, the computer's own there (/api/credits); a package added is credited without a
  // new app
  async loadCredits() {
    try {
      this.credits = await (await api("/api/credits")).json();
    } catch {}  // the default links below
  },

  // What a figure was drawn with, credited with a link to each project's page: Typst and
  // its packages (picture_source.made_with: "ctz-euclide 0.3.0"), their pages as the credits
  // give them (the maps' data is no Typst package); [] for an SVG one
  figureCredits(card) {
    return (card?.picture_source?.made_with ?? []).map((item) => {
      const [name, version = ""] = item.split(" ");
      const known = this.credits.find((c) => c.name === name && c.version === version)
        ?? this.credits.find((c) => c.name === name);
      const url = known?.url ?? (name === "Typst" ? "https://typst.app" : `https://typst.app/universe/package/${name}`);
      return { name, version, url };
    });
  },

  // A figure's credit line, before its projects' links: who drew it
  figureCreditText(card) {
    return t("app.pictures.madeWith", { model: card?.picture_source?.model || "AI" });
  },

  // The sources of the pictures found, as their credit line says them
  foundSources(card) {
    return [...new Set((card._found ?? []).map((f) => SOURCE_NAMES[f.source]))].join(", ");
  },

  async chooseFound(card, found) {
    const res = await this.pictureAction(card, {
      path: "/found",
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source: found.source, id: found.id, ...this.pendingPicture(card) }),
    });
    if (res) card._decided = null;
    if (card.picture) card._found = null;
  },

  removePicture(card) {
    return this.pictureAction(card, { method: "DELETE" });
  },

  // The open lesson's pictures are being drawn (not another's, left while they were)
  drawingHere() {
    return this.drawingLessons.includes(this.lessonId);
  },

  // A card's picture shown on this side (`onBack`: with its answer), as it says: there, or
  // being made (asked for, and this lesson's being drawn)
  pictureShown(card, onBack) {
    return Boolean(card.picture_on_back) === onBack
      && Boolean(card.picture || card._drawing || ((card.picture_prompt || card.figure) && this.drawingHere()));
  },

  // The pictures the cards ask for: figures drawn, free pictures found; those none fits are
  // drawn by the image model only when the user says yes (`draw`: the banner's "Draw them")
  // One drawing at a time for a lesson (two drew the same cards, each paid): asked while one
  // runs, done again once it ends (a card a correction added meanwhile)
  async drawPictures(draw = false) {
    if (this.readOnly() || !this.cards.some((c) => (c.picture_prompt || c.figure) && !c.picture)) return;
    if (this.saveTimer) await this.saveNow();
    const lessonId = this.lessonId;
    if (this.drawingLessons.includes(lessonId)) {
      this.drawLater[lessonId] = Boolean(this.drawLater[lessonId] || draw);
      return;
    }
    this.drawingLessons.push(lessonId);
    this.toDraw = [];
    try {
      const res = await this.pictureSteps(lessonId, await api(`/api/lessons/${lessonId}/pictures`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/x-ndjson" },
        // A card whose picture a correction replaced: not the lesson's drawing again; its figure
        // drawn again from the one it had (previousFigure)
        body: JSON.stringify({
          draw,
          not_from_lesson: this.cards.filter((c) => c._notFromLesson && !c.picture).map((c) => c.id),
          previous: Object.fromEntries(this.cards.filter((c) => c._previous && !c.picture).map((c) => [c.id, c._previous])),
        }),
      }));
      // Cancelled (nothing drawn: the cards as they were), or another lesson opened meanwhile
      if (!res || this.lessonId !== lessonId) return;
      // With where each comes from: the next save would drop it otherwise
      const drawn = new Map(res.lesson.cards.map((c) => [c.id, c]));
      this.cards.forEach((c) => {
        const made = drawn.get(c.id);
        if (!c.picture && made?.picture) {
          this.takePicture(c, made);
          Object.assign(c, { _replacing: "", _previous: null });
        }
      });
      this.toDraw = res.to_draw ?? [];
      if (res.failures) {
        this.error = t("app.pictures.failed", { count: res.failures }) + (res.error ? ` ${errorMessage(res.error)}` : "");
      }
    } catch (e) {
      this.error = e.message;
    } finally {
      this.drawingLessons.splice(this.drawingLessons.indexOf(lessonId), 1);
      const later = this.drawLater[lessonId];
      delete this.drawLater[lessonId];
      if (this.lessonId === lessonId) {
        // (the one replaced shown until then; one drawn again on its own, by redrawFigure, its own)
        this.cards.forEach((c) => Object.assign(c, { _step: "", _problem: "", _first: "", ...(c._drawing ? {} : { _replacing: "" }) }));
        if (later !== undefined) this.drawPictures(later);
      }
    }
  },

  // The figure a correction replaced on a card (`old`, the card as it was), to draw the new one
  // from: where it came from (its sources, kept beside it until pruned) and its family; what the
  // correction asks changed, the rest kept. None when it had no sources (drawn anew)
  previousFigure(old, card) {
    if (!old?.figure || !card.figure || !old.picture_source?.sources?.length) return null;
    return { source: old.picture_source, kind: old.figure_kind ?? "" };
  },

  // The pictures' answer, each card's steps shown on it as they begin (resultAsItComes): a
  // figure drawn, checked, redrawn when wrong (its first one shown meanwhile, faded); a
  // picture looked for, drawn. Null when it was cancelled
  pictureSteps(lessonId, res) {
    return resultAsItComes(res, (step, item) => {
      const card = this.lessonId === lessonId && this.cards.find((c) => c.id === item.card);
      if (!card) return;
      if (step === "ready") {  // its picture, shown at once: not when the others are done
        if (!card.picture) {
          this.takePicture(card, item);
          card._previous = null;
        }
        Object.assign(card, { _step: "", _problem: "", _first: "" });
      } else Object.assign(card, { _step: step, _problem: item.problem ?? "", _first: item.first ?? "" });
    });
  },

  // What a card's picture is being made by, on it ("drawing…", "checked…", "drawn again…")
  pictureStepText(card) {
    const figure = Boolean(card.figure);
    const key = {
      deciding: "deciding", searching: "searching", checking: "checking", redrawing: "redrawing", lesson: "lesson",
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

  // The card's picture is its figure as drawn (an SVG): checked against its description, drawn
  // again when wrong. Any other (a photo found, drawn by the image model, the user's, even in a
  // figure's place): checked against its card, another one picked when wrong
  drawnFigure(card) {
    return Boolean(card.figure && card.picture?.endsWith(".svg"));
  },

  // The figure found wrong, shown faded while it's drawn again (never kept): the one being
  // replaced (redrawFigure), or a first one the server sent
  firstFigureUrl(card) {
    if (card._replacing) return card._replacing;
    return card._first ? `data:image/svg+xml;charset=utf-8,${encodeURIComponent(card._first)}` : "";
  },
};
