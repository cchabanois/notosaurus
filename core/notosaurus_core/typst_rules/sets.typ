#set page(width: auto, height: auto, margin: 6pt)
#import "@preview/cetz:0.5.2"
#import "@preview/cetz-venn:0.2.0"
#let hatch = tiling(size: (5pt, 5pt), std.line(start: (0pt, 5pt), end: (5pt, 0pt), stroke: 0.6pt))
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
// ---- What the AI writes, from here (the rule's example: everything above is given)
#cetz.canvas({
  import cetz.draw: *
  cetz-venn.venn2(name: "v", ab-fill: hatch)
  content("v.a", [$A$])
  content("v.b", [$B$])
})
