#set page(width: auto, height: auto, margin: 6pt)
#import "@preview/cetz:0.5.2"
// A phylogenetic tree from what each species has (the lesson's table of species and
// characters): each character's group is the species having it, the groups nested; the tree
// is built from them, never drawn by eye. Each innovation marked on its group's branch; a
// character only one species has, on its own branch. species: (name, (characters…)) pairs;
// hidden: species or characters written "?" (a card asking which one); root: the root's name
#let phylogeny(species: (), hidden: (), root: none) = context {
  assert(
    species.len() >= 2 and species.all(s => type(s) == array and s.len() == 2 and type(s.at(1)) in (array, str)),
    message: "species are (name, (characters…)) pairs, two at least",
  )
  let names = species.map(s => s.at(0))
  // a single character written without its comma ("(\"Truite\", (\"mâchoires\"))") is a string
  let has = species.map(s => if type(s.at(1)) == str { (s.at(1),) } else { s.at(1) })
  let characters = has.flatten().dedup()
  // each character's group: the indices of the species having it
  let group-of(c) = range(species.len()).filter(i => c in has.at(i))
  let groups = (:)  // a group (as its indices joined) -> its characters
  for c in characters {
    let key = group-of(c).map(str).join(",")
    groups.insert(key, groups.at(key, default: ()) + (c,))
  }
  let sets = groups.keys().map(k => k.split(",").map(int))
  // nested or apart, as a tree's groups must be
  for a in sets {
    for b in sets {
      let common = a.filter(i => i in b)
      assert(
        common.len() == 0 or common.len() == a.len() or common.len() == b.len(),
        message: "the characters overlap without nesting (" + a.map(i => names.at(i)).join(", ") + " / "
          + b.map(i => names.at(i)).join(", ") + "): no tree has both groups",
      )
    }
  }
  // a clade's children: its species no group inside it holds, each a leaf, then the largest
  // groups inside it (the smallest first: the tree reads as a ladder from its root)
  let build(members) = {
    let inside = sets.filter(s => s.len() < members.len() and s.all(i => i in members))
    let largest = inside.filter(s => not inside.any(t => t.len() > s.len() and s.all(i => i in t)))
    let held = largest.flatten()
    let alone = members.filter(i => i not in held)
    alone.map(i => (i,)) + largest.sorted(key: s => s.len())
  }
  let key-of(members) = members.map(str).join(",")
  let innovations(members) = groups.at(key-of(members), default: ())
  // the leaves in their order and each clade's depth
  let order = ()
  let nodes = ()  // (members, depth, parent-index)
  let all = range(species.len())
  // walked by hand, earliest branching first: closures can't change what is outside them
  let stack = ((all, 0, -1),)
  while stack.len() > 0 {
    let (members, depth, parent) = stack.pop()
    let here = nodes.len()
    nodes.push((members: members, depth: depth, parent: parent))
    if members.len() == 1 { order.push(members.first()) } else {
      for child in build(members).rev() { stack.push((child, depth + 1, here)) }
    }
  }
  let deepest = calc.max(..nodes.map(n => n.depth))
  let shown(name) = if name in hidden { [?] } else { name }
  // every label as tall as any line (accents, descenders): the names on one line
  let txt(body) = text(9pt, top-edge: "ascender", bottom-edge: "descender", body)
  // a label wraps past 3 cm; the columns as wide as the widest label, the rows as tall as
  // the innovations of the branch carrying most
  let label(body) = box(width: auto, txt(body))
  let wrapped(body) = {
    let w = measure(label(body)).width
    if w > 3cm { box(width: 3cm, { set par(leading: 0.2em); txt(body) }) } else { label(body) }
  }
  let widest(items) = calc.max(0cm, ..items.map(c => measure(wrapped(shown(c))).width)) / 1cm
  let height(c) = measure(wrapped(shown(c))).height / 1cm
  let needs = nodes.map(n => innovations(n.members)).map(m => m.map(height).sum(default: 0) + 0.3 * (m.len() + 1))
  let dx = calc.max(1.6, widest(characters) + 0.5, widest(names) + 0.35)
  let dy = calc.max(1.1, ..needs)
  let x-of-leaf(i) = order.position(j => j == i) * dx
  let leaf-y = (deepest + 1) * dy
  cetz.canvas({
    import cetz.draw: *
    // each clade's point: under the middle of its leaves, at its depth
    let point(n) = {
      let xs = n.members.map(x-of-leaf)
      let x = (calc.min(..xs) + calc.max(..xs)) / 2
      (x, if n.members.len() == 1 { leaf-y } else { n.depth * dy })
    }
    let points = nodes.map(point)
    // a branch from (x, low) up to (x, high), its innovations evenly along it
    let branch(x, low, high, marks) = {
      line((x, low), (x, high), stroke: 1pt)
      for (k, c) in marks.enumerate() {
        let my = low + (high - low) * (k + 1) / (marks.len() + 1)
        line((x - 0.12, my), (x + 0.12, my), stroke: 1.6pt)
        content((x + 0.2, my), wrapped(shown(c)), anchor: "west")
      }
    }
    // the root's stem: as long as a branch when innovations all the species share are on it
    let (rx, ry) = points.first()
    let marks = innovations(nodes.first().members)
    let low = ry - if marks.len() > 0 { dy } else { 0.4 * dy }
    branch(rx, low, ry, marks)
    if root != none { content((rx, low - 0.1), wrapped(shown(root)), anchor: "north") }
    for (i, n) in nodes.enumerate() {
      if n.parent < 0 { continue }
      let (px, py) = points.at(n.parent)
      let (x, y) = points.at(i)
      // across from its parent's height, then up to it
      line((px, py), (x, py), stroke: 1pt)
      branch(x, py, y, innovations(n.members))
      if n.members.len() == 1 {
        content((x, y + 0.15), wrapped(shown(names.at(n.members.first()))), anchor: "south")
      }
    }
  })
}
// ---- What the AI writes, from here (the rule's example: everything above is given)
#phylogeny(species: (
  ("Lamproie", ()),
  ("Truite", ("mâchoires",)),
  ("Grenouille", ("mâchoires", "membres")),
  ("Lézard", ("mâchoires", "membres", "amnios")),
  ("Chat", ("mâchoires", "membres", "amnios", "poils")),
))
