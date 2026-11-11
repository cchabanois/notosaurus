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
// An arrow head halfway from a to b, pointing to b, its name beside it on the side `side`
// (1: left of the way from a to b, -1: right), with the wire from a to b
#let arrow-on-wire(a, b, label, side) = {
  wire(a, b)
  let m = ((a.at(0) + b.at(0)) / 2, (a.at(1) + b.at(1)) / 2)
  cetz.draw.mark(m, b, symbol: ">", fill: black, anchor: "center", scale: 0.9)
  let (dx, dy) = (b.at(0) - a.at(0), b.at(1) - a.at(1))
  let d = calc.sqrt(dx * dx + dy * dy)
  let (nx, ny) = (-dy / d * side, dx / d * side)
  let anchor = if calc.abs(nx) > calc.abs(ny) { if nx > 0 { "west" } else { "east" } } else { if ny > 0 { "south" } else { "north" } }
  cetz.draw.content((m.at(0) + 0.2 * nx, m.at(1) + 0.2 * ny), label, anchor: anchor)
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
// A component given without its points, for `branch` to place: its drawing, its length along
// the wire (zap's sizes), whether it is a generator; its name and named arguments as the AI
// writes them. Given its points, the component drawn as zap draws it
#let placeable(draw, length, generator: false) = (name, ..args) => {
  if args.pos().len() == 0 {
    (placeable: draw, length: length, generator: generator, name: name, args: args.named())
  } else {
    draw(name, ..args)
  }
}
#let battery = placeable(battery, 0.54, generator: true)
#let cell = placeable(cell, 0.18, generator: true)
#let vsource = placeable(vsource, 1.06, generator: true)
#let acvsource = placeable(acvsource, 1.06, generator: true)
#let isource = placeable(isource, 1.06, generator: true)
#let lamp = placeable(lamp, 0.57)
#let resistor = placeable(resistor, 1.41)
#let rheostat = placeable(rheostat, 1.41)
#let heater = placeable(heater, 1.41)
#let switch = placeable(switch, 0.8)
#let button = placeable(button, 0.8)
#let ammeter = placeable(ammeter, 0.94)
#let voltmeter = placeable(voltmeter, 0.94)
#let ohmmeter = placeable(ohmmeter, 0.94)
#let wattmeter = placeable(wattmeter, 0.94)
#let diode = placeable(diode, 0.6)
#let led = placeable(led, 0.6)
#let zener = placeable(zener, 0.6)
#let photodiode = placeable(photodiode, 0.6)
#let capacitor = placeable(capacitor, 0.25)
#let inductor = placeable(inductor, 1.65)
#let fuse = placeable(fuse, 0.88)
#let dcmotor = placeable(dcmotor, 1.16)
#let acmotor = placeable(acmotor, 1.16)
#let socket = placeable(socket, 0.54)
// Where a branch `length` long puts its parts (placeable components, in their order), as
// distances from its start: each component's span (`parts`), the current's arrow's (`arrow`,
// none without a current) and the components' scale. They are spaced evenly (at least 0.4 of
// wire between two: the components drawn smaller when the branch is too short for them); the
// arrow, 0.6 long, in the middle of the stretch of wire after the generator (the current
// leaving its +), else of the first stretch, that stretch 1.2 long at least
#let branch-layout(length, parts, current: false) = {
  let n = parts.len()
  let (gap-min, arrow-room) = (0.4, 1.2)
  let arrow-gap = if not current { none } else {
    let g = range(n).find(i => parts.at(i).at("generator", default: false))
    if g == none { 0 } else { g + 1 }
  }
  let needed = gap-min * (n + 1) + if current { arrow-room - gap-min } else { 0 }
  // a hair of wire at both ends of each: zap draws none of zero length
  let sizes = parts.map(p => p.at("length", default: 0.6) + 0.1)
  let total = sizes.sum(default: 0)
  let scale = if total > 0 and total > length - needed { calc.max((length - needed) / total, 0.3) } else { 1 }
  let sizes = sizes.map(size => size * scale)
  let free = length - sizes.sum(default: 0)
  let even = free / (n + 1)
  let gaps = if not current or even >= arrow-room { range(n + 1).map(_ => even) } else {
    let room = calc.min(arrow-room, free)
    let rest = if n == 0 { 0 } else { (free - room) / n }
    range(n + 1).map(i => if i == arrow-gap { room } else { rest })
  }
  let (spans, arrow, at) = ((), none, 0)
  for i in range(n + 1) {
    if i == arrow-gap {
      let half = calc.min(0.3, gaps.at(i) / 2 - 0.15)
      let mid = at + gaps.at(i) / 2
      if half > 0.05 { arrow = (mid - half, mid + half) }
    }
    at += gaps.at(i)
    if i < n {
      spans.push((at, at + sizes.at(i)))
      at += sizes.at(i)
    }
  }
  (parts: spans, arrow: arrow, scale: scale)
}
// A branch of the circuit, straight from `from` to `to`, its components in their order, laid
// out by `branch-layout`: joined by wires to each other and to both ends, so the branch is
// never open. The branch is written the way its current goes: each component from `from`
// towards `to` (a generator's + towards `to`), the current's arrow pointing to `to`. The
// components' names on one side of the branch (zap's: left of the way it goes), the
// current's on the other
#let branch(from, to, ..items, current: none) = {
  let parts = items.pos()
  let (ax, ay) = (float(from.at(0)), float(from.at(1)))
  let (bx, by) = (float(to.at(0)), float(to.at(1)))
  let length = calc.sqrt(calc.pow(bx - ax, 2) + calc.pow(by - ay, 2))
  let at(s) = (ax + (bx - ax) * s / length, ay + (by - ay) * s / length)
  let layout = branch-layout(length, parts, current: current != none)
  // the wire's stretches: between the components, cut where the arrow is
  let ends = (0,) + layout.parts.flatten() + (length,)
  for i in range(0, ends.len(), step: 2) {
    let (s, e) = (ends.at(i), ends.at(i + 1))
    let arrow = layout.arrow
    if arrow != none and s <= arrow.at(0) and arrow.at(1) <= e {
      wire(at(s), at(arrow.at(0)))
      arrow-on-wire(at(arrow.at(0)), at(arrow.at(1)), current, -1)
      wire(at(arrow.at(1)), at(e))
    } else if e - s > 0.001 {
      wire(at(s), at(e))
    }
  }
  for (p, (s, e)) in parts.zip(layout.parts) {
    let args = p.at("args", default: (:))
    if layout.scale < 1 { args.insert("scale", layout.scale) }
    (p.placeable)(p.name, at(s), at(e), ..args)
  }
}
// ---- What the AI writes, from here (the rule's example: everything above is given)
#circuit({
  battery("g", (0, 0), (0, 3), label: $G$)
  switch("k", (0, 3), (3, 3), label: $K$)
  lamp("l", (3, 3), (3, 0), label: $L$)
  wire((3, 0), (0, 0))
})
