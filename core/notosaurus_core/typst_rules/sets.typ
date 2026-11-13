#set page(width: auto, height: auto, margin: 6pt)
#import "@preview/cetz:0.5.2"
#import "@preview/cetz-venn:0.2.0"
#import "common.typ": *
#let hatch = tiling(size: (5pt, 5pt), std.line(start: (0pt, 5pt), end: (5pt, 0pt), stroke: 0.6pt))
// Colours mixed: lights added (additive synthesis, on black: red + green = yellow, the three
// white) or filters and pigments taken away (subtractive, on white: cyan and magenta = blue,
// the three black). Each part's colour computed from the colours over it, never chosen.
// colours: two or three; labels: their names, written on them; mixed: names written on the
// mixed parts, (ab: [jaune], abc: [blanc]); none unless given (a card may ask them); ask:
// the parts a card asks the colour of, left grey with a question mark
// the synthesis' own colours, pure (Typst's green is #2ecc40: no white from it)
#let pure = (
  red: rgb(255, 0, 0), green: rgb(0, 255, 0), blue: rgb(0, 0, 255),
  cyan: rgb(0, 255, 255), magenta: rgb(255, 0, 255), yellow: rgb(255, 255, 0),
  white: rgb(255, 255, 255), black: rgb(0, 0, 0),
)
#let colour-mix(kind: "additive", colours: (), labels: (), mixed: (:), ask: ()) = {
  assert(kind in ("additive", "subtractive"), message: "kind is \"additive\" or \"subtractive\"")
  let colours = colours.map(c => if type(c) == str {
    assert(c in pure, message: "a colour is one of " + pure.keys().join(", ") + ", or an rgb(…)")
    pure.at(c)
  } else { c })
  assert(colours.len() in (2, 3) and colours.all(c => type(c) == color), message: "two or three colours")
  assert(labels.len() <= colours.len(), message: "labels are the colours' names, one per colour: as many as the colours at most")
  let channels(c) = c.rgb().components(alpha: false).map(v => v / 100%)
  let mixed-colour(indices) = {
    let parts = indices.map(i => channels(colours.at(i)))
    let out = range(3).map(k => {
      let values = parts.map(p => p.at(k))
      if kind == "additive" { calc.min(1, values.sum()) } else { values.product() }
    })
    rgb(..out.map(v => v * 100%))
  }
  let names = ("a", "b", "c").slice(0, colours.len())
  let parts = if colours.len() == 2 { ("a", "b", "ab") } else { ("a", "b", "c", "ab", "ac", "bc", "abc") }
  let ground = if kind == "additive" { black } else { white }
  let style = (:)
  for part in parts {
    style.insert(part + "-fill", mixed-colour(part.clusters().map(l => names.position(n => n == l))))
    style.insert(part + "-stroke", none)
  }
  for part in ask {
    assert(part in parts, message: "a part asked is one of " + parts.join(", "))
    style.insert(part + "-fill", luma(55%))  // its colour not given away
  }
  let outside = if colours.len() == 2 { "not-ab" } else { "not-abc" }
  style.insert(outside + "-fill", ground)
  // a name in black on a light part, in white on a dark one
  let ink(part) = {
    let (r, g, b) = channels(style.at(part + "-fill"))
    if 0.2126 * r + 0.7152 * g + 0.0722 * b > 0.5 { black } else { white }
  }
  // drawn larger than a set diagram, its names smaller: each fits in its part
  set text(9pt)
  cetz.canvas(length: 1.9cm, {
    import cetz.draw: *
    if colours.len() == 2 { cetz-venn.venn2(name: "v", ..style) } else { cetz-venn.venn3(name: "v", ..style) }
    for (i, label) in labels.enumerate() {
      content("v." + names.at(i), text(fill: ink(names.at(i)), label))
    }
    for part in ask { content("v." + part, text(fill: white, weight: "bold", 12pt, [?])) }
    for (part, label) in mixed {
      assert(part in parts, message: "a mixed part is one of " + parts.join(", "))
      content("v." + part, text(fill: ink(part), label))
    }
  })
}
// Sets inside one another (ℕ ⊂ ℤ ⊂ ℝ, a classification's groups): from the smallest to the
// largest, each its name and its own elements (those of no smaller one). Ellipses one in
// another standing on nearly the same bottom, as textbooks draw them: each ring wide enough
// for its texts (measured), its name in the band above the smaller one, its elements on
// its sides, right and left in turn: each where it belongs, by the preamble, never by eye.
// The layout (within a context: texts measured): each ellipse (its centre's height, half-width,
// half-height) and each text where it goes, with its set's rank
#let _nested-layout(levels) = {
  // a long text on two lines or more (side by side in their rings, the figure grew too wide)
  let fit(c) = if measure(c).width > 2.6cm { block(width: 2.6cm, align(center, c)) } else { c }
  // a set's elements: one written without its trailing comma, ($3$): itself, not a list
  // of one; a set given by its name alone: no elements of its own
  let levels = levels.map(level => if type(level) != array { (level, ()) } else if level.len() == 1 { (level.at(0), ()) } else { level })
  assert(levels.all(level => level.len() == 2), message: "each set is (its name, (its elements,)): ($NN$, ($3$, $7$))")
  let levels = levels.map(((name, items)) => (name, if type(items) == array { items } else { (items,) }))
  let levels = levels.map(((name, items)) => (fit(name), items.map(fit)))
  let size(c) = { let m = measure(c); (m.width / 1cm, m.height / 1cm) }
  let gap = 0.25
  let shapes = ()
  for (k, (name, items)) in levels.enumerate() {
    let texts = (name, ..items)
    let w = calc.max(..texts.map(c => size(c).at(0)))
    let h = calc.max(..texts.map(c => size(c).at(1)))
    if k == 0 {
      let stack = texts.len() * (h + gap)
      let (a, b) = ((w / 2 + 0.35) * 1.42, (stack / 2 + 0.2) * 1.42)
      shapes.push((b, a, b))
    } else {
      let (cy, a, b) = shapes.at(k - 1)
      let (bottom, top) = (cy - b - 0.2, cy + b + h + 2 * gap)
      let rows = calc.ceil(items.len() / 2)
      // the sides tall enough for its elements' rows, from the smaller one's middle up
      let top = calc.max(top, cy + rows * (h + gap) + h)
      let (ncy, nb) = ((top + bottom) / 2, (top - bottom) / 2)
      // wide enough at each row's height (the ellipse narrows going up) for its elements
      let na = a + w + 0.6
      for r in range(rows) {
        let y = cy + r * (h + gap)
        let inner = a * calc.sqrt(calc.max(0, 1 - calc.pow((y - cy) / b, 2)))
        na = calc.max(na, (inner + w + 0.5) / calc.sqrt(1 - calc.pow((y - ncy) / nb, 2)))
      }
      // never flatter than a textbook's (wide rings side by side drew a thin band, tiny)
      if nb < 0.45 * na { nb = 0.45 * na; ncy = bottom + nb }
      shapes.push((ncy, na, nb))
    }
  }
  // where an ellipse is at a height: its half-width there
  let across(s, y) = { let (cy, a, b) = s; a * calc.sqrt(calc.max(0, 1 - calc.pow((y - cy) / b, 2))) }
  let placed = ()
  for (k, (name, items)) in levels.enumerate() {
    let (cy, a, b) = shapes.at(k)
    if k == 0 {
      let texts = (name, ..items)
      let step = 2 * b / 1.42 / texts.len()
      for (j, c) in texts.enumerate() { placed.push((k, (0, cy + b / 1.42 - step * (j + 0.5)), c)) }
    } else {
      let inner = shapes.at(k - 1)
      let h = calc.max(..(name, ..items).map(c => size(c).at(1)))
      placed.push((k, (0, (inner.at(0) + inner.at(2) + cy + b) / 2), name))
      for (j, c) in items.enumerate() {
        let side = if calc.rem(j, 2) == 0 { 1 } else { -1 }
        let y = inner.at(0) + calc.floor(j / 2) * (h + gap)
        placed.push((k, (side * (across(inner, y) + across(shapes.at(k), y)) / 2, y), c))
      }
    }
  }
  (shapes: shapes, placed: placed)
}
#let nested-sets(..sets) = context {
  let (shapes, placed) = _nested-layout(sets.pos())
  cetz.canvas({
    import cetz.draw: *
    for (cy, a, b) in shapes.rev() { circle((0, cy), radius: (a, b), stroke: 0.8pt, fill: white) }
    for (k, at, c) in placed { content(at, c) }
  })
}
// Groups inside groups as a tree (a classification: two groups side by side in a third, the
// mammals and the birds in the tetrapods): each group a box, its name in a band at its top,
// its own members (those of no smaller group) in a column at its right, the groups it holds
// side by side under its name. Every size measured, every place computed: no name cut by a
// box nor on another name, no member on an edge. Each group `(id: "t", name: [Tétrapodes],
// inside: "v", members: ([Lézard],))`, `inside` the id of the group holding it (none: the largest).
// The layout (within a context: texts measured): each box (x, top, width, height), each
// text (its place, its content, its rectangle)
#let _groups-layout(gs) = {
  for g in gs {
    assert(type(g) == dictionary and "id" in g and "name" in g, message: "each group is (id: \"v\", name: [Vertébrés], inside: \"…\", members: (…))")
  }
  let ids = gs.map(g => g.id)
  for g in gs {
    let up = g.at("inside", default: none)
    assert(up == none or up in ids, message: "a group's inside is another group's id: " + repr(up) + " is none of " + ids.join(", "))
    assert(up != g.id, message: "a group is not in itself: " + g.id)
  }
  assert(ids.dedup().len() == ids.len(), message: "each group its own id")
  let wrap(c) = if measure(c).width > 4.5cm { block(width: 4.5cm, c) } else { c }
  let members(g) = { let m = g.at("members", default: ()); if type(m) == array { m } else { (m,) } }
  let byid = gs.map(g => (g.id, g)).to-dict()
  let kids(id) = gs.filter(g => g.at("inside", default: none) == id).map(g => g.id)
  let dim(c) = { let m = measure(c); (m.width / 1cm, m.height / 1cm) }
  let (pad, gap) = (0.25, 0.3)
  // each group's (width, height), from the smallest up (a loop, no recursion: deepest first)
  let depth(id) = { let d = 0; let up = byid.at(id).at("inside", default: none); while up != none { d += 1; up = byid.at(up).at("inside", default: none) }; d }
  let order = ids.sorted(key: id => -depth(id))
  let size = (:)
  let names = (:)
  for id in order {
    let g = byid.at(id)
    let ms = members(g).map(c => dim(wrap(c)))
    let ks = kids(id).map(k => size.at(k))
    let kw = if ks.len() > 0 { ks.map(k => k.at(0)).sum() + gap * (ks.len() - 1) } else { 0 }
    let kh = if ks.len() > 0 { calc.max(..ks.map(k => k.at(1))) } else { 0 }
    let mw = if ms.len() > 0 { calc.max(..ms.map(m => m.at(0))) } else { 0 }
    let mh = if ms.len() > 0 { ms.map(m => m.at(1)).sum() + gap * (ms.len() - 1) } else { 0 }
    let bw = kw + mw + if ks.len() > 0 and ms.len() > 0 { gap } else { 0 }
    let bh = calc.max(kh, mh)
    // its name on one line when the box is that wide anyway, else on two or more (4.5 cm at least)
    let room = calc.max(4.5, bw) * 1cm
    let name = if measure(g.name).width > room { block(width: room, g.name) } else { g.name }
    let (nw, nh) = dim(name)
    names.insert(id, name)
    size.insert(id, (calc.max(nw, bw) + 2 * pad, pad + nh + (if bh > 0 { gap + bh } else { 0 }) + pad, nh))
  }
  // where each box goes: (x, top), from the largest down
  let at = (:)
  let roots = ids.filter(id => byid.at(id).at("inside", default: none) == none)
  let x = 0
  for r in roots { at.insert(r, (x, 0)); x += size.at(r).at(0) + gap }
  for id in order.rev() {
    let (x0, top) = at.at(id)
    let cx = x0 + pad
    for k in kids(id) {
      at.insert(k, (cx, top - pad - size.at(id).at(2) - gap))
      cx += size.at(k).at(0) + gap
    }
  }
  let texts = ()
  for id in order.rev() {
    let g = byid.at(id)
    let (x0, top) = at.at(id)
    let (w, h, nh) = size.at(id)
    let (tw, th) = dim(names.at(id))
    texts.push((id: id, kind: "name", at: (x0 + pad, top - pad), body: names.at(id), rect: (x0 + pad, top - pad - th, x0 + pad + tw, top - pad)))
    let ks = kids(id)
    let mx = if ks.len() > 0 { at.at(ks.last()).at(0) + size.at(ks.last()).at(0) + gap } else { x0 + pad }
    let y = top - pad - nh - gap
    for c in members(g) {
      let c = wrap(c)
      let (cw, ch) = dim(c)
      texts.push((id: id, kind: "member", at: (mx, y), body: c, rect: (mx, y - ch, mx + cw, y)))
      y -= ch + gap
    }
  }
  let boxes = order.rev().map(id => { let (x0, top) = at.at(id); let (w, h, _) = size.at(id); (id: id, inside: byid.at(id).at("inside", default: none), rect: (x0, top - h, x0 + w, top)) })
  (boxes: boxes, texts: texts)
}
#let nested-groups(..groups) = context {
  let (boxes, texts) = _groups-layout(groups.pos())
  cetz.canvas({
    import cetz.draw: *
    for b in boxes {
      let (x0, y0, x1, y1) = b.rect
      rect((x0, y0), (x1, y1), radius: 0.2, stroke: 0.8pt, fill: white)
    }
    for t in texts { content(t.at, t.body, anchor: "north-west") }
  })
}
// A part's name (`"v.ab"`): in it when it fits, else under the diagram, joined to the part by
// a thin line (a lens is narrower than "A ∩ B"). Its width estimated from its text (no
// `measure` inside a canvas); `room`: the part's width, about a lens's.
#let part-label(part, label, room: auto) = cetz.draw.get-ctx(ctx => {
  import cetz.draw: *
  let p = cetz.coordinate.resolve(ctx, part).at(1)
  // a set's own part ("v.a") is wide, its name at its anchor: the elements under the name;
  // a part shared by sets (a lens) is narrow
  let own = part.split(".").last().len() == 1
  let room = if room == auto { if own { 1.3 } else { 0.7 } } else { room }
  if own { p = (p.at(0), p.at(1) - 0.4) }
  // outside every set ("v.not-ab"): beside the universe's name written at that anchor
  if part.split(".").last().starts-with("not") { p = (p.at(0) + 0.6, p.at(1)) }
  if 0.24 * _plain(label).clusters().len() <= room {
    content(p, label)
  } else {
    let bottom = cetz.coordinate.resolve(ctx, part.split(".").first() + ".south").at(1).at(1)
    // slanting: straight down it ran over a set's name drawn under the centre (C)
    let q = (p.at(0) + 0.9, bottom - 0.35)
    circle(p, radius: 0.035, fill: black, stroke: none)
    line(p, q, stroke: 0.5pt)
    content(q, label, anchor: "north-west", padding: 0.05)
  }
})
// A region made of several parts (a union, a complement): its name under the diagram,
// centred, clear of the universe's name and of the parts' own.
#let region-label(diagram, label) = cetz.draw.get-ctx(ctx => {
  let s = cetz.coordinate.resolve(ctx, diagram + ".south").at(1)
  cetz.draw.content((s.at(0), s.at(1) - 0.3), label, anchor: "north")
})
// ---- What the AI writes, from here (the rule's example: everything above is given)
#cetz.canvas({
  import cetz.draw: *
  cetz-venn.venn2(name: "v", ab-fill: hatch)
  content("v.a", [$A$])
  content("v.b", [$B$])
})
