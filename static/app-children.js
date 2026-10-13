// The children the lessons are for (app/children.py): which one the next lesson is for
// (kept on this device), their cards edited in a sheet (first name, class, decks,
// instructions). The first name never goes to the AI: only the class and the instructions.
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

  openChildren() {
    this.childrenSheet = { open: true, list: this.children.map((c) => ({ ...c })), saving: false, error: "" };
  },

  addChild() {
    this.childrenSheet.list.push({ id: "", name: "", grade: "", decks: "", instructions: "" });
  },

  removeChild(i) {
    this.childrenSheet.list.splice(i, 1);
  },

  // The decks' suggestions: its first name, or its first name and its class (updated each year)
  suggestDecks(child, withClass) {
    const name = child.name.trim();
    if (!name) return;
    child.decks = withClass ? `${name}::${t("app.children.classToken")}` : name;
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
        body: JSON.stringify(list.map(({ id, name, grade, decks, instructions }) => (
          { id, name: name.trim(), grade, decks: decks.trim(), instructions: instructions.trim() }))),
      })).json();
      if (!this.children.some((c) => c.id === this.childId)) this.chooseChild(this.children[0]?.id ?? "");
      sheet.open = false;
    } catch (e) {
      sheet.error = e.message;
    } finally {
      sheet.saving = false;
    }
  },
};

// A child's id from its first name: letters and digits ("Léa" → "lea")
function childSlug(name) {
  return name.normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase()
    .replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 40);
}
