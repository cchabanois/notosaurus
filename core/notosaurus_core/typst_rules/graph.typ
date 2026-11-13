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
#import "common.typ": *
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
  // A plain number ("2") that would touch a value named otherwise ("u₂" at 1.93, "α"): not
  // written (its tick stays), the named value being what the figure is about
  let flat(c) = if type(c) in (str, int, float) { str(c) } else if type(c) != content { "?" } else if c.has("text") { c.text } else if c.has("body") { flat(c.body) } else if c.has("children") { c.children.map(flat).join(default: "") } else if c.func() == [ ].func() { "" } else { "?" }
  let plain(name) = flat(name).trim().match(regex("^[−-]?[0-9][0-9.,\u{202F} ]*$")) != none
  let span(value, name) = (at(value) - extent(name) / 2, at(value) + extent(name) / 2)
  let touch(a, b) = a.at(0) < b.at(1) + gap and b.at(0) < a.at(1) + gap
  let others = ticks.filter(((v, n)) => not plain(n))
  let ticks = ticks.map(((v, n)) => if plain(n) and others.any(((w, m)) => touch(span(v, n), span(w, m))) { (v, []) } else { (v, n) })
  let ends = (-1e9pt, -1e9pt) // where each row's last name ends
  let out = ()
  for (value, name) in ticks.sorted(key: t => t.at(0)) {
    if name == [] { out.push((value, name)); continue }
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
#let _crossings(found) = "x = " + found.map(p => str(calc.round(p.at(0), digits: 2))).join(", ")
#let meet(f, g, from, to, label: none, lines: false, side: right, some: false, n: none) = {
  // `n`: as many crossings there as the description names (as `meet-x`), else refused
  if n != none {
    let found = _meet-points(f, g, from, to)
    if found.len() != n {
      panic("meet: the curves meet " + str(found.len()) + " times between " + repr(from) + " and " + repr(to)
        + (if found.len() > 0 { " (" + _crossings(found) + ")" } else { "" }) + ", not " + str(n)
        + ": a curve of your own crosses as many times as the description says, no more (its points chosen so)")
    }
  }
  let sep = if decimal-separator == "," { " ; " } else { ", " }
  let parts = ()
  for (x, y) in _meet-points(f, g, from, to) {
    if lines {
      parts.push(lq.line((x, 0), (x, y), stroke: (dash: "dotted", paint: luma(90))))
      parts.push(lq.line((0, y), (x, y), stroke: (dash: "dotted", paint: luma(90))))
    }
    parts.push(lq.place(x, y, circle(radius: 2.2pt, fill: black), align: center + horizon))
    let text = if label == auto { [(#written-number(x, digits: 2)#sep#written-number(y, digits: 2))] } else { label }
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
    clip: true, z-index: 22, meets: (f: f, g: g, from: from, to: to, some: some),
  )
}
// The x where two curves meet (f(c) = 0: `meet-x(f, x => 0, a, b)`; f(c) = k; two curves),
// computed as `meet` finds it, for a tick or a dotted line at it: never a number the AI writes
// by eye. One point named, one crossing between `from` and `to`; `n: 2` the description's two
// (c₁, c₂: an array of their x, in order). Another count there (none; a curve of the AI's own
// crossing again where the description names one point): refused, saying where they are
#let meet-x(f, g, from, to, n: 1) = {
  let found = _meet-points(f, g, from, to)
  if found.len() == 0 { panic("meet-x: the curves don't meet between " + repr(from) + " and " + repr(to)) }
  if found.len() != n {
    panic("meet-x: the curves meet " + str(found.len()) + " times between " + repr(from) + " and " + repr(to)
      + " (" + _crossings(found) + "), not " + str(n) + ": a curve of your own crosses as many times as the description says, no more (its points chosen so), its range the description's bounds")
  }
  if n == 1 { found.first().at(0) } else { found.map(p => p.at(0)) }
}
// An asymptote, a limit, a line y = c or x = a: dashed across the whole frame, on both sides
// of the other axis; broken only where it would cross that axis's numbers (their places and
// widths computed as lilaq writes them: the AI's ticks, or lilaq's own from the limits and the
// size), resumed past the axis. A curve or a line named (`named(lq.plot(…), [$cal(C)_f$])`):
// its name set along it. Every name (an asymptote's, "y = 3" by default, the figure's decimal
// separator; a curve's) placed by the preamble where nothing else is, never by eye
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
#let _unseen = (xaxis: none, yaxis: none, curves: (), places: (), asymptotes: ())
// The frame as an element sees it (in its own lengths, from its top left): its size, its
// limits, where each axis is (none when off the frame) and the boxes (x, y, width, height) of
// their numbers as the theme writes them: left of the vertical axis, under the horizontal one,
// none at 0 nor within 5pt of the frame's edge
#let _frame(seen, transform, size) = {
  let (w, h) = (size.width, size.height)
  let (ox, oy) = transform(0, 0)
  let (ux, uy) = transform(1, 1)
  let (sx, sy) = (ux - ox, uy - oy) // a unit, in the frame
  let (x0, x1) = ((0pt - ox) / sx, (w - ox) / sx)
  let (y0, y1) = ((h - oy) / sy, (0pt - oy) / sy)
  let (tick-out, tick-pad) = (1.5pt, 0.4em.to-absolute()) // the theme's ticks
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
  (w: w, h: h, px: px, py: py, boxes: boxes)
}
// An asymptote's line: where it is across the frame (`at`), and its pieces along it, broken
// where it would cross the other axis's numbers, from before them to past the axis
#let _asymptote-line(a, fr, transform) = {
  let horizontal = a.ay != none
  let clear = 0.3em.to-absolute() // the line's ends kept that far from the numbers
  let tick-in = 1.5pt
  let (at, length, across) = if horizontal { (transform(0, a.ay).at(1), fr.w, fr.h) } else { (transform(a.ax, 0).at(0), fr.h, fr.w) }
  let gaps = ()
  if horizontal {
    for (bx, by, bw, bh) in fr.boxes.y {
      if at > by - clear and at < by + bh + clear { gaps.push((bx - clear, fr.px + tick-in + clear)) }
    }
  } else {
    for (bx, by, bw, bh) in fr.boxes.x {
      if at > bx - clear and at < bx + bw + clear { gaps.push((fr.py - tick-in - clear, by + bh + clear)) }
    }
  }
  let pieces = if gaps.len() == 0 { ((0pt, length),) } else {
    let (a, b) = (calc.min(..gaps.map(g => g.at(0))), calc.max(..gaps.map(g => g.at(1))))
    // a piece shorter than a dash or two left out: by a number, it would read as a minus
    ((0pt, a), (b, length)).filter(((s, e)) => e - s > 0.8em.to-absolute())
  }
  // on an axis (y = 0, x = 0): the axis drawn already, the dashes over it would only blur it
  let own = if horizontal { fr.py } else { fr.px }
  let on-axis = own != none and calc.abs(at - own) < 0.5pt
  if on-axis { pieces = () }
  let inside = at >= -0.5pt and at <= across + 0.5pt
  (horizontal: horizontal, at: at, inside: inside, on-axis: on-axis, pieces: if inside { pieces } else { () })
}
#let _render-asymptote(self, transform) = layout(size => {
  let fr = _frame(self.at("seen", default: _unseen), transform, size)
  let l = _asymptote-line(self, fr, transform)
  for (s, e) in l.pieces {
    let (start, end) = if l.horizontal { ((s, l.at), (e, l.at)) } else { ((l.at, s), (l.at, e)) }
    place(line(start: start, end: end, stroke: self.stroke))
  }
})
// A curve's points in the frame, every 3pt at most along it (a line of two points sampled)
#let _sampled(xs, ys, transform) = {
  let drawn = xs.zip(ys).filter(((x, y)) => type(x) in (int, float) and type(y) in (int, float)
    and x == x and y == y and calc.abs(x) < 1e300 and calc.abs(y) < 1e300).map(((x, y)) => transform(x, y))
  let points = ()
  for i in range(drawn.len()) {
    let (a, b) = (drawn.at(i), drawn.at(calc.min(i + 1, drawn.len() - 1)))
    let steps = calc.max(1, calc.min(400, int(calc.max(calc.abs(b.at(0) - a.at(0)), calc.abs(b.at(1) - a.at(1))) / 3pt)))
    for k in range(steps) {
      let t = k / steps
      points.push((a.at(0) + (b.at(0) - a.at(0)) * t, a.at(1) + (b.at(1) - a.at(1)) * t))
    }
  }
  points
}
#let _box-points((bx, by, bw, bh)) = range(5).map(i => range(3).map(j => (bx + bw * i / 4, by + bh * j / 2))).flatten().chunks(2)
// Every name: the asymptotes' first (at an end of their line), then the curves' (along each),
// each on the side farthest from what is drawn and from the names placed before it
#let _render-names(self, transform) = layout(size => {
  let seen = self.seen
  let fr = _frame(seen, transform, size)
  let (w, h) = (fr.w, fr.h)
  let in-frame((x, y)) = x >= -5pt and x <= w + 5pt and y >= -5pt and y <= h + 5pt
  // what is drawn, each point with its owner: a curve (its index), "axis-x", "axis-y", an
  // asymptote ("a" + its index), "text"
  let points = ()
  let curves = seen.curves.map(c => _sampled(c.xs, c.ys, transform))
  for (i, c) in curves.enumerate() { points += c.filter(in-frame).map(p => (p, i)) }
  if fr.py != none { points += range(101).map(k => ((w * k / 100, fr.py), "axis-x")) }
  if fr.px != none { points += range(101).map(k => ((fr.px, h * k / 100), "axis-y")) }
  for b in fr.boxes.x + fr.boxes.y { points += _box-points(b).map(p => (p, "text")) }
  for (x, y, body, align) in seen.places {
    let (qx, qy) = transform(x, y)
    let m = measure(body)
    let (ax, ay) = if type(align) == alignment and align.axis() == none { (align.x, align.y) }
      else if type(align) == alignment and align.axis() == "horizontal" { (align, horizon) }
      else if type(align) == alignment { (center, align) } else { (center, horizon) }
    let bx = if ax == left { qx } else if ax == right { qx - m.width } else { qx - m.width / 2 }
    let by = if ay == top { qy } else if ay == bottom { qy - m.height } else { qy - m.height / 2 }
    points += _box-points((bx, by, m.width, m.height)).map(p => (p, "text"))
  }
  let lines = seen.asymptotes.map(a => _asymptote-line(a, fr, transform))
  for (i, l) in lines.enumerate() {
    for (s, e) in l.pieces {
      let n = calc.max(1, int((e - s) / 3pt))
      points += range(n + 1).map(k => {
        let along = s + (e - s) * k / n
        (if l.horizontal { (along, l.at) } else { (l.at, along) }, "a" + str(i))
      })
    }
  }
  // how far a box is from what is drawn: (from its own, from the rest)
  let apart((x, y), m, own) = {
    let (near, far) = (1e6pt, 1e6pt)
    for ((qx, qy), owner) in points {
      let dx = calc.max(x - qx, qx - x - m.width, 0pt)
      let dy = calc.max(y - qy, qy - y - m.height, 0pt)
      let d = calc.max(dx, dy)
      if owner in own { near = calc.min(near, d) } else { far = calc.min(far, d) }
    }
    (near, far)
  }
  let fits((x, y), m) = x >= 0pt and y >= 0pt and x + m.width <= w and y + m.height <= h
  let free = 0.6em.to-absolute()
  let placed = ()
  let pad = 0.3em.to-absolute()
  for (i, a) in seen.asymptotes.enumerate() {
    let l = lines.at(i)
    if not l.inside { continue }
    let name = if a.name == auto {
      if l.horizontal { $y = #written-number(a.ay, digits: 2)$ } else { $x = #written-number(a.ax, digits: 2)$ }
    } else { a.name }
    if name == none { continue }
    let m = measure(name)
    let at = l.at
    // each end, each side, close to the line, then a little farther (points along the line,
    // a sequence's terms, would touch it)
    let candidates = ()
    for off in (0.3em, 0.8em).map(o => o.to-absolute()) {
      candidates += if l.horizontal {
        let (r, le) = (w - pad - m.width, pad)
        ((r, at - off - m.height), (r, at + off), (le, at - off - m.height), (le, at + off))
      } else {
        let (t, b) = (pad, h - pad - m.height)
        ((at + off, t), (at - off - m.width, t), (at + off, b), (at - off - m.width, b))
      }
    }
    candidates = candidates.filter(c => fits(c, m))
    if candidates.len() == 0 { continue }
    // its own line apart, and the axis it lies on (the line itself)
    let own = ("a" + str(i),) + if l.on-axis { (if l.horizontal { "axis-x" } else { "axis-y" },) } else { () }
    let scored = candidates.map(c => (c, apart(c, m, own).at(1)))
    let good = scored.filter(((c, d)) => d >= free)
    let (x, y) = if good.len() > 0 { good.first().at(0) } else { scored.sorted(key: ((c, d)) => d).last().at(0) }
    place(dx: x, dy: y, name)
    points += _box-points((x, y, m.width, m.height)).map(p => (p, "text"))
  }
  // a dimension's spots for its name (a period, an amplitude): beside it, either side, a little
  // farther each time, then past its ends; those within the frame
  let dimension-spots(i, m) = {
    let g = 0.3em.to-absolute()
    let mine = curves.at(i).filter(((x, y)) => x >= 0pt and x <= w and y >= 0pt and y <= h)
    if mine.len() == 0 { return () }
    let (sx, sy) = mine.first()
    let (ex, ey) = mine.last()
    let upright = calc.abs(ex - sx) < calc.abs(ey - sy)
    let at(t) = (sx + (ex - sx) * t, sy + (ey - sy) * t)
    let spots = ()
    // beside it at its middle, quarters and ends, a little farther each time when the
    // curves leave no room close to it (between two arches)
    for d in (0, 0.5, 1, 1.5, 2.5).map(k => g + k * 1em.to-absolute()) {
      for t in (0.5, 0.25, 0.75, 0.1, 0.9) {
        let (px, py) = at(t)
        spots += if upright {
          ((px + d, py - m.height / 2), (px - d - m.width, py - m.height / 2))
        } else {
          ((px - m.width / 2, py - d - m.height), (px - m.width / 2, py + d))
        }
      }
      if d == g {
        // past each end, along it
        let (top, bottom) = if sy < ey { ((sx, sy), (ex, ey)) } else { ((ex, ey), (sx, sy)) }
        let (lefter, righter) = if sx < ex { ((sx, sy), (ex, ey)) } else { ((ex, ey), (sx, sy)) }
        spots += if upright {
          ((top.at(0) - m.width / 2, top.at(1) - g - m.height), (bottom.at(0) - m.width / 2, bottom.at(1) + g))
        } else {
          ((righter.at(0) + g, righter.at(1) - m.height / 2), (lefter.at(0) - g - m.width, lefter.at(1) - m.height / 2))
        }
      }
    }
    // over the frame's top too, in the margin left empty above it (a period at the crests'
    // height in a frame that stops just above them)
    spots.filter(((x, y)) => x >= 0pt and x + m.width <= w and y >= -m.height - 0.4em.to-absolute() and y + m.height <= h)
  }
  // the dimensions first, the one with the fewest clear spots first (written in any order: a
  // period's name has no room but under its arrow, an amplitude's has more), then the curves
  let clear-spots(i) = {
    let m = measure(seen.curves.at(i).name)
    dimension-spots(i, m).filter(p => apart(p, m, (i,)).at(1) >= 0.4em.to-absolute()).len()
  }
  let named-dims = range(seen.curves.len()).filter(i => seen.curves.at(i).name != none and seen.curves.at(i).at("dimension", default: false))
  let order = named-dims.sorted(key: clear-spots) + range(seen.curves.len()).filter(i => i not in named-dims)
  for i in order {
    let c = seen.curves.at(i)
    if c.name == none { continue }
    let mine = curves.at(i).filter(((x, y)) => x >= 0pt and x <= w and y >= 0pt and y <= h)
    if mine.len() == 0 { continue }
    let m = measure(c.name)
    let g = 0.3em.to-absolute()
    // a dimension: its first spot clear of all the rest, else the clearest
    if c.at("dimension", default: false) {
      let spots = dimension-spots(i, m)
      let scored = spots.map(p => (p, apart(p, m, (i,)).at(1)))
      if scored.len() > 0 {
        let good = scored.filter(((p, far)) => far >= 0.4em.to-absolute())
        let (x, y) = if good.len() > 0 { good.first().at(0) } else { scored.sorted(key: ((p, far)) => far).last().at(0) }
        place(dx: x, dy: y, c.name)
        points += _box-points((x, y, m.width, m.height)).map(p => (p, "text"))
        continue
      }
    }
    let candidates = ()
    // along it from its end, each point with the name above left, below right, above right
    // or below left of it
    for f in (0.92, 0.8, 0.68, 0.56, 0.44, 0.32, 0.2, 0.08) {
      let (ax, ay) = mine.at(int(f * (mine.len() - 1)))
      candidates += (
        (ax - g - m.width, ay - g - m.height), (ax + g, ay + g),
        (ax + g, ay - g - m.height), (ax - g - m.width, ay + g),
      )
    }
    candidates = candidates.filter(p => fits(p, m))
    if candidates.len() == 0 { continue }
    let scored = candidates.map(p => (p, apart(p, m, (i,))))
    // the first one well clear of the rest (read as its own curve's, not a neighbour's), else
    // the first one clear, else the clearest
    let chosen = none
    for clear in (1.2em, 0.5em).map(c => c.to-absolute()) {
      let good = scored.filter(((p, (near, far))) => near >= 0.2em.to-absolute() and far >= clear)
      if good.len() > 0 { chosen = good.first().at(0); break }
    }
    let (x, y) = if chosen != none { chosen } else {
      scored.sorted(key: ((p, (near, far))) => calc.min(far, near * 2)).last().at(0)
    }
    place(dx: x, dy: y, c.name)
    points += _box-points((x, y, m.width, m.height)).map(p => (p, "text"))
  }
})
#let asymptote(x: none, y: none, label: auto, stroke: (paint: black, thickness: 0.8pt, dash: "dashed")) = {
  assert((x == none) != (y == none), message: "asymptote: give x (a vertical line) or y (a horizontal one)")
  (
    plot: _render-asymptote, id: "asymptote", ax: x, ay: y, name: label, stroke: stroke,
    xlimits: () => none, ylimits: () => none, datetime: (:), label: none, clip: true, z-index: 3,
  )
}
// A curve or a line named: the AI's `lq.plot(…)` or `lq.line(…)` with its name, set along it
#let named(curve, name) = curve + (curve-name: name)
// A dimension: a double arrow between two points (a period, an amplitude, a length), its
// name beside its middle on the side clear of the curves, the axes and the texts, never placed
// by hand (set by _render-names, as a curve's)
#let dimension(start, end, name) = lq.line(start, end, tip: tiptoe.stealth, toe: tiptoe.stealth) + (
  vertices: (start, end), curve-name: name, dimension: true,
)
// The AI's `lq.line(…)`, keeping its ends (lilaq's own keeps them in a closure): a name kept
// clear of it (figures_typst.source)
#let line-kept(start, end, ..args) = lq.line(start, end, ..args) + (vertices: (start, end))
#let frame-most = 9cm
// The AI's diagram, its ticks' names kept apart and its asymptotes and names given what
// they need (figures_typst.source draws `lq.diagram(…)` so)
#let apart(args) = {
  let named = args.named()
  // A frame never wider nor taller than `frame-most`: one larger (an orthonormal frame over a
  // tall range, x² up to 9 against x from −3 to 3: 7 by 13 cm) has both its sides shrunk by
  // the same factor (its unit smaller, the frame still orthonormal), its text kept: a card
  // shows a figure at most 320 px wide and half the screen tall, shrinking it whole else
  let (wide, tall) = (named.at("width", default: none), named.at("height", default: none))
  if type(wide) == length and type(tall) == length and wide.to-absolute() > 0pt and tall.to-absolute() > 0pt {
    let k = calc.min(1, frame-most / wide.to-absolute(), frame-most / tall.to-absolute())
    if k < 1 {
      named.insert("width", wide.to-absolute() * k)
      named.insert("height", tall.to-absolute() * k)
    }
  }
  // A single tick written `ticks: ((4, $M$))`: Typst reads it as the pair itself, not a list
  // of one pair (no trailing comma), and lilaq refused it ("cannot compare integer and
  // content"); taken as the one tick it means
  for key in ("xaxis", "yaxis") {
    let axis = named.at(key, default: none)
    if type(axis) != dictionary { continue }
    let ticks = axis.at("ticks", default: none)
    // No tick at all, written `ticks: ()` (or `(none,)`): lilaq refused it ("expected at least
    // one value"); taken as `ticks: none`, the axis without numbers it means
    if type(ticks) == array and ticks.all(t => t == none) {
      axis.ticks = none
      named.insert(key, axis)
      continue
    }
    if type(ticks) == array and ticks.len() == 2 and type(ticks.at(0)) in (int, float) and type(ticks.at(1)) in (content, str, symbol) {
      axis.ticks = (ticks,)
      named.insert(key, axis)
    }
    // Two values named at one place (f(a) and f(b) chosen equal): lilaq refused ticks at the
    // same value ("value must be strictly positive"); one tick there, its names joined by " = "
    let ticks = axis.at("ticks", default: none)
    if type(ticks) == array and ticks.all(t => type(t) == array and t.len() == 2 and type(t.at(0)) in (int, float)) {
      let merged = ()
      for (v, name) in ticks {
        let i = merged.position(((w, m)) => calc.abs(w - v) < 1e-9)
        if i == none { merged.push((v, name)) } else { merged.at(i) = (merged.at(i).at(0), [#merged.at(i).at(1) $=$ #name]) }
      }
      if merged.len() < ticks.len() {
        axis.ticks = merged
        named.insert(key, axis)
      }
    }
  }
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
  // The asymptotes (`asymptote(y: 3)`) and the names of the curves and lines (`named(…)`)
  // given what they can't see from inside the frame: the axes as the AI set them (their
  // position, their ticks: where their numbers are), the other plots' points, the texts
  // placed; every name placed by one element of its own, after the plots
  let pos = args.pos()
  // Where two curves meet (`meet(f, g, from, to)`): checked over the whole of the curves drawn
  // (each plot whose points are f's, or g's), not only its range: a range narrowed to leave out
  // crossings the curve has (a curve of the AI's own waving across the axis, one point marked)
  // refused, saying where they are; `some: true` when the description asks for those only
  let plots = pos.filter(p => type(p) == dictionary and type(p.at("x", default: none)) == array
    and type(p.at("y", default: none)) == array and p.x.len() > 1 and p.x.len() == p.y.len()
    and p.x.all(v => type(v) in (int, float)))
  // a function's plot: the one plot whose points within the range (where the function is
  // known to be defined: meet computes it there) are its own; its xs' span. None, or several
  // (a curve in two pieces, undefined between): not checked
  let span-of(h, from, to) = {
    let mine = plots.filter(p => {
      let k = range(0, p.x.len(), step: calc.max(1, int(p.x.len() / 20))).filter(i => p.x.at(i) >= from and p.x.at(i) <= to)
      k.len() >= 2 and k.all(i => { let y = p.y.at(i); type(y) in (int, float) and calc.abs(h(p.x.at(i)) - y) <= 1e-9 * (1 + calc.abs(y)) })
    })
    if mine.len() != 1 { none } else { (calc.min(..mine.first().x), calc.max(..mine.first().x)) }
  }
  // a function with no plot of its own: checked only as a line y = k (the axis, a level),
  // known everywhere
  let level(h, from, to) = h(from) == h(to) and h(from) == h((from + to) / 2)
  // each meet: the crossings of the curves drawn, and those it marks; every crossing marked by
  // one meet or another (two meets, one crossing each, mark both)
  let checks = ()
  for m in pos.filter(p => type(p) == dictionary and p.at("id", default: none) == "meet" and "meets" in p) {
    let (f, g, from, to, some) = m.meets
    if some or type(from) not in (int, float) or type(to) not in (int, float) { continue }
    let (from, to) = (calc.min(from, to), calc.max(from, to))
    let (sf, sg) = (span-of(f, from, to), span-of(g, from, to))
    if sf == none and sg == none { continue }
    if (sf == none and not level(f, from, to)) or (sg == none and not level(g, from, to)) { continue }
    let spans = (sf, sg).filter(s => s != none)
    let (lo, hi) = (calc.max(..spans.map(s => s.at(0))), calc.min(..spans.map(s => s.at(1))))
    if hi <= lo { continue }
    let all = _meet-points(f, g, lo, hi)
    let marked = _meet-points(f, g, from, to)
    checks.push((all, marked, from, to))
  }
  let marked-all = checks.map(c => c.at(1)).flatten().chunks(2).map(p => p.at(0))
  for (all, marked, from, to) in checks {
    if all.any(p => not marked-all.any(x => calc.abs(x - p.at(0)) < 1e-6)) {
      panic("meet: the curves drawn meet " + str(all.len()) + " times (" + _crossings(all) + "), the range from "
        + repr(from) + " to " + repr(to) + " marking " + str(marked.len()) + ": a curve of your own crosses only where the description says (its points chosen so), else the range the whole curve, or `some: true` when the description asks for those only")
    }
  }
  let curves = pos.filter(p => type(p) == dictionary and (
    (type(p.at("x", default: none)) == array and type(p.at("y", default: none)) == array)
    or type(p.at("vertices", default: none)) == array))
  let asymptotes = pos.filter(p => type(p) == dictionary and p.at("id", default: none) == "asymptote")
  if asymptotes.len() == 0 and not curves.any(c => c.at("curve-name", default: none) != none) {
    return arguments(..pos, ..named)
  }
  let seen = (
    xaxis: named.at("xaxis", default: none), yaxis: named.at("yaxis", default: none),
    curves: curves.map(p => {
      let (xs, ys) = if "vertices" in p { (p.vertices.map(v => v.at(0)), p.vertices.map(v => v.at(1))) } else { (p.x, p.y) }
      (xs: xs, ys: ys, name: p.at("curve-name", default: none), dimension: p.at("dimension", default: false))
    }),
    places: pos.filter(p => type(p) == dictionary and p.at("id", default: none) == "place"
      and type(p.x) in (int, float) and type(p.y) in (int, float)).map(p => (p.x, p.y, p.body, p.align)),
    asymptotes: asymptotes.map(a => (ax: a.ax, ay: a.ay, name: a.name)),
  )
  let names = (
    plot: _render-names, id: "names", seen: seen,
    // not clipped: a dimension's name may stand over the frame's top (_render-names)
    xlimits: () => none, ylimits: () => none, datetime: (:), label: none, clip: false, z-index: 23,
  )
  pos = pos.map(p => if type(p) == dictionary and p.at("id", default: none) == "asymptote" { p + (seen: seen) } else { p })
  arguments(..pos, names, ..named)
}
#let diagram-apart(..args) = context lq.diagram(..apart(args))
// A curve known by its points (a table of variations, "passing through" points, no formula):
// the function through them, computed, never a polynomial the AI solves for by hand (one
// drawing in six missed a point it marked, two came flat into their ends). Monotone cubic
// interpolation (Fritsch–Carlson): through each point exactly, rising or falling between two
// of them without a bump of its own, level at a minimum or a maximum, at its ends sloping as
// it goes (never flat there). points: ((x, y), …), two at least, their x all different.
#let through(points, straight: false, monotone: false) = {
  if type(points) != array or points.len() < 2 or not points.all(p => type(p) == array and p.len() == 2 and p.all(v => type(v) in (int, float))) {
    panic("through: the points ((x, y), …), two at least, numbers, not " + repr(points))
  }
  let ps = points.sorted(key: p => p.at(0))
  let n = ps.len()
  let (xs, ys) = (ps.map(p => p.at(0)), ps.map(p => p.at(1)))
  let h = range(n - 1).map(k => xs.at(k + 1) - xs.at(k))
  if h.any(v => v == 0) { panic("through: two points with the same x: " + repr(points)) }
  let d = range(n - 1).map(k => (ys.at(k + 1) - ys.at(k)) / h.at(k))
  // Values that only rise, or only fall: a monotone function, said so (`monotone: true`: the
  // description says it increasing, decreasing, monotone, or gives such points), else refused,
  // saying why: a function the description gives no variations of is drawn with a turn (its
  // monotone curves, all the AI drew for one, read as an increasing function it never said)
  if not monotone and not straight and (d.all(v => v >= 0) or d.all(v => v <= 0)) {
    panic("through: the values " + repr(ys) + " only " + (if d.all(v => v >= 0) { "rise" } else { "fall" })
      + ": a function the description says increasing, decreasing or monotone (or whose points it gives so): `monotone: true`; any other function: a turn of your own, one value going back against the others, on the same side of the level as its neighbours")
  }
  let sign(v) = if v > 0 { 1 } else if v < 0 { -1 } else { 0 }
  // an end's slope: three points' estimate, kept on its side and not too steep
  let end(h0, h1, d0, d1) = {
    let m = ((2 * h0 + h1) * d0 - h0 * d1) / (h0 + h1)
    if sign(m) != sign(d0) { 0 } else if sign(d0) != sign(d1) and calc.abs(m) > 3 * calc.abs(d0) { 3 * d0 } else { m }
  }
  // Two points alone (a function given by its ends): a gentle curve between them, steep then
  // levelling off, rising or falling all the way (end slopes 1.6 and 0.4 times the chord's:
  // monotone, Fritsch–Carlson), never the straight segment of an affine function, unless
  // `straight: true` (the description says a line, an affine function)
  let m = if n == 2 { if straight { (d.at(0), d.at(0)) } else { (1.6 * d.at(0), 0.4 * d.at(0)) } } else {
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
