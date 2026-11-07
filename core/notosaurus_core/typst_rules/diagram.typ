#set page(width: auto, height: auto, margin: 6pt)
#import "@preview/fletcher:0.5.8" as fletcher: diagram, edge
// A node's text wider than a column goes on to the next line by itself: a newline typed in
// it is only a space, and a long text on one line makes the whole diagram tiny
#let node(..args) = {
  let given = args.pos()
  if given.len() < 2 { return fletcher.node(..args) }
  let body = given.at(1)
  let wrapped = context {
    if measure(body).width > 4.5cm { block(width: 4.5cm, align(center, body)) } else { body }
  }
  fletcher.node(given.at(0), wrapped, ..given.slice(2), ..args.named())
}
// ---- What the AI writes, from here (the rule's example: everything above is given)
#diagram(node-stroke: 0.8pt, spacing: 2em,
  node((0, 0), [Évaporation]), edge("-|>"),
  node((1, 0), [Condensation]), edge("-|>"),
  node((1, 1), [Précipitations]),
)
