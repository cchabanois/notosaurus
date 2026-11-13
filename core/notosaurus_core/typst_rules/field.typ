#set page(width: auto, height: auto, margin: 6pt)
#import "@preview/cetz:0.5.2"
// Field lines, computed, never drawn by eye: a magnet's (its poles' charges spread over its
// end faces) or point charges' (q at their places), the field the sum of theirs, each line
// followed step by step along it from a north pole or a positive charge to a south pole or a
// negative one, or out of the frame; a line coming from beyond the frame into a south pole
// or a negative charge followed back from it. An arrow on each line, the field's way.
// magnets: ((at: (x, y), north: "right"),…) each 3 long, its north half red and named N, its
// south half blue and named S; charges: ((at: (x, y), sign: "+"),…); lines: how many leave
// each north pole or positive charge.

#let _ways = (right: 0deg, up: 90deg, left: 180deg, down: 270deg)
#let _magnet-length = 3
#let _magnet-width = 0.8
// a magnet's sources: its north face's three charges +1/3, its south face's −1/3
#let _magnet-sources(m) = {
  let a = _ways.at(m.at("north", default: "right"))
  let (cx, cy) = m.at("at", default: (0, 0))
  let (ux, uy) = (calc.cos(a), calc.sin(a))
  let half = _magnet-length / 2
  range(3).map(k => {
    let s = (k - 1) * _magnet-width / 3
    let side = (-uy * s, ux * s)
    (
      (pos: (cx + ux * half + side.at(0), cy + uy * half + side.at(1)), q: 1 / 3),
      (pos: (cx - ux * half + side.at(0), cy - uy * half + side.at(1)), q: -1 / 3),
    )
  }).flatten()
}
#let _sources(magnets, charges) = (
  magnets.map(_magnet-sources).flatten()
    + charges.map(c => (pos: c.at("at"), q: if c.at("sign", default: "+") == "-" { -1 } else { 1 }))
)
// the field at p, from every source: q (p − s) / |p − s|³
#let field-at(sources, p) = {
  let (fx, fy) = (0.0, 0.0)
  for s in sources {
    let (dx, dy) = (p.at(0) - s.pos.at(0), p.at(1) - s.pos.at(1))
    let r2 = dx * dx + dy * dy + 1e-9
    let k = s.q / (r2 * calc.sqrt(r2))
    fx += k * dx
    fy += k * dy
  }
  (fx, fy)
}
// whether p is inside a magnet's body
#let _in-magnet(magnets, p) = magnets.any(m => {
  let a = _ways.at(m.at("north", default: "right"))
  let (cx, cy) = m.at("at", default: (0, 0))
  let (dx, dy) = (p.at(0) - cx, p.at(1) - cy)
  let along = dx * calc.cos(a) + dy * calc.sin(a)
  let across = -dx * calc.sin(a) + dy * calc.cos(a)
  calc.abs(along) < _magnet-length / 2 and calc.abs(across) < _magnet-width / 2
})
// a field line from p, along the field (way 1) or against it (way −1): its points, step h
// (midpoint method), up to a pole or charge of the other sign, a magnet's body or the frame
// (box: (x0, y0, x1, y1)); and where it ended ("sink", "source", "out")
#let field-line(sources, magnets, p, box, way: 1, h: 0.04, steps: 900) = {
  let pts = (p,)
  let end = "out"
  let dir(q) = {
    let (fx, fy) = field-at(sources, q)
    let n = calc.sqrt(fx * fx + fy * fy) + 1e-12
    (way * fx / n, way * fy / n)
  }
  for _ in range(steps) {
    let q = pts.last()
    let (ax, ay) = dir(q)
    let m = (q.at(0) + ax * h / 2, q.at(1) + ay * h / 2)
    let (bx, by) = dir(m)
    let next = (q.at(0) + bx * h, q.at(1) + by * h)
    if next.at(0) < box.at(0) or next.at(0) > box.at(2) or next.at(1) < box.at(1) or next.at(1) > box.at(3) {
      pts.push(next)
      break
    }
    // at a source of the other sign: the line ends on it
    let hit = sources.find(s => s.q * way < 0 and calc.pow(next.at(0) - s.pos.at(0), 2) + calc.pow(next.at(1) - s.pos.at(1), 2) < 0.012)
    if hit != none { pts.push(next); end = if way > 0 { "sink" } else { "source" }; break }
    if _in-magnet(magnets, next) { end = if way > 0 { "sink" } else { "source" }; break }
    pts.push(next)
  }
  (pts: pts, end: end)
}
#let field(magnets: (), charges: (), lines: auto) = {
  assert(type(magnets) == array and type(charges) == array, message: "magnets and charges are lists: magnets: ((at: (0, 0), north: \"right\"),)")
  assert(magnets.len() + charges.len() > 0, message: "a field needs a magnet or a charge")
  for m in magnets {
    assert(type(m) == dictionary and m.at("north", default: "right") in _ways,
      message: "a magnet is (at: (x, y), north: \"right\"), north one of right, left, up, down")
  }
  for c in charges {
    assert(type(c) == dictionary and "at" in c and c.at("sign", default: "+") in ("+", "-"),
      message: "a charge is (at: (x, y), sign: \"+\") or sign: \"-\"")
  }
  let sources = _sources(magnets, charges)
  // the frame: what is drawn, and room around it for the lines
  let xs = sources.map(s => s.pos.at(0))
  let ys = sources.map(s => s.pos.at(1))
  let pad = if magnets.len() > 0 { 3 } else { 2.6 }
  let box = (calc.min(..xs) - pad, calc.min(..ys) - pad, calc.max(..xs) + pad, calc.max(..ys) + pad)
  let n = if lines == auto { if magnets.len() > 0 { 10 } else { 8 } } else { lines }
  // the seeds: around each north face's middle (outward, from its sides round to its back)
  // or each charge, outward for a north pole or a + charge, inward (followed back) for the others
  let seeds = ()
  for m in magnets {
    let a = _ways.at(m.at("north", default: "right"))
    let (cx, cy) = m.at("at", default: (0, 0))
    let half = _magnet-length / 2
    for (sign, base) in ((1, a), (-1, a + 180deg)) {
      let c = (cx + calc.cos(base) * half, cy + calc.sin(base) * half)
      // just outside the body: on a half circle a little wider than the magnet, from one
      // side round the face to the other (none inside the magnet)
      for k in range(n) {
        let t = base + (-160deg + 320deg * k / (n - 1))
        let p = (c.at(0) + 0.5 * calc.cos(t), c.at(1) + 0.5 * calc.sin(t))
        if not _in-magnet(magnets, p) { seeds.push((p: p, way: sign)) }
      }
    }
  }
  for c in charges {
    let sign = if c.at("sign", default: "+") == "-" { -1 } else { 1 }
    for k in range(n) {
      let t = 360deg * k / n + 22.5deg
      seeds.push((p: (c.at.at(0) + 0.2 * calc.cos(t), c.at.at(1) + 0.2 * calc.sin(t)), way: sign))
    }
  }
  // each line: from a source forward, or back from a sink when it comes from beyond the frame
  // (back to a source: drawn already, forward)
  let drawn = ()
  for s in seeds {
    let l = field-line(sources, magnets, s.p, box, way: s.way)
    if s.way < 0 and l.end == "source" { continue }
    // back from its seed to the magnet's face it leaves (or the charge): no gap between them
    let back = field-line(sources, magnets, s.p, box, way: -s.way, steps: 25).pts.slice(1).rev()
    let whole = back + l.pts
    let pts = if s.way < 0 { whole.rev() } else { whole }
    if pts.len() > 3 { drawn.push(pts) }
  }
  cetz.canvas({
    import cetz.draw: *
    for pts in drawn {
      line(..pts, stroke: 0.7pt)
      // the arrow, the field's way, at the middle of the line
      let i = calc.floor(pts.len() / 2)
      let (a, b) = (pts.at(calc.max(0, i - 2)), pts.at(calc.min(pts.len() - 1, i + 2)))
      line(a, b, stroke: 0.7pt, mark: (end: "stealth", fill: black, scale: 0.7))
    }
    for m in magnets {
      let a = _ways.at(m.at("north", default: "right"))
      let (cx, cy) = m.at("at", default: (0, 0))
      let (ux, uy) = (calc.cos(a), calc.sin(a))
      let (vx, vy) = (-uy, ux)
      let (hl, hw) = (_magnet-length / 2, _magnet-width / 2)
      let corner(s, t) = (cx + ux * s + vx * t, cy + uy * s + vy * t)
      line(corner(0, -hw), corner(hl, -hw), corner(hl, hw), corner(0, hw), close: true, fill: rgb("#e3342f"), stroke: 0.8pt)
      line(corner(-hl, -hw), corner(0, -hw), corner(0, hw), corner(-hl, hw), close: true, fill: rgb("#3b82c4"), stroke: 0.8pt)
      content(corner(hl / 2, 0), text(11pt, fill: white, weight: "bold")[N])
      content(corner(-hl / 2, 0), text(11pt, fill: white, weight: "bold")[S])
    }
    for c in charges {
      let plus = c.at("sign", default: "+") != "-"
      circle(c.at, radius: 0.22, fill: if plus { rgb("#e3342f") } else { rgb("#3b82c4") }, stroke: 0.8pt)
      content(c.at, text(11pt, fill: white, weight: "bold", if plus { "+" } else { "−" }))
    }
  })
}
// ---- What the AI writes, from here (the rule's example: everything above is given)
#set text(lang: "fr")
#field(magnets: ((at: (0, 0), north: "right"),))
