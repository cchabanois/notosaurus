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
// A group of a classification as a tree: its name, then its members, each an element (a text)
// or a group inside it (another `nest`), in any order: nest([Tétrapodes], [lézard],
// nest([Mammifères], [chat]), nest([Oiseaux], [pigeon]))
#let nest(name, ..members) = {
  assert(members.named().len() == 0, message: "a group is nest(its name, its elements and groups…): nest([Tétrapodes], [lézard], nest([Mammifères], [chat]))")
  let is-group(m) = type(m) == dictionary and m.at("nest", default: false)
  let (items, groups) = ((), ())
  // its elements given as a list too, ([chat], [chien]): each an element
  for m in members.pos().map(m => if type(m) == array { m } else { (m,) }).flatten() {
    if is-group(m) { groups.push(m) } else { items.push(if type(m) == content { m } else { [#m] }) }
  }
  (nest: true, name: if type(name) == content { name } else { [#name] }, items: items, groups: groups)
}
// A group's box laid out from the inside out (within a context: texts measured), in cm, y down
// from its top-left corner: its sub-groups side by side under its name (more rows when too wide,
// boxes of a row as tall as the tallest), its own elements under them, in their own rows. Each
// box (its corners, its depth, its path: "0.1" the second sub-group of the first) and each text
// (its centre, its size, the path of the box it belongs to)
#let _nest-box(g, path, depth) = {
  let size(c) = { let m = measure(c); (m.width / 1cm, m.height / 1cm) }
  let fit(c, width) = if measure(c).width > width * 1cm { block(width: width * 1cm, align(center, c)) } else { c }
  let (pad, gap, spread, widest) = (0.3, 0.35, 0.45, 11.0)
  let move(b, dx, dy) = (
    boxes: b.boxes.map(r => r + (x0: r.x0 + dx, x1: r.x1 + dx, y0: r.y0 + dy, y1: r.y1 + dy, rule: r.rule + dy)),
    texts: b.texts.map(t => t + (x: t.x + dx, y: t.y + dy)),
    w: b.w, h: b.h,
  )
  // in rows no wider than `room`: each row its members and its width
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
  let kids = g.groups.enumerate().map(((i, k)) => _nest-box(k, path + "." + str(i), depth + 1))
  let kid-rows = rows(kids.map(k => k.w), widest, gap)
  let block-w = calc.max(0, ..kid-rows.map(r => r.width))
  // its name on one line as wide as its sub-groups, a rule under it: told from its elements
  let name = fit(g.name, calc.max(4.5, block-w))
  let (nw, nh) = size(name)
  let items = g.items.map(c => fit(c, 3.6))
  let item-sizes = items.map(size)
  let item-rows = rows(item-sizes.map(s => s.at(0)), calc.max(block-w, nw, 4.0), spread)
  let inner = calc.max(nw, block-w, ..item-rows.map(r => r.width))
  let w = inner + 2 * pad
  let (boxes, texts) = ((), ())
  let y = pad
  texts.push((x: w / 2, y: y + nh / 2, w: nw, h: nh, body: name, box: path, kind: "name"))
  y += nh + gap / 2
  let rule = y
  y += gap / 2
  for row in kid-rows {
    let tall = calc.max(..row.members.map(i => kids.at(i).h))
    let x = (w - row.width) / 2
    for i in row.members {
      let k = move(kids.at(i), x, y)
      // a row's boxes as tall as the tallest: its own box only, its contents where they were
      k.boxes.at(0).y1 = y + tall
      boxes += k.boxes
      texts += k.texts
      x += k.w + gap
    }
    y += tall + gap
  }
  for row in item-rows {
    let tall = calc.max(..row.members.map(i => item-sizes.at(i).at(1)))
    let x = (w - row.width) / 2
    for i in row.members {
      let (iw, ih) = item-sizes.at(i)
      texts.push((x: x + iw / 2, y: y + tall / 2, w: iw, h: ih, body: items.at(i), box: path, kind: "item"))
      x += iw + spread
    }
    y += tall + 0.2
  }
  if item-rows.len() > 0 { y -= 0.2 } else if kid-rows.len() > 0 { y -= gap } else { y -= gap }
  let h = y + pad
  (boxes: ((x0: 0, y0: 0, x1: w, y1: h, rule: rule, depth: depth, path: path),) + boxes, texts: texts, w: w, h: h)
}
// A tree whose every group holds one sub-group at most is a chain: its sets from the smallest
#let _nest-chain(g) = {
  let levels = ()
  let g = g
  while true {
    levels.insert(0, (g.name, g.items))
    if g.groups.len() == 0 { break }
    g = g.groups.first()
  }
  levels
}
#let _nest-is-chain(g) = g.groups.len() == 0 or (g.groups.len() == 1 and _nest-is-chain(g.groups.first()))
#let nested-sets(..sets) = context {
  let sets = sets.pos()
  // the chain's sets given as one list, ((name, (elements,)), …) or (name, (elements,), name,
  // …): each set its own, as when given one by one
  if sets.len() == 1 and type(sets.first()) == array and sets.first().len() > 0 {
    let one = sets.first()
    if one.all(s => type(s) == array) { sets = one } else if (
      one.len() >= 4 and calc.even(one.len()) and one.chunks(2).all(((n, e)) => type(n) != array and type(e) == array)
    ) { sets = one.chunks(2) }
  }
  let tree = sets.len() == 1 and type(sets.first()) == dictionary and sets.first().at("nest", default: false)
  if tree and not _nest-is-chain(sets.first()) {
    // groups side by side in one: boxes, each from its contents
    let (boxes, texts) = _nest-box(sets.first(), "0", 0)
    cetz.canvas({
      import cetz.draw: *
      for r in boxes {
        rect((r.x0, -r.y0), (r.x1, -r.y1), radius: 0.2, stroke: 0.8pt, fill: white)
        line((r.x0, -r.rule), (r.x1, -r.rule), stroke: 0.4pt + luma(120))
      }
      for t in texts { content((t.x, -t.y), t.body) }
    })
  } else {
    let (shapes, placed) = _nested-layout(if tree { _nest-chain(sets.first()) } else { sets })
    cetz.canvas({
      import cetz.draw: *
      for (cy, a, b) in shapes.rev() { circle((0, cy), radius: (a, b), stroke: 0.8pt, fill: white) }
      for (k, at, c) in placed { content(at, c) }
    })
  }
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
