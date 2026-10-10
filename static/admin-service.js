// The AI service that makes the cards: chosen, its keys, its models (recommended, listed), tested.
// Methods of the settings page's Alpine component (admin.js), as `this`.

const servicePart = {
  // The demo provider (canned cards, whatever the photo) is for tests and development
  // (NOTOSAURUS_LLM=fake): only listed when it is the saved choice.
  shownProviders() {
    return PROVIDERS.filter((p) => p.id !== "fake" || this.saved?.llm === "fake");
  },

  provider() {
    return PROVIDERS.find((p) => p.id === this.form.llm) ?? PROVIDERS[0];
  },

  // A model belongs to its provider: switching provider takes the saved one when
  // coming back to it, else the provider's default (shown in the field) instead of
  // keeping e.g. "claude-opus-5" for OpenAI.
  providerChanged() {
    this.form.model = this.form.llm === this.saved.llm ? this.saved.model : "";
    this.clearModels();
    this.autoLoadModels();
  },

  openaiLike() {
    return OPENAI_LIKE.includes(this.form.llm);
  },

  // Once the access is set (key, or address), the service's models list themselves:
  // OpenRouter's short list shows without a click (listing models is free).
  accessReady() {
    const ready = {
      openai: this.saved.openai_api_key,
      openrouter: this.saved.openrouter_api_key,
      compatible: this.saved.compatible_base_url,
    };
    return Boolean(ready[this.form.llm]) && this.form.llm === this.saved.llm;
  },

  autoLoadModels() {
    if (this.openaiLike() && this.accessReady() && !this.loadedModels.length && !this.loadingModels) this.loadModels();
  },

  clearModels() {
    this.loadedModels = [];
    this.modelsInfo = "";
  },

  // The recommended ones (the buttons below the field), then every model the service
  // lists: the field filters them as one types
  modelSuggestions() {
    const own = this.recommendedCards().map((m) => m.id);
    return [...new Set([...own, ...(this.provider().models ?? []), ...this.loadedModels])];
  },

  // Notosaurus's recommended models, in order (the first is the default)
  recommendedCards() {
    return this.saved?.recommended?.cards[this.form?.llm] ?? [];
  },

  // "⭐ Gemini 3.8 Flash · 1.3 ¢ · a free key's model"
  recommendedLabel(m, i) {
    const parts = [(i === 0 ? "⭐ " : "") + m.name, this.formatCost(m.cents / 100)];
    if (m.note) parts.push(t(`admin.recommended.notes.${m.note}`));
    return parts.join(" · ");
  },

  // Saved key (masked) for a key field
  savedKey(field) {
    return this.saved[field];
  },

  async loadModels() {
    this.modelsInfo = "";
    if (!(await this.flush())) return;  // the server lists with the saved address and key
    this.loadingModels = true;
    try {
      const { models, vision_only } = await this.request("/api/admin/models", { method: "POST" });
      this.loadedModels = models;
      // vision_only: the service says which models accept images; otherwise the test tells.
      const key = vision_only ? "admin.service.modelsVision" : "admin.service.modelsAll";
      this.modelsInfo = models.length ? t(key, { count: models.length })
        : t(vision_only ? "admin.service.noVisionModels" : "admin.service.noModels");
    } catch (e) {
      this.modelsInfo = `✗ ${e.message}`;
    } finally {
      this.loadingModels = false;
    }
  },

  keysForProvider() {
    return KEYS[this.form.llm] ?? [];
  },

  clearKey(field) {
    this.keys[field] = null;
  },

  async test() {
    this.testResult = null;
    if (!(await this.flush())) return;  // tests what is shown
    this.testing = true;
    try {
      const r = await this.request("/api/admin/test", { method: "POST" });
      // Notosaurus needs both: reading the lesson photo and answering in JSON.
      // r.quota: Gemini's chosen model has no quota for this key (free), a fallback answered
      const key = r.refused ? "admin.access.testRefused"
        : !r.json ? "admin.access.testNoJson"
        : !r.vision ? "admin.access.testNoVision" : r.quota ? "admin.access.testOkQuota" : "admin.access.testOk";
      this.testResult = { ok: Boolean(r.json && r.vision), text: t(key, r) };
    } catch (e) {
      this.testResult = { ok: false, text: `✗ ${e.message}` };
    } finally {
      this.testing = false;
    }
  },
};
