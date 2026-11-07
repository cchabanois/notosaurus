#set page(width: auto, height: auto, margin: 6pt)
#import "@preview/cetz:0.5.2"
// Polyhedra in cavalier perspective (the receding edges at 45°, halved): each vertex
// projected, each edge hidden when both faces along it turn their back to the viewer
// (dashed), computed: never placed or chosen by eye. x to the right, y away from the
// viewer, z up; the solid scaled to about 4 cm whatever its lengths.
#let _k = 0.5
#let _proj(p) = (p.at(0) + _k * calc.cos(45deg) * p.at(1), p.at(2) + _k * calc.sin(45deg) * p.at(1))
#let _view = (_k * calc.cos(45deg), -1, _k * calc.sin(45deg)) // towards the viewer
#let _sub(a, b) = a.zip(b).map(((x, y)) => x - y)
#let _dot(a, b) = a.zip(b).map(((x, y)) => x * y).sum()
#let _cross(a, b) = (
  a.at(1) * b.at(2) - a.at(2) * b.at(1),
  a.at(2) * b.at(0) - a.at(0) * b.at(2),
  a.at(0) * b.at(1) - a.at(1) * b.at(0),
)
#let _mean(ps) = range(ps.at(0).len()).map(i => ps.map(p => p.at(i)).sum() / ps.len())
#let _away(p, c, by) = {
  let d = _sub(p, c)
  let n = calc.sqrt(_dot(d, d))
  if n < 1e-9 { p } else { p.zip(d).map(((x, y)) => x + y / n * by) }
}

// How far a point is from a segment (on the page)
#let _gap(p, a, b) = {
  let (ab, ap) = (_sub(b, a), _sub(p, a))
  let t = calc.clamp(_dot(ap, ab) / calc.max(_dot(ab, ab), 1e-9), 0, 1)
  let d = _sub(p, a.zip(ab).map(((x, y)) => x + t * y))
  calc.sqrt(_dot(d, d))
}

// points: (x, y, z) each; faces: arrays of indices; names: one per point (none: no names);
// edge-labels: ((i, j, label), …); extra(at): more drawing, at(p) the projection of a point
#let _polyhedron(points, faces, names: (), edge-labels: (), extra: none, largest: none) = {
  let size = calc.max(..range(3).map(i => calc.max(..points.map(p => p.at(i))) - calc.min(..points.map(p => p.at(i)))))
  let scale = 4 / if largest == none { size } else { largest }
  let points = points.map(p => p.map(x => x * scale))
  let center = _mean(points)
  let visible = faces.map(f => {
    let (a, b, c) = (points.at(f.at(0)), points.at(f.at(1)), points.at(f.at(2)))
    let n = _cross(_sub(b, a), _sub(c, a))
    if _dot(n, _sub(_mean(f.map(i => points.at(i))), center)) < 0 { n = n.map(x => -x) }
    _dot(n, _view) > 1e-9
  })
  let edges = (:)
  for (i, f) in faces.enumerate() {
    for j in range(f.len()) {
      let (u, v) = (f.at(j), f.at(calc.rem(j + 1, f.len())))
      let key = str(calc.min(u, v)) + "-" + str(calc.max(u, v))
      edges.insert(key, (u: u, v: v, seen: edges.at(key, default: (seen: false)).seen or visible.at(i)))
    }
  }
  let at(p) = _proj(p.map(x => x * scale))
  let middle = _proj(center)
  cetz.canvas({
    import cetz.draw: *
    for e in edges.values() {
      line(_proj(points.at(e.u)), _proj(points.at(e.v)),
        stroke: if e.seen { 1pt } else { (thickness: 0.7pt, dash: "dashed") })
    }
    if extra != none { extra(at) }
    // each name in the one of 8 directions around its vertex farthest from every edge
    let segments = edges.values().map(e => (_proj(points.at(e.u)), _proj(points.at(e.v))))
    for (i, name) in names.enumerate() {
      let p = _proj(points.at(i))
      let spots = range(8).map(k => (p.at(0) + 0.3 * calc.cos(k * 45deg), p.at(1) + 0.3 * calc.sin(k * 45deg)))
      let best = spots.sorted(key: q => -calc.min(..segments.map(((a, b)) => _gap(q, a, b)))).first()
      content(best, text(11pt, name))
    }
    // each length beside its edge, outwards: held by its side facing the solid, so that a
    // long one ("10 mm") reaches away from the edge, never across it
    for (i, j, label) in edge-labels {
      let m = _mean((_proj(points.at(i)), _proj(points.at(j))))
      let out = _sub(m, middle)
      let angle = calc.atan2(out.at(0), out.at(1))
      let k = calc.rem(int(calc.round(angle / 45deg)) + 8, 8)
      let side = ("west", "south-west", "south", "south-east", "east", "north-east", "north", "north-west").at(k)
      content(_away(m, middle, 0.15), text(11pt, label), anchor: side)
    }
  })
}

// A cuboid (a cube: three equal lengths), standing on its base ABCD: A at the front left,
// B front right, C back right, D back left, EFGH above them
#let cuboid(length, width, height, names: (), length-label: none, width-label: none, height-label: none, largest: none) = {
  let (l, w, h) = (length, width, height)
  let points = ((0, 0, 0), (l, 0, 0), (l, w, 0), (0, w, 0), (0, 0, h), (l, 0, h), (l, w, h), (0, w, h))
  let faces = ((0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4), (3, 2, 6, 7), (0, 3, 7, 4), (1, 2, 6, 5))
  let labels = ((0, 1, length-label), (1, 2, width-label), (0, 4, height-label)).filter(e => e.at(2) != none)
  _polyhedron(points, faces, names: names, edge-labels: labels, largest: largest)
}

// A right prism: its base a polygon of (x, y) points (y away from the viewer), standing
// (ABC… below, then the top's in the same order); lying: true, its base upright, (x, z)
// points, the prism going away from the viewer
#let prism(base, height, lying: false, names: (), height-label: none, largest: none) = {
  let n = base.len()
  let points = if lying {
    base.map(((x, z)) => (x, 0, z)) + base.map(((x, z)) => (x, height, z))
  } else {
    base.map(((x, y)) => (x, y, 0)) + base.map(((x, y)) => (x, y, height))
  }
  let faces = (range(n), range(n, 2 * n)) + range(n).map(i => (i, calc.rem(i + 1, n), n + calc.rem(i + 1, n), n + i))
  let labels = if height-label == none { () } else { ((0, n, height-label),) }
  _polyhedron(points, faces, names: names, edge-labels: labels, largest: largest)
}

// A pyramid: its base a square of side `side` (a rectangle with `depth`), or any polygon
// of (x, y) points, its apex above the base's centre; names: the base's, then the apex's;
// foot: the base's centre named, the height drawn to it (dashed) with its right angle
#let pyramid(side: 4, height: 5, depth: none, base: none, names: (), foot: none, side-label: none, height-label: none, largest: none) = {
  let base = if base != none { base } else {
    let d = if depth == none { side } else { depth }
    ((0, 0), (side, 0), (side, d), (0, d))
  }
  let n = base.len()
  let (cx, cy) = _mean(base)
  let points = base.map(((x, y)) => (x, y, 0)) + ((cx, cy, height),)
  let faces = (range(n),) + range(n).map(i => (i, calc.rem(i + 1, n), n))
  let labels = if side-label == none { () } else { ((0, 1, side-label),) }
  let extra = if foot == none and height-label == none { none } else {
    at => {
      import cetz.draw: *
      let (o, s) = (at((cx, cy, 0)), at((cx, cy, height)))
      line(o, s, stroke: (thickness: 0.7pt, dash: "dashed"))
      let r = 0.22
      line((o.at(0) + r, o.at(1)), (o.at(0) + r, o.at(1) + r), (o.at(0), o.at(1) + r), stroke: 0.6pt)
      if foot != none { content((o.at(0) - 0.2, o.at(1) - 0.2), text(11pt, foot)) }
      // left of the height, low: away from the apex's edges
      if height-label != none { content((o.at(0) - 0.12, o.at(1) + (s.at(1) - o.at(1)) * 0.35), text(11pt, height-label), anchor: "east") }
    }
  }
  _polyhedron(points, faces, names: names, edge-labels: labels, extra: extra, largest: largest)
}
// Round solids as textbooks draw them: their circles as horizontal ellipses (half as deep:
// _flat), the hidden half dashed; their sizes in proportion, scaled as polyhedra
#let _flat = 0.35
#let _solid = 1pt
#let _hidden = (thickness: 0.7pt, dash: "dashed")
// the ellipse centred on c from angle a to b (degrees, 0 at its right, counter-clockwise)
#let _arc(c, rx, ry, a, b) = range(41).map(i => {
  let t = (a + (b - a) * i / 40) * 1deg
  (c.at(0) + rx * calc.cos(t), c.at(1) + ry * calc.sin(t))
})
#let _round(size, largest, body) = {
  let s = 4 / if largest == none { size } else { largest }
  cetz.canvas({
    import cetz.draw: *
    body(s)
  })
}
#let _label(at, body, anchor: "center") = cetz.draw.content(at, text(11pt, body), anchor: anchor)
// a length's double arrow beside the solid, its label beside it
#let _dimension(a, b, body, side) = {
  import cetz.draw: *
  line(a, b, stroke: 0.5pt, mark: (start: ">", end: ">", fill: black, scale: 0.6))
  _label(((a.at(0) + b.at(0)) / 2 + side.at(0), (a.at(1) + b.at(1)) / 2 + side.at(1)), body)
}
#let _right-angle(o, r) = cetz.draw.line((o.at(0) + r, o.at(1)), (o.at(0) + r, o.at(1) + r), (o.at(0), o.at(1) + r), stroke: 0.6pt)

// A cylinder standing on a base (lying: true, its axis horizontal, going to the right);
// centre-names: its bases' centres ("O", "O'"), its axis then dashed
#let cylinder(radius, height, lying: false, radius-label: none, height-label: none, centre-names: (), largest: none) = _round(
  calc.max(2 * radius, height), largest, s => {
    import cetz.draw: *
    let (r, h) = (radius * s, height * s)
    if not lying {
      let (b, t) = ((0, 0), (0, h))
      line(.._arc(b, r, r * _flat, 180, 360), stroke: _solid)
      line(.._arc(b, r, r * _flat, 0, 180), stroke: _hidden)
      line(.._arc(t, r, r * _flat, 0, 360), stroke: _solid)
      line((-r, 0), (-r, h), stroke: _solid)
      line((r, 0), (r, h), stroke: _solid)
      if centre-names.len() > 0 {
        line(b, t, stroke: _hidden)
        for (p, name) in ((b, centre-names.at(0)), (t, centre-names.at(1, default: none))) {
          if name != none { circle(p, radius: 0.04, fill: black); _label((p.at(0) - 0.25, p.at(1)), name) }
        }
      }
      if radius-label != none { line(t, (r, h), stroke: 0.7pt); _label((r / 2, h + 0.22), radius-label) }
      if height-label != none { _dimension((r + 0.4, 0), (r + 0.4, h), height-label, (0.3, 0)) }
    } else {
      let (a, b) = ((0, 0), (h, 0))
      line(.._arc(a, r * _flat, r, 90, 270), stroke: _solid)
      line(.._arc(a, r * _flat, r, -90, 90), stroke: _hidden)
      line(.._arc(b, r * _flat, r, 0, 360), stroke: _solid)
      line((0, r), (h, r), stroke: _solid)
      line((0, -r), (h, -r), stroke: _solid)
      if centre-names.len() > 0 {
        line(a, b, stroke: _hidden)
        for (p, name) in ((a, centre-names.at(0)), (b, centre-names.at(1, default: none))) {
          if name != none { circle(p, radius: 0.04, fill: black); _label((p.at(0), p.at(1) - 0.25), name) }
        }
      }
      if radius-label != none { line(b, (h, r), stroke: 0.7pt); _label((h + r * _flat + 0.22, r / 2), radius-label) }
      if height-label != none { _dimension((0, -r - 0.4), (h, -r - 0.4), height-label, (0, -0.3)) }
    }
  },
)

// A cone on its base, its apex above the centre; its contour the two tangents from the
// apex to the base's ellipse (computed), the base's hidden arc dashed
#let cone(radius, height, apex-name: none, centre-name: none, base-name: none, radius-label: none, height-label: none, slant-label: none, largest: none) = context _round(
  calc.max(2 * radius, height), largest, s => {
    import cetz.draw: *
    let (r, h, ry) = (radius * s, height * s, radius * s * _flat)
    // where the tangents from the apex (0, h) touch the ellipse x²/r² + y²/ry² = 1
    let ty = calc.min(ry * ry / h, ry * 0.999)
    let tx = r * calc.sqrt(1 - calc.pow(ty / ry, 2))
    let t = calc.asin(ty / ry).deg()
    line(.._arc((0, 0), r, ry, 180 - t, 360 + t), stroke: _solid)
    line(.._arc((0, 0), r, ry, t, 180 - t), stroke: _hidden)
    line((-tx, ty), (0, h), (tx, ty), stroke: _solid)
    let o = (0, 0)
    if centre-name != none or height-label != none {
      line(o, (0, h), stroke: _hidden)
      _right-angle(o, 0.2)
    }
    if centre-name != none { circle(o, radius: 0.04, fill: black); _label((-0.25, -0.15), centre-name) }
    if apex-name != none { _label((0, h + 0.25), apex-name) }
    if base-name != none { _label((tx + 0.25, ty), base-name) }
    if radius-label != none { line(o, (r, 0), stroke: _hidden); _label((r / 2, -0.25), radius-label) }
    // the height's length beside [SO], on its left, as high as it fits inside the cone (the
    // slant line nearer the axis as it rises; the base's hidden arc below): else beside the cone
    if height-label != none {
      let w = measure(text(11pt, height-label)).width / 1cm
      let top = h - (w + 0.4) * (h - ty) / tx - 0.25  // the label's top, nearer the slant, clear of it
      let y = calc.min(h * 0.45, top)
      if y >= ry + 0.25 { _label((-0.12, y), height-label, anchor: "east") } else {
        _dimension((-r - 0.4, 0), (-r - 0.4, h), height-label, (-0.15 - w / 2, 0))
      }
    }
    if slant-label != none { _label((tx / 2 + 0.3, (ty + h) / 2 + 0.1), slant-label, anchor: "west") }
  },
)

// A sphere (a ball): its outline, its equator (the hidden half dashed); diameter: the names
// of a diameter's ends drawn through the centre on the equator
#let sphere(radius, centre-name: none, radius-label: none, diameter: (), equator: true, largest: none) = _round(
  2 * radius, largest, s => {
    import cetz.draw: *
    let r = radius * s
    circle((0, 0), radius: r, stroke: _solid)
    if equator {
      line(.._arc((0, 0), r, r * _flat, 180, 360), stroke: _solid)
      line(.._arc((0, 0), r, r * _flat, 0, 180), stroke: _hidden)
    }
    if centre-name != none { circle((0, 0), radius: 0.04, fill: black); _label((-0.1, 0.25), centre-name) }
    if radius-label != none { line((0, 0), (r, 0), stroke: 0.7pt); _label((r / 2, 0.22), radius-label) }
    if diameter.len() == 2 {
      line((-r, 0), (r, 0), stroke: 0.7pt)
      _label((-r - 0.25, 0), diameter.at(0))
      _label((r + 0.25, 0), diameter.at(1))
    }
  },
)

// A half-sphere (a half-ball) on its flat face: its dome, its base's hidden half dashed
#let hemisphere(radius, centre-name: none, radius-label: none, largest: none) = _round(
  2 * radius, largest, s => {
    import cetz.draw: *
    let r = radius * s
    line(..range(41).map(i => (r * calc.cos(i * 180deg / 40), r * calc.sin(i * 180deg / 40))), stroke: _solid)
    line(.._arc((0, 0), r, r * _flat, 180, 360), stroke: _solid)
    line(.._arc((0, 0), r, r * _flat, 0, 180), stroke: _hidden)
    if centre-name != none { circle((0, 0), radius: 0.04, fill: black); _label((-0.1, -0.25), centre-name) }
    if radius-label != none { line((0, 0), (r, 0), stroke: 0.7pt); _label((r / 2, 0.22), radius-label) }
  },
)
// ---- What the AI writes, from here (the rule's example: everything above is given)
#cuboid(5, 3, 2, length-label: $L$, width-label: $l$, height-label: $h$)
