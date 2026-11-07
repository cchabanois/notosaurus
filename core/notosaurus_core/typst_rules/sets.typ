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
// ---- What the AI writes, from here (the rule's example: everything above is given)
#cetz.canvas({
  import cetz.draw: *
  cetz-venn.venn2(name: "v", ab-fill: hatch)
  content("v.a", [$A$])
  content("v.b", [$B$])
})
