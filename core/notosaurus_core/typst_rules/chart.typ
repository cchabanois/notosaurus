#set page(width: auto, height: auto, margin: 6pt)
#import "@preview/cetz:0.5.2"
// Numbers written as the figure's language writes them: its decimal separator, set by
// figures_typst.source from the AI's `#set text(lang: …)` (a point when none is said)
#import "common.typ": *
// A statistics chart from counts: "bars" (a bar per value, as high as its count: a
// diagramme en bâtons), "pie" (a circle, each sector count / total × 360°), "semi" (a half
// circle, × 180°): the angles computed, never given; or "line", measures joined (a heart
// rate over time). values: (label, count) pairs in the lesson's order, for "line" the
// measures as (x, y), or several lines of the same measure, each named with its measures
// ((name, ((x, y), …)), …: on the same axis, each its colour and dash, a legend); written: the values written on the chart ("all", or some labels; for
// "line" some x): a bar chart's and a pie's all by default (the values the description
// gives are what it shows), a line's none; hidden: the labels whose value a card asks for,
// written "?" (their count, share or angle never shown); unit: written after each value
// ("%": 31 %, with the figure's language's space);
// degrees: a sector's angle written with its count; axis: the bars' axis title (the
// lesson's: "Effectif"); axes: a line's (x title, y title), their units with them; step:
// the bars' graduation (auto: every unit up to 12, then 2, 5, 10…), a line's (x, y).
// A line only: marks, events at an x ((x, label): a dashed line across, its label under the
// axis); spans, stretches of x ((from, to, label): shaded); second, another measure with
// its own unit on a right axis ((values: ((x, y), …), axis: title)), in another colour;
// kind "box": box plots, each (name, (min, q1, median, q3, max)), on one axis (_box-plots).
// kind "pyramid": two series back to back by class, classes: their names (_pyramid).
// numbered: false when the description gives no value for y (only how it varies): the
// line's shape without numbers on its axis; smooth: a curve through the measures instead of
// straight lines, never above nor below them between two (monotone: Fritsch–Carlson).
// horizontal: bars lying, their names one under the other at the left, the first at the top
// A curve through measures (x, y) sorted by x, sampled: each stretch a cubic passing through
// its two ends, with slopes that never let it overshoot them (a rise stays a rise, a flat
// stays flat), so that the curve says nothing the measures don't
#let monotone(vs, per: 16) = {
  let vs = vs.sorted(key: v => v.at(0))
  let n = vs.len()
  let (xs, ys) = (vs.map(v => v.at(0)), vs.map(v => v.at(1)))
  assert(range(n - 1).all(k => xs.at(k + 1) != xs.at(k)), message: "smooth: two measures with the same x, a curve has one value at each x: " + repr(vs))
  let d = range(n - 1).map(k => (ys.at(k + 1) - ys.at(k)) / (xs.at(k + 1) - xs.at(k)))
  let m = range(n).map(k => if k == 0 { d.first() } else if k == n - 1 { d.last() } else if d.at(k - 1) * d.at(k) <= 0 { 0 } else { (d.at(k - 1) + d.at(k)) / 2 })
  for k in range(n - 1) {
    if d.at(k) == 0 { m.at(k) = 0; m.at(k + 1) = 0 } else {
      let (a, b) = (m.at(k) / d.at(k), m.at(k + 1) / d.at(k))
      if a * a + b * b > 9 {
        let t = 3 / calc.sqrt(a * a + b * b)
        m.at(k) = t * a * d.at(k)
        m.at(k + 1) = t * b * d.at(k)
      }
    }
  }
  let out = ((xs.first(), ys.first()),)
  for k in range(n - 1) {
    let h = xs.at(k + 1) - xs.at(k)
    for j in range(1, per + 1) {
      let t = j / per
      let y = (2 * t * t * t - 3 * t * t + 1) * ys.at(k) + (t * t * t - 2 * t * t + t) * h * m.at(k) + (-2 * t * t * t + 3 * t * t) * ys.at(k + 1) + (t * t * t - t * t) * h * m.at(k + 1)
      out.push((xs.at(k) + t * h, y))
    }
  }
  out
}
// Box plots (boîtes à moustaches): each box from its five values (minimum, first quartile,
// median, third quartile, maximum), all on one shared axis, the first box at the top, each
// named at its left. The axis's length fixed (about 8 cm with the names, whatever the data's
// range: never the values taken as centimetres), its graduation computed (a round step, at
// most 10 of them, a finer tick between two numbers), from `limits` when the description
// gives the axis's ends, else around the values. written: the boxes whose five values are
// written ("all", or names), none by default (a card asking a quartile never shows it).
#let _box-plots(values, written: (), axis: none, step: auto, limits: auto) = context {
  let number(x) = type(x) in (int, float)
  let five(v) = type(v) == array and v.len() == 5 and v.all(number)
  // one box alone: its five values, no name; else (name, (min, q1, median, q3, max)) each
  let boxes = if five(values) { ((none, values),) } else { values }
  assert(
    type(boxes) == array and boxes.len() > 0 and boxes.all(b => type(b) == array and b.len() == 2 and five(b.at(1))),
    message: "a box plot's values are (name, (min, q1, median, q3, max)) each, or one box's five numbers",
  )
  assert(
    boxes.all(b => range(4).all(k => b.at(1).at(k) <= b.at(1).at(k + 1))),
    message: "a box's five values go up: min ≤ q1 ≤ median ≤ q3 ≤ max",
  )
  assert(written == "all" or type(written) == array, message: "written is \"all\" or a list of the boxes' names")
  assert(limits == auto or (type(limits) == array and limits.len() == 2 and limits.all(number) and limits.at(0) < limits.at(1)),
    message: "limits is the axis's (first, last) value")
  let txt(body) = text(10pt, font: "DejaVu Sans", body)
  let num(x) = written-number(x, digits: 3)
  let all = boxes.map(b => b.at(1)).flatten()
  let (lo, hi) = if limits == auto { (calc.min(..all), calc.max(..all)) } else { limits }
  let span = calc.max(hi - lo, 1e-9)
  let names = boxes.map(b => b.at(0)).filter(n => n != none)
  let left = if names.len() == 0 { 0 } else { calc.max(..names.map(n => measure(txt(n)).width / 1cm)) + 0.3 }
  let w = calc.max(6, 7.8 - left)
  // the axis's ends for a step: the description's, else the round values around the data
  let ends(s) = if limits == auto { (calc.floor(lo / s + 1e-9) * s, calc.ceil(hi / s - 1e-9) * s) } else { limits }
  let ticks(s) = { let (a0, a1) = ends(s); range(calc.ceil(a0 / s - 1e-9), calc.floor(a1 / s + 1e-9) + 1).map(k => k * s) }
  // the step: the description's, else the finest round one giving at most 10 steps whose
  // numbers stand apart along the axis
  let s = if step != auto { step } else {
    let found = round-steps(span / 10, 10 * span)
      .find(c => {
        let (a0, a1) = ends(c)
        let widest = calc.max(..ticks(c).map(t => measure(txt(num(t))).width / 1cm))
        c / (a1 - a0) * w >= widest + 0.15
      })
    if found == none { calc.pow(10, calc.ceil(calc.log(span, base: 10))) } else { found }
  }
  let (a0, a1) = ends(s)
  let px(v) = (v - a0) / (a1 - a0) * w
  let shown(name) = written == "all" or (name != none and name in written)
  let pitch = if boxes.any(b => shown(b.at(0))) { 1.7 } else { 1.0 }
  let half = 0.3
  let n = boxes.len()
  cetz.canvas({
    import cetz.draw: *
    // the numbered ticks, then a finer tick between two (a value read between them): a
    // tenth, a fifth or a half of the step, the finest that stays apart
    let top = n * pitch + 0.1
    for t in ticks(s) {
      line((px(t), 0), (px(t), top), stroke: 0.4pt + _grid)
      line((px(t), 0.1), (px(t), -0.1), stroke: 0.6pt)
      content((px(t), -0.18), txt(num(t)), anchor: "north")
    }
    let lead = calc.round(s / calc.pow(10, calc.floor(calc.log(s, base: 10) + 1e-9)), digits: 3)
    let parts = (10, 5, 2).filter(k => k == 10 or (k == 5 and lead in (1, 5)) or (k == 2 and lead in (1, 2, 5)))
    let fine = parts.map(k => s / k).find(f => f / (a1 - a0) * w >= 0.18)
    if fine != none {
      for k in range(calc.ceil(a0 / fine - 1e-9), calc.floor(a1 / fine + 1e-9) + 1) {
        let v = k * fine
        if ticks(s).all(t => calc.abs(t - v) > fine / 10) { line((px(v), 0.06), (px(v), -0.06), stroke: 0.5pt) }
      }
    }
    line((0, 0), (w, 0), stroke: 0.8pt)
    if axis != none { content((w, -0.7), txt(axis), anchor: "north-east") }
    for (i, (name, (mn, q1, me, q3, mx))) in boxes.enumerate() {
      let y = (n - i) * pitch - pitch / 2 + 0.35
      line((px(mn), y), (px(q1), y), stroke: 0.9pt)
      line((px(q3), y), (px(mx), y), stroke: 0.9pt)
      for v in (mn, mx) { line((px(v), y - half / 2), (px(v), y + half / 2), stroke: 0.9pt) }
      rect((px(q1), y - half), (px(q3), y + half), fill: luma(225), stroke: 0.9pt)
      line((px(me), y - half), (px(me), y + half), stroke: 2pt)
      if name != none { content((-0.3, y), txt(name), anchor: "east") }
      if shown(name) {
        // each value at its x, above the box; one that would touch another goes below
        let placed = ()
        for v in (me, q1, q3, mn, mx) {
          let width = measure(txt(num(v))).width / 1cm
          let (from, to) = (px(v) - width / 2 - 0.06, px(v) + width / 2 + 0.06)
          let above = placed.filter(p => p.at(0) and p.at(1) < to and from < p.at(2)).len() == 0
          placed.push((above, from, to))
          let body = txt(num(v))
          if above { content((px(v), y + half + 0.06), body, anchor: "south") }
          else { content((px(v), y - half - 0.06), body, anchor: "north") }
        }
      }
    }
  })
}
// The sectors' and the series' colours, light enough for a number written on them
#let _palette = (
  rgb("#9cc9e8"), rgb("#f6c76b"), rgb("#a5d18f"), rgb("#f2a7ad"), rgb("#c3b1e1"), rgb("#f3e08a"),
  rgb("#8fd3c9"), rgb("#e8b48f"),
)
// A pyramid (a population pyramid, an age pyramid): two series of bars back to back, the
// first at the left, the second at the right, one bar of each per class, at the same height;
// the classes in a column between them, the first at the bottom (the youngest); one value
// axis under each side, graduated alike from 0 at the centre outwards (each side's numbers
// its absolute values), its step computed (a round one whose numbers fit apart); each
// series' name above its side, in its bars' colour. numbered: false when the description
// gives no value (a pyramid's shape only): no graduation, no number, the bars' lengths only
// showing that shape. written: the classes whose two values are written ("all", or classes).
#let _pyramid(classes, values, written: (), axis: none, step: auto, numbered: true) = context {
  let number(x) = type(x) in (int, float)
  assert(type(classes) == array and classes.len() > 0 and classes.all(c => type(c) in (str, content)),
    message: "pyramid: classes is the list of the classes' names, the youngest first: (\"0-9 ans\", \"10-19 ans\", …)")
  assert(
    type(values) == array and values.len() == 2 and values.all(s => type(s) == array and s.len() == 2 and type(s.at(1)) == array),
    message: "pyramid: values is two series, (name, (value, …)) each, the left one first: ((\"Hommes\", (…)), (\"Femmes\", (…)))",
  )
  assert(values.all(s => s.at(1).len() == classes.len()),
    message: "pyramid: each series has one value per class, as many as classes (" + str(classes.len()) + ")")
  assert(values.all(s => s.at(1).all(v => number(v) and v >= 0)),
    message: "pyramid: a series' values are numbers, 0 or more (each side's length; the sides are drawn apart)")
  let top = calc.max(..values.map(s => s.at(1)).flatten())
  assert(top > 0, message: "pyramid: some value is more than 0")
  assert(written == "all" or type(written) == array, message: "written is \"all\" or a list of classes")
  assert(numbered or (written == () and step == auto),
    message: "pyramid: numbered: false shows a shape only, never a number written nor a step")
  let shown(c) = written == "all" or c in written
  let txt(body) = text(10pt, font: "DejaVu Sans", body)
  let num(x) = written-number(x, digits: 3)
  let w = 3.4  // each side's length
  // the step: the description's, else the finest round one whose numbers fit apart, at most 6
  let ticks-end(s) = calc.ceil(top / s - 1e-9) * s
  let s = if step != auto { step } else {
    let found = round-steps(top / 6, 10 * top).find(c => c * w / ticks-end(c) >= measure(txt(num(ticks-end(c)))).width / 1cm + 0.25)
    if found == none { round-step(top, 2) } else { found }
  }
  let end = if numbered { ticks-end(s) } else { top }
  let unit = w / end
  let gap = calc.max(..classes.map(c => measure(txt(c)).width / 1cm)) + 0.4  // the classes' column
  let row = 0.55
  let n = classes.len()
  let height = n * row
  let (left, right) = (-gap / 2, gap / 2)
  let colours = (_palette.at(0), _palette.at(3))
  cetz.canvas({
    import cetz.draw: *
    if numbered {
      for k in range(int(calc.round(end / s)) + 1) {
        let d = k * s * unit
        for (x0, sign) in ((left, -1), (right, 1)) {
          let x = x0 + sign * d
          if k > 0 { line((x, 0), (x, height), stroke: 0.4pt + _grid) }
          line((x, 0), (x, -0.08), stroke: 0.6pt)
          content((x, -0.16), txt(num(k * s)), anchor: "north")
        }
      }
    }
    for (side, (x0, sign)) in ((left, -1), (right, 1)).enumerate() {
      line((x0, 0), (x0 + sign * (w + 0.2), 0), stroke: 0.8pt)
      line((x0, 0), (x0, height + 0.1), stroke: 0.8pt)
      let (name, vs) = values.at(side)
      for (i, v) in vs.enumerate() {
        let y = (i + 0.5) * row
        if v > 0 {
          rect((x0, y - row * 0.42), (x0 + sign * v * unit, y + row * 0.42), fill: colours.at(side), stroke: 0.5pt + luma(90))
        }
        if numbered and shown(classes.at(i)) {
          content((x0 + sign * (v * unit + 0.08), y), txt(num(v)), anchor: if sign < 0 { "east" } else { "west" })
        }
      }
      // the series' name above its side, a patch of its colour before it
      let label = box(width: 0.3cm, height: 0.3cm, baseline: 5%, fill: colours.at(side), stroke: 0.5pt + luma(90)) + h(0.15cm) + txt(name)
      content((x0 + sign * w / 2, height + 0.3), label, anchor: "south")
    }
    for (i, c) in classes.enumerate() { content((0, (i + 0.5) * row), txt(c)) }
    if axis != none { content((0, if numbered { -0.65 } else { -0.2 }), txt(axis), anchor: "north") }
  })
}
// kind "histogram": classes side by side, each (from, to, count), sorted by their bounds; a
// rectangle as wide as its class, as high as its count when the classes are equal, else its
// area the count (its height the count per unit of width: the y axis then unnumbered, the
// counts written on the rectangles); every bound written once under the axis. written,
// hidden: classes by their lower bound ((160,)); axis: the y axis's title ("Effectif");
// axes.at(0): the x axis's title, its unit with it ("Taille (cm)")
#let _histogram(values, written: "all", hidden: (), axis: none, axes: (none, none), step: auto, unit: none, colours: ()) = context {
  let number(x) = type(x) in (int, float)
  assert(
    values.len() > 0 and values.all(v => type(v) == array and v.len() == 3 and v.all(number) and v.at(0) < v.at(1) and v.at(2) >= 0),
    message: "a histogram's values are its classes, (from, to, count) each: (150, 155, 6), from < to",
  )
  let classes = values.sorted(key: v => v.at(0))
  assert(classes.slice(1).zip(classes).all(((b, a)) => b.at(0) >= a.at(1) - 1e-9),
    message: "a histogram's classes never overlap: each ends where the next starts, or before")
  assert(written == "all" or type(written) == array, message: "written is \"all\" or a list of classes' lower bounds")
  let widths = classes.map(v => v.at(1) - v.at(0))
  let equal = widths.all(w => calc.abs(w - widths.first()) <= 1e-9 * calc.max(1, widths.first()))
  let heights = if equal { classes.map(v => v.at(2)) } else { classes.map(v => v.at(2) / (v.at(1) - v.at(0))) }
  let top = calc.max(..heights)
  assert(top > 0, message: "the counts add up to more than 0")
  let txt(body) = text(10pt, font: "DejaVu Sans", body)
  let s = if step != auto and equal { step } else { round-step(top, 6) }
  let ymax = calc.ceil(top / s - 1e-9) * s
  let (x0, x1) = (classes.first().at(0), classes.last().at(1))
  let (w, h) = (8.0, 4.0)
  let px(x) = (x - x0) / (x1 - x0) * w
  let py(y) = y / ymax * h
  let gap = if text.lang == "fr" { "\u{202F}" } else if unit == "%" { "" } else { "\u{00A0}" }
  let value(from, c) = if from in hidden { "?" } else if unit == none { written-number(c, digits: 3) } else {
    written-number(c, digits: 3) + gap + unit
  }
  cetz.canvas({
    import cetz.draw: *
    if equal {
      for k in range(1, int(calc.round(ymax / s)) + 1) {
        let y = py(k * s)
        line((0, y), (w, y), stroke: 0.4pt + _grid)
        line((-0.08, y), (0, y), stroke: 0.6pt)
        content((-0.16, y), txt(written-number(k * s)), anchor: "east")
      }
      content((-0.16, 0), txt("0"), anchor: "east")
    }
    for (i, (a, b, c)) in classes.enumerate() {
      if c > 0 { rect((px(a), 0), (px(b), py(heights.at(i))), fill: if colours == () { luma(185) } else { colours.at(calc.rem(i, colours.len())) }, stroke: 0.6pt + luma(40)) }
      if written == "all" or a in written or a in hidden {
        content(((px(a) + px(b)) / 2, py(heights.at(i)) + 0.08), txt(value(a, c)), anchor: "south")
      }
    }
    // each bound once under the axis (a class's end, the next one's start)
    for x in (classes.map(v => v.at(0)) + classes.map(v => v.at(1))).sorted().dedup() {
      line((px(x), 0), (px(x), -0.08), stroke: 0.6pt)
      content((px(x), -0.16), txt(written-number(x)), anchor: "north")
    }
    line((0, 0), (w + 0.35, 0), stroke: 0.8pt, mark: (end: ">", fill: black))
    line((0, 0), (0, h + 0.45), stroke: 0.8pt, mark: (end: ">", fill: black))
    if axis != none { content((0.12, h + 0.45), txt(axis), anchor: "west") }
    if axes.at(0) != none { content((w + 0.35, -0.6), txt(axes.at(0)), anchor: "north-east") }
  })
}
// A climate chart (diagramme ombrothermique): each month's precipitation as a bar, its mean
// temperature as a curve through its values, on two axes whose scales are tied, P = 2T (the
// precipitation's 20 mm at the temperature's 10 °C: a month is dry where the bar stays under the
// curve), computed: the temperature's step 2, 5 or 10 °C, the precipitation's twice it, both from
// 0 on one line (below it, the temperature's only: a cold month). values: (month, precipitation,
// temperature) each, in order; axes: (the precipitation's title, the temperature's)
#let _climate(values, axes: (none, none)) = context {
  let number(x) = type(x) in (int, float)
  assert(
    values.len() > 1 and values.all(v => type(v) == array and v.len() == 3 and number(v.at(1)) and number(v.at(2)) and v.at(1) >= 0),
    message: "a climate chart's values are its months, (month, precipitation, temperature) each: (\"J\", 45, 5), the precipitation 0 or more",
  )
  assert(type(axes) == array and axes.len() == 2, message: "axes is (the precipitation's title, the temperature's)")
  let txt(body) = text(10pt, font: "DejaVu Sans", body)
  let (rain, temp) = (values.map(v => v.at(1)), values.map(v => v.at(2)))
  // the temperature's range, the precipitation's halved standing in it (P = 2T)
  let lo = calc.min(0, ..temp)
  let hi = calc.max(..temp, ..rain.map(p => p / 2))
  let s = (2, 5, 10, 20, 50).find(s => (hi - lo) / s <= 8)
  if s == none { s = round-step(hi - lo, 8) }
  let (t0, t1) = (calc.floor(lo / s) * s, calc.ceil(hi / s - 1e-9) * s)
  if t1 <= t0 { t1 = t0 + s }
  let n = values.len()
  let (w, h) = (8.0, 5.0)
  let slot = w / n
  let px(i) = (i + 0.5) * slot
  let py(t) = (t - t0) / (t1 - t0) * h
  let (red, blue) = (rgb("#b03a2e"), rgb("#1f5fa8"))
  cetz.canvas({
    import cetz.draw: *
    for k in range(int(calc.round((t1 - t0) / s)) + 1) {
      let t = t0 + k * s
      let y = py(t)
      if k > 0 { line((0, y), (w, y), stroke: 0.4pt + _grid) }
      // the precipitation's numbers at the left (never under 0), the temperature's at the right
      if t >= 0 {
        line((0, y), (-0.08, y), stroke: 0.6pt)
        content((-0.16, y), text(fill: blue, txt(written-number(2 * t))), anchor: "east")
      }
      line((w, y), (w + 0.08, y), stroke: 0.6pt)
      content((w + 0.16, y), text(fill: red, txt(written-number(t))), anchor: "west")
    }
    // the bars from the precipitation's 0, the temperature's 0 too
    for (i, p) in rain.enumerate() {
      if p > 0 { rect((px(i) - 0.36 * slot, py(0)), (px(i) + 0.36 * slot, py(p / 2)), fill: blue.lighten(45%), stroke: 0.5pt + blue) }
    }
    for (i, v) in values.enumerate() {
      content((px(i), -0.16), txt(v.at(0)), anchor: "north")
    }
    line((0, py(0)), (w, py(0)), stroke: 0.8pt)
    if t0 < 0 { line((0, 0), (w, 0), stroke: 0.6pt) }
    line((0, 0), (0, h + 0.45), stroke: 0.8pt, mark: (end: ">", fill: black))
    line((w, 0), (w, h + 0.45), stroke: 0.8pt, mark: (end: ">", fill: black))
    let curve = monotone(values.enumerate().map(((i, v)) => (i, v.at(2)))).map(((i, t)) => (px(i), py(t)))
    line(..curve, stroke: (paint: red, thickness: 1.4pt, join: "round"))
    for (i, t) in temp.enumerate() { circle((px(i), py(t)), radius: 0.06, fill: red, stroke: none) }
    let (pt, tt) = axes
    if pt != none { content((-0.12, h + 0.45), text(fill: blue, txt(pt)), anchor: "south-west") }
    if tt != none { content((w + 0.12, h + 0.45), text(fill: red, txt(tt)), anchor: "south-east") }
  })
}
#let chart(kind: "bars", values: (), written: auto, hidden: (), unit: none, degrees: false, axis: none, axes: (none, none), step: auto,
  marks: (), spans: (), second: none, numbered: true, smooth: false, limits: auto, horizontal: false, classes: none, fit: none, reversed: false, colours: ()) = context {
  assert(kind in ("bars", "pie", "semi", "line", "scatter", "box", "pyramid", "histogram", "climate"),
    message: "kind is \"bars\", \"pie\", \"semi\", \"line\", \"scatter\", \"box\", \"pyramid\", \"histogram\" or \"climate\"")
  // a month's precipitation and temperature together: the climate chart, its two scales tied
  // colours: the colours the description asks for (the bars in green, each sector its own),
  // one for all, or one per value in their order (per line, per class); else the chart's own
  let colours = if type(colours) == color { (colours,) } else { colours }
  assert(type(colours) == array and colours.all(c => type(c) == color),
    message: "colours is a colour (green, rgb(\"#2e7d32\")) or a list of them, one per value")
  assert(colours == () or kind in ("bars", "pie", "semi", "line", "scatter", "histogram"),
    message: "colours is for bars, pies, lines, scatter plots and histograms")
  if kind == "climate" {
    assert(written == auto and hidden == () and unit == none and axis == none and step == auto and marks == () and spans == ()
      and second == none and not smooth and not degrees and limits == auto and not horizontal and numbered and fit == none
      and not reversed and classes == none,
      message: "a climate chart takes values, (month, precipitation, temperature) each, and axes only: its bars, its curve and their two scales are computed")
    return _climate(values, axes: axes)
  }
  assert(fit == none or kind == "scatter", message: "fit is a scatter plot's only")
  assert(not reversed or kind in ("line", "scatter"), message: "reversed is for lines and scatter plots: their x axis from its largest value to its smallest")
  assert(kind == "pyramid" or classes == none, message: "classes is for a pyramid only")
  assert(type(hidden) == array, message: "hidden is a list of the labels whose value a card asks for")
  assert(unit == none or type(unit) == str, message: "unit is a text written after each value (\"%\")")
  assert((hidden == () and unit == none) or kind in ("bars", "pie", "semi", "line", "scatter", "histogram"),
    message: "hidden and unit are for bars, pies and lines, histograms too")
  // what is written by default: a bar chart's and a pie's values (what it shows), else none
  let given-written = written
  let written = if written != auto { written } else if kind in ("bars", "pie", "semi", "histogram") { "all" } else { () }
  if kind == "histogram" {
    assert(marks == () and spans == () and second == none and not smooth and not degrees and limits == auto
      and not horizontal and numbered,
      message: "a histogram takes values, axis, axes, step, unit, written and hidden only")
    return _histogram(values, written: written, hidden: hidden, axis: axis, axes: axes, step: step, unit: unit, colours: colours)
  }
  // a scatter plot: a line's measures as points, never joined; fit: (a, b), the line y = ax + b
  // drawn across them and named
  let plotted = kind in ("line", "scatter")
  assert(kind != "scatter" or (not smooth and second == none), message: "a scatter plot's points are never joined: no smooth, no second")
  assert(fit == none or (type(fit) == array and fit.len() == 2 and fit.all(n => type(n) in (int, float))),
    message: "fit is (a, b): the line y = ax + b")
  if kind == "pyramid" {
    assert(marks == () and spans == () and second == none and not smooth and axes == (none, none) and not degrees
      and limits == auto and not horizontal,
      message: "a pyramid takes classes, values, axis, step, numbered and written only")
    return _pyramid(if classes == none { () } else { classes }, values, written: written, axis: axis, step: step,
      numbered: numbered)
  }
  if kind == "box" {
    assert(marks == () and spans == () and second == none and not smooth and axes == (none, none) and not degrees,
      message: "box plots take values, axis, step, limits and written only")
    return _box-plots(values, written: written, axis: axis, step: step, limits: limits)
  }
  assert(limits == auto, message: "limits is for box plots only")
  assert(not horizontal or kind == "bars", message: "horizontal is for bars only")
  let number(x) = type(x) in (int, float)
  let measures(vs) = (
    type(vs) == array and vs.len() > 1 and vs.all(v => type(v) == array and v.len() == 2 and number(v.at(0)) and number(v.at(1)))
  )
  // a line's values: one line's measures, or lines named, each with its measures
  let named = plotted and values.len() > 0 and values.all(v => type(v) == array and v.len() == 2 and type(v.at(1)) == array)
  let lines = if named { values } else { ((none, values),) }
  if plotted {
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
    assert(second == none and not smooth, message: "second and smooth are a line's only: a month's precipitation as bars with its temperature as a curve is kind: \"climate\"")
    assert((marks == () and spans == ()) or (kind == "bars" and not horizontal), message: "marks and spans are a line's, or standing bars'")
    // on bars: a mark at a bar (its name or its value: the expectation, the mean), a span from a
    // bar to another (an interval of values), each found among the bars' names
    let key(v) = if type(v) == str { v.trim() } else { str(v) }
    let names = values.map(v => key(v.at(0)))
    for m in marks { assert(type(m) == array and m.len() == 2 and key(m.at(0)) in names, message: "marks on bars: (a bar's name, label), " + repr(m.at(0)) + " not among " + names.join(", ")) }
    for sp in spans { assert(type(sp) == array and sp.len() == 3 and key(sp.at(0)) in names and key(sp.at(1)) in names, message: "spans on bars: (first bar's name, last bar's name, label), among " + names.join(", ")) }
    assert(
      values.len() > 0 and values.all(v => type(v) == array and v.len() == 2 and number(v.at(1)) and v.at(1) >= 0),
      message: "values are (label, count) pairs, each count a number",
    )
  }
  let total = if plotted { 1 } else { values.map(v => v.at(1)).sum() }
  assert(total > 0, message: "the counts add up to more than 0")
  assert(written == "all" or type(written) == array, message: "written is \"all\" or a list of labels")
  let shown(label) = written == "all" or label in written or label in hidden
  let palette = if colours == () { _palette } else { colours }
  let bar(i) = if colours == () { luma(55) } else { colours.at(calc.rem(i, colours.len())) }
  let txt(body) = text(10pt, font: "DejaVu Sans", body)
  // a number as the figure's language writes it: whole, or with its decimal separator; to
  // the thousandth (a probability, 0,078), an angle to the tenth
  let num(x, digits: 3) = written-number(x, digits: digits)
  // a value as written on the chart: its number and its unit (French: a narrow no-break
  // space before any unit, 31 %; else none before "%", a no-break space before the others),
  // "?" for a value the card asks for
  let gap = if text.lang == "fr" { "\u{202F}" } else if unit == "%" { "" } else { "\u{00A0}" }
  let value(label, x, digits: 3) = if label in hidden { "?" } else if unit == none { num(x, digits: digits) } else {
    num(x, digits: digits) + gap + unit
  }
  cetz.canvas({
    import cetz.draw: *
    if plotted {
      let xs = lines.map(l => l.at(1).map(v => v.at(0))).flatten()
      let ys = lines.map(l => l.at(1).map(v => v.at(1))).flatten()
      // the fit's ends, where the measures start and end, in the frame too
      let ends = if fit == none { () } else { (calc.min(..xs), calc.max(..xs)) }
      ys += ends.map(x => fit.at(0) * x + fit.at(1))
      // what else stands on the x axis: the events, the stretches, the second measure
      let others = marks.map(m => m.at(0)) + spans.map(s => s.at(0)) + spans.map(s => s.at(1))
      if second != none { others += second.values.map(v => v.at(0)) }
      // an axis's graduation (start, end, step): from 0, unless its values are far from it
      // (a heart rate: from the graduation under the lowest, the axes still meeting at the
      // bottom left; years: around them)
      // (x, measures taken at a round interval: that interval, every 2 minutes, every 5 years)
      let graduation(vals, given, at-interval, also: ()) = {
        let (lo, hi) = (calc.min(..vals, ..also), calc.max(..vals, ..also))
        // a step: a round one giving at most `most` steps over `span`, never finer than the
        // values' size calls for (a fifth of the largest, 0,1 at most: values that change
        // little keep a graduation showing it so, 0,49 to 0,51 by tenths, while small values,
        // 0,002 to 0,010 mol/L, keep steps of their own size)
        let size = calc.max(calc.abs(lo), calc.abs(hi))
        let finest = calc.min(0.1, round-step(size, 5))
        let nice(span, most) = calc.max(round-step(span, most), finest)
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
      // (reversed: the largest x at the left, as an infrared spectrum's wavenumbers)
      let px(x) = if reversed { (x1 - x) / (x1 - x0) * w } else { (x - x0) / (x1 - x0) * w }
      let py(y) = (y - y0) / (y1 - y0) * h
      let n = int(calc.round((x1 - x0) / sx))
      for k in range(n + 1) {
        let x = px(x0 + k * sx)
        if x > 1e-9 { line((x, 0), (x, h), stroke: 0.4pt + _grid) }
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
      ).enumerate().map(((k, look)) => if colours == () { look } else { (..look, paint: colours.at(calc.rem(k, colours.len()))) })
      // (a scatter plot's points larger: they are all it shows)
      let r = if kind == "scatter" { 0.09 } else { 0.06 }
      let point(p, look) = {
        let (x, y) = p
        if look.point == "circle" { circle(p, radius: r, fill: look.paint, stroke: none) }
        else if look.point == "square" { rect((x - r, y - r), (x + r, y + r), fill: look.paint, stroke: none) }
        else { line((x - 1.25 * r, y - r), (x + 1.25 * r, y - r), (x, y + 1.17 * r), close: true, fill: look.paint, stroke: none) }
      }
      // the stretches first, under everything
      for (a, b, _) in spans {
        rect((px(a), 0), (px(b), h), fill: rgb("#f6c76b").transparentize(55%), stroke: none)
      }
      let m = int(calc.round((y1 - y0) / sy))
      for k in range(m + 1) {
        let y = py(y0 + k * sy)
        if k > 0 { line((0, y), (w, y), stroke: 0.4pt + _grid) }
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
        let path = if smooth { monotone(second.values).map(((x, z)) => (px(x), pz(z))) } else { points }
        line(..path, stroke: (paint: blue, thickness: 1.3pt, join: "round", dash: "dashed"))
        for p in points { rect((p.at(0) - 0.06, p.at(1) - 0.06), (p.at(0) + 0.06, p.at(1) + 0.06), fill: blue, stroke: none) }
      }
      for (k, (name, vs)) in lines.enumerate() {
        let look = looks.at(calc.rem(k, looks.len()))
        let points = vs.map(((x, y)) => (px(x), py(y)))
        let path = if smooth { monotone(vs).map(((x, y)) => (px(x), py(y))) } else { points }
        if kind == "line" { line(..path, stroke: (paint: look.paint, thickness: 1.3pt, join: "round", dash: look.dash)) }
        for (i, (x, y)) in vs.enumerate() {
          point(points.at(i), look)
          if written == "all" or x in written or x in hidden {
            content((points.at(i).at(0), points.at(i).at(1) + 0.12), text(fill: if named { look.paint } else { black }, txt(value(x, y))), anchor: "south")
          }
        }
      }
      // the fit: from the first measure's x to the last's, named at its end
      if fit != none {
        let (a, b) = fit
        let (xa, xb) = ends
        line((px(xa), py(a * xa + b)), (px(xb), py(a * xb + b)), stroke: (paint: rgb("#1f5fa8"), thickness: 1.1pt))
        let sign = if b < 0 { " − " } else { " + " }
        // a coefficient with three significant digits at least: 0,00038 never rounded to 0
        let coefficient(c) = written-number(c, digits: if c == 0 { 3 } else { calc.max(3, 2 - int(calc.floor(calc.log(calc.abs(c))))) })
        let name = "y = " + coefficient(a) + "x" + if b == 0 { "" } else { sign + coefficient(calc.abs(b)) }
        // named at its right end
        let end = if px(xb) >= px(xa) { xb } else { xa }
        content((px(end) + 0.1, py(a * end + b)), text(fill: rgb("#1f5fa8"), txt(name)), anchor: "west")
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
      let given-step = step != auto
      // round steps: 1, 2, 5 times a power of ten, and 25, 250, 2500…, 0.25 for decimals (as
      // many as counts can need: a city's inhabitants); whole counts from 1 up
      let rounds = (range(0, 10).map(e => (1, 2, 5, 25).map(b => b * calc.pow(10, e))).flatten()
        + if whole { () } else { (0.01, 0.02, 0.05, 0.1, 0.2, 0.25, 0.5) }).sorted()
      let step = if step != auto { step } else if whole {
        rounds.find(s => top / s <= 12)
      } else {
        rounds.find(s => top / s < 10)
      }
      // lying, the numbers side by side: a step whose numbers fit between two marks
      let w = 6.5
      let step = if horizontal and not given-step {
        let fits = rounds.filter(s => s >= step).find(s => {
          let end = calc.ceil(top / s - 1e-9) * s
          s * w / end >= measure(txt(num(end))).width / 1cm + 0.2
        })
        if fits == none { step } else { fits }
      } else { step }
      let ymax = calc.ceil(top / step - 1e-9) * step
      let marks-n = int(calc.round(ymax / step))
      if horizontal {
        // the bars lying: each name at the left of its bar, the graduation under them
        let unit = w / ymax
        // a name longer than 3.2 cm on two lines or more, at the right of its column; each row
        // as high as the highest name, so that a name on two lines never meets the next
        let name(label) = if measure(txt(label)).width / 1cm > 3.2 { box(width: 3.2cm, align(right, txt(label))) } else { txt(label) }
        let row = calc.max(0.75, ..values.map(v => measure(name(v.at(0))).height / 1cm + 0.3))
        let h = row * values.len()
        for k in range(1, marks-n + 1) {
          let x = k * step * unit
          line((x, 0), (x, h), stroke: 0.4pt + _grid)
          line((x, 0), (x, -0.08), stroke: 0.6pt)
          content((x, -0.16), txt(num(k * step)), anchor: "north")
        }
        content((0, -0.16), txt("0"), anchor: "north")
        line((0, 0), (0, h + 0.2), stroke: 0.8pt)
        line((0, 0), (w + 0.45, 0), stroke: 0.8pt, mark: (end: ">", fill: black))
        if axis != none { content((w + 0.45, -0.62), txt(axis), anchor: "north-east") }
        for (i, (label, count)) in values.enumerate() {
          let y = h - row * (i + 0.5)
          if count > 0 { rect((0, y - 0.13), (count * unit, y + 0.13), fill: bar(i), stroke: none) }
          content((-0.16, y), name(label), anchor: "east")
          if shown(label) { content((count * unit + 0.1, y), txt(value(label, count)), anchor: "west") }
        }
      } else {
      let h = 4.0
      let unit = h / ymax
      // each bar's room: its label's width at least, so that long names never overlap; a
      // name longer than 2.4 cm on two lines or more, never widening the whole chart
      let wide = 2.4
      let name(label) = if measure(txt(label)).width / 1cm > wide { box(width: wide * 1cm, align(center, txt(label))) } else { txt(label) }
      // many bars (a probability law of 21 values): each narrower, the chart about 10 cm wide
      // (1.5 cm each, it was 31 cm, drawn tiny on a card)
      let least = if values.len() <= 7 { 1.5 } else { calc.max(0.45, 10.5 / values.len()) }
      let slot = calc.max(least, ..values.map(v => measure(name(v.at(0))).width / 1cm + 0.3))
      // every count written by default, unless they don't fit over their bars (21 bars of a
      // probability law: their values on one another, on the interval's name): none then
      let crowded = written == "all" and given-written == auto and values.any(v => measure(txt(value(v.at(0), v.at(1)))).width / 1cm > slot - 0.1)
      let shown-any = shown
      let shown(label) = if crowded { label in hidden } else { shown-any(label) }
      let w = slot * values.len()
      // the graduation: a tick and a light line at each step, so that a count is read, not guessed
      for k in range(1, marks-n + 1) {
        let y = k * step * unit
        line((0, y), (w, y), stroke: 0.4pt + _grid)
        line((-0.08, y), (0, y), stroke: 0.6pt)
        content((-0.16, y), txt(num(k * step)), anchor: "east")
      }
      content((-0.16, 0), txt("0"), anchor: "east")
      line((0, 0), (w + 0.3, 0), stroke: 0.8pt)
      line((0, 0), (0, h + 0.45), stroke: 0.8pt, mark: (end: ">", fill: black))
      if axis != none { content((0.12, h + 0.45), txt(axis), anchor: "west") }
      // spans behind the bars: from the first bar's left edge to the last's right, shaded, their
      // label at their top; marks: a dashed line through the bar, its label over the chart
      let key(v) = if type(v) == str { v.trim() } else { str(v) }
      let names = values.map(v => key(v.at(0)))
      let at(v) = slot * (names.position(n => n == key(v)) + 0.5)
      for (i, (a, b, label)) in spans.enumerate() {
        let (xa, xb) = (calc.min(at(a), at(b)) - slot / 2, calc.max(at(a), at(b)) + slot / 2)
        rect((xa, 0), (xb, h + 0.15), fill: rgb(250, 215, 150, 110), stroke: none)
        content(((xa + xb) / 2, h + 0.2), txt(label), anchor: "south")
      }
      for (i, (label, count)) in values.enumerate() {
        let x = slot * (i + 0.5)
        if count > 0 { rect((x - calc.min(0.11, slot * 0.25), 0), (x + calc.min(0.11, slot * 0.25), count * unit), fill: bar(i), stroke: none) }
        content((x, -0.14), name(label), anchor: "north")
        if shown(label) { content((x, count * unit + 0.08), txt(value(label, count)), anchor: "south") }
      }
      for (v, label) in marks {
        line((at(v), 0), (at(v), h + 0.15), stroke: (paint: rgb("#b3261e"), thickness: 0.8pt, dash: "dashed"))
        content((at(v), if spans == () { h + 0.2 } else { h + 0.75 }), text(fill: rgb("#b3261e"), txt(label)), anchor: "south")
      }
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
            value(t.label, t.count)
            if degrees and t.label not in hidden { " (" + num(t.angle / 1deg, digits: 1) + "°)" }
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
