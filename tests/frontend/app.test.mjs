// static/app.js: the pure helpers (escaping, gaps, formulas, search folding), the
// card comparison behind the AI correction, the lesson list's sections, and the
// state machine of the review (payload, undo, notifications).

import assert from "node:assert/strict";
import test from "node:test";

import { Response, loadScripts, plain } from "./harness.mjs";

const app = await loadScripts("app.js");

test("search folding: no case, no accents (\"lecon\" finds \"Leçon\")", () => {
  assert.equal(app.run("normalize('Leçon 5')"), "lecon 5");
  assert.equal(app.run("fold('LEÇON')"), "lecon");
  assert.equal(app.run("normalize('¿Cómo?')"), "¿como?");
});

test("deck names split into their levels, empties dropped", () => {
  assert.deepEqual(plain(app.run('deckParts("A :: B :: C")')), ["A", "B", "C"]);
  assert.deepEqual(plain(app.run('deckParts("No deck")')), ["No deck"]);
  assert.deepEqual(plain(app.run('deckParts("::")')), []);
});

test("a PDF is told by its type or its name", () => {
  assert.equal(app.run('isPdf({ type: "application/pdf", name: "x" })'), true);
  assert.equal(app.run('isPdf({ type: "", name: "Lesson.PDF" })'), true);
  assert.equal(app.run('isPdf({ type: "image/jpeg", name: "p.jpg" })'), false);
});

test("a card's id is 12 hex characters, different every time", () => {
  assert.match(app.run("newId()"), /^[0-9a-f]{12}$/);
  assert.notEqual(app.run("newId()"), app.run("newId()"));
});

test("withKey fills the card defaults and gives each card its own key", () => {
  const a = app.run("withKey({ front: 'la mère' })");
  assert.deepEqual(
    plain(Object.keys(a).sort()),
    ["choices", "explanation", "figure", "front", "fun_fact", "info", "key", "mnemonic", "picture", "picture_on_back",
     "picture_prompt", "subdeck", "tags"],
  );
  assert.equal(a.info, "");
  assert.deepEqual(plain(a.choices), []);
  const b = app.run("withKey({ front: 'x', info: 'nom' })");
  assert.equal(b.info, "nom");  // given values win
  assert.notEqual(a.key, b.key);
});

test("blocked storage: last prompt and options degrade silently", async () => {
  const blocked = await loadScripts("app.js", { throwingStorage: true });
  assert.equal(blocked.run("storage('get')"), undefined);
  blocked.run("storage('set', 'x')");
  assert.equal(blocked.component().funFacts, false);
  assert.deepEqual(plain(blocked.component().openSubjects), {});
});

test("api(): a server error becomes a translated message, with its code kept", async () => {
  const failing = await loadScripts("app.js", {
    routes: (url) =>
      url === "/api/fail"
        ? new Response({ detail: { code: "lesson.read_only", params: { owner: "Léa" } } }, { status: 403 })
        : new Response({ value: 42 }),
  });
  const error = await failing.run("api('/api/fail').catch((e) => e)");
  assert.equal(error.message, "Read only: only Léa's Anki profile can change this lesson.");
  assert.equal(error.status, 403);
  assert.equal(error.detail.code, "lesson.read_only");
  assert.equal((await failing.run("api('/api/other')")).ok, true);
});

// --- The review -------------------------------------------------------------

const review = app.component();

test("the card preview: escaped, gaps numbered, line breaks kept", () => {
  review.katexReady = false;
  assert.equal(
    review.previewHtml("a < b\nc {{c1::1789}} and {{c2::la Bastille::lieu}} end"),
    "a &lt; b<br>c <span class=\"gap\"><sup>1</sup>1789</span> and <span class=\"gap\"><sup>2</sup>la Bastille</span> end",
  );
  assert.equal(review.previewHtml(undefined), "");  // a card being typed
});

test("the card preview: formulas drawn, the rest escaped around them", () => {
  review.katexReady = true;
  const html = review.previewHtml(String.raw`aire : \(\pi r^2\) et \[x = y\] & <`);
  assert.ok(html.includes('<span class="katex">\\pi r^2</span>'), html);
  assert.ok(html.includes('<span class="katex-display">x = y</span>'), html);
  assert.ok(html.endsWith(" &amp; &lt;"), html);
});

test("formulas and gaps are recognised as such", () => {
  assert.equal(review.hasMath(String.raw`\(x\)`), true);
  assert.equal(review.hasMath(String.raw`\[x\]`), true);
  assert.equal(review.hasMath("(a + b) / 2"), false);
  assert.equal(review.isCloze("en {{c1::1789}}"), true);
  assert.equal(review.isCloze("{{c12::x::indice}}"), true);
  assert.equal(review.isCloze("une {accolade}"), false);
});

test("the AI correction's stats and per-card flags", () => {
  const { cards, stats } = review.compareCards(
    [
      { key: 1, front: "la mère", back: "la madre" },
      { key: 2, front: "le père", back: "el padre" },
    ],
    [
      { front: "la mère", back: "la mamá" },  // same front: changed
      { front: "le chat", back: "el gato" },  // added
    ],
  );
  assert.deepEqual(cards.map((c) => c._state), ["modified", "new"]);
  assert.equal(cards[0].key, 1);  // the changed card keeps its key…
  assert.notEqual(cards[1].key, cards[0].key);  // …the added one a fresh one
  assert.equal(cards[0].back, "la mamá");
  assert.equal(stats, "+1 new · 1 changed · −1 removed");

  const same = review.compareCards([{ key: 7, front: "a", back: "b" }], [{ front: "a", back: "b" }]);
  assert.deepEqual(plain(same.cards), [{ key: 7, front: "a", back: "b" }]);  // key kept, no flag
  assert.equal(same.stats, "no change");
});

test("the payload sent to the server: a card's UI-only fields left out", () => {
  review.deck = "D";
  review.cards = [
    { front: "a", key: 5, _panel: true, picture: "p.jpg" },
    { front: "b", _state: "new", id: "x1" },
  ];
  assert.deepEqual(plain(review.payload().cards), [{ front: "a", picture: "p.jpg" }, { front: "b", id: "x1" }]);
});

test("a lesson coming from the server becomes the review's state, already saved", () => {
  review.show({ id: "lesson-1", deck: "Espagnol", cards: [{ front: "la mère", back: "la madre" }], prompt: "FR → ES" });
  assert.equal(review.lessonId, "lesson-1");
  assert.equal(review.cards[0].key !== undefined, true);
  assert.equal(review.saveState, "saved");
  assert.equal(review.lastSaved, review.snapshot());
  const saved = JSON.parse(review.lastSaved);
  assert.equal(saved.deck, "Espagnol");
  assert.equal(saved.cards.length, 1);
  assert.ok(!("key" in saved.cards[0]));  // keys are for the page only
});

test("Undo brings the previous version back", () => {
  review.deck = "Changed";
  review.revision.undo = { deck: "D", cards: [{ front: "a" }], voice: "v", frames: [], lessonPrompt: "p", typing: true };
  review.undoRevision();
  assert.equal(review.deck, "D");
  assert.deepEqual(review.cards, [{ front: "a" }]);
  assert.equal(review.voice, "v");
  assert.equal(review.typing, true);
  assert.equal(review.revision.summary, "Correction undone.");
  assert.equal(review.revision.undo, null);
});

test("the success message goes away after a while", async (t) => {
  // Timers mocked before the scripts load: the page's setTimeout is the mocked one
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const page = await loadScripts("app.js");
  const component = page.component();
  component.notify("Sent to Anki", true);
  assert.equal(component.success, "Sent to Anki");
  t.mock.timers.tick(11_999);
  assert.equal(component.success, "Sent to Anki");
  t.mock.timers.tick(1);
  assert.equal(component.success, "");
});

// --- The lesson list --------------------------------------------------------

const list = app.component();

test("many lessons: the recent ones first, subjects folded, case together", () => {
  const deck = (name) => ({ id: name, deck: name });
  list.lessons = [
    "Anglais::Leçon 1", "anglais::leçon 2", "Maths::Fractions", "Maths::Nombres",
    "Histoire::Révolution", "Sans deck", "A::x", "B::y", "C::z",
  ].map(deck);
  const sections = list.lessonSections();
  assert.equal(sections[0].key, "recent");
  assert.deepEqual(sections[0].lessons.map((l) => l.deck), ["Anglais::Leçon 1", "anglais::leçon 2", "Maths::Fractions"]);
  const anglais = sections.find((s) => s.subject === "anglais");
  assert.equal(anglais.name, "Anglais");  // the first spelling seen
  assert.equal(anglais.count, 2);
  assert.equal(anglais.open, false);  // folded until opened
  const none = sections.find((s) => s.name === "Sans deck");
  assert.equal(none.lessons[0].title, "Sans deck");  // nothing after the subject: it is the title

  list.openSubjects = { anglais: true };
  assert.equal(list.lessonSections().find((s) => s.subject === "anglais").open, true);
});

test("a search shows the lessons found instead", () => {
  list.lessonQuery = "  angl  ";
  const [found] = list.lessonSections();
  assert.equal(found.key, "found");
  assert.deepEqual(found.lessons.map((l) => l.deck), ["Anglais::Leçon 1", "anglais::leçon 2"]);
});

test("few lessons: no recent section, everything open", () => {
  const few = app.component();
  few.lessons = [{ id: "a", deck: "A::1" }, { id: "b", deck: "B::1" }];
  const sections = few.lessonSections();
  assert.equal(sections.some((s) => s.key === "recent"), false);
  assert.ok(sections.every((s) => s.open));
});

test("whose lessons are shown: the profile's own, the shared, the ownerless", () => {
  list.anki.profile = "Léa";
  list.lessons = [
    { owner: "Léa" }, { owner: "Paul" }, { owner: "" }, { owner: "Paul", shared: true },
  ];
  assert.deepEqual(plain(list.visibleLessons()), [{ owner: "Léa" }, { owner: "" }, { owner: "Paul", shared: true }]);
  list.anki.profile = null;  // Anki closed: no profile to filter by
  assert.equal(list.visibleLessons().length, 4);
});

test("read-only when the lesson belongs to another profile", () => {
  list.anki.profile = "Léa";
  list.lessonOwner = "Léa";
  assert.equal(list.readOnly(), false);
  assert.equal(list.canShare(), true);
  list.lessonOwner = "Paul";
  assert.equal(list.readOnly(), true);
  assert.equal(list.canShare(), false);
  assert.equal(list.canDelete({ owner: "Paul" }), false);
  assert.equal(list.canDelete({ owner: "" }), true);  // nobody's: everyone's
});

test("the most recently used prompts, never-used ones in the server's order", () => {
  const page = app.component();
  // As the server lists them: Notosaurus's in their chosen order (not alphabetical), then the user's
  page.prompts = [
    { id: "notosaurus:auto" }, { id: "notosaurus:vocabulary" }, { id: "notosaurus:cloze" }, { id: 1 }, { id: 2 },
  ];
  page.selectedId = 2;
  assert.deepEqual(plain(page.recentPrompts().map((p) => p.id)), ["notosaurus:auto", "notosaurus:vocabulary", "notosaurus:cloze", 2]);

  page.prompts[4].used_at = "2026-10-03T10:00:00Z";  // used last: first, still selected
  assert.deepEqual(plain(page.recentPrompts().map((p) => p.id)).slice(0, 2), [2, "notosaurus:auto"]);

  const many = app.component();  // more prompts than chips: the selected one is always shown
  many.prompts = Array.from({ length: 6 }, (_, i) => ({ id: i + 1 }));
  many.selectedId = 6;
  assert.deepEqual(plain(many.recentPrompts().map((p) => p.id)), [1, 2, 3, 6]);
});

// --- Diagrams ----------------------------------------------------------------

const diagram = app.component();

test("the crop holds every mask of the photo, with a margin, clamped to the photo", () => {
  diagram.frames = [{ page: 1, box: [0.1, 0.1, 0.5, 0.5] }];
  diagram.cards = [
    { mask: { page: 1, box: [0.6, 0.6, 0.8, 0.7] } },
    { mask: { page: 1, box: [0.55, 0.4, 0.7, 0.45] } },  // inside the union anyway
    { mask: { page: 2, box: [0, 0, 1, 1] } },  // another photo: not in this crop
  ];
  // The frame and both masks of page 1, grown by 3%
  const crop = (card) => plain(diagram.cropFor(card)).box.map((v) => Math.round(v * 1000) / 1000);
  assert.deepEqual(crop(diagram.cards[0]), [0.1, 0.1, 0.83, 0.73]);
  assert.deepEqual(plain(diagram.cropFor(diagram.cards[2])), { box: [0, 0, 1, 1] });  // no frame: the whole photo

  diagram.cards[1].mask.box = [0.95, 0.95, 0.99, 0.99];  // by the edge: the crop stops at the photo
  assert.deepEqual(crop(diagram.cards[0]), [0.1, 0.1, 1, 1]);

  diagram.frames = [];
  assert.deepEqual(plain(diagram.cropFor(diagram.cards[0])), { box: [0, 0, 1, 1] });
});

test("a mask's position and size, as percentages of the photo", () => {
  assert.equal(diagram.maskStyle({ box: [0.1, 0.2, 0.3, 0.6] }), "left: 10%; top: 20%; width: 20%; height: 40%");
});

test("masks live on their photo", () => {
  assert.equal(diagram.masksOnPage(diagram.cards[0]).length, 2);  // both masks of page 1
  assert.equal(diagram.hasMasks(), true);
  diagram.photos = [{ url: "p1" }, { url: "p2" }];
  assert.equal(diagram.photoFor({ mask: { page: 2 } }), "p2");
  assert.equal(diagram.photoFor({ mask: { page: 3 } }), null);
});

// --- Audio, cards ------------------------------------------------------------

test("voices: an edge-tts one is told apart from an Anki locale or \"auto\"", () => {
  const page = app.component();
  assert.equal(page.isVoice("es-ES-ElviraNeural"), true);
  assert.equal(page.isVoice("es_ES"), false);
  page.voice = "es-ES-ElviraNeural";
  assert.equal(page.hasAudio(), true);
  page.voice = "";
  assert.equal(page.hasAudio(), false);
});

test("one voice at a time: listening again stops the sound playing", () => {
  app.run(`globalThis.Audio = class {
    constructor(src) { this.src = src; this.paused = true; (globalThis.sounds ??= []).push(this); }
    addEventListener() {}
    play() { this.paused = false; return Promise.resolve(); }
    pause() { this.paused = true; }
  }`);
  const page = app.component();
  page.voice = "es-ES-ElviraNeural";
  page.play("la madre");
  page.play("la madre");  // tapped again
  page.play("el padre");  // another card
  const sounds = app.run("sounds.map((s) => s.paused)");
  assert.deepEqual(plain(sounds), [true, true, false]);  // only the last one plays
});

test("a sample sentence in the voice's language", () => {
  const page = app.component();
  assert.equal(page.sampleText("es-ES-X"), "Hola, ¿cómo estás?");
  assert.equal(page.sampleText("fr-FR-X"), "Bonjour, comment ça va ?");
  assert.equal(page.sampleText("xx-XX-X"), "Hello!");
});

test("subdecks of the lesson's cards", () => {
  const page = app.component();
  page.cards = [{ subdeck: "Vocabulaire" }, { subdeck: "Phrases" }, { subdeck: "Vocabulaire" }, {}];
  assert.deepEqual(plain(page.subdecks()), ["Vocabulaire", "Phrases"]);
});

test("dates in the language's variety, short form", () => {
  assert.match(app.run("formatDate('2026-10-03T21:48:00Z')"), /^Oct 3, 09:48[ \u202f]?PM$/);
});
