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
// ---- What the AI writes, from here (the rule's example: everything above is given)
#let xs = lq.linspace(0.05, 6, num: 300)
#lq.diagram(
  width: 6.7cm, height: 5cm,
  xlim: (-0.5, 6.2), ylim: (-3, 2),
  xlabel: $x$, ylabel: $y$,
  lq.plot(xs, xs.map(calc.ln), mark: none, stroke: black + 1pt),
)
