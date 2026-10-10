// Card pictures: who draws them, with which model (recommended, listed), tested.
// Methods of the settings page's Alpine component (admin.js), as `this`.

const picturesPart = {
  // --- Card pictures: who draws them (same rule as pictures.service on the server)
  hasKey(service) {
    return Boolean(this.saved[PICTURE_KEYS[service]]);
  },

  drawingService() {
    const chosen = this.form.picture_service;
    if (chosen === "none") return "";
    if (chosen) return this.hasKey(chosen) ? chosen : "";
    if (PICTURE_SERVICES.includes(this.form.llm)) return this.hasKey(this.form.llm) ? this.form.llm : "";
    return ["openrouter", "gemini", "openai"].find((s) => this.hasKey(s)) ?? "";
  },

  recommendedPictures() {
    return this.saved?.recommended?.pictures[this.drawingService()] ?? [];
  },

  // The service's own list, once per service: what it lists is what can be chosen
  pictureSuggestions() {
    const drawing = this.drawingService();
    const own = this.recommendedPictures().map((m) => m.id);
    return [...new Set([...own, ...(this.pictureModels[drawing] ?? [])])];
  },

  autoLoadPictureModels() {
    const drawing = this.drawingService();
    if (drawing && !this.pictureModels[drawing] && !this.loadingPictureModels && !this.dirty()) this.loadPictureModels();
  },

  async loadPictureModels() {
    this.loadingPictureModels = true;
    try {
      const { service, models } = await this.request("/api/admin/pictures/models", { method: "POST" });
      if (models.length) this.pictureModels = { ...this.pictureModels, [service]: models };
    } catch {}  // the suggestions stay; the test says what is wrong with the service
    finally {
      this.loadingPictureModels = false;
    }
  },

  setPictureService(service) {
    if (service !== this.form.picture_service) this.form.picture_model = "";  // a model belongs to its service
    this.form.picture_service = service;
  },

  pictureSummary() {
    const name = (id) => t(`admin.provider.${id}.name`);
    const drawing = this.drawingService();
    const chosen = this.form.picture_service;
    if (chosen === "none") return t("admin.pictures.noneChosen");
    if (!drawing) return chosen ? t("admin.pictures.missingKey", { service: name(chosen) }) : t("admin.pictures.nobody", { cards: name(this.form.llm) });
    if (chosen) return t("admin.pictures.drawnBy", { service: name(drawing) });
    if (drawing === this.form.llm) return t("admin.pictures.drawnBySame", { service: name(drawing) });
    return t("admin.pictures.cantDraw", { cards: name(this.form.llm), service: name(drawing) });
  },

  // One real picture with the chosen service and model (a few cents): seen, with its cost
  async testPicture() {
    this.pictureResult = null;
    if (!(await this.flush())) return;
    this.testingPicture = true;
    try {
      const r = await this.request("/api/admin/pictures/test", { method: "POST" });
      const cost = r.cost === null ? t("admin.costs.unknown") : this.formatCost(r.cost);
      this.pictureResult = { ok: true, image: r.image, text: t("admin.pictures.testOk", { model: r.model, seconds: r.seconds, cost }) };
    } catch (e) {
      this.pictureResult = { ok: false, text: `✗ ${e.message}` };
    } finally {
      this.testingPicture = false;
    }
  },
};
