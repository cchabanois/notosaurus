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
// ---- What the AI writes, from here (the rule's example: everything above is given)
#let xs = lq.linspace(0.05, 6, num: 300)
#lq.diagram(
  width: 6.7cm, height: 5cm,
  xlim: (-0.5, 6.2), ylim: (-3, 2),
  xlabel: $x$, ylabel: $y$,
  lq.plot(xs, xs.map(calc.ln), mark: none, stroke: black + 1pt),
)
