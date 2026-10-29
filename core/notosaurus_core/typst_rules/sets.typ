#set page(width: auto, height: auto, margin: 6pt)
#import "@preview/cetz:0.5.2"
#import "@preview/cetz-venn:0.2.0"
#let hatch = tiling(size: (5pt, 5pt), std.line(start: (0pt, 5pt), end: (5pt, 0pt), stroke: 0.6pt))
// ---- What the AI writes, from here (the rule's example: everything above is given)
#cetz.canvas({
  import cetz.draw: *
  cetz-venn.venn2(name: "v", ab-fill: hatch)
  content("v.a", [$A$])
  content("v.b", [$B$])
})
