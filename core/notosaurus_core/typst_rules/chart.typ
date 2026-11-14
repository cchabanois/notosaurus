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
// "line" some x), none by default: a card asking a count or a measure never shows it;
// degrees: a sector's angle written with its count; axis: the bars' axis title (the
// lesson's: "Effectif"); axes: a line's (x title, y title), their units with them; step:
// the bars' graduation (auto: every unit up to 12, then 2, 5, 10…), a line's (x, y).
// A line only: marks, events at an x ((x, label): a dashed line across, its label under the
// axis); spans, stretches of x ((from, to, label): shaded); second, another measure with
// its own unit on a right axis ((values: ((x, y), …), axis: title)), in another colour;
// kind "box": box plots, each (name, (min, q1, median, q3, max)), on one axis (_box-plots).
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
#let chart(kind: "bars", values: (), written: (), degrees: false, axis: none, axes: (none, none), step: auto,
  marks: (), spans: (), second: none, numbered: true, smooth: false, limits: auto, horizontal: false) = context {
  assert(kind in ("bars", "pie", "semi", "line", "box"), message: "kind is \"bars\", \"pie\", \"semi\", \"line\" or \"box\"")
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
    assert(marks == () and spans == () and second == none and not smooth, message: "marks, spans, second and smooth are a line's only")
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
  let num(x, digits: 3) = written-number(x, digits: digits)
  // A graduation's step: a round one giving at most `most` steps over `span`
  // (never finer than 0,1: values that change little keep a graduation showing it so)
  let nice(span, most) = calc.max(round-step(span, most), 0.1)
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
        if k > 0 { line((x, 0), (x, h), stroke: 0.4pt + _grid) }
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
        line(..path, stroke: (paint: look.paint, thickness: 1.3pt, join: "round", dash: look.dash))
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
          if count > 0 { rect((0, y - 0.13), (count * unit, y + 0.13), fill: luma(55), stroke: none) }
          content((-0.16, y), name(label), anchor: "east")
          if shown(label) { content((count * unit + 0.1, y), txt(num(count)), anchor: "west") }
        }
      } else {
      let h = 4.0
      let unit = h / ymax
      // each bar's room: its label's width at least, so that long names never overlap; a
      // name longer than 2.4 cm on two lines or more, never widening the whole chart
      let wide = 2.4
      let name(label) = if measure(txt(label)).width / 1cm > wide { box(width: wide * 1cm, align(center, txt(label))) } else { txt(label) }
      let slot = calc.max(1.5, ..values.map(v => measure(name(v.at(0))).width / 1cm + 0.3))
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
      for (i, (label, count)) in values.enumerate() {
        let x = slot * (i + 0.5)
        if count > 0 { rect((x - 0.11, 0), (x + 0.11, count * unit), fill: luma(55), stroke: none) }
        content((x, -0.14), name(label), anchor: "north")
        if shown(label) { content((x, count * unit + 0.08), txt(num(count)), anchor: "south") }
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
