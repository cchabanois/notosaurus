// static/admin.js: what the settings page computes — the diff it saves, the model
// names it shows, who draws the card pictures, the lessons by owner and the costs.

import assert from "node:assert/strict";
import test from "node:test";

import { loadScripts, plain } from "./harness.mjs";

const page = await loadScripts("admin.js");

// The editable settings, as the server sends them, and the page's copy of them.
function settings(admin, changes = {}, keys = {}, savedChanges = {}) {
  admin.saved = {
    llm: "gemini", model: "gemini-3.8-flash", fallback_models: [], compatible_base_url: "",
    picture_service: "", tts_rate: "+0%", ankiconnect_url: "http://localhost:8765", anki_sync: true,
    instructions: "", profile_instructions: {}, picture_model: "",
    openai_api_key: "", openrouter_api_key: "", gemini_api_key: "k",
    ...savedChanges,
  };
  admin.show(admin.saved);
  Object.assign(admin.form, changes);
  admin.keys = keys;
}

test("what differs from the saved settings is what gets saved", () => {
  const admin = page.component();
  settings(admin, { model: "gemini-3.5-flash" }, { openai_api_key: "  sk-1  " });
  assert.deepEqual(plain(admin.changes()), { model: "gemini-3.5-flash", openai_api_key: "sk-1" });  // typed key trimmed
  assert.deepEqual(plain(admin.changes({ keys: false })), { model: "gemini-3.5-flash" });  // a key half-typed waits
  assert.equal(admin.dirty(), true);

  settings(admin);  // nothing differs
  assert.deepEqual(plain(admin.changes()), {});
  assert.equal(admin.dirty(), false);
});

test("a key being cleared is always part of the changes (a deliberate action)", () => {
  const admin = page.component();
  settings(admin, {}, { gemini_api_key: null });
  assert.deepEqual(plain(admin.changes({ keys: false })), { gemini_api_key: "" });
});

test("model names: the service's own name, cleaned", () => {
  const admin = page.component();
  admin.modelNames = { "~google/gemini-flash-latest": "Google: Gemini Flash Latest" };
  assert.equal(admin.modelLabel("~google/gemini-flash-latest"), "Gemini Flash");
  assert.equal(admin.modelLabel("~openai/gpt-latest"), "gpt");  // an id when the service names none
  assert.equal(admin.modelLabel("mistral-medium-3-5"), "mistral-medium-3-5");
});

test("the demo provider is only listed when it is the saved choice", () => {
  const admin = page.component();
  settings(admin);
  assert.equal(admin.shownProviders().some((p) => p.id === "fake"), false);
  admin.saved.llm = "fake";  // the demo provider is the saved choice
  assert.equal(admin.shownProviders().some((p) => p.id === "fake"), true);
});

test("switching provider takes the saved model coming back to it, empty going elsewhere", () => {
  const admin = page.component();
  settings(admin, { llm: "openai" });
  admin.providerChanged();
  assert.equal(admin.form.model, "");  // not gemini-3.8-flash under OpenAI's name

  admin.form.llm = "gemini";
  admin.providerChanged();
  assert.equal(admin.form.model, "gemini-3.8-flash");
});

test("model suggestions: the provider's own, plus what the service lists", () => {
  const admin = page.component();
  settings(admin);
  assert.deepEqual(plain(admin.modelSuggestions()), ["gemini-3.8-flash", "gemini-3.5-flash", "gemini-3.5-flash-lite", "gemini-3.1-pro-preview"]);

  settings(admin, { llm: "openrouter" });
  admin.loadedModels = ["a", "b"];
  admin.modelAliases = ["~x-latest", "a"];  // a duplicate of the listed ones
  assert.deepEqual(plain(admin.modelSuggestions()), ["~x-latest", "a", "b"]);
});

test("who draws the card pictures: the same rule as the server", () => {
  const admin = page.component();
  settings(admin);  // gemini has a key, and it draws
  assert.equal(admin.drawingService(), "gemini");
  assert.equal(admin.pictureSummary(), "Drawn by Gemini (Google), the cards' own service.");

  settings(admin, { llm: "anthropic" });  // Claude can't draw: another service
  assert.equal(admin.drawingService(), "gemini");
  assert.equal(admin.pictureSummary(), "Claude (Anthropic) can't draw: the pictures go through Gemini (Google).");

  // No service has a key any more
  settings(admin, { llm: "anthropic" }, { gemini_api_key: null }, { gemini_api_key: "" });
  assert.equal(admin.drawingService(), "");
  assert.equal(admin.pictureSummary(), "Claude (Anthropic) can't draw, and no other service has a key: add a Gemini, OpenAI or OpenRouter key to get pictures.");

  settings(admin, { picture_service: "none" });
  assert.equal(admin.drawingService(), "");
  assert.equal(admin.pictureSummary(), "No pictures on the cards.");

  settings(admin, { picture_service: "openai" });  // chosen on purpose, but its key is missing
  assert.equal(admin.drawingService(), "");
  assert.equal(admin.pictureSummary(), "OpenAI (GPT) has no key: add it, or choose another service.");
});

test("the lessons by owner: Anki's profiles in order, the gone ones, then nobody's", () => {
  const admin = page.component();
  admin.lessons = {
    profiles: ["Léa", "Paul"],
    lessons: [
      { id: "1", owner: "Paul", deck: "Maths::A", ai_calls: [{ cost: 0.01 }] },
      { id: "2", owner: "", deck: "Anglais::B", ai_calls: [{ cost: 0.02 }, { cost: null }] },
      { id: "3", owner: "Léa", deck: "espagnol::C", ai_calls: [] },
      { id: "4", owner: "Ghost", deck: "D", ai_calls: [{ cost: 0.1 }] },
      { id: "5", owner: "Léa", deck: "Espagnol::E", ai_calls: [] },
    ],
  };
  const tree = admin.lessonTree();
  assert.deepEqual(plain(tree.map((g) => g.owner)), ["Léa", "Paul", "Ghost", ""]);
  assert.deepEqual(plain(tree.map((g) => g.missing)), [false, false, true, false]);  // Ghost left Anki
  const lea = tree[0];
  assert.deepEqual(plain(lea.subjects.map((s) => s.name)), ["espagnol"]);  // Anki doesn't tell case apart
  assert.equal(lea.subjects[0].lessons.length, 2);
  assert.equal(lea.cost, null);  // no cost known for Léa's lessons
  assert.deepEqual(plain(tree.map((g) => g.cost)), [null, 0.01, 0.1, 0.02]);
});

test("a lesson under its subject: the rest of its deck name", () => {
  const admin = page.component();
  assert.equal(admin.lessonTitle({ deck: "Maths::Fractions::Addition" }), "Fractions › Addition");
  assert.equal(admin.lessonTitle({ deck: "Maths" }), "Maths");
});

test("whose lessons can be given away: Anki's profiles, a gone owner first", () => {
  const admin = page.component();
  admin.lessons = { profiles: ["Léa", "Paul"], lessons: [] };
  assert.deepEqual(plain(admin.ownerChoices({ owner: "Léa" })), ["Léa", "Paul"]);
  assert.deepEqual(plain(admin.ownerChoices({ owner: "Ghost" })), ["Ghost", "Léa", "Paul"]);
});

test("costs: cents say more than dollars, unknown is a dash", () => {
  const admin = page.component();
  assert.equal(admin.formatCost(null), "—");
  assert.equal(admin.formatCost(0.027), "2.7 US¢");
  assert.equal(admin.formatCost(1.5), "$1.50");
  assert.ok(Math.abs(admin.lessonCost({ ai_calls: [{ cost: 0.01 }, { cost: 0.02 }] }) - 0.03) < 1e-9);
  assert.equal(admin.lessonCost({ ai_calls: [{ cost: null }] }), null);  // nothing known: no total
});

test("a blocked session storage degrades to locked, without throwing", async () => {
  const blocked = await loadScripts("admin.js", { throwingStorage: true });
  const admin = blocked.component();
  assert.equal(blocked.run("session('set', 'pw')"), null);
  admin.lock();  // closing the session stays silent
  assert.equal(admin.unlocked, false);
});

test("the Anki test's answer, with and without an open profile", () => {
  const admin = page.component();
  settings(admin);
  assert.equal(admin.ankiOk({ version: 6, profile: "Léa" }), "✓ Anki answers (AnkiConnect version 6, profile “Léa”).");
  admin.saved.embedded = true;
  assert.equal(admin.ankiOk({ profile: "Léa", version: 6 }), "✓ Anki answers (Notosaurus add-on, profile “Léa”).");
  assert.equal(admin.ankiOk({}), "Anki answers, but no profile is open: open one in Anki.");
});
