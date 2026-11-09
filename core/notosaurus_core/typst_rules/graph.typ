#set page(width: auto, height: auto, margin: 6pt)
#import "@preview/lilaq:0.6.0" as lq
#import "@preview/tiptoe:0.4.0"
#show: lq.theme.schoolbook
// An axis never written with a factor of its own: a "× 10³" lilaq puts at the axis's end lay
// on the axis's name; its ticks written in full instead ("2 000"), as school writes them
#show: lq.set-diagram(xaxis: (exponent: none), yaxis: (exponent: none))
// The x axis's name past the arrow, a little apart and level with the axis (the theme set it
// below the axis's end, on the row of the tick numbers: the last one, "0,25", touched "I (A)")
#show: lq.show_(lq.label.with(kind: "x"), it => place(left + horizon, dx: 100% + .8em, dy: -.15em, it))
// Numbers on the axes written as the figure's language writes them: its decimal separator,
// set by figures_typst.source from the AI's `#set text(lang: …)` (a point when none is said)
#let decimal-separator = "."
#import "@preview/zero:0.6.1"
#zero.set-num(decimal-separator: decimal-separator)
// Ticks named by the AI (`xaxis: (ticks: ((1, $a$), (calc.pow(2, 1/3), $alpha$)))`) whose
// names would touch, their values close ("a" against "α", "u₂" against "u₃"): each name that
// would touch the one before goes on a second row, below it (an x axis) or left of it (a y
// axis). Computed from the limits, the size and the names' own widths, never placed by eye:
// the AI's `lq.diagram(…)` drawn by `diagram-apart(…)` (figures_typst.source).
#let staggered(ticks, low, high, size, horizontal) = {
  if type(ticks) != array or ticks.any(t => type(t) != array or t.len() != 2) { return ticks }
  if ticks.any(t => type(t.at(0)) not in (int, float)) { return ticks }
  let gap = 0.8em.to-absolute() // about a letter apart, at least
  let at(v) = (v - low) / (high - low) * size
  let extent(name) = { let m = measure(name); if horizontal { m.width } else { m.height } }
  let ends = (-1e9pt, -1e9pt) // where each row's last name ends
  let out = ()
  for (value, name) in ticks.sorted(key: t => t.at(0)) {
    let (start, end) = (at(value) - extent(name) / 2, at(value) + extent(name) / 2)
    let row = if start >= ends.at(0) + gap { 0 } else if start >= ends.at(1) + gap { 1 } else { 0 }
    ends.at(row) = end
    let moved = if row == 0 { name } else if horizontal {
      box(inset: (top: measure(name).height + 0.3em), name)
    } else {
      box(inset: (right: measure(name).width + 0.5em), name)
    }
    out.push((value, moved))
  }
  out
}
#let apart(args) = {
  let named = args.named()
  for (key, lim, size, horizontal) in (("xaxis", "xlim", "width", true), ("yaxis", "ylim", "height", false)) {
    let axis = named.at(key, default: none)
    let limits = named.at(lim, default: none)
    if type(axis) != dictionary or "ticks" not in axis or type(limits) != array or limits.len() != 2 { continue }
    if limits.any(v => type(v) not in (int, float)) { continue }
    let span = named.at(size, default: if horizontal { 6cm } else { 4cm })
    if type(span) != length { continue }
    axis.ticks = staggered(axis.ticks, limits.at(0), limits.at(1), span.to-absolute(), horizontal)
    named.insert(key, axis)
  }
  arguments(..args.pos(), ..named)
}
#let diagram-apart(..args) = context lq.diagram(..apart(args))
// A surface filled (an integral, the area under a curve or between two, a probability under a
// density): its edge computed from the functions between the bounds, never drawn by hand; the
// x axis below it, or a second curve's function (`below`). Its name at the surface's centre
// (the centroid of its slices), inside it, never on a curve; on a ground of its own, an axis
// or its numbers crossing that centre (a surface on both sides of 0) never drawn over it
#let _slices(f, a, b, below) = {
  let xs = lq.linspace(a, b, num: 200)
  (xs, xs.map(f), if below == none { xs.map(x => 0) } else { xs.map(below) })
}
#let area(f, a, b, below: none, fill: rgb(200, 215, 240)) = {
  let (xs, top, bottom) = _slices(f, a, b, below)
  lq.fill-between(xs, top, y2: bottom, fill: fill)
}
#let area-name(f, a, b, name, below: none) = {
  let (xs, top, bottom) = _slices(f, a, b, below)
  let heights = top.zip(bottom).map(((t, u)) => calc.abs(t - u))
  let total = calc.max(heights.sum(), 1e-9)
  let x = xs.zip(heights).map(((x, h)) => x * h).sum() / total
  let y = top.zip(bottom, heights).map(((t, u, h)) => (t + u) / 2 * h).sum() / total
  lq.place(x, y, box(fill: white, inset: 0.15em, radius: 2pt, name), align: center + horizon)
}
// Where two curves meet (two lines, a parabola and a line): computed, never by eye: each
// change of sign of f − g between `from` and `to`, refined by bisection; a dot there, seen
// at any size; its coordinates written when `label` is `auto` ("(1 ; 1)": the figure's
// decimal separator, " ; " between them where the decimal separator is a comma), or the
// label given, or nothing (`none`); `lines: true` the dotted lines down to the axes
#let _number(v) = {
  let r = calc.round(v, digits: 2)
  let s = if calc.abs(r - calc.round(r)) < 1e-9 { str(int(calc.round(r))) } else { str(r) }
  s.replace(".", decimal-separator).replace("-", "−")
}
#let _meet-points(f, g, from, to) = {
  let h(x) = f(x) - g(x)
  let n = 400
  let xs = range(n + 1).map(i => from + (to - from) * i / n)
  let roots = ()
  for i in range(n) {
    let (a, b) = (xs.at(i), xs.at(i + 1))
    let (ha, hb) = (h(a), h(b))
    if ha == 0 { roots.push(a); continue }
    if ha * hb < 0 {
      for _ in range(60) {
        let m = (a + b) / 2
        if h(a) * h(m) <= 0 { b = m } else { a = m }
      }
      roots.push((a + b) / 2)
    }
  }
  if h(to) == 0 { roots.push(to) }
  roots.map(x => (x, f(x)))
}
#let meet(f, g, from, to, label: none, lines: false, side: right) = {
  let sep = if decimal-separator == "," { " ; " } else { ", " }
  let parts = ()
  for (x, y) in _meet-points(f, g, from, to) {
    if lines {
      parts.push(lq.line((x, 0), (x, y), stroke: (dash: "dotted", paint: luma(90))))
      parts.push(lq.line((0, y), (x, y), stroke: (dash: "dotted", paint: luma(90))))
    }
    parts.push(lq.place(x, y, circle(radius: 2.2pt, fill: black), align: center + horizon))
    let text = if label == auto { [(#_number(x)#sep#_number(y))] } else { label }
    if text != none {
      parts.push(lq.place(x, y, pad(left: 0.45em, right: 0.45em, bottom: 0.35em, text),
        align: bottom + if side == right { left } else { right }))
    }
  }
  // one element of the diagram (its children are dictionaries: several would merge into
  // the last), drawing each of its parts
  (
    plot: (self, transform) => { for p in parts { (p.plot)(p, transform) } },
    id: "meet", xlimits: () => none, ylimits: () => none, datetime: (:), label: none,
    clip: true, z-index: 22,
  )
}
// A curve known by its points (a table of variations, "passing through" points, no formula):
// the function through them, computed, never a polynomial the AI solves for by hand (one
// drawing in six missed a point it marked, two came flat into their ends). Monotone cubic
// interpolation (Fritsch–Carlson): through each point exactly, rising or falling between two
// of them without a bump of its own, level at a minimum or a maximum, at its ends sloping as
// it goes (never flat there). points: ((x, y), …), two at least, their x all different.
#let through(points) = {
  if type(points) != array or points.len() < 2 or not points.all(p => type(p) == array and p.len() == 2 and p.all(v => type(v) in (int, float))) {
    panic("through: the points ((x, y), …), two at least, numbers, not " + repr(points))
  }
  let ps = points.sorted(key: p => p.at(0))
  let n = ps.len()
  let (xs, ys) = (ps.map(p => p.at(0)), ps.map(p => p.at(1)))
  let h = range(n - 1).map(k => xs.at(k + 1) - xs.at(k))
  if h.any(v => v == 0) { panic("through: two points with the same x: " + repr(points)) }
  let d = range(n - 1).map(k => (ys.at(k + 1) - ys.at(k)) / h.at(k))
  let sign(v) = if v > 0 { 1 } else if v < 0 { -1 } else { 0 }
  // an end's slope: three points' estimate, kept on its side and not too steep
  let end(h0, h1, d0, d1) = {
    let m = ((2 * h0 + h1) * d0 - h0 * d1) / (h0 + h1)
    if sign(m) != sign(d0) { 0 } else if sign(d0) != sign(d1) and calc.abs(m) > 3 * calc.abs(d0) { 3 * d0 } else { m }
  }
  let m = if n == 2 { (d.at(0), d.at(0)) } else {
    let inner = range(1, n - 1).map(k => {
      let (d0, d1, h0, h1) = (d.at(k - 1), d.at(k), h.at(k - 1), h.at(k))
      // a turn (or a flat stretch): level there; else a weighted harmonic mean, no overshoot
      if d0 * d1 <= 0 { 0 } else { 3 * (h0 + h1) / ((2 * h1 + h0) / d0 + (h1 + 2 * h0) / d1) }
    })
    (end(h.at(0), h.at(1), d.at(0), d.at(1)),) + inner + (end(h.at(n - 2), h.at(n - 3), d.at(n - 2), d.at(n - 3)),)
  }
  x => {
    let k = calc.min(calc.max(xs.filter(v => v <= x).len() - 1, 0), n - 2)
    let t = (x - xs.at(k)) / h.at(k)
    let (t2, t3) = (t * t, t * t * t)
    (2 * t3 - 3 * t2 + 1) * ys.at(k) + (t3 - 2 * t2 + t) * h.at(k) * m.at(k) + (-2 * t3 + 3 * t2) * ys.at(k + 1) + (t3 - t2) * h.at(k) * m.at(k + 1)
  }
}
// ---- What the AI writes, from here (the rule's example: everything above is given)
#let xs = lq.linspace(0.05, 6, num: 300)
#lq.diagram(
  width: 6.7cm, height: 5cm,
  xlim: (-0.5, 6.2), ylim: (-3, 2),
  xlabel: $x$, ylabel: $y$,
  lq.plot(xs, xs.map(calc.ln), mark: none, stroke: black + 1pt),
)
