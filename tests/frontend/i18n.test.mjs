// static/i18n.js: the fallback chain, plurals, parameter interpolation and escaping,
// error messages from the server's { code, params }, the language picked on the page.

import assert from "node:assert/strict";
import test from "node:test";

import { loadScripts } from "./harness.mjs";

test("the browser's language is used, English for those without a file", async () => {
  const fr = await loadScripts("app.js", { languages: ["fr-FR", "en-US"] });
  assert.equal(fr.run("I18N.lang"), "fr");
  assert.equal(fr.run('t("app.lessons.recent")'), "Récentes");

  const en = await loadScripts("app.js", { languages: ["fr-FR", "en-US"] });
  await en.run('setLanguage("en")');
  assert.equal(en.run('t("app.lessons.recent")'), "Recent");

  const japanese = await loadScripts("app.js", { languages: ["ja-JP"] });
  assert.equal(japanese.run("I18N.lang"), "en");  // no Japanese file
  assert.equal(japanese.run('t("app.lessons.recent")'), "Recent");
});

test("a key missing from the language falls back to English, then to the key itself", async () => {
  const page = await loadScripts("app.js", { languages: ["fr-FR"] });
  // All the shipped files have the same keys: drop one to see the fallback
  page.run("delete I18N.messages.app.lessons.recent");
  assert.equal(page.run('t("app.lessons.recent")'), "Recent");
  assert.equal(page.run('t("no.such.key")'), "no.such.key");
});

test("plurals follow the language's rules (French: zero takes the singular)", async () => {
  const en = await loadScripts("app.js");
  assert.equal(en.run('t("common.count.cards", { count: 1 })'), "1 card");
  assert.equal(en.run('t("common.count.cards", { count: 2 })'), "2 cards");

  const fr = await loadScripts("app.js", { languages: ["fr-FR"] });
  assert.equal(fr.run('t("common.count.cards", { count: 0 })'), "0 carte");
  assert.equal(fr.run('t("common.count.cards", { count: 2 })'), "2 cartes");
});

test("parameters are interpolated; unknown ones stay as written", async () => {
  const page = await loadScripts("app.js");
  assert.equal(
    page.run('t("errors.lesson.read_only", { owner: "Léa" })'),
    "Read only: only Léa's Anki profile can change this lesson.",
  );
  assert.equal(page.run('t("errors.unknown", { wrong: 1 })'), "Unexpected error ({code}).");
});

test("tHtml escapes what it interpolates: a profile name can't inject HTML", async () => {
  const page = await loadScripts("app.js");
  const html = page.run('tHtml("errors.lesson.read_only", { owner: \'<b>"Léa"</b>\' })');
  assert.ok(html.includes("&#60;b&#62;&#34;Léa&#34;&#60;/b&#62;"), html);
  assert.ok(!html.includes("<b>"), html);
});

test("server errors: a known code is translated, an unknown one says so", async () => {
  const page = await loadScripts("app.js");
  assert.equal(
    page.run('errorMessage({ code: "lesson.read_only", params: { owner: "Léa" } })'),
    "Read only: only Léa's Anki profile can change this lesson.",
  );
  assert.equal(page.run('errorMessage({ code: "nope.nope" })'), "Unexpected error (nope.nope).");
  assert.equal(page.run('errorMessage("the server said")'), "the server said");
  assert.equal(page.run("errorMessage({ no: 'code' })"), "Invalid value.");
  assert.equal(page.run("errorMessage()"), "Invalid value.");
});

test("dates in the browser's variety of the language", async () => {
  const page = await loadScripts("app.js", { languages: ["en-US", "fr-FR"] });
  assert.equal(page.run('formatLocale("en")'), "en-US");
  assert.equal(page.run('formatLocale("fr")'), "fr-FR");
  assert.equal(page.run('formatLocale("es")'), "es");  // no variety of it here: the language

  const odd = await loadScripts("app.js", { languages: ["fr-#"] });  // not a valid locale
  assert.equal(odd.run('formatLocale("fr")'), "fr");
});

test("the browser's language, among those Notosaurus has a file for", async () => {
  const pick = async (languages) => (await loadScripts("app.js", { languages })).run("browserLanguage(I18N.available)");
  assert.equal(await pick(["es-MX", "en-US"]), "es");  // the exact variety, else the language
  assert.equal(await pick(["pt-BR"]), "pt");
  assert.equal(await pick(["ja-JP", "en-US"]), "en");
  assert.equal(await pick(["ja-JP"]), null);  // nothing fits
});

test("blocked storage: the language stays automatic, nothing throws", async () => {
  const page = await loadScripts("app.js", { languages: ["fr-FR"], throwingStorage: true });
  assert.equal(page.run("storedChoice()"), "");
  assert.equal(page.run("I18N.lang"), "fr");
});

test("a language picked on the page: applied at once, remembered, announced", async () => {
  const page = await loadScripts("app.js", { languages: ["fr-FR", "en-US"] });
  const before = page.alpine.stores.i18n.version;
  await page.run('setLanguage("fr")');

  assert.equal(page.run("I18N.lang"), "fr");
  assert.equal(page.storage._dump()["notosaurus.lang"], "fr");
  assert.equal(page.alpine.stores.i18n.choice, "fr");
  assert.ok(page.alpine.stores.i18n.version > before, "the magic $t() re-renders");
  const changed = page.events.find((e) => e.type === "i18n:changed");
  assert.equal(changed?.detail, "fr");

  await page.run('setLanguage("")');  // back to automatic
  assert.equal(page.run("I18N.lang"), "fr");
  assert.equal(page.storage._dump()["notosaurus.lang"], undefined);
});

test("the Alpine store is filled once the language is ready", async () => {
  const page = await loadScripts("app.js", { languages: ["fr-FR", "en-US"] });
  assert.match(page.document.documentElement.lang, /fr/);
  const store = page.alpine.stores.i18n;
  assert.equal(store.ready, true);
  assert.equal(store.auto, "fr");
  assert.deepEqual(store.available, ["de", "en", "es", "fr", "it", "pt"]);
});
