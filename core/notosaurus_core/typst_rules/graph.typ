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
  // An asymptote (`asymptote(y: 3)`) given what it can't see from inside the frame: the axes
  // as the AI set them (their position, their ticks: where their numbers are) and the points
  // of the other plots (where its name would lie on a curve)
  let others = args.pos().filter(p => type(p) == dictionary and type(p.at("x", default: none)) == array
    and type(p.at("y", default: none)) == array)
  let seen = (
    xaxis: named.at("xaxis", default: none), yaxis: named.at("yaxis", default: none),
    curves: others.map(p => (p.x, p.y)),
  )
  let pos = args.pos().map(p => if type(p) == dictionary and p.at("id", default: none) == "asymptote" {
    p + (seen: seen)
  } else { p })
  arguments(..pos, ..named)
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
// An asymptote, a limit, a line y = c or x = a: dashed across the whole frame, on both sides
// of the other axis; broken only where it would cross that axis's numbers (their places and
// widths computed as lilaq writes them: the AI's ticks, or lilaq's own from the limits and the
// size), resumed past the axis; its name ("y = 3" by default, the figure's decimal separator)
// at one of its ends, inside the frame, on the side farthest from the curves and the axes
#let _numbers(axis, low, high, size, horizontal) = {
  // the numbers an axis writes: (value, its label), as lilaq locates and formats them
  let ticks = if type(axis) == dictionary { axis.at("ticks", default: auto) } else { auto }
  if ticks == none { return () }
  if type(ticks) == array {
    return ticks.map(t => if type(t) == array and t.len() == 2 { t } else { (t, [#t]) })
      .filter(t => type(t.at(0)) in (int, float))
  }
  let distance = if type(axis) == dictionary { axis.at("tick-distance", default: auto) } else { auto }
  let suggestion = size / (if horizontal { 3.3em } else { 2em }).to-absolute()
  let found = lq.locate-ticks-linear(calc.min(low, high), calc.max(low, high),
    tick-distance: distance, num-ticks-suggestion: suggestion)
  let labels = lq.format-ticks-linear(found.ticks, tick-info: found, exponent: none)
  if type(labels) == dictionary { labels = labels.labels }
  found.ticks.zip(labels)
}
#let _axis-at(axis, low, high) = {
  // where an axis crosses the other one, in its data: 0 unless the AI placed it
  let position = if type(axis) == dictionary { axis.at("position", default: 0) } else { 0 }
  if type(position) in (int, float) { position }
  else if position == left or position == bottom { low }
  else if position == right or position == top { high }
  else { none }
}
#let _render-asymptote(self, transform) = layout(size => {
  let (w, h) = (size.width, size.height)
  let seen = self.at("seen", default: (xaxis: none, yaxis: none, curves: ()))
  let (ox, oy) = transform(0, 0)
  let (ux, uy) = transform(1, 1)
  let (sx, sy) = (ux - ox, uy - oy) // a unit, in the frame
  let (x0, x1) = ((0pt - ox) / sx, (w - ox) / sx)
  let (y0, y1) = ((h - oy) / sy, (0pt - oy) / sy)
  let clear = 0.3em.to-absolute() // the line's ends kept that far from the numbers
  let (tick-in, tick-out, tick-pad) = (1.5pt, 1.5pt, 0.4em.to-absolute()) // the theme's ticks
  // the axes, where each crosses the other (none when off the frame), and the boxes of their
  // numbers (x, y, width, height), as the theme writes them: left of the vertical axis, under
  // the horizontal one, none at 0 nor within 5pt of the frame's edge
  let ya = _axis-at(seen.yaxis, x0, x1)
  let px = if ya != none { transform(ya, 0).at(0) }
  if px != none and (px < -0.5pt or px > w + 0.5pt) { px = none }
  let xa = _axis-at(seen.xaxis, y0, y1)
  let py = if xa != none { transform(0, xa).at(1) }
  if py != none and (py < -0.5pt or py > h + 0.5pt) { py = none }
  let boxes = (y: (), x: ())
  if px != none {
    for (value, name) in _numbers(seen.yaxis, y0, y1, h, false) {
      let c = transform(0, value).at(1)
      if calc.abs(value) < 1e-12 or calc.min(c, h - c) < 5pt { continue }
      let m = measure(name)
      boxes.y.push((px - tick-out - tick-pad - m.width, c - m.height / 2, m.width, m.height))
    }
  }
  if py != none {
    for (value, name) in _numbers(seen.xaxis, x0, x1, w, true) {
      let c = transform(value, 0).at(0)
      if calc.abs(value) < 1e-12 or calc.min(c, w - c) < 5pt { continue }
      let m = measure(name)
      boxes.x.push((c - m.width / 2, py + tick-out + tick-pad, m.width, m.height))
    }
  }
  let horizontal = self.ay != none
  // the line, along its own direction (from 0 to its length), broken where it would cross the
  // other axis's numbers: from before them to past the axis
  let (at, length, across) = if horizontal { (transform(0, self.ay).at(1), w, h) } else { (transform(self.ax, 0).at(0), h, w) }
  let gaps = ()
  if horizontal {
    for (bx, by, bw, bh) in boxes.y {
      if at > by - clear and at < by + bh + clear { gaps.push((bx - clear, px + tick-in + clear)) }
    }
  } else {
    for (bx, by, bw, bh) in boxes.x {
      if at > bx - clear and at < bx + bw + clear { gaps.push((py - tick-in - clear, by + bh + clear)) }
    }
  }
  let pieces = if gaps.len() == 0 { ((0pt, length),) } else {
    let (a, b) = (calc.min(..gaps.map(g => g.at(0))), calc.max(..gaps.map(g => g.at(1))))
    // a piece shorter than a dash or two left out: by a number, it would read as a minus
    ((0pt, a), (b, length)).filter(((s, e)) => e - s > 0.8em.to-absolute())
  }
  if at < -0.5pt or at > across + 0.5pt { return }
  // on an axis (y = 0, x = 0): the axis drawn already, the dashes over it would only blur it
  let own = if horizontal { py } else { px }
  if own != none and calc.abs(at - own) < 0.5pt { pieces = () }
  for (s, e) in pieces {
    let (start, end) = if horizontal { ((s, at), (e, at)) } else { ((at, s), (at, e)) }
    place(line(start: start, end: end, stroke: self.stroke))
  }
  // its name, at an end of it, inside the frame, on the side farthest from what is drawn
  let name = if self.name == auto {
    if horizontal { $y = #_number(self.ay)$ } else { $x = #_number(self.ax)$ }
  } else { self.name }
  if name == none { return }
  let m = measure(name)
  // each end, each side, close to the line, then a little farther (points along the line,
  // a sequence's terms, would touch it)
  let pad = 0.3em.to-absolute()
  let candidates = ()
  for off in (0.3em, 0.8em).map(o => o.to-absolute()) {
    candidates += if horizontal {
      let (r, l) = (w - pad - m.width, pad)
      ((r, at - off - m.height), (r, at + off), (l, at - off - m.height), (l, at + off))
    } else {
      let (t, b) = (pad, h - pad - m.height)
      ((at + off, t), (at - off - m.width, t), (at + off, b), (at - off - m.width, b))
    }
  }
  candidates = candidates.filter(((x, y)) => x >= 0pt and y >= 0pt and x + m.width <= w and y + m.height <= h)
  if candidates.len() == 0 { return }
  // what it stays clear of: the curves (each segment sampled along its length), the axes and
  // their numbers
  let points = ()
  for (xs, ys) in seen.curves {
    let drawn = xs.zip(ys).filter(((x, y)) => type(x) in (int, float) and type(y) in (int, float)
      and x == x and y == y and calc.abs(x) < 1e300 and calc.abs(y) < 1e300).map(((x, y)) => transform(x, y))
    for i in range(drawn.len()) {
      let (a, b) = (drawn.at(i), drawn.at(calc.min(i + 1, drawn.len() - 1)))
      let steps = calc.max(1, calc.min(200, int(calc.max(calc.abs(b.at(0) - a.at(0)), calc.abs(b.at(1) - a.at(1))) / 3pt)))
      for k in range(steps) {
        let t = k / steps
        points.push((a.at(0) + (b.at(0) - a.at(0)) * t, a.at(1) + (b.at(1) - a.at(1)) * t))
      }
    }
  }
  // (the axis it lies on, if it does, being the line itself)
  if py != none and not (horizontal and pieces == ()) { for k in range(101) { points.push((w * k / 100, py)) } }
  if px != none and not (not horizontal and pieces == ()) { for k in range(101) { points.push((px, h * k / 100)) } }
  for (bx, by, bw, bh) in boxes.x + boxes.y {
    for i in range(5) { for j in range(3) { points.push((bx + bw * i / 4, by + bh * j / 2)) } }
  }
  points = points.filter(((x, y)) => x >= -5pt and x <= w + 5pt and y >= -5pt and y <= h + 5pt)
  let apart((x, y)) = {
    let d = 1e6pt
    for (qx, qy) in points {
      let dx = calc.max(x - qx, qx - x - m.width, 0pt)
      let dy = calc.max(y - qy, qy - y - m.height, 0pt)
      d = calc.min(d, calc.max(dx, dy))
    }
    d
  }
  let scored = candidates.map(c => (c, apart(c)))
  let free = scored.filter(((c, d)) => d >= 0.6em.to-absolute())
  let (x, y) = if free.len() > 0 { free.first().at(0) } else { scored.sorted(key: ((c, d)) => d).last().at(0) }
  place(dx: x, dy: y, name)
})
#let asymptote(x: none, y: none, label: auto, stroke: (paint: black, thickness: 0.8pt, dash: "dashed")) = {
  assert((x == none) != (y == none), message: "asymptote: give x (a vertical line) or y (a horizontal one)")
  (
    plot: _render-asymptote, id: "asymptote", ax: x, ay: y, name: label, stroke: stroke,
    xlimits: () => none, ylimits: () => none, datetime: (:), label: none, clip: true, z-index: 3,
  )
}
// ---- What the AI writes, from here (the rule's example: everything above is given)
#let xs = lq.linspace(0.05, 6, num: 300)
#lq.diagram(
  width: 6.7cm, height: 5cm,
  xlim: (-0.5, 6.2), ylim: (-3, 2),
  xlabel: $x$, ylabel: $y$,
  lq.plot(xs, xs.map(calc.ln), mark: none, stroke: black + 1pt),
)
