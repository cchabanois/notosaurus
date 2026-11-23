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

test("the cards being made: the words they all begin with are left out", () => {
  assert.equal(app.run('sharedStart(["Quelle est la figure de style : A ?", "Quelle est la figure de style : B ?"])'),
    "Quelle est la figure de style : ");
  assert.equal(app.run('sharedStart(["Quelle est la figure", "Quelle est la figure de style ?"])'), "Quelle est la ");  // a word stays
  assert.equal(app.run('sharedStart(["Le chat", "La chatte"])'), "");
  assert.equal(app.run('sharedStart(["Seule"])'), "");

  const c = app.component();
  c.coming = [{ front: "Quelle est la figure de style : « Ce toit tranquille »" }];
  assert.equal(c.comingFront(c.coming[0]), "Quelle est la figure de style : « Ce toit tranquille »");  // alone: whole
  c.coming.push({ front: "Quelle est la figure de style : « Je meurs de soif auprès de la fontaine »" });
  assert.equal(c.comingFront(c.coming[1]), "…« Je meurs de soif auprès de la fontaine »");
});

test("a card's id is 12 hex characters, different every time", () => {
  assert.match(app.run("newId()"), /^[0-9a-f]{12}$/);
  assert.notEqual(app.run("newId()"), app.run("newId()"));
});

test("withKey fills the card defaults and gives each card its own key", () => {
  const a = app.run("withKey({ front: 'la mère' })");
  assert.deepEqual(
    plain(Object.keys(a).sort()),
    ["choices", "doubt", "explanation", "figure", "front", "fun_fact", "info", "key", "mnemonic", "picture", "picture_on_back",
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
  assert.equal(blocked.run("storage('get')"), null);  // nothing kept: null, as localStorage says it
  blocked.run("storage('set', 'x')");
  assert.equal(blocked.component().quick, true);  // quick by default
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
  review.mathReady = false;
  assert.equal(
    review.previewHtml("a < b\nc {{c1::1789}} and {{c2::la Bastille::lieu}} end"),
    "a &lt; b<br>c <span class=\"gap\"><sup>1</sup>1789</span> and <span class=\"gap\"><sup>2</sup>la Bastille</span> end",
  );
  assert.equal(review.previewHtml(undefined), "");  // a card being typed
});

test("the card preview: formulas drawn, the rest escaped around them", () => {
  review.mathReady = true;
  const html = review.previewHtml(String.raw`aire : \(\pi r^2\) et \[x = y\] & <`);
  assert.ok(html.includes('<mjx-container display="false">\\pi r^2</mjx-container>'), html);
  assert.ok(html.includes('<mjx-container display="true">x = y</mjx-container>'), html);
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

  // Not only its texts: its figure written, its wrong answers, its helps (seen: figures added to
  // cards, "no change" said); nothing and an empty list the same
  const deeper = review.compareCards(
    [
      { key: 1, front: "exp", back: "ℝ", figure: "", choices: [] },
      { key: 2, front: "QCM", back: "1789", choices: ["1790"] },
      { key: 3, front: "astuce", back: "x", mnemonic: "" },
    ],
    [
      { front: "exp", back: "ℝ", figure: "La courbe de exp", choices: [] },
      { front: "QCM", back: "1789", choices: ["1790", "1792"] },
      { front: "astuce", back: "x" },
    ],
  );
  assert.deepEqual(deeper.cards.map((c) => c._state), ["modified", "modified", undefined]);
  assert.equal(deeper.stats, "2 changed");
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
  list.lessonOwner = "Paul";
  assert.equal(list.readOnly(), true);
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

test("the big button: the cards from the photos, from the prompt when it says what to learn, else a photo", () => {
  const page = app.component();
  const vocabulary = "Crée des cartes de vocabulaire.\nSans photo : à partir de ce que j'écris ici (une liste de mots).";
  page.prompts = [{ id: "notosaurus:vocabulary", builtin: true, text: vocabulary }, { id: 1, text: "Mes cartes" }];
  const when = (selectedId, text) => {
    Object.assign(page, { selectedId, form: { ...page.form, text } });
    return page.nextAction();
  };
  assert.equal(when("notosaurus:vocabulary", vocabulary), "photo");  // as it is: meant for photos
  assert.equal(when("notosaurus:vocabulary", vocabulary.replace(" (une", ", (une")), "photo");  // a comma
  assert.equal(when("notosaurus:vocabulary", vocabulary.replace("Crée", "Crée,")), "photo");  // punctuation: no word
  assert.equal(when("notosaurus:vocabulary", `${vocabulary}\nLes capitales`), "prompt");  // a topic in one word ("les" there)
  assert.equal(when("notosaurus:vocabulary", "Les capitales"), "prompt");  // its text replaced by a topic
  assert.equal(when("notosaurus:vocabulary", `${vocabulary}\nla mère, le père, la sœur`), "prompt");
  assert.equal(when(null, "Les capitales de l'Europe"), "prompt");  // the free prompt, written
  assert.equal(when(null, "  "), "photo");  // the free prompt, empty
  assert.equal(when(1, "Mes cartes"), "prompt");  // the user's own
  page.photos = [{ url: "blob:1" }];
  assert.equal(when("notosaurus:vocabulary", vocabulary), "generate");  // a photo: the cards from it
});

test("deleting a prompt is asked in the app's own sheet, not the browser's confirm()", async () => {
  const calls = [];
  const page = await loadScripts("app.js", {
    routes: (url, options) => {
      calls.push(`${options?.method ?? "GET"} ${url}`);
      return new Response([]);
    },
  });
  const c = page.component();
  c.loadPrompts = async () => {};

  const cancelled = c.deletePrompt({ id: 7, name: "Definitions" });
  assert.equal(c.asking.open, true);
  assert.match(c.asking.message, /Definitions/);
  c.answerConfirm(false);
  await cancelled;
  assert.equal(c.asking.open, false);
  assert.deepEqual(calls, []);

  const confirmed = c.deletePrompt({ id: 7, name: "Definitions" });
  c.answerConfirm(true);
  await confirmed;
  assert.deepEqual(calls, ["DELETE /api/prompts/7"]);
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
  assert.equal(page.isVoice("es-ES-Chirp3-HD-Aoede"), true);  // the Android app's (Google Chirp 3 HD)
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

test("dates in the language's variety, short form", () => {
  assert.match(app.run("formatDate('2026-10-03T21:48:00Z')"), /^Oct 3, 09:48[ \u202f]?PM$/);
});

// --- Dictation (the app's 🎤) ------------------------------------------------

test("dictation: listen, then the text said comes after what was written", async () => {
  const calls = [];
  const said = { text: "Ajoute el tío." };
  const page = await loadScripts("app.js", {
    routes: (url, options) => {
      calls.push([url, options?.body ?? null]);
      return new Response(url === "/api/dictation/stop" ? said : {});
    },
  });
  const c = page.component();
  c.form.text = "Vocabulaire de la famille  ";
  await c.dictate("prompt");
  assert.equal(c.mic.listening, "prompt");
  assert.equal(c.dictating("prompt"), true);  // the field waits for its text
  assert.equal(c.canGenerate(), true);  // « Générer » still there: it ends the dictation first
  assert.equal(c.dictationStep("prompt"), "app.dictation.listening");
  assert.equal(c.dictating("correction"), false);
  assert.equal(c.micKey("prompt"), "app.dictation.stop");
  await c.dictate("correction");  // the other field waits
  assert.equal(c.mic.listening, "prompt");
  await c.dictate("prompt");
  assert.equal(c.form.text, "Vocabulaire de la famille\nAjoute el tío.");
  assert.deepEqual(calls, [["/api/dictation/start", null], ["/api/dictation/stop", '{"kind":"prompt"}']]);
  assert.equal(c.mic.listening, "");
  assert.equal(c.mic.busy, "");
  assert.equal(c.dictating("prompt"), false);
  assert.equal(c.dictationStep("prompt"), "");
  assert.equal(c.canGenerate(), true);

  said.text = "  ";  // nothing heard: said so, the field untouched
  await c.dictate("correction");
  await c.dictate("correction");
  assert.equal(c.revision.text, "");
  assert.equal(c.error, "Nothing heard: try again, closer to the microphone.");
});

test("dictation heard by the phone: its text in the field as it comes, then the whole of it", async (t) => {
  // Timers mocked before the scripts load: the page asks every HEARD_EVERY (300 ms), on the test's clock
  t.mock.timers.enable({ apis: ["setTimeout"] });
  let heard = "Douze cartes";
  const page = await loadScripts("app.js", {
    routes: (url) => new Response(
      url === "/api/dictation/start" ? { listening: true, live: true }
        : url === "/api/dictation/heard" ? { text: heard }
          : url === "/api/dictation/stop" ? { text: "Douze cartes sur el abuelo" } : {},
    ),
  });
  const c = page.component();
  // A turn of the clock, then its answer read (its fetch's promises settled)
  const asked = async (ms) => {
    t.mock.timers.tick(ms);
    await new Promise((done) => setImmediate(done));
  };
  c.form.text = "Vocabulaire";
  await c.dictate("prompt");
  await asked(299);
  assert.equal(c.form.text, "Vocabulaire");  // not asked yet
  await asked(1);  // the phone asked what it heard
  assert.equal(c.form.text, "Vocabulaire\nDouze cartes");
  heard = "Douze cartes sur el";
  await asked(300);
  assert.equal(c.form.text, "Vocabulaire\nDouze cartes sur el");  // replaced, not added again
  await c.dictate("prompt");
  assert.equal(c.form.text, "Vocabulaire\nDouze cartes sur el abuelo");
  heard = "late";
  await asked(300);
  assert.equal(c.form.text, "Vocabulaire\nDouze cartes sur el abuelo");  // stopped: no longer asked
});

test("dictation heard by the phone, its recognition failing partway: what it heard kept in the field, the error said", async () => {
  const page = await loadScripts("app.js", {
    routes: (url) => new Response(
      url === "/api/dictation/start" ? { listening: true, live: true }
        : url === "/api/dictation/heard" ? { text: "Douze cartes", error: "dictation.recognizer" }
          : url === "/api/dictation/stop" ? { text: "Douze cartes", error: "dictation.recognizer" } : {},
    ),
  });
  const c = page.component();
  c.form.text = "Vocabulaire";
  await c.dictate("prompt");
  await new Promise((done) => setTimeout(done, 450));  // the error heard: stopped by the page
  assert.equal(c.mic.listening, "");
  assert.equal(c.mic.busy, "");
  assert.equal(c.form.text, "Vocabulaire\nDouze cartes");  // not put back as before the dictation
  assert.match(c.error, /speech recognition isn't answering/);
});

test("dictation: refused microphone, the field doesn't listen", async () => {
  const page = await loadScripts("app.js", {
    routes: () => new Response({ detail: { code: "dictation.refused", params: {} } }, { status: 400 }),
  });
  const c = page.component();
  await c.dictate("prompt");
  assert.equal(c.mic.listening, "");
  assert.match(c.error, /can't use the microphone/);
});

// --- “✨ Tidy up” the instructions ---------------------------------------------

test("tidy up: the text rewritten, “↩” brings it back until it's changed", async () => {
  const sent = [];
  const page = await loadScripts("app.js", {
    routes: (url, options) => {
      sent.push([url, options?.body]);
      return new Response({ text: "Douze cartes : la famille en espagnol." });
    },
  });
  const c = page.component();
  c.form.text = "euh la famille en espagnol, dix non douze";
  await c.tidyPrompt();
  assert.equal(c.form.text, "Douze cartes : la famille en espagnol.");
  assert.deepEqual(sent, [["/api/prompt/rephrase", '{"text":"euh la famille en espagnol, dix non douze"}']]);
  assert.equal(c.canUntidy(), true);
  c.untidyPrompt();
  assert.equal(c.form.text, "euh la famille en espagnol, dix non douze");
  assert.equal(c.canUntidy(), false);

  await c.tidyPrompt();
  c.form.text += " Avec des images.";  // changed since: “↩” would lose it
  assert.equal(c.canUntidy(), false);
});

// --- Pictures found -----------------------------------------------------------

test("find a picture: the choices, their sources, the one chosen", async () => {
  const sent = [];
  const page = await loadScripts("app.js", {
    routes: (url, options) => {
      sent.push([url, options?.body]);
      if (url === "/api/pictures/search") {
        return new Response({ results: [
          { source: "commons", id: "File:A.jpg", title: "A", preview: "data:,", licence: "CC0" },
          { source: "pixabay", id: "42", title: "B", preview: "data:,", licence: "Pixabay" },
          { source: "commons", id: "File:C.jpg", title: "C", preview: "data:,", licence: "Public domain" },
        ] });
      }
      return new Response({ card: { picture: "picture-x.jpg", picture_prompt: "a castle", figure: "" } });
    },
  });
  const c = page.component();
  c.lessonId = "L1";
  const card = { id: "c1", front: "Un château ?", back: "el castillo", _subject: " un château fort " };
  await c.searchPictures(card);
  assert.equal(card._found.length, 3);
  assert.equal(c.foundSources(card), "Wikimedia Commons, Pixabay");
  await c.chooseFound(card, card._found[1]);
  assert.equal(card.picture, "picture-x.jpg");
  assert.equal(card._found, null);
  assert.deepEqual(sent, [
    ["/api/pictures/search", '{"subject":"un château fort","context":"Un château ? → el castillo","words":""}'],
    ["/api/lessons/L1/cards/c1/picture/found", '{"source":"pixabay","id":"42"}'],
  ]);

  // Its own picture's description: the search words chosen with it, as they are
  sent.length = 0;
  Object.assign(card, { picture_prompt: "a stone castle", picture_search: "castle", _subject: "a stone castle" });
  await c.searchPictures(card, "castle");
  assert.deepEqual(plain(JSON.parse(sent[0][1])), { subject: "a stone castle", context: "Un château ? → el castillo", words: "castle" });
});

test("find a picture: each source's pictures shown as it answers", async () => {
  let seen = null;
  const page = await loadScripts("app.js", {
    routes: (url, options) => {
      seen = options.headers.Accept;
      return Response.ndjson([
        { found: [{ source: "commons", id: "File:A.jpg", title: "A", preview: "data:,", licence: "CC0" }] },
        { found: [{ source: "openverse", id: "o1", title: "B", preview: "data:,", licence: "CC0" }] },
        { done: { words: "castle" } },
      ]);
    },
  });
  const c = page.component();
  const card = { id: "c1", front: "Un château ?", back: "el castillo", _subject: "un château" };
  await c.searchPictures(card);
  assert.equal(seen, "application/x-ndjson");
  assert.deepEqual(plain(card._found.map((f) => f.id)), ["File:A.jpg", "o1"]);
  assert.equal(card._searching, false);
});

test("find a picture: an error as the last line is said, the pictures already shown kept", async () => {
  const page = await loadScripts("app.js", {
    routes: () => Response.ndjson([
      { found: [{ source: "commons", id: "File:A.jpg", title: "A", preview: "data:,", licence: "CC0" }] },
      { error: { code: "picture.search_failed", params: {} } },
    ]),
  });
  const c = page.component();
  const card = { id: "c1", front: "x", back: "y" };
  await c.searchPictures(card);
  assert.ok(c.error);
  assert.equal(card._found.length, 1);
});

test("a picture's source: said in its panel, kept when the pictures come", async () => {
  const page = await loadScripts("app.js", {
    routes: () => new Response({ lesson: { cards: [{ id: "c1", picture: "picture-c1.jpg",
      picture_source: { source: "commons", licence: "Public domain", page: "https://commons.wikimedia.org/wiki/File:A.jpg" } }] },
      failures: 0 }),
  });
  const c = page.component();
  c.lessonId = "L1";
  c.cards = [{ id: "c1", picture_prompt: "a castle", picture: "" }];
  await c.drawPictures();
  assert.equal(c.cards[0].picture, "picture-c1.jpg");
  assert.equal(c.cards[0].picture_source.page, "https://commons.wikimedia.org/wiki/File:A.jpg");
  assert.equal(c.pictureSourceText(c.cards[0]), "Source: Wikimedia Commons · Public domain");
  assert.equal(c.pictureSourceText({ picture_source: { source: "drawn", model: "gpt-image-2" } }), "Drawn by the AI (gpt-image-2)");
  assert.equal(c.pictureSourceText({ picture_source: { source: "photo" } }), "Your photo");
  assert.equal(c.pictureSourceText({}), "");
  // Its page a link only when it is an https: address
  assert.equal(c.pictureSourcePage(c.cards[0]), "https://commons.wikimedia.org/wiki/File:A.jpg");
  for (const page of ["javascript:alert(1)", " javascript:alert(1)", "data:text/html,x", "http://example.org", ""]) {
    assert.equal(c.pictureSourcePage({ picture_source: { source: "commons", page } }), "", page);
  }
  assert.equal(c.pictureSourcePage({}), "");
});

test("a picture drawn with the lesson's: all its fields taken as it is ready, where it shows too", async () => {
  // "ready" left picture_on_back out: a picture meant for the answer shown on the question,
  // and the next save gave the server the card without it
  const ready = { card: "c1", step: "ready", picture: "picture-c1.svg", picture_source: { source: "drawn" },
    figure: "un triangle", figure_kind: "geometry", picture_prompt: "", picture_search: "", picture_on_back: true };
  const page = await loadScripts("app.js", { routes: () => Response.ndjson([ready, { result: { lesson: { cards: [] }, failures: 0 } }]) });
  const c = page.component();
  c.lessonId = "L1";
  c.cards = [{ id: "c1", front: "f", back: "b", figure: "un triangle", picture: "", picture_on_back: false }];
  await c.drawPictures();
  const { step, card, ...fields } = ready;
  for (const [field, value] of Object.entries(fields)) assert.deepEqual(plain(c.cards[0][field]), value, field);

  // An older server, all at once: the same from the lesson's cards
  const older = await loadScripts("app.js", { routes: () => new Response({ lesson: { cards: [{ id: "c1", ...fields }] }, failures: 0 }) });
  const o = older.component();
  o.lessonId = "L1";
  o.cards = [{ id: "c1", front: "f", back: "b", figure: "un triangle", picture: "", picture_on_back: false }];
  await o.drawPictures();
  for (const [field, value] of Object.entries(fields)) assert.deepEqual(plain(o.cards[0][field]), value, field);
});

test("a figure's credits link each project to its page as the credits give it (the maps' data is no Typst package)", async () => {
  const credits = [{ name: "notosaurus-atlas", version: "0.3.0", licence: "AGPL-3.0-or-later", url: "https://example.org/atlas" }];
  const page = await loadScripts("app.js", { routes: () => new Response(credits) });
  const c = page.component();
  const card = { picture_source: { made_with: ["Typst 0.15.1", "notosaurus-atlas 0.3.0", "cetz 0.5.2"] } };
  // Before the credits come (or without them): Typst's site, Typst Universe's pages
  assert.deepEqual(plain(c.figureCredits(card).map((p) => p.url)),
    ["https://typst.app", "https://typst.app/universe/package/notosaurus-atlas", "https://typst.app/universe/package/cetz"]);
  await c.loadCredits();
  assert.deepEqual(plain(c.figureCredits(card).map((p) => p.url)),
    ["https://typst.app", "https://example.org/atlas", "https://typst.app/universe/package/cetz"]);
});

test("the 🎤 stays when a lesson is shown, and the lesson's dictation option stays a yes/no", async () => {
  // Both were called "dictation": showing a lesson replaced the 🎤's state by its option
  const page = await loadScripts("app.js", { routes: () => new Response({}) });
  const c = page.component();
  c.mic.available = true;
  c.show({ id: "L1", deck: "D", cards: [], prompt: "p", dictation: false, voice: "" });
  assert.equal(c.mic.available, true);
  assert.equal(c.payload().dictation, false);
  c.newLesson?.();
  assert.equal(c.mic.available, true);
});

test("tidy up: not offered for Notosaurus's instructions as they are", async () => {
  const page = await loadScripts("app.js", { routes: () => new Response({}) });
  const c = page.component();
  c.prompts = [
    { id: "notosaurus:auto", builtin: true, name: "Automatique", text: "Regarde la leçon…" },
    { id: 3, builtin: false, name: "Mes mots", text: "les mots, euh, en espagnol" },
  ];
  c.selectedId = "notosaurus:auto";
  c.form.text = "Regarde la leçon…";
  assert.equal(c.canTidy(), false);  // tidy already
  c.form.text += " Dix cartes, non, douze.";  // changed (or dictated): offered
  assert.equal(c.canTidy(), true);
  c.selectedId = 3;
  c.form.text = "les mots, euh, en espagnol";
  assert.equal(c.canTidy(), true);  // one's own
  c.selectedId = null;
  c.form.text = "";
  assert.equal(c.canTidy(), false);  // nothing to tidy
});

test("instructions written before the prompts come stay (the first load came after them)", async () => {
  const builtin = [{ id: "notosaurus:auto", builtin: true, name: "Automatique", text: "Regarde la leçon…" }];
  const page = await loadScripts("app.js", { routes: () => new Response(builtin) });
  const c = page.component();
  c.$refs.promptText = { focus() {} };  // the field "Free" puts the cursor in
  c.chooseFree();
  c.form.text = "Une carte par mot de la famille";
  await c.loadPrompts("notosaurus:auto", true);
  assert.equal(c.selectedId, null);
  assert.equal(c.form.text, "Une carte par mot de la famille");
  const fresh = page.component();
  await fresh.loadPrompts("notosaurus:auto", true);  // nothing chosen yet: the last prompt used
  assert.equal(fresh.form.text, "Regarde la leçon…");
});

test("what the service tells for now: a notice closed once, features off, an update", async () => {
  const page = await loadScripts("app.js", {
    routes: (url) => (url === "/api/switches"
      ? new Response({ notice: { id: "n1", level: "warning", text: "Fixing it" }, disabled: ["lesson.complete"],
        update: true, store: "https://play.google.com/store/apps/details?id=app.notosaurus" })
      : null),
  });
  const c = page.component();
  await c.loadSwitches();
  assert.equal(c.switches.notice.text, "Fixing it");
  assert.equal(c.switches.update, true);
  assert.ok(c.off("lesson.complete") && !c.off("anki.send"));
  c.regeneratesInPlace = () => true;
  c.newPages = () => [{}];
  c.cards = [{ id: "c1" }];
  assert.equal(c.canComplete(), false);  // turned off: not offered
  c.closeNotice();
  assert.equal(c.noticeClosed, "n1");
  assert.equal(page.storage.getItem("notosaurus.noticeClosed"), "n1");  // closed for good on this device
});

test("no switches (the computer's page): nothing off, nothing shown", async () => {
  const page = await loadScripts("app.js", { routes: () => new Response({ detail: "Not Found" }, { status: 404 }) });
  const c = page.component();
  await c.loadSwitches();
  assert.equal(c.switches.notice, null);
  assert.equal(c.off("anki.send"), false);
});

test("🔊 says what the card's sound says: a dictation's sentence, then the word", async () => {
  const page = await loadScripts("app.js");
  const c = page.component();
  const card = { front: "Le chat boit du … (une boisson)", back: "lait" };
  assert.equal(c.spokenText(card), "lait");  // not a dictation
  c.dictation = true;
  assert.equal(c.spokenText(card), "Le chat boit du lait.\nlait");
  assert.equal(c.spokenText({ front: "Il a ... ans !", back: "$1" }), "Il a $1 ans !\n$1");
  assert.equal(c.spokenText({ front: "la mère", back: "la madre" }), "la madre");
});


// "✨ Image": the AI decides, then free pictures; one fits: it's the card's; several: picked;
// none: asked before the image model draws (it costs)
async function imagePage(found) {
  const sent = [];
  const page = await loadScripts("app.js", {
    routes: (url, options) => {
      sent.push(url);
      if (url.endsWith("/picture/make")) {
        return new Response({ card: { picture: "", picture_prompt: "a castle", picture_search: "castle", figure: "" }, search: "castle" });
      }
      if (url === "/api/pictures/search") return Response.ndjson([{ found }, { done: { words: "castle" } }]);
      return new Response({ card: { picture: "picture-c1-1.jpg", picture_prompt: "a castle", figure: "" } });
    },
  });
  const c = page.component();
  c.lessonId = "L1";
  return { c, sent };
}
const castle = (id) => ({ source: "commons", id, title: id, preview: "data:,", licence: "CC0", page: `https://x/${id}` });

test("✨ Image: the one free picture that fits is the card's at once", async () => {
  const { c, sent } = await imagePage([castle("a")]);
  const card = { id: "c1", front: "Un château ?", back: "el castillo" };
  await c.makePicture(card);
  assert.deepEqual(sent, ["/api/lessons/L1/cards/c1/picture/make", "/api/pictures/search", "/api/lessons/L1/cards/c1/picture/found"]);
  assert.equal(card.picture, "picture-c1-1.jpg");
  assert.equal(card._ask, false);
});

test("✨ Image: several fit, the user picks (the AI's first); none, asked before drawing", async () => {
  const several = await imagePage([castle("a"), castle("b")]);
  const card = { id: "c1", front: "Un château ?", back: "el castillo" };
  await several.c.makePicture(card);
  assert.deepEqual(plain(card._found.map((f) => f.id)), ["a", "b"]);  // the AI's order: its choice first
  assert.ok(!several.sent.some((u) => u.endsWith("/found")));

  const none = await imagePage([]);
  const other = { id: "c1", front: "Un château ?", back: "el castillo" };
  none.c.drawingCredits = 67;
  await none.c.makePicture(other);
  assert.equal(other._ask, true);
  assert.ok(!none.sent.some((u) => u.endsWith("/draw")));  // never drawn without a yes
  assert.match(none.c.drawingCost(), /67/);
  await none.c.drawPicture(other);
  assert.ok(none.sent.at(-1).endsWith("/picture/draw"));
  assert.equal(other._ask, false);
});

test("pictures cancelled as they are drawn: no error, the cards as they were, their steps cleared", async () => {
  const page = await loadScripts("app.js", {
    routes: () => Response.ndjson([{ card: "c1", step: "drawing" }, { cancelled: true }]),
  });
  const c = page.component();
  c.lessonId = "L1";
  c.cards = [{ id: "c1", front: "f", back: "b", figure: "un triangle", picture: "" }];
  await c.drawPictures();
  assert.equal(c.error, "");
  assert.equal(c.cards[0].picture, "");
  assert.equal(c.cards[0]._step, "");
  assert.deepEqual(plain(c.drawingLessons), []);

  // A card's own picture, cancelled: no error, the card as it was
  const card = { id: "c2", front: "Un château ?", back: "el castillo", picture: "old.jpg", figure: "", picture_prompt: "a castle" };
  c.saveTimer = null;
  assert.equal(await c.pictureAction(card, { path: "/draw", method: "POST" }), null);
  assert.equal(c.error, "");
  assert.equal(card.picture, "old.jpg");
  assert.equal(card._drawing, false);
});

test("the pictures being drawn belong to their lesson: another one opened meanwhile isn't held back", async () => {
  let done;
  const page = await loadScripts("app.js", {
    routes: () => new Promise((resolve) => { done = () => resolve(new Response({ lesson: { cards: [] } })); }),
  });
  const c = page.component();
  c.lessonId = "A";
  c.cards = [{ id: "c1", front: "f", back: "b", figure: "un triangle", picture: "" }];
  const drawing = c.drawPictures();
  assert.equal(c.drawingHere(), true);
  c.lessonId = "B";  // another lesson opened: its saves and its "drawing…" not held back by A's
  assert.equal(c.drawingHere(), false);
  c.lessonId = "A";
  assert.equal(c.drawingHere(), true);
  await new Promise((resolve) => setTimeout(resolve, 0));
  done();
  await drawing;
  assert.equal(c.drawingHere(), false);
  assert.deepEqual(plain(c.drawingLessons), []);
});

test("a card's picture shown on one side only: its own, or while this lesson's are drawn", async () => {
  const c = (await loadScripts("app.js")).component();
  c.lessonId = "A";
  const sides = (card) => [c.pictureShown(card, false), c.pictureShown(card, true)];
  assert.deepEqual(sides({ picture: "p.svg" }), [true, false]);
  assert.deepEqual(sides({ picture: "p.svg", picture_on_back: true }), [false, true]);
  assert.deepEqual(sides({ picture: "", _drawing: true, picture_on_back: true }), [false, true]);
  const asked = { picture: "", figure: "un triangle" };
  assert.deepEqual(sides(asked), [false, false]);  // nothing being drawn: no empty frame
  c.drawingLessons = ["B"];
  assert.deepEqual(sides(asked), [false, false]);  // another lesson's
  c.drawingLessons = ["A"];
  assert.deepEqual(sides(asked), [true, false]);
  assert.deepEqual(sides({ picture: "" }), [false, false]);  // none asked for
});

test("children: the one chosen kept on this device, the lessons filtered, its decks' levels not shown again", async () => {
  const sent = [];
  const kids = [
    { id: "jules", name: "Jules", grade: "5e", decks: "Jules::{classe}", instructions: "" },
    { id: "mathilde", name: "Mathilde", grade: "3e", decks: "Mathilde", instructions: "" },
  ];
  const page = await loadScripts("app.js", {
    routes: (url, options) => {
      if (url === "/api/children" && options?.method === "PUT") {
        sent.push(JSON.parse(options.body));
        return new Response(JSON.parse(options.body));
      }
      if (url === "/api/children") return new Response(kids);
      return null;
    },
  });
  const c = page.component();
  await c.loadChildren();
  assert.equal(c.currentChild().name, "Jules");  // the first, nothing chosen yet
  c.chooseChild("mathilde");
  assert.equal(page.storage.getItem("notosaurus.child"), "mathilde");
  c.lessons = [{ id: "a", deck: "Mathilde::SVT", child: "mathilde" }, { id: "b", deck: "Jules::5e::Anglais", child: "jules" },
               { id: "c", deck: "Maths", child: "" }];
  assert.deepEqual(plain(c.visibleLessons().map((l) => l.id)), ["a", "c"]);  // hers, and those for no one
  c.allChildren = true;
  assert.equal(c.visibleLessons().length, 3);
  c.chooseChild("jules");
  assert.deepEqual(plain(c.withoutChildLevels(["Jules", "5e", "Anglais"])), ["Anglais"]);

  // A new child: its id from its first name; its decks suggested
  c.openChildren();
  c.addChild();
  const added = c.childrenSheet.list.at(-1);
  added.name = "Léa";
  c.setGrade(added, "Year 7");
  added.decks = c.decksWithClass(added);
  assert.equal(added.decks, "Léa::Year 7");
  c.setGrade(added, "Year 8");  // a new school year: its decks follow
  assert.equal(added.decks, "Léa::Year 8");
  c.setGrade(added, "  Maths::Sup  ");  // typed freely: one deck's name, not sub-decks
  assert.equal(added.grade, "Maths Sup");
  assert.equal(added.decks, "Léa::Maths Sup");
  c.setGrade(added, "Year 8");
  await c.saveChildren();
  assert.deepEqual(plain(sent[0].map((k) => k.id)), ["jules", "mathilde", "lea"]);
  assert.equal(c.children.length, 3);
});


test("children: the instructions' example fits the class", async () => {
  const page = await loadScripts("app.js", { languages: ["fr-FR"] });
  const c = page.component();
  const example = (grade) => c.instructionsExample({ grade });
  assert.match(example("CE1"), /lit encore lentement/);
  assert.match(example("5e"), /contrôle/);
  assert.match(example("Terminale"), /bac/);
  assert.match(example(""), /peu de cartes/);
  assert.match(example("Maths Sup"), /peu de cartes/);  // a class of its own: the general example
  assert.match(example("Prépa"), /bac/);  // the suggested higher classes: the oldest's
});

test("children: the sheet opens on the choice; one card edited at a time, cancelled as it was", async () => {
  const kids = [{ id: "jules", name: "Jules", grade: "5e", decks: "", instructions: "" }];
  const page = await loadScripts("app.js", { routes: (url) => (url === "/api/children" ? new Response(kids) : null) });
  const c = page.component();
  await c.loadChildren();
  c.openChildren();
  assert.equal(c.childrenSheet.editing, null);  // the choice first
  c.editChild(0);
  c.childrenSheet.list[0].name = "Julien";
  c.cancelChild();
  assert.equal(c.childrenSheet.list[0].name, "Jules");  // as it was
  assert.equal(c.childrenSheet.editing, null);
  c.chooseChild("jules");
  assert.equal(c.childrenSheet.open, false);  // chosen: closed

  c.children = [];
  c.openChildren();
  assert.equal(c.childrenSheet.editing, 0);  // none yet: a new one's card at once
});

test("a profile said with its child's name; a lesson, whom it is for", () => {
  const c = app.component();
  c.children = [
    { id: "lea", name: "Léa", anki_profile: "Léa" },  // a profile per child
    { id: "jules", name: "Jules", anki_profile: "Famille" },
    { id: "tom", name: "Tom", anki_profile: "Famille" },
  ];
  assert.equal(c.profileFor("Léa"), "Léa");
  assert.equal(c.profileChild("Léa").id, "lea");  // the same name as its profile: still its child
  assert.equal(c.profileFor("Famille"), "Famille");  // two children: the profile's name
  assert.equal(c.profileChild("Famille"), null);
  c.lessonChild = "jules";
  c.lessonOwner = "Famille";
  assert.equal(c.lessonFor(), "Jules");
  c.lessonChild = "";
  assert.equal(c.lessonFor(), "Famille");  // no child said: the profile that made it
});

test("the card a note's key names: its id, a diagram label, or its front text", () => {
  const cards = JSON.stringify([
    { id: "a1", front: "le <b>crayon</b>\nbleu", mask: null },
    { id: "d1", front: "Qu'est-ce que (2) ?", mask: { page: 1, n: 2 } },
    { id: "d2", front: "Qu'est-ce que (2) ?", mask: { page: 2, n: 2 } },
  ]);
  const found = (key) => plain(app.run(`findLinkedCard(${cards}, ${JSON.stringify(key)})?.id ?? null`));
  assert.equal(found("a1"), "a1");
  assert.equal(found("2026-10-15-svt:2:2"), "d2"); // a diagram label: lesson:page:n
  assert.equal(found("le crayon bleu"), "a1"); // Anki's {{text:Front}}: tags gone, one space
  assert.equal(found("Qu'est-ce que (2) ?"), "d1"); // the same front twice: the first
  assert.equal(found("nope"), null);
});

// "Add to Anki" with the page's answer to /api/anki/send (`lines`, as it comes): the
// labels its button showed meanwhile, and the component after
async function sendWith(lines) {
  const page = await loadScripts("app.js", {
    routes: (url, options) => {
      if (url !== "/api/anki/send") return new Response([]);
      assert.equal(options.headers.Accept, "application/x-ndjson");
      return Response.ndjson(lines);
    },
  });
  const c = page.component();
  const shown = [];
  let step = "";
  Object.defineProperty(c, "sendStep", { get: () => step, set: (v) => { step = v; if (v) shown.push(v); } });
  await c.sendToAnki();
  return { c, shown };
}

test("Add to Anki: its steps said on the button as they come, then its answer", async () => {
  const { c, shown } = await sendWith([
    { step: "sounds", done: 0, total: 2 },
    { step: "sounds", done: 1, total: 2 },
    { step: "cards" },
    { result: { added: 2, updated: 0, audio_failures: 0, leftovers: [] } },
  ]);
  assert.equal(shown.length, 3);
  assert.match(shown[1], /1 \/ 2/);
  assert.ok(!/\d/.test(shown[2]));  // the cards: no count
  assert.equal(c.sending, false);
  assert.equal(c.sendStep, "");  // the button's own label again
  assert.equal(c.error, "");
  assert.equal(c.lessonExported, true);
});

test("Add to Anki: cancelled as it goes, nothing said, nothing taken as sent", async () => {
  const { c, shown } = await sendWith([{ step: "sounds", done: 0, total: 2 }, { cancelled: true }]);
  assert.equal(shown.length, 1);
  assert.equal(c.error, "");  // as any cancelled work: no error
  assert.equal(c.success, "");
  assert.equal(c.lessonExported, false);
  assert.equal(c.sending, false);
  assert.equal(c.sendStep, "");
});

test("Add to Anki: cards not sent are said, never \"nothing to change\" alone", async () => {
  // ANK-08: a dictation whose cards had no front, none sent: "✓ In Anki: nothing to change"
  const { c } = await sendWith([{ result: { added: 0, updated: 0, skipped: 2, audio_failures: 0, leftovers: [] } }]);
  assert.match(c.error, /2/);
  const sent = await sendWith([{ result: { added: 2, updated: 0, skipped: 0, audio_failures: 0, leftovers: [] } }]);
  assert.equal(sent.c.error, "");
});

test("Add to Anki: an error as the last line is said", async () => {
  const { c } = await sendWith([{ step: "cards" }, { error: { code: "anki.unreachable", params: {} } }]);
  assert.ok(c.error);
  assert.equal(c.sending, false);
  assert.equal(c.lessonExported, false);
});

test("photos past the lesson's pages: not added, said", async () => {
  const page = await loadScripts("app.js");
  page.run("resize = async (file) => file; URL.createObjectURL = () => 'blob:'");  // no canvas here
  page.run("configKnown()");  // the server's settings read, as init() does: the room below is the lesson's
  const c = page.component();
  c.maxPhotos = 10;
  c.photos = Array.from({ length: 9 }, () => ({ url: "p" }));
  await c.addFiles([{ name: "a.jpg", type: "image/jpeg" }, { name: "b.jpg", type: "image/jpeg" }, { name: "c.jpg", type: "image/jpeg" }]);
  assert.equal(c.photos.length, 10);
  assert.equal(c.error, "A lesson holds 10 pages: 2 photos were not added.");
});

test("a photo's crop frame: its corners dragged within the photo, never smaller than its least size", () => {
  const moved = (corner, dx, dy) => plain(app.run(`cropMoved([0, 0, 1, 1], "${corner}", ${dx}, ${dy})`));
  assert.deepEqual(moved("nw", 0.2, 0.1), [0.2, 0.1, 1, 1]);  // the opposite corner stays
  assert.deepEqual(moved("se", -0.25, -0.5), [0, 0, 0.75, 0.5]);
  assert.deepEqual(moved("ne", 0.5, -0.5), [0, 0, 1, 1]);  // never out of the photo
  assert.deepEqual(moved("sw", 2, -2), [0.9, 0, 1, 0.1]);  // never smaller than CROP_MIN
});

test("a photo's crop in its pixels: none when it keeps the whole photo; seen again as the frame", () => {
  assert.equal(app.run("cropPixels([0, 0, 1, 1], 600, 800)"), null);
  assert.equal(app.run("cropPixels([0.0001, 0, 1, 0.9999], 600, 800)"), null);  // less than a pixel off: the whole photo
  assert.deepEqual(plain(app.run("cropPixels([0.1, 0.25, 0.5, 1], 600, 800)")), [60, 200, 300, 800]);
  assert.deepEqual(plain(app.run("cropBox([60, 200, 300, 800], 600, 800)")), [0.1, 0.25, 0.5, 1]);
  assert.deepEqual(plain(app.run("cropBox(undefined, 600, 800)")), [0, 0, 1, 1]);
});

test("a photo turned a quarter turn clockwise turns its crop with it", () => {
  // 600 × 800, the top left quarter kept: once turned (800 × 600), the top right quarter
  assert.deepEqual(plain(app.run("turnedCrop([0, 0, 300, 400], 800)")), [400, 0, 800, 300]);
  // a band at the bottom: on the left once turned
  assert.deepEqual(plain(app.run("turnedCrop([0, 600, 600, 800], 800)")), [0, 0, 200, 600]);
  // four turns: as it was
  let crop = "[60, 200, 300, 800]";
  const sizes = [800, 600, 800, 600];  // the photo's height before each turn
  for (const h of sizes) crop = JSON.stringify(plain(app.run(`turnedCrop(${crop}, ${h})`)));
  assert.equal(crop, "[60,200,300,800]");
});

test("a shared text in a lesson's pages: its words never cut, its paragraphs kept, as many pages as it needs", () => {
  const fits = "(s) => s.length <= 12";  // a line holds 12 characters
  const lines = plain(app.run(`textLines("La Bastille est prise.\\n\\nEn 1789.\\r\\nhttps://example.org/longue", ${fits})`));
  assert.deepEqual(lines.map((l) => l.text), ["La Bastille", "est prise.", "", "En 1789.", "https://exam", "ple.org/long", "ue"]);
  assert.deepEqual(lines.map((l) => l.end), [false, true, true, true, false, false, true]);
  const pages = plain(app.run(`textPages(textLines("La Bastille est prise.\\n\\nEn 1789.", ${fits}), 3)`));
  assert.deepEqual(pages.map((p) => p.text), ["La Bastille est prise.", "En 1789."]);  // a page's text: its words, its paragraphs
  assert.deepEqual(pages[0].lines, ["La Bastille", "est prise.", ""]);
  assert.deepEqual(plain(app.run(`textPages(textLines("  \\n ", ${fits}), 3)`)), []);  // blank: no page
});

test("what was shared to the app: a lesson made kept and a new one started, a lesson in progress added to", async () => {
  const calls = [];
  let shared = { files: [{ n: 1, name: "cahier.jpg", type: "image/jpeg" }, { n: 2, name: "Leçon.pdf", type: "application/pdf" }], text: "La Bastille.", skipped: ["archive.zip"], id: "s 1" };
  const page = await loadScripts("app.js", {
    routes: (url, options) => {
      calls.push(`${options?.method ?? "GET"} ${url}`);
      if (url === "/api/shared" && !options?.method) return new Response(shared);
      return new Response(new Blob(["x"]));
    },
  });
  const c = page.component();
  const added = [];
  c.addFiles = async (files) => added.push(...files.map((f) => `${f.name} ${f.type}`));
  c.addText = async (text) => added.push(`text: ${text}`);
  let fresh = 0;
  c.newLesson = async () => { fresh++; c.lessonId = null; };

  c.lessonId = "abc";  // a lesson made, open: kept, what was shared starts a new one
  await c.takeShared();
  assert.equal(fresh, 1);
  assert.deepEqual(added, ["cahier.jpg image/jpeg", "Leçon.pdf application/pdf", "text: La Bastille."]);
  assert.equal(c.error, "Notosaurus takes photos, PDFs and text: “archive.zip” was not added.");
  // Its files and its taking: that share only, by its id (another shared meanwhile has its own
  // files under the same numbers, and stays for the next call)
  assert.deepEqual(calls.filter((call) => call.includes("shared")), ["GET /api/shared", "GET /api/shared/1?id=s%201", "GET /api/shared/2?id=s%201", "DELETE /api/shared?id=s%201"]);

  added.length = 0;
  c.error = "";
  shared = { files: [{ n: 1, name: "p2.jpg", type: "image/jpeg" }], text: "", skipped: [] };
  c.photos = [{ url: "p1" }];  // a lesson in progress, not made: added to, nothing replaced
  await c.takeShared();
  assert.equal(fresh, 1);
  assert.deepEqual(added, ["p2.jpg image/jpeg"]);
  assert.equal(c.error, "");

  shared = { files: [], text: "", skipped: [] };  // nothing waiting (opened again): nothing done
  await c.takeShared();
  assert.deepEqual(added, ["p2.jpg image/jpeg"]);
});

test("a web page's address alone shared: nothing added, the lesson as it is, said what to share instead", async () => {
  const calls = [];
  const page = await loadScripts("app.js", {
    languages: ["fr-FR"],
    routes: (url, options) => {
      calls.push(`${options?.method ?? "GET"} ${url}`);
      return new Response({ files: [], text: "", skipped: [], error: "share.link_only" });
    },
  });
  const c = page.component();
  let fresh = 0;
  c.newLesson = async () => { fresh++; };
  c.addText = async () => { throw new Error("no page for a link"); };
  c.lessonId = "abc";  // a lesson open: left as it is
  await c.takeShared();
  assert.equal(fresh, 0);
  assert.equal(c.error, "Ce partage ne contient que l'adresse d'une page web. Partagez plutôt une capture d'écran de la page, ou la page enregistrée en PDF depuis Chrome.");
  assert.deepEqual(calls.filter((call) => call.includes("shared")), ["GET /api/shared", "DELETE /api/shared"]);
});

test("lessons ticked to share: a whole subject at once, the deck they share as the package's name", () => {
  const c = app.component();
  c.lessons = [
    { id: "a", deck: "Histoire::Révolution" },
    { id: "b", deck: "histoire::Napoléon" },
    { id: "c", deck: "Anglais::Unit 1" },
  ];
  c.startLessonPick();
  const group = { lessons: [{ id: "a" }, { id: "b" }] };
  c.togglePickedGroup(group);
  assert.deepEqual(plain(c.lessonPick), ["a", "b"]);
  assert.equal(c.groupPicked(group), true);
  c.togglePickedLesson({ id: "b" });  // one taken off: the subject no longer whole
  assert.equal(c.groupPicked(group), false);
  c.togglePickedGroup(group);
  assert.equal(c.sharedDeck(c.lessonPick), "Histoire");
  assert.equal(c.sharedDeck(["a", "c"]), "");
  c.togglePickedGroup(group);  // whole: taken off together
  assert.deepEqual(plain(c.lessonPick), []);
});

test("sharing the cards: offered where the host makes .apkg, hidden while the relay turns it off", () => {
  const c = app.component();
  c.apkg = true;
  c.switches = { ...c.switches, disabled: [] };
  assert.equal(c.canShare(), true);
  c.switches = { ...c.switches, disabled: ["anki.share"] };
  assert.equal(c.canShare(), false);
  c.switches = { ...c.switches, disabled: [] };
  c.apkg = false;  // a host without .apkg (an older app's page)
  assert.equal(c.canShare(), false);
});

test("the waiting card's estimate: by mode and pages, as measured; a correction by its cards and pages", async () => {
  const page = await loadScripts("app.js", { languages: ["fr-FR"] });
  const c = page.component();
  const note = (quick, pages, revising = false, cards = 0) => {
    Object.assign(c, { loadingQuick: quick, loadingPages: pages, loadingCards: cards, batch: null, aiStep: "", coming: [] });
    c.revision.busy = revising;
    return c.loadingNote();
  };
  assert.equal(note(true, 1), "Environ 15 secondes.");
  assert.equal(note(true, 0), "Environ 15 secondes.");  // the instructions alone: as a page
  assert.equal(note(true, 5), "Environ 25 secondes.");
  assert.equal(note(true, 10), "Environ 40 secondes.");
  assert.equal(note(false, 1), "Environ 20 secondes.");
  assert.equal(note(false, 10), "Environ 40 secondes.");
  // a correction writes every card again: 16 cards of 2 pages, 22 s measured careful, 15 s quick
  assert.equal(note(false, 2, true, 16), "Environ 25 secondes.");
  assert.equal(note(true, 2, true, 16), "Environ 20 secondes.");
  assert.equal(note(false, 3, true, 40), "Environ 50 secondes.");
  c.aiStep = "slow";  // late: said instead
  assert.equal(c.loadingNote(), "L'IA met plus de temps que d'habitude à répondre…");
});

test("the waiting card's estimate goes by the pages sent: those of this call, at most perCall", async () => {
  const asked = [];
  const page = await loadScripts("app.js", {
    languages: ["fr-FR"],
    routes: (url) => {
      if (url === "/api/extract") return new Promise((answered) => asked.push(answered));  // the AI still writing
      return new Response({});
    },
  });
  const c = page.component();
  for (const [photos, pages, said] of [[5, 5, "Environ 25 secondes."], [15, 10, "Environ 40 secondes."]]) {
    c.photos = Array.from({ length: photos }, () => ({ blob: new Blob(["jpeg"], { type: "image/jpeg" }), text: "" }));
    c.quick = true;
    c.extract();
    await new Promise((done) => setTimeout(done, 50));
    assert.equal(c.loadingPages, pages);
    c.batch = null;  // (15 photos: "pages 1 to 10 of 15" said instead while it goes)
    assert.equal(c.loadingNote(), said);
    asked.pop()(new Response({ error: "cancelled" }, { status: 409 }));
    await new Promise((done) => setTimeout(done, 50));
  }
});

test("Review with nothing due today: said, AnkiDroid opened on its decks", async () => {
  let answer = { opened: true, nothing_due: true };
  const page = await loadScripts("app.js", {
    languages: ["fr-FR"],
    routes: (url) => new Response(url === "/api/anki/review" ? answer : {}),
  });
  const c = page.component();
  c.deck = "Espagnol::Leçon 5";
  await c.reviewLesson();
  assert.equal(c.success, "Rien à réviser aujourd'hui dans ce paquet : AnkiDroid est ouvert sur vos paquets.");
  answer = { opened: true };  // its reviewer opened: nothing to say
  await c.reviewLesson();
  assert.equal(c.success, "");
});

test("a card's correction about its figure as drawn: drawn again, told what is wrong", async () => {
  const asked = [];
  const figure = { id: "c1", front: "ABC ?", back: "un triangle", figure: "Triangle ABC", picture: "picture-c1-0123abcd.svg" };
  let problem = "E est sous [BC]";
  const page = await loadScripts("app.js", {
    routes: (url, options) => {
      asked.push([url, options?.body ? JSON.parse(options.body) : null]);
      if (url.startsWith("/api/lessons/L1/fix-card")) {
        return new Response({ card: figure, summary: "Figure", figure_problem: problem });
      }
      if (url === "/api/lessons/L1/cards/c1/picture/draw") return new Response({ card: { ...figure, picture: "picture-c1-89abcdef.svg" } });
      return new Response({});
    },
  });
  const c = page.component();
  c.lessonId = "L1";
  c.saveNow = async () => {};
  c.cards = [{ ...figure, key: 1, _fix: { text: "le E est mal placé", busy: false } }];
  await c.fixCard(c.cards[0]);
  const draws = asked.filter(([url]) => url.endsWith("/picture/draw"));
  assert.deepEqual(draws.map(([, body]) => body), [{ problem: "E est sous [BC]", careful: false }]);
  assert.equal(c.cards[0].picture, "picture-c1-89abcdef.svg");
  // a correction about its text: its figure as it was
  problem = "";
  asked.length = 0;
  c.cards[0]._fix = { text: "la réponse est un triangle rectangle", busy: false };
  await c.fixCard(c.cards[0]);
  assert.deepEqual(asked.filter(([url]) => url.includes("/picture")), []);
});

test("corrections as the lesson is made: quick or careful, then once more carefully", async () => {
  const asked = [];
  const card = { id: "c1", front: "la mère", back: "la madre" };
  const page = await loadScripts("app.js", {
    routes: (url, options) => {
      const body = options?.body && typeof options.body === "string" ? JSON.parse(options.body) : null;
      if (url.startsWith("/api/lessons/L1/fix-card")) {
        asked.push(["fix", body.quick, body.instruction]);
        return new Response({ card: { ...card, back: body.quick ? "la mama" : "la mamá" }, summary: "Corrigée" });
      }
      if (url.startsWith("/api/lessons/L1/revise")) {
        asked.push(["revise", body.quick, body.instruction]);
        return new Response({ lesson: { deck: "D", cards: [{ ...card, back: "la mamá" }], reverse: false }, summary: "Corrigée" });
      }
      return new Response({});
    },
  });
  const c = page.component();
  Object.assign(c, { lessonId: "L1", quick: true, saveNow: async () => {}, loadLessons: () => {}, drawPictures: () => {} });
  c.cards = [{ ...card, key: 1, _fix: { text: "plutôt la mamá", busy: false } }];
  await c.fixCard(c.cards[0]);
  assert.deepEqual(c.cards[0]._fixed.quick, true);
  await c.fixCarefully(c.cards[0]);  // undone, asked again with thinking
  assert.equal(c.cards[0].back, "la mamá");
  assert.equal(c.cards[0]._fixed.quick, false);  // careful already: not offered again
  c.revision.text = "plutôt la mamá";
  await c.revise();
  assert.equal(c.revision.quick, true);
  await c.reviseCarefully();
  assert.equal(c.revision.quick, false);
  c.quick = false;  // careful chosen: corrections careful too
  c.revision.text = "x";
  await c.revise();
  assert.deepEqual(asked, [
    ["fix", true, "plutôt la mamá"], ["fix", false, "plutôt la mamá"],
    ["revise", true, "plutôt la mamá"], ["revise", false, "plutôt la mamá"], ["revise", false, "x"],
  ]);
});

test("a figure drawn again after a correction: the old one shown until the new one comes", async () => {
  const card = { id: "c1", front: "ABC ?", back: "un carré", figure: "Un carré ABCD", picture: "picture-c1-0123abcd.svg" };
  let drawn;
  const page = await loadScripts("app.js", {
    routes: (url) => {
      if (url.startsWith("/api/lessons/L1/fix-card")) {
        return new Response({ card: { ...card, figure: "Un carré ABCD en rouge", picture: "" }, summary: "Figure en rouge" });
      }
      if (url === "/api/lessons/L1/pictures") return new Promise((answer) => { drawn = answer; });  // being drawn
      return new Response({});
    },
  });
  const c = page.component();
  Object.assign(c, { lessonId: "L1", saveNow: async () => {} });
  c.cards = [{ ...card, key: 1, _fix: { text: "le carré en rouge", busy: false } }];
  await c.fixCard(c.cards[0]);
  await new Promise((done) => setTimeout(done, 20));
  assert.equal(c.firstFigureUrl(c.cards[0]), "/api/lessons/L1/pictures/picture-c1-0123abcd.svg");  // shown faded meanwhile
  drawn(new Response({ lesson: { cards: [{ ...card, figure: "Un carré ABCD en rouge", picture: "picture-c1-89abcdef.svg" }] } }));
  await new Promise((done) => setTimeout(done, 20));
  assert.equal(c.cards[0].picture, "picture-c1-89abcdef.svg");
  assert.equal(c.firstFigureUrl(c.cards[0]), "");  // replaced
});

test("a lesson's correction changing a figure: its old one shown until drawn again", async () => {
  const card = { id: "c1", front: "ABC ?", back: "un carré", figure: "Un carré ABCD", picture: "picture-c1-0123abcd.svg" };
  const page = await loadScripts("app.js", {
    routes: (url) => {
      if (url.startsWith("/api/lessons/L1/revise")) {
        return new Response({ lesson: { deck: "D", cards: [{ ...card, figure: "Un carré ABCD en rouge", picture: "" }], reverse: false }, summary: "ok" });
      }
      if (url === "/api/lessons/L1/pictures") return new Promise(() => {});  // being drawn
      return new Response({});
    },
  });
  const c = page.component();
  Object.assign(c, { lessonId: "L1", loadLessons: () => {} });
  c.cards = [{ ...card, key: 1 }];
  c.revision.text = "le carré en rouge";
  await c.revise();
  assert.equal(c.firstFigureUrl(c.cards[0]), "/api/lessons/L1/pictures/picture-c1-0123abcd.svg");
});

test("pictures not pruned while a figure a correction replaced is still to be drawn again from", async () => {
  const sent = [];
  const page = await loadScripts("app.js", {
    routes: (url, options) => {
      sent.push([url, options?.method]);
      return new Response({ removed: 0 });
    },
  });
  const c = page.component();
  const old = {
    front: "a", back: "b", figure: "Un carré ABCD", figure_kind: "geometry", picture: "picture-c1-0123abcd.svg",
    picture_source: { source: "drawn", engine: "typst", sources: [{ file: "picture-c1-0123abcd.typ" }] },
  };
  c.show({ id: "L1", deck: "D", cards: [{ ...old, figure: "Un carré ABCD en rouge", picture: "", picture_source: null }] });
  c.cards[0]._previous = c.previousFigure(old, c.cards[0]);
  assert.equal(JSON.stringify(c.cards[0]._previous), JSON.stringify({ source: old.picture_source, kind: "geometry" }));
  await c.prunePictures();
  assert.deepEqual(sent, []);  // its sources: what it is drawn again from
  c.cards[0].picture = "picture-c1-4567cdef.svg";  // drawn
  await c.prunePictures();
  assert.deepEqual(sent.filter(([url]) => url.endsWith("/prune")), [["/api/lessons/L1/pictures/prune", "POST"]]);
});

test("a figure a correction replaced is drawn again from it only when it was a figure with sources", async () => {
  const page = await loadScripts("app.js", { routes: () => new Response({}) });
  const c = page.component();
  const source = { source: "drawn", engine: "typst", sources: [{ file: "picture-c1-0123abcd.typ" }] };
  const figure = { figure: "Un carré", figure_kind: "geometry", picture_source: source };
  assert.equal(c.previousFigure({ ...figure, picture_source: { source: "drawn", engine: "svg" } }, { figure: "x" }), null);
  assert.equal(c.previousFigure({ picture_prompt: "a dog", picture_source: source }, { figure: "x" }), null);
  assert.equal(c.previousFigure(figure, { picture_prompt: "a dog" }), null);
});

test("pictures pruned only once no card is edited: the first card (key 0) edited is one", async () => {
  const sent = [];
  const page = await loadScripts("app.js", {
    routes: (url, options) => {
      sent.push([url, options?.method]);
      return new Response({ removed: 0 });
    },
  });
  const c = page.component();
  c.show({ id: "L1", deck: "D", cards: [{ front: "a", back: "b" }, { front: "c", back: "d" }] });
  assert.equal(c.cards[0].key, 0);  // keys start at 0
  c.editing = c.cards[0].key;
  await c.prunePictures();
  assert.deepEqual(sent, []);  // its correction may still be undone: its old picture kept
  c.editing = "";
  await c.prunePictures();
  assert.deepEqual(sent, [["/api/lessons/L1/pictures/prune", "POST"]]);
});
