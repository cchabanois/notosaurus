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
// A house installation's parts, drawn as a French school book draws them. The socket (prise de
// courant 2P+T, seen from the front: a circle, its two holes, its earth pin) between two
// points like a lamp: the wire from its first point goes into one hole (anchor "phase"), the
// one to its second point into the other ("neutre"); its earth pin's terminal is apart, on its
// side ("terre"), so that the earth is never wired to either. Its name on that side too, by
// the first point: clear of the earth wire, of the branch's wires and of its neighbours' names
#let socket(name, a, b, label: none, ..args) = {
  let named = if label == none { none } else if type(label) == dictionary { label } else { (content: label, anchor: "name", distance: 0pt) }
  symbol("socket", name, a, b, label: named, ..args, draw: (ctx, position, style) => {
    let (r, hole, gap) = (0.42, 0.07, 0.2)
    interface((-gap - hole, -r), (gap + hole, r))
    cetz.draw.set-style(stroke: style.stroke)
    cetz.draw.circle((0, 0), radius: r)
    cetz.draw.circle((-gap, 0), radius: hole, fill: white)
    cetz.draw.circle((gap, 0), radius: hole, fill: white)
    cetz.draw.circle((0, gap), radius: 0.05, fill: black)
    cetz.draw.line((0, gap), (0, r))
    cetz.draw.anchor("phase", (-gap - hole, 0))
    cetz.draw.anchor("neutre", (gap + hole, 0))
    cetz.draw.anchor("terre", (0, r))
    cetz.draw.anchor("name", (-0.75 * r, r + 0.18))
  })
}
// One pole of a circuit breaker: an open contact, the breaker's cross at its fixed end
#let breaker-pole(name, a, b, ..args) = {
  symbol("breaker", name, a, b, ..args, draw: (ctx, position, style) => {
    let w = 0.4
    interface((-w, -0.2), (w, 0.2))
    cetz.draw.set-style(stroke: style.stroke)
    cetz.draw.line((-w, 0), (-w + 2 * w * calc.cos(30deg), 2 * w * calc.sin(30deg)))
    let c = 0.08
    cetz.draw.line((w - c, -c), (w + c, c))
    cetz.draw.line((w - c, c), (w + c, -c))
  })
}
// The general circuit breaker, two-pole: a pole on the phase (from a to b), one on the neutral
// (from c to d), their contacts joined by a dashed line (they open together); its name by the
// phase's pole
#let breaker(name, a, b, c, d, label: none) = {
  cetz.draw.group(name: name, {
    // its name clear of the open blade, which rises above the contact's bounds
    breaker-pole("phase", a, b, label: if label == none { none } else { (content: label, distance: 12pt) })
    breaker-pole("neutre", c, d)
    // the blades' middles, where the dashed link joins them
    let blade(p, q) = {
      let t = calc.atan2(q.at(0) - p.at(0), q.at(1) - p.at(1))
      let (x, y) = (-0.4 + 0.4 * calc.cos(30deg), 0.4 * calc.sin(30deg))
      let m = ((p.at(0) + q.at(0)) / 2, (p.at(1) + q.at(1)) / 2)
      (m.at(0) + x * calc.cos(t) - y * calc.sin(t), m.at(1) + x * calc.sin(t) + y * calc.cos(t))
    }
    cetz.draw.line(blade(a, b), blade(c, d), stroke: (thickness: 0.6pt, dash: "dashed"))
  })
}
// The earth conductor, green-and-yellow striped, along its points (from a socket's "terre"),
// zap's earth symbol at its last point
#let earth-wire(..points) = {
  let pts = points.pos()
  cetz.draw.line(..pts, stroke: (paint: rgb("#169c3c"), thickness: 2.2pt, join: "round"))
  cetz.draw.line(..pts, stroke: (paint: rgb("#f5d000"), thickness: 2.2pt, dash: (4pt, 4pt), join: "round"))
  earth("", pts.last())
}
// ---- What the AI writes, from here (the rule's example: everything above is given)
#circuit({
  battery("g", (0, 0), (0, 3), label: $G$)
  switch("k", (0, 3), (3, 3), label: $K$)
  lamp("l", (3, 3), (3, 0), label: $L$)
  wire((3, 0), (0, 0))
})
