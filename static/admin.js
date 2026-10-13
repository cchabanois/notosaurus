const PASSWORD_KEY = "notosaurus.admin";  // kept for the browser session only

// Names and descriptions: admin.provider.<id>.* in static/i18n/<lang>.json. The models
// suggested come from the server: Notosaurus's recommended ones (core/notosaurus_core/recommended.py),
// then every one the service lists.
const PROVIDERS = [
  { id: "gemini" },
  { id: "anthropic" },
  { id: "openai" },
  { id: "openrouter" },
  { id: "compatible", models: ["qwen2.5vl", "gemma3"] },  // examples of local vision models
  { id: "fake" },
];
// Speak OpenAI's API: their models can be listed from the service
const OPENAI_LIKE = ["openai", "openrouter", "compatible"];

// label / help: translation keys; keyUrl: where to create the key
const KEYS = {
  gemini: [{ field: "gemini_api_key", label: "admin.access.geminiKey", help: "admin.access.geminiHelp" }],
  anthropic: [{ field: "anthropic_api_key", label: "admin.access.anthropicKey", help: "admin.access.anthropicHelp" }],
  openai: [{ field: "openai_api_key", label: "admin.access.openaiKey", keyUrl: "https://platform.openai.com/api-keys" }],
  openrouter: [{ field: "openrouter_api_key", label: "admin.access.openrouterKey", keyUrl: "https://openrouter.ai/keys" }],
  compatible: [{ field: "compatible_api_key", label: "admin.access.compatibleKey" }],
};

// Card pictures: the services that draw (their models: the recommended ones, then every
// one the service lists, see loadPictureModels)
const PICTURE_SERVICES = ["gemini", "openai", "openrouter"];
const PICTURE_KEYS = { gemini: "gemini_api_key", openai: "openai_api_key", openrouter: "openrouter_api_key" };

const EDITABLE = ["llm", "model", "fallback_models", "compatible_base_url", "picture_service", "tts_rate", "ankiconnect_url", "anki_sync", "card_helps",
                  "instructions", "profile_instructions", "picture_model"];

const deckParts = (deck) => deck.split("::").map((part) => part.trim()).filter(Boolean);

function session(action, value) {
  try {
    if (action === "get") return sessionStorage.getItem(PASSWORD_KEY);
    if (action === "set") sessionStorage.setItem(PASSWORD_KEY, value);
    if (action === "remove") sessionStorage.removeItem(PASSWORD_KEY);
  } catch {}
  return null;
}

// The settings page's component; the setup assistant (setup.html) builds on it
function adminComponent() {
  return {
    providers: PROVIDERS,
    pictureServices: PICTURE_SERVICES,
    loadedModels: [],    // models listed by the OpenAI-like service
    modelsInfo: "",
    loadingModels: false,
    status: null,
    password: null,
    unlocked: false,
    saved: null,     // settings as returned by the server (keys masked)
    form: null,      // editable copy of the non-secret settings
    keys: {},        // key field → new value typed ("" = unchanged, null = clear)
    pw: { login: "", new: "", confirm: "" },
    saving: false,
    testing: false,
    testResult: null,
    pictureModels: {},    // service → every image model it lists (loaded once its key is saved)
    loadingPictureModels: false,
    testingPicture: false,
    pictureResult: null,  // the picture test: { ok, text, image }
    testingAnki: false,
    ankiResult: null,
    lessons: null,   // { lessons, profiles } from /api/admin/lessons (profiles: null = Anki closed)
    ankiStatus: null,  // /api/anki/status: profile, logged in to AnkiWeb (sync: null = unknown)
    saveState: "saved",  // "saved", "pending", "saving", "error": settings are saved as they change
    saveTimer: null,
    error: "",
    notice: "",
    phone: null,      // { url }: the link in the phones' QR code

    async init() {
      await i18nReady;
      const setTitle = () => { document.title = `Notosaurus · ${t("admin.title")}`; };
      setTitle();
      document.addEventListener("i18n:changed", setTitle);
      try {
        this.status = await (await fetch("/api/admin")).json();
      } catch {
        this.error = t("errors.unreachable");
        return;
      }
      if (!this.status.allowed) return;  // Anki add-on, opened from a phone: see the message
      // Settings are saved as they change, after a short pause (a model name being typed
      // isn't saved half-way); API keys only once their field is left (see commitKey).
      this.$watch("form", () => {
        if (this.dirty({ keys: false })) this.scheduleSave();
      });
      document.addEventListener("visibilitychange", () => {
        if (document.visibilityState === "hidden" && this.saveTimer) this.flush();
      });
      if (!this.status.password_needed) return this.load(null);  // add-on, on the computer
      const remembered = session("get");
      if (this.status.password_set && remembered) await this.load(remembered);
      this.$nextTick(() => this.$refs.login?.focus());
    },

    async request(path, options = {}) {
      const res = await fetch(path, {
        ...options,
        headers: { "Content-Type": "application/json", "X-Admin-Password": this.password ?? "", ...options.headers },
      });
      if (res.status === 401 && path !== "/api/admin/password") {
        this.lock();
        throw new Error(t("errors.admin.wrong_password"));
      }
      if (!res.ok) {
        let detail = res.statusText;
        try { detail = (await res.json()).detail ?? detail; } catch {}
        throw new Error(errorMessage(detail));
      }
      return res.status === 204 ? null : res.json();
    },

    async load(password) {
      this.password = password;
      try {
        this.show(await this.request("/api/admin/settings"));
        this.unlocked = true;
        if (password) session("set", password);
        this.loadLessons();
        this.loadAnkiStatus();
        this.loadPhone();
        this.autoLoadModels();
        this.autoLoadPictureModels();
      } catch (e) {
        this.error = e.message;
      }
    },

    show(saved) {
      this.saved = saved;
      // A copy: editing the form (profile_instructions is an object) mustn't change `saved`
      this.form = structuredClone(Object.fromEntries(EDITABLE.map((k) => [k, saved[k]])));
      this.keys = {};
    },

    unlock() {
      this.error = "";
      return this.load(this.pw.login);
    },

    lock() {
      session("remove");
      Object.assign(this, { unlocked: false, password: null, form: null, saved: null, testResult: null });
      this.pw.login = "";
    },

    // The methods, by section: admin-service.js, admin-pictures.js, admin-saving.js,
    // admin-anki.js, admin-lessons.js, admin-phones.js, admin-password.js (loaded before this file)
    ...servicePart,
    ...picturesPart,
    ...savingPart,
    ...ankiPart,
    ...lessonsPart,
    ...phonesPart,
    ...passwordPart,
  };
}

// The setup assistant: the AI and its key (checked), then the phone (its pairing seen
// as it happens), then ready. Everything else keeps its default (the settings page).
const SETUP_STEPS = ["ai", "phone", "done"];
const PAIRING_POLL_MS = 2000;

function setupComponent() {
  const admin = adminComponent();
  return {
    ...admin,
    steps: SETUP_STEPS,
    step: "ai",
    pairedAt: undefined,  // when a phone last paired, as the step began (undefined: not asked yet)
    phonePaired: false,
    pollTimer: null,

    async init() {
      await admin.init.call(this);
      document.title = `Notosaurus · ${t("setup.title")}`;
    },

    // The service the assistant suggests first: a free tier, and the best value in our tests
    recommended(id) {
      return id === "gemini";
    },

    // "Next" once the test says the model reads a photo and answers in JSON
    aiReady() {
      return Boolean(this.testResult?.ok);
    },

    go(step) {
      this.step = step;
      clearInterval(this.pollTimer);
      this.pollTimer = null;
      if (step === "phone") this.watchPairing();
      this.$nextTick(() => document.querySelector(".setup-step h2")?.focus());
    },

    // The QR code, then wait for a phone to open it: the server notes when one pairs
    async watchPairing() {
      await this.loadPhone();
      if (!this.phone) return;
      this.pairedAt = this.phone.paired_at;
      this.phonePaired = false;
      this.pollTimer = setInterval(async () => {
        try {
          const { paired_at } = await this.request("/api/admin/phone");
          if (paired_at && paired_at !== this.pairedAt) {
            this.phonePaired = true;
            clearInterval(this.pollTimer);
            this.pollTimer = null;
          }
        } catch {}  // the server restarting: try again at the next tick
      }, PAIRING_POLL_MS);
    },
  };
}

document.addEventListener("alpine:init", () => {
  Alpine.data("admin", adminComponent);
  Alpine.data("setup", setupComponent);
});
