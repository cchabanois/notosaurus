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
// ---- What the AI writes, from here (the rule's example: everything above is given)
#let xs = lq.linspace(0.05, 6, num: 300)
#lq.diagram(
  width: 6.7cm, height: 5cm,
  xlim: (-0.5, 6.2), ylim: (-3, 2),
  xlabel: $x$, ylabel: $y$,
  lq.plot(xs, xs.map(calc.ln), mark: none, stroke: black + 1pt),
)
