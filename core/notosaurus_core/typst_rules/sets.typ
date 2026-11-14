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
// mammals and the birds in the tetrapods): each group a box, its name centred at its top with a
// thin rule under it, the groups it holds side by side under the rule (more rows past about
// 11 cm, the boxes of a row as tall as the tallest), its own members (those of no smaller group)
// under them, in centred rows. Every size measured, every place computed: no name cut by a box
// nor on another name, no member on an edge. Each group `(id: "t", name: [Tétrapodes],
// inside: "v", members: ([Lézard],))`, `inside` the id of the group holding it (none: the largest).
// The layout (within a context: texts measured): each box (its rect, the height of the rule
// under its name: none when it holds nothing), each text (its place, its content, its rectangle)
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
  // a text wider than `width` (cm) on two lines or more, centred
  let fit(c, width) = if measure(c).width > width * 1cm { block(width: width * 1cm, align(center, c)) } else { c }
  let members(g) = { let m = g.at("members", default: ()); if type(m) == array { m } else { (m,) } }
  let byid = gs.map(g => (g.id, g)).to-dict()
  let kids(id) = gs.filter(g => g.at("inside", default: none) == id).map(g => g.id)
  let dim(c) = { let m = measure(c); (m.width / 1cm, m.height / 1cm) }
  let (pad, gap, spread, widest) = (0.3, 0.35, 0.45, 11.0)
  // widths in rows no wider than `room`: each row its indices and its width
  let rows(widths, room, space) = {
    let out = ()
    for (i, w) in widths.enumerate() {
      if out.len() > 0 and out.last().width + space + w <= room {
        out.last().members.push(i)
        out.last().width += space + w
      } else { out.push((members: (i,), width: w)) }
    }
    out
  }
  // a laid-out group moved by (dx, dy): in cm, y down from its top-left corner
  let move(l, dx, dy) = (
    boxes: l.boxes.map(b => b + (x0: b.x0 + dx, x1: b.x1 + dx, y0: b.y0 + dy, y1: b.y1 + dy, rule: if b.rule == none { none } else { b.rule + dy })),
    texts: l.texts.map(t => t + (x: t.x + dx, y: t.y + dy)),
    w: l.w, h: l.h,
  )
  // laid-out groups in rows, each row centred in `width`, from `y` down: (boxes, texts, y below)
  let place(ls, width, y) = {
    let (boxes, texts) = ((), ())
    for row in rows(ls.map(l => l.w), widest, gap) {
      let tall = calc.max(..row.members.map(i => ls.at(i).h))
      let x = (width - row.width) / 2
      for i in row.members {
        let l = move(ls.at(i), x, y)
        // a row's boxes as tall as the tallest: its own box only, its contents where they were
        l.boxes.at(0).y1 = y + tall
        boxes += l.boxes
        texts += l.texts
        x += l.w + gap
      }
      y += tall + gap
    }
    (boxes, texts, y)
  }
  // each group laid out from the inside out (a loop, no recursion: deepest first)
  let depth(id) = { let d = 0; let up = byid.at(id).at("inside", default: none); while up != none { d += 1; up = byid.at(up).at("inside", default: none) }; d }
  let order = ids.sorted(key: id => -depth(id))
  let lay = (:)
  for id in order {
    let g = byid.at(id)
    let ks = kids(id).map(k => lay.at(k))
    let block-w = calc.max(0, ..rows(ks.map(k => k.w), widest, gap).map(r => r.width))
    // its name on one line when its sub-groups are that wide anyway, else on two or more
    let name = fit(g.name, calc.max(4.5, block-w))
    let (nw, nh) = dim(name)
    let items = members(g).map(c => fit(c, 3.6))
    let sizes = items.map(dim)
    let item-rows = rows(sizes.map(s => s.at(0)), calc.max(block-w, nw, 4.0), spread)
    let w = calc.max(nw, block-w, ..item-rows.map(r => r.width)) + 2 * pad
    let texts = ((id: id, kind: "name", x: w / 2, y: pad + nh / 2, w: nw, h: nh, body: name),)
    let full = ks.len() > 0 or items.len() > 0
    let rule = if full { pad + nh + gap / 2 } else { none }
    let y = pad + nh + if full { gap } else { 0 }
    let (boxes, kid-texts, below) = place(ks, w, y)
    texts += kid-texts
    y = below
    for row in item-rows {
      let tall = calc.max(..row.members.map(i => sizes.at(i).at(1)))
      let x = (w - row.width) / 2
      for i in row.members {
        let (iw, ih) = sizes.at(i)
        texts.push((id: id, kind: "member", x: x + iw / 2, y: y + tall / 2, w: iw, h: ih, body: items.at(i)))
        x += iw + spread
      }
      y += tall + gap
    }
    if full { y -= gap }
    let h = y + pad
    let own = (id: id, inside: g.at("inside", default: none), x0: 0, y0: 0, x1: w, y1: h, rule: rule)
    lay.insert(id, (boxes: (own,) + boxes, texts: texts, w: w, h: h))
  }
  // the largest groups (one, as a rule) in rows too
  let roots = ids.filter(id => byid.at(id).at("inside", default: none) == none).map(id => lay.at(id))
  let width = calc.max(..rows(roots.map(r => r.w), widest, gap).map(r => r.width))
  let (boxes, texts, _) = place(roots, width, 0)
  // in cetz's coordinates (y up): each box's rect (x0, y0, x1, y1), each text's top-left corner
  (
    boxes: boxes.map(b => (id: b.id, inside: b.inside, rect: (b.x0, -b.y1, b.x1, -b.y0), rule: if b.rule == none { none } else { -b.rule })),
    texts: texts.map(t => (id: t.id, kind: t.kind, at: (t.x - t.w / 2, -t.y + t.h / 2), body: t.body, rect: (t.x - t.w / 2, -t.y - t.h / 2, t.x + t.w / 2, -t.y + t.h / 2))),
  )
}
#let nested-groups(..groups) = context {
  let (boxes, texts) = _groups-layout(groups.pos())
  cetz.canvas({
    import cetz.draw: *
    for b in boxes {
      let (x0, y0, x1, y1) = b.rect
      rect((x0, y0), (x1, y1), radius: 0.2, stroke: 0.8pt, fill: white)
      if b.rule != none { line((x0, b.rule), (x1, b.rule), stroke: 0.4pt + luma(120)) }
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
