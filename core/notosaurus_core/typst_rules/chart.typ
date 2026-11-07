#set page(width: auto, height: auto, margin: 6pt)
#import "@preview/cetz:0.5.2"
// Numbers written as the figure's language writes them: its decimal separator, set by
// figures_typst.source from the AI's `#set text(lang: …)` (a point when none is said)
#let decimal-separator = "."
// A statistics chart from counts: "bars" (a bar per value, as high as its count: a
// diagramme en bâtons), "pie" (a circle, each sector count / total × 360°), "semi" (a half
// circle, × 180°): the angles computed, never given; or "line", measures joined (a heart
// rate over time). values: (label, count) pairs in the lesson's order, for "line" the
// measures as (x, y), or several lines of the same measure, each named with its measures
// ((name, ((x, y), …)), …: on the same axis, each its colour and dash, a legend); written: the values written on the chart ("all", or some labels; for
// "line" some x), none by default: a card asking a count or a measure never shows it;
// degrees: a sector's angle written with its count; axis: the bars' axis title (the
// lesson's: "Effectif"); axes: a line's (x title, y title), their units with them; step:
// the bars' graduation (auto: every unit up to 12, then 2, 5, 10…), a line's (x, y).
// A line only: marks, events at an x ((x, label): a dashed line across, its label under the
// axis); spans, stretches of x ((from, to, label): shaded); second, another measure with
// its own unit on a right axis ((values: ((x, y), …), axis: title)), in another colour;
// numbered: false when the description gives no value for y (only how it varies): the
// line's shape without numbers on its axis
#let chart(kind: "bars", values: (), written: (), degrees: false, axis: none, axes: (none, none), step: auto,
  marks: (), spans: (), second: none, numbered: true) = context {
  assert(kind in ("bars", "pie", "semi", "line"), message: "kind is \"bars\", \"pie\", \"semi\" or \"line\"")
  let number(x) = type(x) in (int, float)
  let measures(vs) = (
    type(vs) == array and vs.len() > 1 and vs.all(v => type(v) == array and v.len() == 2 and number(v.at(0)) and number(v.at(1)))
  )
  // a line's values: one line's measures, or lines named, each with its measures
  let named = kind == "line" and values.len() > 0 and values.all(v => type(v) == array and v.len() == 2 and type(v.at(1)) == array)
  let lines = if named { values } else { ((none, values),) }
  if kind == "line" {
    assert(
      lines.all(l => measures(l.at(1))),
      message: "a line's values are (x, y) measures, two at least, each a number; several lines: (name, ((x, y), …)) each",
    )
    assert(not named or second == none, message: "second is for a single line: several lines of the same measure share its axis")
    assert(
      marks.all(m => type(m) == array and m.len() == 2 and number(m.at(0))),
      message: "marks are (x, label) pairs, x a number",
    )
    assert(
      spans.all(s => type(s) == array and s.len() == 3 and number(s.at(0)) and number(s.at(1)) and s.at(0) < s.at(1)),
      message: "spans are (from, to, label), from < to, both numbers",
    )
    assert(
      second == none or (type(second) == dictionary and "values" in second and second.values.len() > 1
        and second.values.all(v => type(v) == array and v.len() == 2 and number(v.at(0)) and number(v.at(1)))),
      message: "second is (values: ((x, y), …), axis: title), two measures at least",
    )
  } else {
    assert(marks == () and spans == () and second == none, message: "marks, spans and second are a line's only")
    assert(
      values.len() > 0 and values.all(v => type(v) == array and v.len() == 2 and number(v.at(1)) and v.at(1) >= 0),
      message: "values are (label, count) pairs, each count a number",
    )
  }
  let total = if kind == "line" { 1 } else { values.map(v => v.at(1)).sum() }
  assert(total > 0, message: "the counts add up to more than 0")
  assert(written == "all" or type(written) == array, message: "written is \"all\" or a list of labels")
  let shown(label) = written == "all" or label in written
  let palette = (
    rgb("#9cc9e8"), rgb("#f6c76b"), rgb("#a5d18f"), rgb("#f2a7ad"), rgb("#c3b1e1"), rgb("#f3e08a"),
    rgb("#8fd3c9"), rgb("#e8b48f"),
  )
  let txt(body) = text(10pt, font: "DejaVu Sans", body)
  // a number as the figure's language writes it: whole, or with its decimal separator; to
  // the thousandth (a probability, 0,078), an angle to the tenth
  let num(x, digits: 3) = {
    let r = calc.round(x, digits: digits)
    if calc.fract(r) == 0 { str(int(r)) } else { str(r).replace(".", decimal-separator) }
  }
  // A graduation's step: a round one giving at most `most` steps over `span`
  let nice(span, most) = (0.1, 0.2, 0.5, 1, 2, 2.5, 5, 10, 20, 25, 50, 100, 200, 250, 500, 1000, 2000, 2500, 5000, 10000)
    .find(s => span / s <= most)
  cetz.canvas({
    import cetz.draw: *
    if kind == "line" {
      let xs = lines.map(l => l.at(1).map(v => v.at(0))).flatten()
      let ys = lines.map(l => l.at(1).map(v => v.at(1))).flatten()
      // what else stands on the x axis: the events, the stretches, the second measure
      let others = marks.map(m => m.at(0)) + spans.map(s => s.at(0)) + spans.map(s => s.at(1))
      if second != none { others += second.values.map(v => v.at(0)) }
      // an axis's graduation (start, end, step): from 0, unless its values are far from it
      // (a heart rate: from the graduation under the lowest, the axes still meeting at the
      // bottom left; years: around them)
      // (x, measures taken at a round interval: that interval, every 2 minutes, every 5 years)
      let graduation(vals, given, at-interval, also: ()) = {
        let (lo, hi) = (calc.min(..vals, ..also), calc.max(..vals, ..also))
        let from0 = lo <= 0 or lo <= 3 * nice(hi - calc.min(0, lo), 10)
        let first = if from0 { calc.min(0, lo) } else { lo }
        let sorted = vals.dedup().sorted()
        let gaps = sorted.slice(1).zip(sorted).map(((a, b)) => a - b)
        let even = gaps.len() > 0 and gaps.all(g => calc.abs(g - gaps.first()) < 1e-9)
        let s = if given != auto { given } else {
          let s = nice(hi - first, 8)
          if at-interval and even and gaps.first() > s and nice(gaps.first(), 1) == gaps.first() { gaps.first() } else { s }
        }
        (calc.floor(first / s) * s, calc.ceil(hi / s) * s, s)
      }
      let (gx, gy) = if step == auto { (auto, auto) } else { step }
      let (x0, x1, sx) = graduation(xs, gx, true, also: others)
      let (y0, y1, sy) = graduation(ys, gy, false)
      let (w, h) = (8.0, 5.0)
      let px(x) = (x - x0) / (x1 - x0) * w
      let py(y) = (y - y0) / (y1 - y0) * h
      let n = int(calc.round((x1 - x0) / sx))
      for k in range(n + 1) {
        let x = px(x0 + k * sx)
        if k > 0 { line((x, 0), (x, h), stroke: 0.4pt + luma(210)) }
        line((x, 0), (x, -0.08), stroke: 0.6pt)
        content((x, -0.16), txt(num(x0 + k * sx)), anchor: "north")
      }
      let (red, blue) = (rgb("#b03a2e"), rgb("#1f5fa8"))
      // each line's look: a colour, a dash and a point of its own (told apart in grey too)
      let looks = (
        (paint: red, dash: none, point: "circle"),
        (paint: blue, dash: "dashed", point: "square"),
        (paint: rgb("#2e7d32"), dash: "dotted", point: "triangle"),
        (paint: rgb("#7b3fa0"), dash: "dash-dotted", point: "circle"),
        (paint: rgb("#c77700"), dash: "densely-dashed", point: "square"),
        (paint: luma(40), dash: "loosely-dotted", point: "triangle"),
      )
      let point(p, look) = {
        let (x, y) = p
        if look.point == "circle" { circle(p, radius: 0.06, fill: look.paint, stroke: none) }
        else if look.point == "square" { rect((x - 0.06, y - 0.06), (x + 0.06, y + 0.06), fill: look.paint, stroke: none) }
        else { line((x - 0.075, y - 0.06), (x + 0.075, y - 0.06), (x, y + 0.07), close: true, fill: look.paint, stroke: none) }
      }
      // the stretches first, under everything
      for (a, b, _) in spans {
        rect((px(a), 0), (px(b), h), fill: rgb("#f6c76b").transparentize(55%), stroke: none)
      }
      let m = int(calc.round((y1 - y0) / sy))
      for k in range(m + 1) {
        let y = py(y0 + k * sy)
        if k > 0 { line((0, y), (w, y), stroke: 0.4pt + luma(210)) }
        if numbered {
          line((0, y), (-0.08, y), stroke: 0.6pt)
          content((-0.16, y), txt(num(y0 + k * sy)), anchor: "east")
        }
      }
      // a right axis: the x axis ends on it, its own numbers taking the room beyond
      line((0, 0), (if second == none { w + 0.35 } else { w }, 0), stroke: 0.8pt,
        mark: if second == none { (end: ">", fill: black) } else { none })
      line((0, 0), (0, h + 0.45), stroke: 0.8pt, mark: (end: ">", fill: black))
      let (xt, yt) = axes
      // two measures: each axis's title in its line's colour
      let titled(body, paint) = text(fill: if second == none { black } else { paint }, txt(body))
      if yt != none { content((0.12, h + 0.45), titled(yt, red), anchor: "west") }
      // the x title under the axis's end; with events under the axis, at its arrow's tip
      // instead (their labels' arrows would cross it)
      if xt != none and (marks != () or spans != ()) and second == none {
        content((w + 0.45, 0), txt(xt), anchor: "west")
      } else if xt != none { content((w + 0.35, -0.55), txt(xt), anchor: "north-east") }
      if second != none {
        let zs = second.values.map(v => v.at(1))
        let (z0, z1, sz) = graduation(zs, auto, false)
        let pz(z) = (z - z0) / (z1 - z0) * h
        for k in range(int(calc.round((z1 - z0) / sz)) + 1) {
          let y = pz(z0 + k * sz)
          line((w, y), (w + 0.08, y), stroke: 0.6pt)
          content((w + 0.16, y), text(fill: blue, txt(num(z0 + k * sz))), anchor: "west")
        }
        line((w, 0), (w, h + 0.45), stroke: 0.8pt, mark: (end: ">", fill: black))
        // its title at the right, a row higher when both titles don't fit side by side
        if second.at("axis", default: none) != none {
          let wide(body) = measure(txt(body)).width / 1cm
          let both = (if yt == none { 0 } else { wide(yt) }) + wide(second.axis) + 0.5
          let y = if both > w { h + 0.95 } else { h + 0.45 }
          content((w + 0.12, y), titled(second.axis, blue), anchor: "east")
        }
        let points = second.values.map(((x, z)) => (px(x), pz(z)))
        line(..points, stroke: (paint: blue, thickness: 1.3pt, join: "round", dash: "dashed"))
        for p in points { rect((p.at(0) - 0.06, p.at(1) - 0.06), (p.at(0) + 0.06, p.at(1) + 0.06), fill: blue, stroke: none) }
      }
      for (k, (name, vs)) in lines.enumerate() {
        let look = looks.at(calc.rem(k, looks.len()))
        let points = vs.map(((x, y)) => (px(x), py(y)))
        line(..points, stroke: (paint: look.paint, thickness: 1.3pt, join: "round", dash: look.dash))
        for (i, (x, y)) in vs.enumerate() {
          point(points.at(i), look)
          if written == "all" or x in written {
            content((points.at(i).at(0), points.at(i).at(1) + 0.12), text(fill: if named { look.paint } else { black }, txt(num(y))), anchor: "south")
          }
        }
      }
      // the lines' names: a legend at the right, each with its line's look
      if named {
        for (k, (name, _)) in lines.enumerate() {
          let look = looks.at(calc.rem(k, looks.len()))
          let y = h - k * 0.5
          line((w + 0.55, y), (w + 1.25, y), stroke: (paint: look.paint, thickness: 1.3pt, dash: look.dash))
          point((w + 0.9, y), look)
          content((w + 1.4, y), txt(name), anchor: "west")
        }
      }
      // The events' and the stretches' labels under the axis, under its title's row, each
      // at its x; one too close to the one before goes a row lower
      let events = marks.map(((x, label)) => (x: px(x), label: label, mark: true))
      events += spans.map(((a, b, label)) => (x: (px(a) + px(b)) / 2, label: label, mark: false))
      let rows = ()  // each row's right edge so far
      for e in events.sorted(key: e => e.x) {
        let half = measure(txt(e.label)).width / 1cm / 2
        let row = rows.position(r => r + 0.15 < e.x - half)
        if row == none { rows.push(e.x + half); row = rows.len() - 1 } else { rows.at(row) = e.x + half }
        let y = -0.75 - row * 0.45
        if e.mark { line((e.x, h), (e.x, 0), stroke: (paint: luma(90), thickness: 0.8pt, dash: "dashed")) }
        line((e.x, y + 0.05), (e.x, -0.48), stroke: 0.6pt + luma(90), mark: (end: ">", fill: luma(90), scale: 0.6))
        content((e.x, y), txt(e.label), anchor: "north")
      }
    } else if kind == "bars" {
      let top = calc.max(..values.map(v => v.at(1)))
      // counts by whole steps; values under 1 or with decimals (a probability law) by tenths,
      // hundredths…: never a graduation 0 and 1 alone
      let whole = values.all(v => calc.fract(v.at(1)) == 0)
      let step = if step != auto { step } else if whole {
        (1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500, 1000).find(s => top / s <= 12)
      } else {
        (0.01, 0.02, 0.05, 0.1, 0.2, 0.25, 0.5, 1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500, 1000).find(s => top / s < 10)
      }
      let ymax = calc.ceil(top / step - 1e-9) * step
      let h = 4.0
      let unit = h / ymax
      // each bar's room: its label's width at least, so that long names never overlap
      let slot = calc.max(1.5, ..values.map(v => measure(txt(v.at(0))).width / 1cm + 0.3))
      let w = slot * values.len()
      // the graduation: a tick and a light line at each step, so that a count is read, not guessed
      for k in range(1, int(calc.round(ymax / step)) + 1) {
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
            if degrees { " (" + num(t.angle / 1deg, digits: 1) + "°)" }
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
