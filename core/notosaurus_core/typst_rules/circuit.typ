#set page(width: auto, height: auto, margin: 6pt)
#import "@preview/zap:0.6.0": *
#let switch(name, ..args) = {
  let params = args.named()
  let closed = params.remove("closed", default: false)
  symbol("switch", name, ..args.pos(), ..params, draw: (ctx, position, style) => {
    interface((-style.width / 2, -0.2), (style.width / 2, 0.2), io: position.len() < 2)
    let w = style.width / 2
    cetz.draw.set-style(stroke: style.stroke)
    let blade = if closed { (w, 0) } else { (-w + 2 * w * calc.cos(style.angle), 2 * w * calc.sin(style.angle)) }
    cetz.draw.line((-w, 0), blade)
    cetz.draw.circle((-w, 0), radius: 0.06, fill: black)
    cetz.draw.circle((w, 0), radius: 0.06, fill: black)
  })
}
// The current's direction on a wire, said by where it goes: an arrow head halfway from a to
// b, pointing to b, its name beside it (whatever way the components were drawn). The wire
// from a to b drawn too: an arrow written between two wires, as one more stretch of the
// circuit, never leaves it open
#let current-arrow(a, b, label) = {
  wire(a, b)
  let m = ((a.at(0) + b.at(0)) / 2, (a.at(1) + b.at(1)) / 2)
  cetz.draw.mark(m, b, symbol: ">", fill: black, anchor: "center", scale: 0.9)
  let vertical = calc.abs(b.at(0) - a.at(0)) < calc.abs(b.at(1) - a.at(1))
  if vertical {
    cetz.draw.content((m.at(0) + 0.2, m.at(1)), label, anchor: "west")
  } else {
    cetz.draw.content((m.at(0), m.at(1) + 0.2), label, anchor: "south")
  }
}
// ---- What the AI writes, from here (the rule's example: everything above is given)
#circuit({
  battery("g", (0, 0), (0, 3), label: $G$)
  switch("k", (0, 3), (3, 3), label: $K$)
  lamp("l", (3, 3), (3, 0), label: $L$)
  wire((3, 0), (0, 0))
})
