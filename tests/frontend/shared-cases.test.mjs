// The cases Python, Kotlin and JavaScript must agree on (core/shared-cases.json, Python's
// answers the reference): the page's own copies of the logic checked against them.
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import { loadScripts } from "./harness.mjs";

const ROOT = path.join(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const cases = JSON.parse(await readFile(path.join(ROOT, "core", "shared-cases.json"), "utf8"));

test("speakable: what a voice reads of a text, as tts.py", async () => {
  const page = await loadScripts("app.js");
  for (const c of cases.speakable) assert.equal(page.run(`speakable(${JSON.stringify(c.in)})`), c.out, c.in);
});

test("a card's deck, its levels, as app/anki.py's _deck_name", async () => {
  const page = await loadScripts("app.js");
  const component = page.component();
  for (const c of cases.deck_name) {
    component.deck = c.deck;
    assert.equal(component.deckPath({ subdeck: c.subdeck }).join("::"), c.out, `${c.deck} | ${c.subdeck}`);
  }
});

test("what each side says read aloud, as tts.spoken_sides", async () => {
  const page = await loadScripts("app.js");
  const component = page.component();
  for (const c of cases.spoken_sides) {
    component.dictation = c.dictation;
    const card = { front: c.front, back: c.back, choices: c.choices, sound: c.sound };
    assert.deepEqual([...component.spokenSides(card)], c.out, `${c.front} | ${c.sound}`);  // (the page's own Array)
  }
});

test("a card's sound: what it says, as tts.spoken", async () => {
  const page = await loadScripts("app.js");
  const component = page.component();
  for (const c of cases.spoken) {
    component.dictation = c.dictation;
    assert.equal(component.spokenText({ front: c.front, back: c.back }), c.out, `${c.front} | ${c.back}`);
  }
});

test("two deck levels the same, as children.same_level", async () => {
  const page = await loadScripts("app.js");
  for (const c of cases.same_level) {
    const same = page.run(`sameLevel(${JSON.stringify(c.a)}) === sameLevel(${JSON.stringify(c.b)})`);
    assert.equal(same, c.out, `${c.a} | ${c.b}`);
  }
});
