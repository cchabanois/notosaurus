#set page(width: auto, height: auto, margin: 6pt)
#import "@preview/ctz-euclide:0.3.0": *
#import "@preview/cetz:0.5.2"
// A number line: its line from half a step before its first tick to half a step after its
// last, a tick each `step` at (value − first) × scale, its whole numbers written under them
// (`numbers: false`: none, the description's own written by hand); `arrow: true` an arrow
// at its right end.
#let ctz-draw-number-line(first, last, step: 1, scale: 1, numbers: true, arrow: false) = {
  let x(v) = (v - first) * scale
  cetz.draw.line((x(first) - step * scale / 2, 0), (x(last) + step * scale / 2, 0), mark: if arrow { (end: "stealth", fill: black) } else { none })
  let n = int(calc.round((last - first) / step))
  for i in range(n + 1) {
    let v = first + i * step
    cetz.draw.line((x(v), -0.15), (x(v), 0.15))
    if numbers and calc.fract(v) == 0 {
      cetz.draw.content((x(v), -0.45), if v < 0 [−#str(int(-v))] else [#str(int(v))])
    }
  }
}
// An interval on a number line: its stretch thick and coloured, a bracket at each bound
// turned as school writes it (closed: towards the inside, `[` on the left; open: away from
// it), an infinite end (`none`) going on to the line's end with no bracket. Its bounds are
// the description's values, placed as the line's ticks: (value − first) × scale.
#let ctz-draw-interval(a, b, closed: (true, true), first: 0, last: none, scale: 1, color: rgb("#0072d6")) = {
  let x(v) = (v - first) * scale
  let end = if last == none { calc.max(..(a, b).filter(v => v != none)) + 1 } else { last }
  let (xa, xb) = (if a == none { x(first) - 0.5 * scale } else { x(a) }, if b == none { x(end) + 0.5 * scale } else { x(b) })
  let (h, w) = (0.3, 0.15)
  let stroke = (paint: color, thickness: 1.5pt)
  cetz.draw.line((xa, 0), (xb, 0), stroke: (paint: color, thickness: 3pt))
  // a bracket at x, its two short strokes towards `side` (+1 right, −1 left)
  let bracket(x, side) = cetz.draw.line((x + side * w, h), (x, h), (x, -h), (x + side * w, -h), stroke: stroke)
  if a != none { bracket(xa, if closed.at(0) { 1 } else { -1 }) }
  if b != none { bracket(xb, if closed.at(1) { -1 } else { 1 }) }
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
#let ctz-draw-length(a, b, label, away: none, level: 1) = cetz.draw.get-ctx(ctx => {
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
  let mid = ((pa.at(0) + pb.at(0)) / 2, (pa.at(1) + pb.at(1)) / 2)
  content(shift(mid, off + if level > 1 { 0.1 } else { 0 }), label, anchor: anchor)
})
// ---- What the AI writes, from here (the rule's example: everything above is given)
#ctz-canvas({
  ctz-init()
  ctz-def-points(A: (0, 0), B: (4, 0), C: (1, 3))
  ...
})
