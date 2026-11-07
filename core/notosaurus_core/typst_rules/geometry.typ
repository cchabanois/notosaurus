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
// written there. Angles placed by their values, never by eye.
#let ctz-draw-unit-circle(angles: (), project: none, r: 3) = {
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
  for (a, label) in angles {
    circle(at(a, r), radius: 0.07, fill: black)
    // on an axis, its name turned a little off it (on the axis, the line ran through it)
    let off = if calc.rem(calc.abs(a), 90) == 0 { 10 } else { 0 }
    content(at(a + off, r + 0.5), label)
  }
}
// ---- What the AI writes, from here (the rule's example: everything above is given)
#ctz-canvas({
  ctz-init()
  ctz-def-points(A: (0, 0), B: (4, 0), C: (1, 3))
  ...
})
