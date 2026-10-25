// The children the lessons are for (app/children.py): which one the next lesson is for
// (kept on this device), their cards edited in a sheet (first name, class, decks,
// instructions). The first name never goes to the AI: only the class and the instructions.
// On the computer, a card belongs to the Anki profile it was made in (anki_profile): only the
// open profile's are offered (a profile per child: its one, chosen; a shared profile: its
// children), never another profile's (its cards would go to that one's collection).
// Methods of the page's Alpine component (app.js), as `this`.

const CHILD = "notosaurus.child";  // the child chosen on this device

const childrenPart = {
  async loadChildren() {
    try {
      this.children = await (await api("/api/children")).json();
    } catch {
      this.children = [];  // a server without children (an older one): none
    }
    const kept = storage("get", undefined, CHILD);
    this.childId = this.children.some((c) => c.id === kept) ? kept : (this.children[0]?.id ?? "");
    this.followProfile();
  },

  // The Anki profile the cards belong to: the open one, on the computer (none: the app, Anki closed)
  childrenProfile() {
    return this.profiles ? (this.anki.profile ?? "") : "";
  },

  // A child of the open Anki profile (every one where no profile is open)
  ofProfile(child) {
    const profile = this.childrenProfile();
    return !profile || child.anki_profile === profile;
  },

  // The open profile's children: its only one chosen, a child of another profile no longer
  followProfile() {
    const mine = this.children.filter((c) => this.ofProfile(c));
    const current = this.currentChild();
    if (mine.length === 1 && current !== mine[0]) this.childId = mine[0].id;
    else if (current && !this.ofProfile(current)) this.childId = mine[0]?.id ?? "";
    else if (!current && mine.length) this.childId = mine[0].id;
    else return;
    storage("set", this.childId, CHILD);
  },

  // The open Anki profile, under the name: where the cards go, always said on the computer
  profileShown() {
    return this.anki.available && this.profiles;
  },

  // The child an Anki profile is for, when it is one child's alone (a profile per child)
  profileChild(profile) {
    const theirs = this.children.filter((c) => c.anki_profile === profile);
    return theirs.length === 1 ? theirs[0] : null;
  },

  // An Anki profile said with its child's name, when it has one
  profileFor(profile) {
    return this.profileChild(profile)?.name ?? profile;
  },

  // Whom the open lesson is for: its child, else the Anki profile that made it
  lessonFor() {
    return this.children.find((c) => c.id === this.lessonChild)?.name || this.lessonOwner;
  },

  currentChild() {
    return this.children.find((c) => c.id === this.childId) ?? null;
  },

  chooseChild(id) {
    this.childId = id;
    storage("set", id, CHILD);
    this.childrenSheet.open = false;
  },

  // The lessons of the child chosen (and those for no child), unless all are asked for
  forChild(lessons) {
    if (!this.childId || this.allChildren) return lessons;
    return lessons.filter((l) => !l.child || l.child === this.childId);
  },

  // A lesson's deck as the list shows it: the chosen child's levels ("Jules::5e") left out
  withoutChildLevels(parts) {
    const child = this.currentChild();
    if (!child?.decks) return parts;
    const levels = child.decks.replace(/\{[^}]+\}/g, child.grade ?? "").split("::").map((p) => fold(p.trim())).filter(Boolean);
    let n = 0;
    while (n < parts.length && n < levels.length && fold(parts[n]) === levels[n]) n++;
    return parts.slice(n);
  },

  // The decks offered for the deck name: the chosen child's and those of no child, never
  // another child's (as children.decks_for_ai); no child chosen: all
  decksForChild(decks) {
    const child = this.currentChild();
    if (!child) return decks;
    const mine = childLevels(child);
    const every = new Set(this.children.flatMap((c) => [...childLevels(c)]));
    return decks.filter((deck) => {
      const parts = deck.split("::").map((p) => p.trim()).filter(Boolean);
      let n = 0;
      while (n < parts.length && every.has(sameLevel(parts[n]))) n++;
      return parts.slice(0, n).every((p) => mine.has(sameLevel(p)));
    });
  },

  // The sheet opens on the choice (a row each, tapped: chosen); a child's card edited on
  // its own (editing: its place in the list); none yet: a new one's card at once
  // Cards made before they belonged to a profile: the open profile's (saved)
  async openChildren() {
    this.childrenSheet = { open: true, list: this.children.map((c) => ({ ...c })), editing: null, saving: false, error: "" };
    const profile = this.childrenProfile();
    const orphans = profile ? this.childrenSheet.list.filter((c) => !c.anki_profile) : [];
    if (orphans.length) {
      for (const c of orphans) c.anki_profile = profile;
      await this.saveChildren();
    }
    if (!this.childrenSheet.list.some((c) => this.ofProfile(c))) this.addChild();
  },

  addChild() {
    this.childrenSheet.list.push({ id: "", name: "", grade: "", decks: "", instructions: "", anki_profile: this.childrenProfile() });
    this.childrenSheet.editing = this.childrenSheet.list.length - 1;
  },

  editChild(i) {
    this.childrenSheet.error = "";
    this.childrenSheet.editing = i;
  },

  // Back to the choice, the card as it was (a new one, not kept)
  cancelChild() {
    const sheet = this.childrenSheet;
    sheet.list = this.children.map((c) => ({ ...c }));
    sheet.editing = null;
    sheet.error = "";
    if (!sheet.list.length) sheet.open = false;
  },

  async removeChild(i) {
    this.childrenSheet.list.splice(i, 1);
    await this.saveChildren();
  },

  // The instructions' example, for its class: primary, middle or high school (the language's
  // grades list, cut where gradeBands says), else a general one
  instructionsExample(child) {
    const grades = t("app.children.grades").split("|");
    const i = grades.indexOf(child.grade);
    if (i < 0) return t("app.children.examples.none");
    const [middle, high] = t("app.children.gradeBands").split("|").map(Number);
    return t(`app.children.examples.${i < middle ? "primary" : i < high ? "middle" : "high"}`);
  },

  // The decks' suggestions: its first name, or its first name and its class ("Mathilde::4e")
  decksWithClass(child) {
    const name = child.name.trim();
    return child.grade ? `${name}::${child.grade}` : name;
  },

  // Its class changed (a new school year): decks ending with the old one ("Mathilde::4e")
  // follow ("Mathilde::3e"); the lessons made before stay in theirs
  setGrade(child, typed) {
    // Typed freely: one deck's name ("::" would make sub-decks of it), no stray spaces
    const grade = typed.replaceAll("::", " ").replace(/\s+/g, " ").trim().slice(0, 40);
    const old = child.grade;
    child.grade = grade;
    const decks = child.decks.trim();
    if (old && decks.endsWith(`::${old}`)) child.decks = decks.slice(0, -old.length) + grade;
    if (old && !grade && decks.endsWith("::")) child.decks = decks.slice(0, -2);
  },

  // The children the open lesson can be copied for: every other one, whatever its profile
  copyTargets() {
    return this.children.filter((c) => c.id !== this.lessonChild);
  },

  // The open lesson copied for another child (its decks, its Anki profile): the copy opened
  // when it is in the open profile, else said where it is
  async copyFor(child) {
    const sheet = this.copySheet;
    sheet.busy = true;
    sheet.error = "";
    try {
      if (this.saveTimer) await this.saveNow();
      const copy = await (await api(`/api/lessons/${this.lessonId}/copy`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ child: child.id }),
      })).json();
      sheet.open = false;
      await this.loadLessons();
      if (this.ofProfile(child)) {
        this.chooseChild(child.id);
        await this.openLesson(copy.id);
        this.notify(t("app.copy.done", { name: child.name }));
      } else {
        this.notify(t("app.copy.doneElsewhere", { name: child.name }));
      }
    } catch (e) {
      sheet.error = e.message;
    } finally {
      sheet.busy = false;
    }
  },

  async saveChildren() {
    const sheet = this.childrenSheet;
    const list = sheet.list.filter((c) => c.name.trim());
    const taken = new Set(list.filter((c) => c.id).map((c) => c.id));
    for (const c of list) {
      if (c.id) continue;
      const base = childSlug(c.name) || "child";
      let id = base;
      for (let n = 2; taken.has(id); n++) id = `${base}-${n}`;
      c.id = id;
      taken.add(id);
    }
    sheet.saving = true;
    sheet.error = "";
    try {
      this.children = await (await api("/api/children", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(list.map(({ id, name, grade, decks, instructions, anki_profile }) => (
          { id, name: name.trim(), grade, decks: decks.trim(), instructions: instructions.trim(), anki_profile: anki_profile ?? "" }))),
      })).json();
      const edited = sheet.editing === null ? null : sheet.list[sheet.editing];
      if (edited?.id && !this.children.some((c) => c.id === this.childId)) this.childId = edited.id;  // the first: chosen
      if (!this.children.some((c) => c.id === this.childId)) this.childId = this.children[0]?.id ?? "";
      storage("set", this.childId, CHILD);
      this.followProfile();
      sheet.list = this.children.map((c) => ({ ...c }));
      sheet.editing = null;  // back to the choice
    } catch (e) {
      sheet.error = e.message;
    } finally {
      sheet.saving = false;
    }
  },
};

// A child's own deck levels: its first name, its decks' levels (its class put in)
function childLevels(child) {
  const decks = (child.decks ?? "").replace(/\{[^}]+\}/g, child.grade ?? "");
  return new Set([child.name, ...decks.split("::")].map(sameLevel).filter(Boolean));
}

// A deck level as compared: no case, no accents, an ordinal's ending dropped ("5ème", "5e")
function sameLevel(level) {
  return fold(level.trim()).replace(/^(\d+)\s*(e|eme|er|ere|re|de|nd|nde|st|rd|th|o|a|º|ª)$/, "$1");
}

// A child's id from its first name: letters and digits ("Léa" → "lea")
function childSlug(name) {
  return name.normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase()
    .replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 40);
}
