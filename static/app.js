const MAX_SIDE = 1600;   // px: enough to read a page, light to upload
const JPEG_QUALITY = 0.85;
const LAST_PROMPT = "notosaurus.prompt";

// Case- and accent-insensitive form, for search.
const normalize = (text) => text.normalize("NFD").replace(/\p{Diacritic}/gu, "").toLowerCase();

async function api(path, options = {}) {
  // The server uses the page's language for default prompts and AI summaries.
  const headers = { "X-Notosaurus-Lang": I18N.lang, ...options.headers };
  const res = await fetch(path, { ...options, headers });
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail ?? detail; } catch {}
    const error = new Error(errorMessage(detail));
    Object.assign(error, { status: res.status, detail });
    throw error;
  }
  return res;
}

// A lesson made as the AI writes it (application/x-ndjson, one JSON per line): each
// card told to `onCard` as it comes (null: start again), then the lesson; null when
// it was cancelled. A server that answers all at once (the Android app's): its lesson.
async function lessonAsItComes(res, onCard) {
  if (!(res.headers.get("Content-Type") ?? "").includes("ndjson")) return res.json();
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done });
    let end;
    while ((end = buffer.indexOf("\n")) >= 0) {
      const line = buffer.slice(0, end).trim();
      buffer = buffer.slice(end + 1);
      if (!line) continue;
      const item = JSON.parse(line);
      if (item.lesson) return item.lesson;
      if (item.cancelled) return null;
      if (item.error) throw Object.assign(new Error(errorMessage(item.error)), { detail: item.error });
      onCard(item.card ?? null);
    }
    if (done) throw new Error(t("errors.unreachable"));
  }
}

// A card's text as it shows while it is being made: the gaps' words, not their syntax
function plainCardText(text) {
  return (text ?? "").replace(/\{\{c\d+::(.*?)(::[^}]*)?\}\}/g, "[$1]");
}

function storage(action, value, key = LAST_PROMPT) {
  try {
    if (action === "get") return localStorage.getItem(key);
    localStorage.setItem(key, value);
  } catch {}
}
const HELPS = "notosaurus.helps";  // the "helps on the back" switch, once changed on this device
const FUN_FACTS = "notosaurus.funFacts";  // the "did you know" switch, kept on this device
const CAREFUL = "notosaurus.careful";  // "Careful" chosen over "Quick" (the default), kept on this device
const OPEN_SUBJECTS = "notosaurus.openSubjects";  // subjects opened or closed in the lessons, on this device
const MANY_LESSONS = 8;  // beyond: a search, the recent lessons first, the subjects folded
const RECENT_LESSONS = 3;
// For a search: no case, no accents ("lecon" finds "Leçon")
const fold = (text) => text.normalize("NFD").replace(/\p{M}/gu, "").toLocaleLowerCase();
const deckParts = (deck) => deck.split("::").map((part) => part.trim()).filter(Boolean);

const RECENT_PROMPTS = 4;  // chips shown before "All"
const SAVE_DELAY = 800;  // ms: save shortly after the last edit
const PROFILE_POLL = 3000;  // ms: follow Anki profile switches (local request, only while visible)

let sounding = null;  // the sound playing (play): stopped when another starts

const formatDate = (iso) =>
  new Date(iso).toLocaleString(I18N.locale, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

// Formulas: MathJax syntax, \( … \) within text, \[ … \] on their own (as in Anki)
const MATH = /\\\((.+?)\\\)|\\\[(.+?)\\\]/gs;
const HAS_MATH = /\\\(|\\\[/;  // as core/notosaurus_core/tts.py: no read-aloud for these
const CLOZE = /\{\{c\d+::/;  // a gap, as core/notosaurus_core/cards.py: {{c1::1789}}
// Outside formulas: a gap's start ({{c2::) and its end, with an optional hint (::lieu}})
const GAP_START = /\{\{c(\d+)::/g;
const GAP_END = /(?:::[^{}]*?)?\}\}/g;
const escapeHtml = (text) => text.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);

let nextKey = 0;
const withKey = (card) =>
  ({ info: "", fun_fact: "", explanation: "", mnemonic: "", choices: [], subdeck: "", tags: [], picture: "", picture_prompt: "", figure: "", picture_on_back: false, ...card, key: nextKey++ });

// A card's stable id (crypto.randomUUID needs HTTPS; getRandomValues doesn't)
const newId = () => [...crypto.getRandomValues(new Uint8Array(6))].map((b) => b.toString(16).padStart(2, "0")).join("");

document.addEventListener("alpine:init", () => {
  Alpine.data("notosaurus", () => ({
    photos: [],          // { blob, url }
    prompts: [],
    selectedId: null,
    promptChosen: false,         // a prompt picked (or "Free") by the user: the first load keeps it
    form: { name: "", text: "", deck: "", voice: "", typing: false, dictation: false },
    voices: [],          // edge-tts voices: { voice, locale, gender }
    deck: "",
    cards: [],
    reverse: false,
    voice: "",                   // the open lesson's voice (the prompt's may be "auto": form.voice)
    decks: [],                   // existing deck names, for the deck field
    lessonChoice: "",            // what the AI chose to make (prompt "Automatic")
    lessonExported: false,       // already sent to Anki or exported
    photosEdited: false,         // photos added or removed since the lesson was shown
    typing: false,               // the answer is typed in Anki
    dictation: false,            // a dictation card: hear the back, type it
    funFacts: storage("get", undefined, FUN_FACTS) === "1",  // ask for "did you know" facts (off by default)
    // Quick by default: the AI thinks little, 2 to 4 times faster; "Careful" for a rich lesson
    quick: storage("get", undefined, CAREFUL) !== "1",
    madeQuick: false,  // the open lesson was just made quick: "Careful, again" offered
    coming: [],  // the cards being made, as the AI writes them: shown while waiting
    errorAction: { for: "", kind: "" },  // a button on that error's message ("installAnki")
    generating: "",  // the id of the lesson being made: what "Cancel" stops
    cancelling: false,
    loadingQuick: false,
    helps: false,  // ask for helps on the back: as changed on this device, else the settings' default
    lessons: [],         // saved lesson summaries
    lessonId: null,       // open lesson (null = new lesson, not generated yet)
    saveState: "",       // "", "pending", "saving", "saved", "error"
    lastSaved: "",
    saveTimer: null,
    loading: false,
    exporting: false,
    lessonsOpen: false,
    maxPhotos: 10,       // pages per lesson (the server's limit, from /api/config)
    configured: true,    // an AI service with its key: until then, the setup assistant is offered
    pdfBusy: false,      // a PDF's pages being drawn
    dropTile: "",        // "gallery" or "pdf": a file dragged over it (the computer)
    pdf: { open: false, name: "", free: 0, pages: [] },  // its page picker
    lessonQuery: "",
    // "✨ Tidy up" the instructions: the text before kept for "↩", while the tidied one is unchanged
    tidy: { busy: false, before: null, after: "" },
    // The 🎤 of the instructions and the correction (the app): the field listening, or being written
    mic: { available: false, listening: "", busy: "", timer: null },
    openSubjects: (() => { try { return JSON.parse(storage("get", undefined, OPEN_SUBJECTS)) ?? {}; } catch { return {}; } })(),
    picker: { open: false, query: "" },
    // Natural-language correction of the cards; `undo` holds the previous version.
    revision: { text: "", busy: false, summary: "", stats: "", undo: null },
    successNext: false,          // the success toast offers to start a new lesson
    viewer: { open: false, list: [], index: 0, zoomed: false, touchX: 0 },  // a photo in full
    removal: { open: false, lesson: null, checking: false, available: false, count: 0, anki: false, busy: false },
    editor: { open: false, id: null, name: "", text: "", deck: "", voice: "", error: "" },
    error: "",
    success: "",
    anki: { available: false },  // Anki reachable → direct send; `profile`: open Anki profile
    profiles: true,              // Anki profiles shown (not in the Android app: AnkiDroid doesn't say them)
    settingsHere: true,          // false on a phone when Notosaurus runs in the Anki add-on
    inAndroidApp: /\bNotosaurusApp\//.test(navigator.userAgent),
    apkg: true,                  // a .apkg to download: not where the cards go straight to AnkiDroid (the app)
    reviewInAnki: false,         // a sent lesson reviewed in Anki from here (the app: AnkiDroid)
    donations: true,             // "Support Notosaurus": not where it's paid for (the app's subscription)  // the Notosaurus Android app (its WebView says so)
    profileToApply: null,        // Anki profile switch waiting for the current task to finish
    diagramWarning: false,       // the AI model places diagram masks loosely: say so
    lessonOwner: "",              // Anki profile that created the open lesson ("" = nobody: shared)
    lessonShared: false,         // visible from every profile (only the owner's profile can change it)
    lessonPrompt: "",            // prompt text the open lesson was generated with
    frames: [],                  // diagram frames of the open lesson: what Anki shows of each photo
    sending: false,
    drawing: false,              // the pictures the cards ask for are being drawn
    pictureJobs: 0,              // a card's picture being redrawn, uploaded or removed
    katexReady: false,           // the formula previews can be drawn (KaTeX loaded)
    unpaired: false,             // this device has no token yet: it must scan the QR code

    async init() {
      // Notosaurus's prompts come in the page's language: again when it changes
      document.addEventListener("i18n:changed", () => this.reloadPrompts());
      // Any change to the open lesson is saved automatically.
      Alpine.effect(() => {
        const snapshot = this.snapshot();
        if (this.lessonId && !this.readOnly() && snapshot !== this.lastSaved) this.scheduleSave();
      });
      // Phone locked or tab closed: don't wait for the delay.
      document.addEventListener("visibilitychange", () => {
        if (document.visibilityState === "hidden" && this.saveTimer) this.saveNow(true);
      });

      // KaTeX loads after the page (deferred): the previews redraw once it's there
      const katexLoaded = () => { this.katexReady = typeof katex !== "undefined"; };
      if (document.readyState === "complete") katexLoaded();
      else window.addEventListener("load", katexLoaded);

      await i18nReady;  // the language is needed for the first default prompts
      try {
        await api("/api/config");
      } catch (e) {
        if (e.detail?.code === "device.not_paired") {
          this.unpaired = true;
          return;
        }
      }
      try {
        this.settingsHere = (await (await fetch("/api/admin")).json()).allowed;
        const config = await (await api("/api/config")).json();
        this.diagramWarning = config.diagram_warning;
        this.profiles = config.profiles ?? true;
        this.maxPhotos = config.max_photos ?? this.maxPhotos;
        this.configured = config.configured ?? true;
        this.donations = config.donations ?? true;
        this.apkg = config.apkg ?? true;
        this.reviewInAnki = config.review_in_anki ?? false;
        this.mic.available = config.dictation ?? false;
        const helps = storage("get", undefined, HELPS);
        this.helps = helps === null ? Boolean(config.card_helps) : helps === "1";
      } catch {}
      this.$watch("funFacts", (on) => storage("set", on ? "1" : "0", FUN_FACTS));
      this.$watch("quick", (on) => storage("set", on ? "0" : "1", CAREFUL));
      await Promise.all([this.loadPrompts(storage("get"), true), this.loadLessons()]);
      this.checkAnki();
      // Anki may be started later: check again when coming back to the app.
      document.addEventListener("visibilitychange", () => {
        if (document.visibilityState === "visible") this.checkAnki();
      });
      // Follow profile switches in Anki while the page stays open.
      setInterval(() => { if (document.visibilityState === "visible") this.checkAnki(); }, PROFILE_POLL);
      try {
        this.voices = await (await api("/api/voices")).json();
      } catch {}  // the list is only an input aid
    },

    // The methods, by topic: app-photos.js, app-prompts.js, app-lessons.js, app-cards.js,
    // app-anki.js, app-dictation.js (loaded before this file)
    ...photosPart,
    ...promptsPart,
    ...lessonsPart,
    ...cardsPart,
    ...ankiPart,
    ...dictationPart,
  }));
});
