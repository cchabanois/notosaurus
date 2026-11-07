#set page(width: auto, height: auto, margin: 6pt)
#import "@preview/cetz:0.5.2"
// A statistics chart from counts: "bars" (a bar per value, as high as its count: a
// diagramme en bâtons), "pie" (a circle, each sector count / total × 360°), "semi" (a half
// circle, × 180°): the angles computed, never given. values: (label, count) pairs in the
// lesson's order; written: the values whose count is written on the chart ("all", or some
// labels), none by default: a card asking a count never shows it; degrees: a sector's angle
// written with its count; axis: the bars' axis title (the lesson's: "Effectif"); step: the
// bars' graduation (auto: every unit up to 12, then 2, 5, 10…)
#let chart(kind: "bars", values: (), written: (), degrees: false, axis: none, step: auto) = context {
  assert(kind in ("bars", "pie", "semi"), message: "kind is \"bars\", \"pie\" or \"semi\"")
  assert(
    values.len() > 0 and values.all(v => type(v) == array and v.len() == 2 and type(v.at(1)) in (int, float) and v.at(1) >= 0),
    message: "values are (label, count) pairs, each count a number",
  )
  let total = values.map(v => v.at(1)).sum()
  assert(total > 0, message: "the counts add up to more than 0")
  assert(written == "all" or type(written) == array, message: "written is \"all\" or a list of labels")
  let shown(label) = written == "all" or label in written
  let palette = (
    rgb("#9cc9e8"), rgb("#f6c76b"), rgb("#a5d18f"), rgb("#f2a7ad"), rgb("#c3b1e1"), rgb("#f3e08a"),
    rgb("#8fd3c9"), rgb("#e8b48f"),
  )
  let txt(body) = text(10pt, font: "DejaVu Sans", body)
  // a number as the lesson writes it: whole, or with a decimal comma
  let num(x) = {
    let r = calc.round(x, digits: 1)
    if calc.fract(r) == 0 { str(int(r)) } else { str(r).replace(".", ",") }
  }
  cetz.canvas({
    import cetz.draw: *
    if kind == "bars" {
      let top = calc.max(..values.map(v => v.at(1)))
      let step = if step != auto { step } else {
        (1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500, 1000).find(s => top / s <= 12)
      }
      let ymax = calc.ceil(top / step) * step
      let h = 4.0
      let unit = h / ymax
      let slot = 1.5
      let w = slot * values.len()
      // the graduation: a tick and a light line at each step, so that a count is read, not guessed
      for k in range(1, int(ymax / step) + 1) {
        let y = k * step * unit
        line((0, y), (w, y), stroke: 0.4pt + luma(205))
        line((-0.08, y), (0, y), stroke: 0.6pt)
        content((-0.16, y), txt(num(k * step)), anchor: "east")
      }
      content((-0.16, 0), txt("0"), anchor: "east")
      line((0, 0), (w + 0.3, 0), stroke: 0.8pt)
      line((0, 0), (0, h + 0.45), stroke: 0.8pt, mark: (end: ">", fill: black))
      if axis != none { content((0.12, h + 0.45), txt(axis), anchor: "west") }
      for (i, (label, count)) in values.enumerate() {
        let x = slot * (i + 0.5)
        if count > 0 { rect((x - 0.11, 0), (x + 0.11, count * unit), fill: luma(55), stroke: none) }
        content((x, -0.14), txt(label), anchor: "north")
        if shown(label) { content((x, count * unit + 0.08), txt(num(count)), anchor: "south") }
      }
    } else {
      let r = if kind == "pie" { 2 } else { 2.4 }
      let span = if kind == "pie" { 360deg } else { 180deg }
      // clockwise from twelve o'clock; a half circle from the left, over the top
      let a = if kind == "pie" { 90deg } else { 180deg }
      let sectors = ()
      for (i, (label, count)) in values.enumerate() {
        let angle = span * count / total
        if count > 0 { sectors.push((i: i, label: label, count: count, start: a, angle: angle)) }
        a -= angle
      }
      for t in sectors {
        arc((0, 0), start: t.start, delta: -t.angle, radius: r, mode: "PIE", anchor: "origin",
          fill: palette.at(calc.rem(t.i, palette.len())), stroke: 0.7pt)
      }
      if kind == "semi" { line((-r, 0), (r, 0), stroke: 0.7pt) }
      // Each name inside its sector when it fits across it, else outside: a column on each
      // side, one under the other, a line to its sector
      let outside = ()
      for t in sectors {
        let mid = t.start - t.angle / 2
        let (c, s) = (calc.cos(mid), calc.sin(mid))
        let body = align(center, txt({
          t.label
          if shown(t.label) {
            linebreak()
            num(t.count)
            if degrees { " (" + num(t.angle / 1deg) + "°)" }
          }
        }))
        let size = measure(body)
        let (w, h) = (size.width / 1cm, size.height / 1cm)
        let d = 0.6 * r
        let across = if t.angle >= 180deg { 2 * d } else { 2 * d * calc.sin(t.angle / 2) }
        if w <= across * 0.9 and h <= across * 0.9 {
          content((d * c, d * s), body)
        } else {
          outside.push((side: if c >= 0 { 1 } else { -1 }, y: r * s, h: h, c: c, s: s, body: body))
        }
      }
      for side in (1, -1) {
        let placed = ()
        for o in outside.filter(o => o.side == side).sorted(key: o => -o.y) {
          let y = if placed.len() == 0 { o.y } else {
            calc.min(o.y, placed.last().y - (placed.last().h + o.h) / 2 - 0.12)
          }
          placed.push((..o, y: y))
        }
        for o in placed {
          line((0.9 * r * o.c, 0.9 * r * o.s), (side * (r + 0.2), o.y), (side * (r + 0.35), o.y), stroke: 0.5pt)
          content((side * (r + 0.42), o.y), o.body, anchor: if side == 1 { "west" } else { "east" })
        }
      }
    }
  })
}
// ---- What the AI writes, from here (the rule's example: everything above is given)
#chart(kind: "semi", values: (("Chat", 12), ("Chien", 10), ("Lapin", 5), ("Poisson", 3)))
