#set page(width: auto, height: auto, margin: 6pt)
#import "@preview/cetz:0.5.2"
#import "@preview/cetz-venn:0.2.0"
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
