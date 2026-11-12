#set page(width: auto, height: auto, margin: 6pt)
#import "@preview/ctz-euclide:0.3.0": *
#import "@preview/cetz:0.5.2"
// A fraction shown on a shape: a disc, a bar or a rectangle (`rows` rows) cut into `parts`
// equal parts, exactly `coloured` of them filled whole (a disc's from the top, clockwise; a
// bar's or a rectangle's from the left, row by row), every bar or rectangle the same outside:
// the count drawn by the preamble, never a part filled by hand. `caption` written under it. Alone, a figure of its own (no canvas).
#let fraction-shape(kind: "disc", parts: 4, coloured: 0, rows: 1, size: 3, caption: none, colour: rgb("#9fc3e7")) = {
  assert(kind in ("disc", "bar", "rect"), message: "kind is \"disc\", \"bar\" or \"rect\"")
  assert(type(parts) == int and parts >= 1, message: "parts is a whole number of parts")
  assert(type(coloured) == int and 0 <= coloured and coloured <= parts, message: "coloured is between 0 and parts")
  let drawing = cetz.canvas({
    import cetz.draw: *
    if kind == "disc" {
      let r = size / 2
      for i in range(parts) {
        let start = 90deg - i * 360deg / parts
        if parts == 1 {
          circle((0, 0), radius: r, fill: if coloured == 1 { colour } else { white }, stroke: 0.9pt)
        } else {
          arc((0, 0), start: start, delta: -360deg / parts, radius: r, mode: "PIE", anchor: "origin",
            fill: if i < coloured { colour } else { white }, stroke: 0.9pt)
        }
      }
    } else {
      let r = if kind == "bar" { 1 } else { rows }
      assert(calc.rem(parts, r) == 0, message: "a rectangle's parts fill its rows: parts a multiple of rows")
      let cols = int(parts / r)
      // every bar, every rectangle the same outside, however cut: two compared side by side
      // (3/10 and 3/5) are the same whole
      let w = size * 1.6 / cols
      let h = (if kind == "bar" { size / 4 } else { size * 0.8 }) / r
      for i in range(parts) {
        let (row, col) = (calc.floor(i / cols), calc.rem(i, cols))
        rect((col * w, -row * h), ((col + 1) * w, -(row + 1) * h),
          fill: if i < coloured { colour } else { white }, stroke: 0.9pt)
      }
    }
  })
  if caption == none { drawing } else { stack(dir: ttb, spacing: 0.6em, drawing, align(center, caption)) }
}
// Several fraction shapes side by side (an improper fraction over several shapes, two
// fractions compared): each a dictionary of fraction-shape's arguments, all the same size.
#let fraction-shapes(..shapes, gap: 1cm) = stack(dir: ltr, spacing: gap,
  ..shapes.pos().map(s => align(bottom, fraction-shape(..s))))
// Numbers written as the figure's language writes them: its decimal separator, set by
// figures_typst.source from the AI's `#set text(lang: …)` (a point when none is said)
#let decimal-separator = "."
// A number line, everything on it placed from its values: its line from half a step before
// its first tick to half a step after its last, a tick each `step`, each value v at
// (v − first) × scale. numbers: true its whole numbers written under their ticks, false
// none, or the numbers the description writes, `(2.3, 2.4)` (with the language's decimal
// separator) or `((0.75, $3/4$), …)` (a value and its text); points: each point named at
// its value, `(A: -3, B: 3/4)`, its letter above (a point the description names by no letter:
// `(P: (at: 0.75, name: $j$))`, that name written instead); names too close to stand side by
// side (their widths guessed from their letters) raised a row, a short line down to their
// point, only those: names that fit are written as ever.
// `arrow: true` an arrow at its right end. Never a point, a tick or a number placed by hand.
// `log: true`, a logarithmic line: its values (above 0, as the description gives them,
// 2 / 1000 for 2 mm in metres) each at its log10, (log10 v − its first
// decade) × scale; its first and last values left out (the decades around its points and
// numbers) or given as values (1e-8, never the exponent −8); a tick at each power of ten, 10ⁿ
// written every `step` decades (by default as few as keep them apart), or the numbers given
// instead, each on a tick of its own; `scale` a decade's length (by default the line about 12).
// A name's width in letters, guessed (no context inside a canvas): a fraction its wider part,
// an exponent smaller
#let _name-chars(c) = if type(c) == str { c.clusters().len() } else if c.func() == math.frac { calc.max(_name-chars(c.num), _name-chars(c.denom)) } else if c.func() == math.attach { _name-chars(c.base) + 0.6 * ("t", "b").filter(k => c.has(k)).map(k => _name-chars(c.at(k))).sum(default: 0) } else if c.has("text") { c.text.clusters().len() } else if c.has("children") { c.children.map(_name-chars).sum(default: 0) } else if c.has("body") { _name-chars(c.body) } else { 1 }
// Each name's row above its line (0 the first), from the names' places and widths, left to
// right: the lowest row where it clears the names already in it, its line down to its point
// clear of the names below it and its own name clear of the lines going up past it (when a
// row allows it; else the lowest row where it clears the names). The same for a line's
// numbers, rows going down.
#let _name-rows(placed, gap: 0.15) = {
  let apart(a, b) = calc.abs(a.x - b.x) >= (a.w + b.w) / 2 + gap
  let crosses(name, x) = calc.abs(name.x - x) < name.w / 2 + 0.05
  let rows = placed.map(_ => 0)
  let done = ()
  for i in range(placed.len()).sorted(key: i => placed.at(i).x) {
    let p = placed.at(i)
    let free(r) = done.all(j => rows.at(j) != r or apart(placed.at(j), p))
    let clear(r) = done.all(j => (rows.at(j) >= r or not crosses(placed.at(j), p.x)) and (rows.at(j) <= r or not crosses(p, placed.at(j).x)))
    let top = done.fold(0, (m, j) => calc.max(m, rows.at(j))) + 1
    let r = range(top + 1).find(r => free(r) and clear(r))
    rows.at(i) = if r == none { range(top + 1).find(free) } else { r }
    done.push(i)
  }
  rows
}
// A logarithmic line's measure: its first and last decades (around its first and last values
// `given`, if any, and its `values`), a decade's length, `step`
#let _log-measure(given, values, step, scale) = {
  let number(v) = type(v) in (int, float)
  assert(given.len() in (0, 2) and given.all(v => number(v) and v > 0), message: "a logarithmic line's first and last are values above 0 (1e-8, never the exponent -8), or left out")
  let values = given + values
  assert(values.len() > 0 and values.all(v => number(v) and v > 0), message: "a logarithmic line holds values above 0, as the description gives them (2 / 1000), never their logarithm")
  let lg(v) = calc.log(v, base: 10)
  let lo = calc.floor(calc.min(..values.map(lg)) + 1e-9)
  let hi = calc.max(lo + 1, calc.ceil(calc.max(..values.map(lg)) - 1e-9))
  let scale = if scale == auto { calc.min(2, 12 / (hi - lo)) } else { scale }
  assert(number(scale) and scale > 0, message: "scale is a number above 0: a decade's length")
  // 10ⁿ written every `step` decades (1, 2, 3, 5, 10…), at its multiples: about a centimetre and
  // a half apart
  let step = if step == auto { (1, 2, 3, 5, 10, 20, 50, 100).find(k => k * scale >= 1.4) } else { step }
  assert(type(step) == int and step >= 1, message: "a logarithmic line's step is a whole number of decades")
  (lo: lo, hi: hi, scale: scale, step: step)
}
#let ctz-draw-number-line(..bounds, step: auto, scale: auto, numbers: true, points: (:), arrow: false, log: false) = {
  let number(v) = type(v) in (int, float)
  assert(bounds.named().len() == 0, message: "unexpected argument: " + bounds.named().keys().join(", "))
  assert(type(points) == dictionary, message: "points are named by their values: (A: -3, B: 2)")
  // each point: its name, its value, its text
  let named = points.pairs().map(((name, p)) => if type(p) == dictionary and "at" in p and "name" in p { (name, p.at, p.name) } else { (name, p, math.equation(math.italic(name))) })
  for (name, v, _) in named {
    assert(number(v), message: "a point is its letter at its value, a number (A: -3, B: 3/4): never its value written as its name")
  }
  // a number as the language writes it: its decimal separator, its thousands apart from
  // 10 000 on (a narrow space)
  let written(v) = {
    let r = calc.round(v, digits: 6)
    let t = if calc.fract(r) == 0 { str(int(calc.abs(r))) } else { str(calc.abs(r)).replace(".", decimal-separator) }
    let whole = t.split(decimal-separator).first()
    if whole.len() > 4 {
      let n = whole.len()
      t = range(n).map(i => (if i > 0 and calc.rem(n - i, 3) == 0 { "\u{202F}" } else { "" }) + whole.at(i)).join() + t.slice(n)
    }
    if r < 0 [−#t] else [#t]
  }
  let (step, scale) = if log { (step, scale) } else { (if step == auto { 1 } else { step }, if scale == auto { 1 } else { scale }) }
  let given = if type(numbers) == array { numbers.map(w => if type(w) == array { w } else { (w, written(w)) }) } else { () }
  for (v, _) in given { assert(number(v), message: "numbers are values, or (value, text) pairs") }
  let m = if log { _log-measure(bounds.pos(), named.map(p => p.at(1)) + given.map(w => w.at(0)), step, scale) }
  if not log {
    assert(bounds.pos().len() == 2, message: "a number line goes from its first value to its last: ctz-draw-number-line(-5, 5)")
    let (first, last) = bounds.pos()
    assert(number(first) and number(last) and first < last, message: "a number line goes from its first value to a larger last one")
    assert(number(step) and step > 0 and number(scale) and scale > 0, message: "step and scale are numbers above 0")
    for (name, v, _) in named {
      assert(first - step / 2 <= v and v <= last + step / 2, message: "the point " + name + " is outside the line, from " + str(first) + " to " + str(last))
    }
  }
  let x(v) = if log { (calc.log(v, base: 10) - m.lo) * m.scale } else { (v - bounds.pos().first()) * scale }
  // its ticks' values, and those written under them by default (whole numbers; 10ⁿ every
  // `step` decades), then the numbers given
  let ticks = if log { range(m.lo, m.hi + 1).map(n => calc.pow(10.0, n)) } else {
    let first = bounds.pos().first()
    range(int(calc.round((bounds.pos().last() - first) / step)) + 1).map(i => first + i * step)
  }
  let numbered = if numbers != true { () } else if log {
    range(ticks.len()).filter(i => calc.rem-euclid(m.lo + i, m.step) == 0)
  } else { range(ticks.len()).filter(i => calc.abs(calc.fract(calc.round(ticks.at(i), digits: 6))) == 0) }
  let shown = numbered.map(i => (ticks.at(i), if log { $10^#(m.lo + i)$ } else { written(ticks.at(i)) })) + given
  let rows = _name-rows(shown.map(((v, body)) => (x: x(v), w: 0.24 * _name-chars(body))), gap: 0.1)
  // the k-th number shown under its tick, a row lower when too close to stand beside another
  let number-at(k) = {
    let (v, body) = shown.at(k)
    let y = -0.25 - rows.at(k) * 0.5
    if rows.at(k) > 0 { cetz.draw.line((x(v), -0.17), (x(v), y + 0.05), stroke: 0.4pt + luma(110)) }
    cetz.draw.content((x(v), y), body, anchor: "north")
  }
  let (a, b) = if log { (x(ticks.first()), x(ticks.last())) } else { (x(bounds.pos().first()), x(bounds.pos().last())) }
  let reach = if log { calc.min(0.5, (b - a) / 10) } else { step * scale / 2 }
  cetz.draw.line((a - reach, 0), (b + reach, 0), mark: if arrow { (end: "stealth", fill: black) } else { none })
  for (i, v) in ticks.enumerate() {
    cetz.draw.line((x(v), -0.15), (x(v), 0.15))
    if i in numbered { number-at(numbered.position(j => j == i)) }
  }
  for k in range(numbered.len(), shown.len()) {
    // a number given on a logarithmic line: on a tick of its own
    if log { cetz.draw.line((x(shown.at(k).at(0)), -0.15), (x(shown.at(k).at(0)), 0.15)) }
    number-at(k)
  }
  // where it ends, kept for an interval drawn on it: its measure (a logarithmic line's
  // values placed again), the bottom of its numbers (a zone's name written under them)
  let low = -0.25 - rows.fold(0, calc.max) * 0.5 - 0.5
  cetz.draw.set-ctx(ctx => {
    ctx.shared-state.insert("number-line", (log: if log { (lo: m.lo, hi: m.hi, scale: m.scale, reach: reach) }, low: low, zones: ()))
    ctx
  })
  let rows = _name-rows(named.map(((_, v, body)) => (x: x(v), w: 0.24 * _name-chars(body))))
  for ((name, v, body), row) in named.zip(rows) {
    cetz.draw.circle((x(v), 0), radius: 0.06, fill: black)
    if row == 0 {
      cetz.draw.content((x(v), 0.3), body, anchor: "south")
    } else {
      // raised a row, a thin line down to its point
      let y = 0.3 + row * 0.55
      cetz.draw.line((x(v), 0.12), (x(v), y - 0.05), stroke: 0.4pt + luma(110))
      cetz.draw.content((x(v), y), body, anchor: "south")
    }
  }
}
// An interval on a number line: its stretch thick and coloured, a bracket at each bound
// turned as school writes it (closed: towards the inside, `[` on the left; open: away from
// it; `closed: none` no bracket), an infinite end (`none`) going on to the line's end with no
// bracket. Its bounds are the description's values, placed as the line's ticks:
// (value − first) × scale; on a logarithmic line, `log: true` and its bounds alone, placed
// where that line put them. `label`, a stretch's name (a zone of a scale): written under its
// middle, below the line's numbers, a row lower when it would touch another zone's name;
// zones side by side coloured apart (each the next colour, unless given).
#let _interval(xa, xb, a, b, closed, color) = {
  let (h, w) = (0.3, 0.15)
  let stroke = (paint: color, thickness: 1.5pt)
  cetz.draw.line((xa, 0), (xb, 0), stroke: (paint: color, thickness: 3pt))
  // a bracket at x, its two short strokes towards `side` (+1 right, −1 left)
  let bracket(x, side) = cetz.draw.line((x + side * w, h), (x, h), (x, -h), (x + side * w, -h), stroke: stroke)
  if closed != none {
    if a != none { bracket(xa, if closed.at(0) { 1 } else { -1 }) }
    if b != none { bracket(xb, if closed.at(1) { -1 } else { 1 }) }
  }
}
#let _zone-colours = (rgb("#0072d6"), rgb("#e07b00"), rgb("#2e9e44"), rgb("#8a4fd0"), rgb("#c8323c"), rgb("#00949a"))
#let ctz-draw-interval(a, b, closed: (true, true), first: 0, last: none, scale: 1, log: false, label: none, color: auto) = {
  assert(closed == none or (type(closed) == array and closed.len() == 2), message: "closed is (true, false), each bound's, or none (no bracket)")
  let x(v) = (v - first) * scale
  let end = if last == none { calc.max(..(a, b).filter(v => v != none)) + 1 } else { last }
  if not log and label == none {
    let (xa, xb) = (if a == none { x(first) - 0.5 * scale } else { x(a) }, if b == none { x(end) + 0.5 * scale } else { x(b) })
    return _interval(xa, xb, a, b, closed, if color == auto { _zone-colours.first() } else { color })
  }
  cetz.draw.get-ctx(ctx => {
    let line = ctx.shared-state.at("number-line", default: none)
    let (xa, xb) = if log {
      assert(line != none and line.log != none, message: "an interval on a logarithmic line is drawn after its line, ctz-draw-number-line(log: true, …)")
      assert((a, b).all(v => v == none or (type(v) in (int, float) and v > 0)), message: "a logarithmic line's bounds are values above 0, or none")
      let m = line.log
      let x(v) = (calc.log(v, base: 10) - m.lo) * m.scale
      // an infinite end to the line's, short of its arrow
      (if a == none { -m.reach } else { x(a) }, if b == none { (m.hi - m.lo) * m.scale + 0.6 * m.reach } else { x(b) })
    } else { (if a == none { x(first) - 0.5 * scale } else { x(a) }, if b == none { x(end) + 0.5 * scale } else { x(b) }) }
    let zones = if line == none { () } else { line.zones }
    let color = if color != auto { color } else if label == none { _zone-colours.first() } else { _zone-colours.at(calc.rem(zones.len(), _zone-colours.len())) }
    _interval(xa, xb, a, b, closed, color)
    if label != none {
      let (cx, w) = ((xa + xb) / 2, 0.24 * _name-chars(label))
      // the first row where it clears the names of the zones drawn before it
      let row = range(zones.len() + 1).find(r => zones.all(z => z.row != r or calc.abs(z.x - cx) >= (z.w + w) / 2 + 0.2))
      let here = (x: cx, w: w, row: row)
      let low = (if line == none { -0.75 } else { line.low }) - row * 0.5
      cetz.draw.content((here.x, low), text(fill: color.darken(35%), label), anchor: "north")
      if line != none {
        cetz.draw.set-ctx(ctx => {
          ctx.shared-state.number-line.zones.push(here)
          ctx
        })
      }
    }
  })
}
// The trigonometric circle: its axes through O, the circle of radius 1 (drawn `r` long),
// a point at each angle given in degrees, named outside the circle along its radius; an
// angle `project`ed: its radius drawn, its cosine and sine dotted down to the axes and
// written there; `join: true`, its points joined in their order, the polygon closed (a
// regular polygon inscribed: the n-th roots of unity). Angles placed by their values, never
// by eye.
#let ctz-draw-unit-circle(angles: (), project: none, join: false, r: 3) = {
  import cetz.draw: *
  // one angle written without its trailing comma, ((60, $M$)): Typst's pair, not a list of one
  let angles = if angles.len() > 0 and type(angles.at(0)) != array { (angles,) } else { angles }
  let at(a, d) = (d * calc.cos(a * 1deg), d * calc.sin(a * 1deg))
  line((-r - 0.6, 0), (r + 0.8, 0), mark: (end: "stealth", fill: black))
  line((0, -r - 0.6), (0, r + 0.8), mark: (end: "stealth", fill: black))
  circle((0, 0), radius: r)
  content((-0.25, -0.3), $O$)
  if project != none {
    let (a, cos-label, sin-label) = project
    let p = at(a, r)
    line((0, 0), p)
    line(p, (p.at(0), 0), stroke: (dash: "dotted"))
    line(p, (0, p.at(1)), stroke: (dash: "dotted"))
    circle((p.at(0), 0), radius: 0.06, fill: black)
    circle((0, p.at(1)), radius: 0.06, fill: black)
    content((p.at(0), if p.at(1) >= 0 { -0.25 } else { 0.25 }), cos-label, anchor: if p.at(1) >= 0 { "north" } else { "south" })
    content((if p.at(0) >= 0 { -0.25 } else { 0.25 }, p.at(1)), sin-label, anchor: if p.at(0) >= 0 { "east" } else { "west" })
  }
  if join and angles.len() > 1 {
    line(..angles.map(((a, _)) => at(a, r)), close: angles.len() > 2)
  }
  for (a, label) in angles {
    circle(at(a, r), radius: 0.07, fill: black)
    // on an axis, its name turned a little off it (on the axis, the line ran through it)
    let off = if calc.rem(calc.abs(a), 90) == 0 { 10 } else { 0 }
    content(at(a + off, r + 0.5), label)
  }
}
// A coordinate frame's axes graduated and numbered at the step's multiples only (ctz-euclide
// counts its steps from the axis's start: from −1.5, "−1.5, −0.5, 0.5", numbers between the
// units, on the points and the circle), each number a little smaller, clear of its axis.
#let ctz-axes-drawn = ctz-draw-axes
#let ctz-draw-axes(xmin: -5, xmax: 5, ymin: -5, ymax: 5, xstep: 1, ystep: 1, stroke: black + 1pt, tick-size: 0.1, ticks: true, labels: true, x-label: $x$, y-label: $y$, origin-label: $O$, arrow: true) = {
  let (line, content) = (cetz.draw.line, cetz.draw.content)
  ctz-axes-drawn(xmin: xmin, xmax: xmax, ymin: ymin, ymax: ymax, stroke: stroke, ticks: false, labels: false, arrow: arrow)
  let multiples(low, high, step) = range(int(calc.ceil(low / step - 1e-9)), int(calc.floor(high / step + 1e-9)) + 1).map(i => i * step).filter(v => calc.abs(v) > 1e-9 and v < high - step / 4)
  let written(v) = if calc.fract(v) == 0 { if v < 0 [−#str(int(-v))] else [#str(int(v))] } else { str(v) }
  for x in multiples(xmin, xmax, xstep) {
    if ticks { line((x, -tick-size), (x, tick-size), stroke: stroke) }
    if labels { content((x, -tick-size - 0.08), text(size: 8pt, written(x)), anchor: "north") }
  }
  for y in multiples(ymin, ymax, ystep) {
    if ticks { line((-tick-size, y), (tick-size, y), stroke: stroke) }
    if labels { content((-tick-size - 0.08, y), text(size: 8pt, written(y)), anchor: "east") }
  }
  if labels {
    content((xmax + 0.3, 0), x-label)
    content((0, ymax + 0.3), y-label)
    if origin-label != none { content((-0.3, -0.3), origin-label) }
  }
}
// A length written on its segment, never on its line: beside its middle, on the side away
// from the point `away` (the figure's other vertex), the text's near edge clear of the line
// (anchored by the side it faces). `level: 2` (a segment holding another one already
// labelled, [AB] around [AM]): a dimension line beside the segment, its two arrows at its
// ends, the length beside that line's middle.
// A content's text, to size a label without measuring it (no context inside a canvas)
#let _plain(c) = if type(c) == str { c } else if c.has("text") { c.text } else if c.has("children") { c.children.map(_plain).join() } else if c.has("body") { _plain(c.body) } else { " " }
#let ctz-draw-length(a, b, label, away: none, level: 1, pos: 0.5) = cetz.draw.get-ctx(ctx => {
  import cetz.draw: *
  let at(n) = cetz.coordinate.resolve(ctx, "ctz:" + n).at(1)
  let (pa, pb) = (at(a), at(b))
  let (dx, dy) = (pb.at(0) - pa.at(0), pb.at(1) - pa.at(1))
  let len = calc.sqrt(dx * dx + dy * dy)
  if len < 0.001 { return }
  let (nx, ny) = (-dy / len, dx / len)
  if away != none {
    let pc = at(away)
    let (mx, my) = ((pa.at(0) + pb.at(0)) / 2, (pa.at(1) + pb.at(1)) / 2)
    if (pc.at(0) - mx) * nx + (pc.at(1) - my) * ny > 0 { (nx, ny) = (-nx, -ny) }
  }
  let anchor = {
    let h = if nx > 0.38 { "west" } else if nx < -0.38 { "east" } else { none }
    let v = if ny > 0.38 { "south" } else if ny < -0.38 { "north" } else { none }
    if h == none { v } else if v == none { h } else { v + "-" + h }
  }
  // a label's depth across its line (its box seen along the normal), in the canvas's cm:
  // a dimension line goes past the labels of the segments it holds (as deep as its own)
  let depth = calc.abs(nx) * 0.25 * _plain(label).clusters().len() + calc.abs(ny) * 0.45
  let off = if level > 1 { 0.15 + (level - 1) * (depth + 0.3) } else { 0.15 }
  let shift(p, d) = (p.at(0) + nx * d, p.at(1) + ny * d)
  if level > 1 {
    let (qa, qb) = (shift(pa, off), shift(pb, off))
    line(shift(pa, 0.08), shift(pa, off + 0.12), stroke: 0.4pt)
    line(shift(pb, 0.08), shift(pb, off + 0.12), stroke: 0.4pt)
    line(qa, qb, stroke: 0.5pt, mark: (start: "straight", end: "straight", scale: 0.6))
  }
  let mid = (pa.at(0) + pos * dx, pa.at(1) + pos * dy)
  content(shift(mid, off + if level > 1 { 0.1 } else { 0 }), label, anchor: anchor)
})
// A translation's image of `point` when the description gives no vector, placed by the
// preamble, never by eye: the vector in the direction furthest from every side of `figure`
// (its vertices, in order: the arrow runs along none), never into the figure nor into its
// image at `point` (the arrow crosses neither), the rightmost of the nearly as good; as long
// as the figure is wide that way plus `gap`, so that the image stands clear of it. Then the
// figure's other points by ctz-def-translate((point, name)), as for a given vector.
#let _translation-vector(pts, p, k, gap) = {
  let angle(v) = calc.atan2(v.at(0), v.at(1)) / 1deg
  let n = pts.len()
  let side(i) = { let (a, b) = (pts.at(i), pts.at(calc.rem(i + 1, n))); angle((b.at(0) - a.at(0), b.at(1) - a.at(1))) }
  let sides = range(if n == 2 { 1 } else { n }).map(side)
  // how far a direction is from a side's line (0 to 90 degrees)
  let off(t, s) = { let d = calc.rem-euclid(t - s, 180); calc.min(d, 180 - d) }
  // the figure's angle at its vertex `k`, 10° wider: no arrow into it
  let inside(t) = if k == none or n < 3 { false } else {
    let (prev, next) = (pts.at(calc.rem-euclid(k - 1, n)), pts.at(calc.rem(k + 1, n)))
    let (a1, a2) = (angle((prev.at(0) - p.at(0), prev.at(1) - p.at(1))), angle((next.at(0) - p.at(0), next.at(1) - p.at(1))))
    let span = calc.rem-euclid(a2 - a1, 360)
    let (from, width) = if span > 180 { (a2, 360 - span) } else { (a1, span) }
    let d = calc.rem-euclid(t - from, 360)
    d < width + 10 or d > 350
  }
  // the directions that leave both figures clear, each with how far it is from every side
  let ok = range(24).map(i => i * 15).filter(t => not inside(t) and not inside(t + 180))
  assert(ok.len() > 0, message: "no direction leaves the figure clear")
  let scored = ok.map(t => (t: t, score: calc.min(..sides.map(s => off(t, s))), right: calc.cos(t * 1deg)))
  // among those nearly as far from the sides as the best, the rightmost (a card is wide)
  let top = calc.max(..scored.map(c => c.score))
  let best = scored.filter(c => c.score >= top - 10).sorted(key: c => -c.right).first()
  let u = (calc.cos(best.t * 1deg), calc.sin(best.t * 1deg))
  let along = pts.map(q => q.at(0) * u.at(0) + q.at(1) * u.at(1))
  let length = calc.max(..along) - calc.min(..along) + gap
  (length * u.at(0), length * u.at(1))
}
#let ctz-def-translation-image(name, point, figure, gap: 1) = {
  assert(type(figure) == array and figure.len() >= 2, message: "the figure is its vertices' names, in order: (\"A\", \"B\", \"C\")")
  (ctx => {
    let at(n) = { let q = _resolve-point(ctx, n); (q.at(0), q.at(1)) }
    let p = at(point)
    let (dx, dy) = _translation-vector(figure.map(at), p, figure.position(f => f == point), gap)
    let points = _get-points(ctx)
    points.insert(name, (p.at(0) + dx, p.at(1) + dy))
    (ctx: _set-points(ctx, points))
  },)
}
// A rotation's direction: an arc around its centre `o` from the direction of `a` to that of
// its image `b`, the way the rotation turns (anticlockwise, `clockwise: true` the other
// way), its arrow at the image's end; `label` (its angle, [90°]) written at its middle,
// outside it. Computed from the points, never an arc's angles or arrow given by hand.
#let ctz-draw-rotation-arc(a, o, b, label: none, radius: 0.9, clockwise: false) = cetz.draw.get-ctx(ctx => {
  let at(n) = cetz.coordinate.resolve(ctx, "ctz:" + n).at(1)
  let (pa, po, pb) = (at(a), at(o), at(b))
  let angle(p) = calc.atan2(p.at(0) - po.at(0), p.at(1) - po.at(1)) / 1deg
  let (from, to) = (angle(pa), angle(pb))
  let delta = if clockwise { -calc.rem-euclid(from - to, 360) } else { calc.rem-euclid(to - from, 360) }
  assert(calc.abs(delta) > 0.5, message: "a rotation's arc goes from a point to its image, apart from it")
  cetz.draw.arc(po, start: from * 1deg, delta: delta * 1deg, radius: radius, anchor: "origin",
    stroke: 0.8pt, mark: (end: "stealth", fill: black, scale: 0.8))
  if label != none {
    let mid = (from + delta / 2) * 1deg
    cetz.draw.content((po.at(0) + (radius + 0.4) * calc.cos(mid), po.at(1) + (radius + 0.4) * calc.sin(mid)), label)
  }
})
// A vector: its arrow from its origin to its end, its head at the end, its name beside it
// toward its head (`pos` of the way: its middle often holds a point, a projection), away from
// the figure's point `away`, as a length is written; never a plain segment.
#let ctz-draw-vector(a, b, label: none, away: none, stroke: 1pt, pos: 0.75) = {
  cetz.draw.get-ctx(ctx => {
    let at(n) = cetz.coordinate.resolve(ctx, "ctz:" + n).at(1)
    cetz.draw.line(at(a), at(b), stroke: stroke, mark: (end: "stealth", fill: black, scale: 1.2))
  })
  if label != none { ctz-draw-length(a, b, label, away: away, pos: pos) }
}
// A whole line through two of its points, past each a little: `add` (a share of the two
// points' distance, as ctz-euclide takes it) kept to 15 % of the figure's size at most (the
// box of its named points), never less than 0.3: a line belongs to its figure, as long as it
// is; carried farther (two points far apart, an `add` of half their distance), the figure
// around it shrank on the card. `add: (0, …)` still a half-line from its first point.
#let _ctz-line-add = ctz-draw-line-add
#let ctz-draw-line-add(a, b, add: (0.2, 0.2), ..opts) = cetz.draw.get-ctx(ctx => {
  let at(n) = cetz.coordinate.resolve(ctx, "ctz:" + n).at(1)
  let (pa, pb) = (at(a), at(b))
  let d = calc.sqrt(calc.pow(pb.at(0) - pa.at(0), 2) + calc.pow(pb.at(1) - pa.at(1), 2))
  let pts = _get-points(ctx).values()
  let xs = pts.map(q => q.at(0))
  let ys = pts.map(q => q.at(1))
  let size = calc.max(calc.max(..xs) - calc.min(..xs), calc.max(..ys) - calc.min(..ys))
  let most = calc.max(0.3, 0.15 * size)
  let (before, after) = if type(add) == array { add } else { (add, add) }
  let kept(k) = if d < 1e-9 { k } else { calc.min(k, most / d) }
  _ctz-line-add(a, b, add: (kept(before), kept(after)), ..opts)
})
// ---- What the AI writes, from here (the rule's example: everything above is given)
#ctz-canvas({
  ctz-init()
  ctz-def-points(A: (0, 0), B: (4, 0), C: (1, 3))
  ...
})
