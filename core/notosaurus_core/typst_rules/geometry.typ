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
// ---- What the AI writes, from here (the rule's example: everything above is given)
#ctz-canvas({
  ctz-init()
  ctz-def-points(A: (0, 0), B: (4, 0), C: (1, 3))
  ...
})
