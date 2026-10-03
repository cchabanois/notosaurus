// Loads the page scripts (static/i18n.js, static/app.js, static/admin.js) in a Node
// vm context with the browser globals they use stubbed, so their functions can be
// unit-tested as they ship — no bundler, no dependency, `node --test` only.
//
// The scripts are classic <script defer> tags sharing the page's globals: running
// them in one context reproduces that (app.js calls i18n.js's t(), I18N…). Top-level
// const/let stay reachable from later scripts in the same context, and so from `run`.

import { readFile } from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import vm from "node:vm";
import { fileURLToPath } from "node:url";

export const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
process.env.TZ = "UTC";  // dates formatted the same on every computer

// A value from the vm context, in this realm: deepEqual sees the other realm's
// prototypes as different, and structuredClone drops that difference.
export const plain = (value) => structuredClone(value);

export class Response {
  constructor(body, { status = 200, statusText = "" } = {}) {
    this.status = status;
    this.ok = status < 400;
    this.statusText = statusText;
    this.headers = new Map();
    this._body = body ?? {};
  }

  json() { return typeof this._body === "string" ? JSON.parse(this._body) : this._body; }
  async blob() { return this._body; }
  async text() { return typeof this._body === "string" ? this._body : JSON.stringify(this._body); }
}

// localStorage / sessionStorage: in-memory, or throwing (private browsing) on demand.
const memoryStorage = (throwing = false) => {
  const data = new Map();
  if (throwing) return { getItem: () => { throw new Error("blocked"); }, setItem: () => { throw new Error("blocked"); }, removeItem: () => { throw new Error("blocked"); } };
  return {
    getItem: (k) => data.get(k) ?? null,
    setItem: (k, v) => data.set(k, String(v)),
    removeItem: (k) => data.delete(k),
    _dump: () => Object.fromEntries(data),
  };
};

// What i18n.js needs to boot: /api/lang, then the translation files from static/i18n/.
async function i18nFetch(url) {
  if (url === "/api/lang") {
    return new Response({
      lang: null,
      available: ["de", "en", "es", "fr", "it", "pt"],
      names: { de: "Deutsch", en: "English", es: "Español", fr: "Français", it: "Italiano", pt: "Português (Brasil)" },
    });
  }
  const translation = url.match(/^i18n\/([\w-]+)\.json$/);
  if (translation) {
    try {
      return new Response(await readFile(path.join(ROOT, "static/i18n", `${translation[1]}.json`), "utf8"));
    } catch {
      return new Response({}, { status: 404 });
    }
  }
  return new Response({}, { status: 404 });
}

// Alpine, as far as the scripts use it: data() captures the component factories,
// store() keeps one store object, magic() does nothing (tests call t() directly).
function alpineStub() {
  const factories = {};
  const stores = {};
  return {
    factories,
    stores,
    data: (name, factory) => { factories[name] = factory; },
    store: (name, value) => (value ? Object.assign(stores[name] ??= {}, value) : (stores[name] ??= {})),
    magic: () => {},
    effect: () => {},
  };
}

// The document the scripts touch: an event registry (fire() plays what Alpine's
// alpine:init would), an html element, a visibility state.
function documentStub() {
  const listeners = new Map();
  const events = [];
  const document = {
    visibilityState: "visible",
    title: "",
    documentElement: { lang: "", classList: { add: () => {} } },
    addEventListener: (type, fn) => listeners.set(type, [...(listeners.get(type) ?? []), fn]),
    dispatchEvent: (event) => {
      events.push(event);
      for (const fn of listeners.get(event.type) ?? []) fn(event);
    },
  };
  return { document, events };
}

export class CustomEvent {
  constructor(type, init = {}) { this.type = type; this.detail = init.detail; }
}

// The i18n.js + app.js (or admin.js) pair, booted like the page does: i18n.js loads,
// the other script registers on alpine:init, then Alpine starts and everything runs.
//
//   const page = await loadScripts("app.js");
//   const component = page.component();       // the Alpine component's data and methods
//   page.run("escapeHtml('<b>')");            // a script's top-level function
//
// Options: the browser's languages (English by default), extra fetch routes for the
// API calls the page makes (a function (url, options) → Response, or null), localStorage
// throwing (private browsing).
export async function loadScripts(
  script,
  { languages = ["en-US", "fr-FR"], routes = null, throwingStorage = false } = {},
) {
  const alpine = alpineStub();
  const { document, events } = documentStub();
  const storage = memoryStorage(throwingStorage);
  const session = memoryStorage(throwingStorage);
  const katex = {
    renderToString: (tex, { displayMode } = {}) =>
      (displayMode ? `<span class="katex-display">` : '<span class="katex">') + tex + "</span>",
  };
  const sandbox = {
    console,
    setTimeout, clearTimeout, setInterval, clearInterval,
    // i18n's own files first (it needs them to boot), then what a test wants to serve
    fetch: async (url, options) => (/^(\/api\/lang|i18n\/)/.test(url) ? i18nFetch(url) : routes?.(url, options)),
    document,
    navigator: { language: languages[0], languages },
    localStorage: storage,
    sessionStorage: session,
    Alpine: alpine,
    katex,
    CustomEvent,
    crypto: globalThis.crypto,
    URL, URLSearchParams, Blob, FormData,
    structuredClone,
    confirm: () => true,
    window: { scrollTo: () => {}, addEventListener: () => {}, removeEventListener: () => {} },
  };
  const context = vm.createContext(sandbox);
  const run = (code) => vm.runInContext(code, context);
  for (const file of ["i18n.js", script]) {
    run(await readFile(path.join(ROOT, "static", file), "utf8"));
  }
  await run("i18nReady");  // the language is loaded: t() answers
  document.dispatchEvent(new CustomEvent("alpine:init"));  // Alpine starts

  const component = (name = script === "admin.js" ? "admin" : "notosaurus") => {
    const c = alpine.factories[name]();
    // What Alpine adds to a component and the page's methods reach for
    c.$nextTick = (fn) => fn();
    c.$refs = {};
    c.$watch = () => {};
    return c;
  };
  return { run, component, alpine, document, events, storage, session };
}
