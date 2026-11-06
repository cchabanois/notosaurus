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
#let _polyhedron(points, faces, names: (), edge-labels: (), extra: none) = {
  let size = calc.max(..range(3).map(i => calc.max(..points.map(p => p.at(i))) - calc.min(..points.map(p => p.at(i)))))
  let scale = 4 / size
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
    for (i, j, label) in edge-labels {
      let m = _mean((_proj(points.at(i)), _proj(points.at(j))))
      content(_away(m, middle, 0.35), text(11pt, label))
    }
  })
}

// A cuboid (a cube: three equal lengths), standing on its base ABCD: A at the front left,
// B front right, C back right, D back left, EFGH above them
#let cuboid(length, width, height, names: (), length-label: none, width-label: none, height-label: none) = {
  let (l, w, h) = (length, width, height)
  let points = ((0, 0, 0), (l, 0, 0), (l, w, 0), (0, w, 0), (0, 0, h), (l, 0, h), (l, w, h), (0, w, h))
  let faces = ((0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4), (3, 2, 6, 7), (0, 3, 7, 4), (1, 2, 6, 5))
  let labels = ((0, 1, length-label), (1, 2, width-label), (0, 4, height-label)).filter(e => e.at(2) != none)
  _polyhedron(points, faces, names: names, edge-labels: labels)
}

// A right prism: its base a polygon of (x, y) points (y away from the viewer), standing
// (ABC… below, then the top's in the same order); lying: true, its base upright, (x, z)
// points, the prism going away from the viewer
#let prism(base, height, lying: false, names: (), height-label: none) = {
  let n = base.len()
  let points = if lying {
    base.map(((x, z)) => (x, 0, z)) + base.map(((x, z)) => (x, height, z))
  } else {
    base.map(((x, y)) => (x, y, 0)) + base.map(((x, y)) => (x, y, height))
  }
  let faces = (range(n), range(n, 2 * n)) + range(n).map(i => (i, calc.rem(i + 1, n), n + calc.rem(i + 1, n), n + i))
  let labels = if height-label == none { () } else { ((0, n, height-label),) }
  _polyhedron(points, faces, names: names, edge-labels: labels)
}

// A pyramid: its base a square of side `side` (a rectangle with `depth`), or any polygon
// of (x, y) points, its apex above the base's centre; names: the base's, then the apex's;
// foot: the base's centre named, the height drawn to it (dashed) with its right angle
#let pyramid(side: 4, height: 5, depth: none, base: none, names: (), foot: none, side-label: none, height-label: none) = {
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
  _polyhedron(points, faces, names: names, edge-labels: labels, extra: extra)
}
// ---- What the AI writes, from here (the rule's example: everything above is given)
#cuboid(5, 3, 2, length-label: $L$, width-label: $l$, height-label: $h$)
