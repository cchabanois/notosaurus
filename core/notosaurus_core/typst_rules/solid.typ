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

// The section of a polyhedron by a plane parallel to one of its faces, `at` from it (in the
// solid's lengths): where the plane cuts its edges, computed. section: a number (parallel to
// the base) or (parallel: "ABCD" | "base" | "top" | "front" | "back" | "left" | "right", at:
// …); sides: those keywords' faces. Its points (p: the point, foot: the edge's end on the
// face's side) by key, and its sides (a, b: keys, face: the face they lie on)
#let _section(points, faces, names, sides, section) = {
  let (which, at) = if type(section) == dictionary {
    (section.at("parallel", default: "base"), section.at("at", default: none))
  } else { ("base", section) }
  let k = if which in sides { sides.at(which) } else {
    faces.position(f => (
      f.all(i => i < names.len()) and f.map(i => names.at(i)).all(n => which.contains(n))
        and f.map(i => names.at(i).len()).sum() == which.len()
    ))
  }
  if k == none {
    panic("section: parallel to " + repr(which) + ": a face by its vertices' names (\"ABCD\", the names given), or base, top, front, back, left, right")
  }
  let f = faces.at(k)
  let (a, b, c) = (points.at(f.at(0)), points.at(f.at(1)), points.at(f.at(2)))
  let n = _cross(_sub(b, a), _sub(c, a))
  if _dot(n, _sub(_mean(points), a)) < 0 { n = n.map(x => -x) }
  let n = n.map(x => x / calc.sqrt(_dot(n, n)))
  let from = _dot(n, a)
  let depth = calc.max(..points.map(p => _dot(n, p))) - from
  if type(at) not in (int, float) or at <= 0 or at >= depth {
    panic("section: at, its distance from the face, between 0 and " + str(calc.round(depth, digits: 3)) + " (the solid's depth from it), not " + repr(at))
  }
  let level = from + at
  let side(i) = _dot(n, points.at(i)) - level
  let cut = (:)
  let ends = (:)  // each face's points: their keys
  for (fi, f) in faces.enumerate() {
    let keys = ()
    for j in range(f.len()) {
      let (u, v) = (f.at(j), f.at(calc.rem(j + 1, f.len())))
      let (su, sv) = (side(u), side(v))
      if calc.abs(su) < 1e-9 {
        cut.insert("v" + str(u), (p: points.at(u), foot: u))
        keys.push("v" + str(u))
      } else if su * sv < 0 and calc.abs(sv) >= 1e-9 {
        let key = str(calc.min(u, v)) + "-" + str(calc.max(u, v))
        let t = su / (su - sv)
        cut.insert(key, (p: points.at(u).zip(points.at(v)).map(((x, y)) => x + t * (y - x)), foot: if su < 0 { u } else { v }))
        keys.push(key)
      }
    }
    ends.insert(str(fi), keys.dedup())
  }
  let lines = ends.pairs().filter(((_, keys)) => keys.len() == 2).map(((fi, keys)) => (a: keys.at(0), b: keys.at(1), face: int(fi)))
  (points: cut, sides: lines, face: f)
}

// points: (x, y, z) each; faces: arrays of indices; names: one per point (none: no names);
// edge-labels: ((i, j, label), …); extra(at): more drawing, at(p) the projection of a point;
// section, sides: _section's, its points named section-names (one per vertex of the face it
// is parallel to, each the point on the edge from that vertex), filled grey, each side
// dashed when the face it lies on is hidden
#let _label(at, body, anchor: "center") = cetz.draw.content(at, text(11pt, body), anchor: anchor)
// a length's double arrow beside the solid, its label beside it
#let _dimension(a, b, body, side) = {
  import cetz.draw: *
  line(a, b, stroke: 0.5pt, mark: (start: ">", end: ">", fill: black, scale: 0.6))
  _label(((a.at(0) + b.at(0)) / 2 + side.at(0), (a.at(1) + b.at(1)) / 2 + side.at(1)), body)
}
#let _polyhedron(points, faces, names: (), edge-labels: (), extra: none, largest: none, section: none, section-names: (), sides: (:), lines: (), marks: ()) = {
  let cut = if section == none { none } else { _section(points, faces, names, sides, section) }
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
  // the section's points projected, by key; its outline in order around them
  let spots = if cut == none { (:) } else { cut.points.pairs().map(((k, q)) => (k, at(q.p))).to-dict() }
  let segments = edges.values().map(e => (_proj(points.at(e.u)), _proj(points.at(e.v))))
  if cut != none { segments += cut.sides.map(l => (spots.at(l.a), spots.at(l.b))) }
  segments += lines.map(((a, b)) => (at(a), at(b)))
  cetz.canvas({
    import cetz.draw: *
    if cut != none and spots.len() >= 3 {
      let m = _mean(spots.values())
      let around = spots.values().sorted(key: q => calc.atan2(q.at(0) - m.at(0), q.at(1) - m.at(1)).deg())
      line(..around, close: true, fill: luma(225), stroke: none)
    }
    for e in edges.values() {
      line(_proj(points.at(e.u)), _proj(points.at(e.v)),
        stroke: if e.seen { 1pt } else { (thickness: 0.7pt, dash: "dashed") })
    }
    if cut != none {
      for l in cut.sides {
        line(spots.at(l.a), spots.at(l.b), stroke: if visible.at(l.face) { 1pt } else { (thickness: 0.7pt, dash: "dashed") })
      }
    }
    if extra != none { extra(at) }
    // each name in the one of 8 directions around its point farthest from every edge and
    // from the names already placed (a mark inside the solid, a height's foot, first)
    let named = marks.map(((q, name)) => (at(q), name)) + names.enumerate().map(((i, name)) => (_proj(points.at(i)), name))
    if cut != none {
      for (k, name) in section-names.enumerate() {
        let found = cut.points.pairs().find(((_, q)) => q.foot == cut.face.at(k, default: -1))
        if found != none { named.push((spots.at(found.at(0)), name)) }
      }
    }
    // a mark's right angle (a height's foot) up and right of it: kept clear too
    let placed = marks.map(((q, _)) => at(q).map(x => x + 0.11))
    for (p, name) in named {
      let around = range(8).map(k => (p.at(0) + 0.3 * calc.cos(k * 45deg), p.at(1) + 0.3 * calc.sin(k * 45deg)))
      let room(q) = calc.min(..segments.map(((a, b)) => _gap(q, a, b)), ..placed.map(c => _gap(q, c, c) - 0.3))
      let best = around.sorted(key: q => -room(q)).first()
      placed.push(best)
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
#let cuboid(length, width, height, names: (), length-label: none, width-label: none, height-label: none, largest: none, section: none, section-names: ()) = {
  let (l, w, h) = (length, width, height)
  let points = ((0, 0, 0), (l, 0, 0), (l, w, 0), (0, w, 0), (0, 0, h), (l, 0, h), (l, w, h), (0, w, h))
  let faces = ((0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4), (3, 2, 6, 7), (0, 3, 7, 4), (1, 2, 6, 5))
  let labels = ((0, 1, length-label), (1, 2, width-label), (0, 4, height-label)).filter(e => e.at(2) != none)
  let sides = (base: 0, top: 1, front: 2, back: 3, left: 4, right: 5)
  _polyhedron(points, faces, names: names, edge-labels: labels, largest: largest, section: section, section-names: section-names, sides: sides)
}

// A right prism: its base a polygon of (x, y) points (y away from the viewer), standing
// (ABC… below, then the top's in the same order); lying: true, its base upright, (x, z)
// points, the prism going away from the viewer
#let prism(base, height, lying: false, names: (), height-label: none, largest: none, section: none, section-names: ()) = {
  let n = base.len()
  let points = if lying {
    base.map(((x, z)) => (x, 0, z)) + base.map(((x, z)) => (x, height, z))
  } else {
    base.map(((x, y)) => (x, y, 0)) + base.map(((x, y)) => (x, y, height))
  }
  let faces = (range(n), range(n, 2 * n)) + range(n).map(i => (i, calc.rem(i + 1, n), n + calc.rem(i + 1, n), n + i))
  let labels = if height-label == none { () } else { ((0, n, height-label),) }
  _polyhedron(points, faces, names: names, edge-labels: labels, largest: largest, section: section, section-names: section-names, sides: (base: 0, top: 1))
}

// A pyramid: its base a square of side `side` (a rectangle with `depth`), or any polygon
// of (x, y) points, its apex above the base's centre; names: the base's, then the apex's;
// foot: the base's centre named, the height drawn to it (dashed) with its right angle
#let pyramid(side: 4, height: 5, depth: none, base: none, names: (), foot: none, side-label: none, height-label: none, largest: none, section: none, section-names: ()) = {
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
      // what the height's length must keep clear of: the edges, the vertices (their names)
      let corners = points.map(at)
      let edges = ()
      for f in faces { for j in range(f.len()) { edges.push((corners.at(f.at(j)), corners.at(f.at(calc.rem(j + 1, f.len()))))) } }
      // the height's length beside [SO], on the side and as high as it crosses no edge and
      // touches no vertex (a slim or a low pyramid's edges close to it): else beside the
      // pyramid, a double arrow as high as it
      if height-label != none {
        let (w, t) = (measure(text(11pt, height-label)).width / 1cm, measure(text(11pt, height-label)).height / 1cm)
        let clear(x0, y0) = {
          let (x1, y1) = (x0 + w + 0.1, y0 + t + 0.1)
          let inside(q) = q.at(0) > x0 - 0.05 and q.at(0) < x1 + 0.05 and q.at(1) > y0 - 0.05 and q.at(1) < y1 + 0.05
          (
            not edges.any(((a, b)) => range(21).any(i => inside(a.zip(b).map(((u, v)) => u + (v - u) * i / 20))))
              and not corners.any(c => c.at(0) > x0 - 0.4 and c.at(0) < x1 + 0.4 and c.at(1) > y0 - 0.4 and c.at(1) < y1 + 0.4)
          )
        }
        let spots = ()
        for k in range(3, 14) {
          let y = o.at(1) + (s.at(1) - o.at(1)) * k / 20 - t / 2 - 0.05
          spots.push((o.at(0) - 0.12 - w - 0.1, y, "left"))
          spots.push((o.at(0) + 0.12, y, "right"))
        }
        let found = spots.find(((x, y, _)) => clear(x, y))
        if found != none {
          content((found.at(0), found.at(1)), text(11pt, height-label), anchor: "south-west")
        } else {
          let x = calc.min(..corners.map(c => c.at(0))) - 0.4
          _dimension((x, o.at(1)), (x, s.at(1)), height-label, (-0.15 - w / 2, 0))
        }
      }
    }
  }
  let height-line = if foot == none and height-label == none { () } else { (((cx, cy, 0), (cx, cy, height)),) }
  let marks = if foot == none { () } else { (((cx, cy, 0), foot),) }
  context _polyhedron(points, faces, names: names, edge-labels: labels, extra: extra, largest: largest, section: section, section-names: section-names, sides: (base: 0), lines: height-line, marks: marks)
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
// A round solid's section by a plane parallel to its base: its disc filled grey, its front
// half drawn, its back half dashed (upright: a lying cylinder's, its left half in front)
#let _round-section(c, rx, ry, upright: false) = {
  import cetz.draw: *
  line(.._arc(c, rx, ry, 0, 360), close: true, fill: luma(225), stroke: none)
  let a = if upright { 90 } else { 180 }
  line(.._arc(c, rx, ry, a, a + 180), stroke: _solid)
  line(.._arc(c, rx, ry, a - 180, a), stroke: _hidden)
}
// a point's name in the one of 8 directions around it farthest from every line drawn (each
// a list of points)
#let _name(p, name, drawn) = {
  let segments = ()
  for l in drawn { segments += range(l.len() - 1).map(i => (l.at(i), l.at(i + 1))) }
  let around = range(8).map(k => (p.at(0) + 0.3 * calc.cos(k * 45deg), p.at(1) + 0.3 * calc.sin(k * 45deg)))
  let best = around.sorted(key: q => -calc.min(..segments.map(((a, b)) => _gap(q, a, b)))).first()
  _label(best, name)
}
#let _within(at, from, to, what) = if type(at) not in (int, float) or at <= from or at >= to {
  panic("section: " + what + " between " + repr(from) + " and " + repr(to) + ", not " + repr(at))
}
#let _right-angle(o, r) = cetz.draw.line((o.at(0) + r, o.at(1)), (o.at(0) + r, o.at(1) + r), (o.at(0), o.at(1) + r), stroke: 0.6pt)

// A cylinder standing on a base (lying: true, its axis horizontal, going to the right);
// centre-names: its bases' centres ("O", "O'"), its axis then dashed
// section: a plane parallel to its bases, that far from the first (below, or left when lying),
// section-centre: its centre's name
#let cylinder(radius, height, lying: false, radius-label: none, height-label: none, centre-names: (), largest: none, section: none, section-centre: none) = _round(
  calc.max(2 * radius, height), largest, s => {
    import cetz.draw: *
    let (r, h) = (radius * s, height * s)
    if section != none {
      _within(section, 0, height, "its distance from the base")
      let c = if lying { (section * s, 0) } else { (0, section * s) }
      if lying { _round-section(c, r * _flat, r, upright: true) } else { _round-section(c, r, r * _flat) }
      if section-centre != none {
        circle(c, radius: 0.04, fill: black)
        if lying { _label((c.at(0), c.at(1) - 0.08), section-centre, anchor: "north") } else { _label((c.at(0) - 0.08, c.at(1)), section-centre, anchor: "east") }
      }
    }
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
// section: a plane parallel to its base, that far from it (a smaller disc); section-centre:
// its centre's name
#let cone(radius, height, apex-name: none, centre-name: none, base-name: none, radius-label: none, height-label: none, slant-label: none, largest: none, section: none, section-centre: none) = context _round(
  calc.max(2 * radius, height), largest, s => {
    import cetz.draw: *
    let (r, h, ry) = (radius * s, height * s, radius * s * _flat)
    if section != none {
      _within(section, 0, height, "its distance from the base")
      let c = (0, section * s)
      let k = r * (1 - section / height)
      _round-section(c, k, k * _flat)
      if section-centre != none { circle(c, radius: 0.04, fill: black); _label((-0.08, c.at(1)), section-centre, anchor: "east") }
    }
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
// of a diameter's ends drawn through the centre on the equator. section: a plane parallel
// to the equator, that far above the centre (below: negative), its circle's radius computed;
// section-centre: its centre's name (H), [OH] then drawn with its right angle, distance-label
// its length; section-label: the circle's radius [HA]; radius-label then on [OA], A on the
// circle; no equator then, unless asked. The radius's label where it fits: above the radius,
// else beyond its end
#let sphere(radius, centre-name: none, radius-label: none, diameter: (), equator: auto, largest: none, section: none, section-centre: none, section-label: none, distance-label: none) = context _round(
  2 * radius, largest, s => {
    import cetz.draw: *
    let r = radius * s
    let o = (0, 0)
    let drawn = (_arc(o, r, r, 0, 360),)  // every line drawn, for the names to keep clear of
    let h = none
    if section != none {
      _within(section, -radius, radius, "its distance from the centre")
      let (y, k) = (section * s, calc.sqrt(radius * radius - section * section) * s)
      _round-section((0, y), k, k * _flat)
      drawn.push(_arc((0, y), k, k * _flat, 0, 360))
      h = (0, y)
      let a = (k, y)
      if section-centre != none or distance-label != none {
        line(o, h, stroke: _hidden)
        drawn.push((o, h))
        let q = 0.18 * if y > 0 { -1 } else { 1 }
        line((calc.abs(q), y), (calc.abs(q), y + q), (0, y + q), stroke: 0.6pt)
      }
      // the lengths low on [OH] and [OA], under the circle's front half that crosses them,
      // else halfway when it passes below the centre
      let under = if y - k * _flat > 0.5 { (y - k * _flat) / 2 } else { y / 2 }
      if distance-label != none { _label((-0.1, under), distance-label, anchor: "east") }
      if section-label != none or radius-label != none { line(h, a, stroke: 0.7pt); drawn.push((h, a)) }
      // the circle's radius labelled above [HA], under the circle's back half when it fits there,
      // else beyond A, above-right of it: outside the ball
      if section-label != none {
        let size = measure(text(11pt, section-label))
        let (w, top) = (size.width / 1cm, 0.06 + size.height / 1cm + 0.05)
        let right = k / 2 + w / 2
        let fits = right < k and k * _flat * calc.sqrt(1 - calc.pow(right / k, 2)) > top
        if fits { _label((k / 2, y + 0.06), section-label, anchor: "south") } else { _label((k + 0.1, y + 0.05), section-label, anchor: "south-west") }
      }
      if radius-label != none {
        line(o, a, stroke: 0.7pt)
        drawn.push((o, a))
        // right of [OA] at its top, the line rising to the right
        _label((k * (under + 0.2) / y + 0.1, under), radius-label, anchor: "west")
      }
    }
    circle(o, radius: r, stroke: _solid)
    if equator == true or (equator == auto and section == none) {
      line(.._arc(o, r, r * _flat, 180, 360), stroke: _solid)
      line(.._arc(o, r, r * _flat, 0, 180), stroke: _hidden)
      drawn.push(_arc(o, r, r * _flat, 0, 360))
    }
    if radius-label != none and section == none {
      line(o, (r, 0), stroke: 0.7pt)
      drawn.push((o, (r, 0)))
      let size = measure(text(11pt, radius-label))
      let (w, top) = (size.width / 1cm, 0.06 + size.height / 1cm + 0.05)
      let left = calc.max(0.12, r / 2 - w / 2)
      let right = left + w
      // the equator's hidden half above the radius: the label under it, clear of it
      let fits = right < r and r * _flat * calc.sqrt(1 - calc.pow(right / r, 2)) > top
      if fits { _label((left, 0.06), radius-label, anchor: "south-west") } else { _label((r + 0.18, 0), radius-label, anchor: "west") }
    }
    if diameter.len() == 2 {
      line((-r, 0), (r, 0), stroke: 0.7pt)
      drawn.push(((-r, 0), (r, 0)))
      _label((-r - 0.25, 0), diameter.at(0))
      _label((r + 0.25, 0), diameter.at(1))
    }
    if centre-name != none { circle(o, radius: 0.04, fill: black); _name(o, centre-name, drawn) }
    if section-centre != none and h != none { circle(h, radius: 0.04, fill: black); _name(h, section-centre, drawn) }
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
// A coordinate frame of space (O ; i, j, k) as textbooks draw it: x towards the viewer (down
// to the left, halved), y to the right, z up; each point placed from its coordinates, each
// segment, line and plane from its points' names, what a plane hides dashed and each name set
// where no line is: computed, never placed by eye. The frame scaled to about 5 cm.
#let _frame-proj(p) = _proj((p.at(1), -p.at(0), p.at(2)))
#let _frame-view = (1, _k * calc.cos(45deg), _k * calc.sin(45deg)) // towards the viewer
// whether a point lies behind a plane's polygon (each a list of 3D points), seen from the
// viewer: its projection inside the polygon's, the polygon between it and the viewer
#let _behind(p, polygons) = polygons.any(poly => {
  let q = _frame-proj(p)
  let ps = poly.map(_frame-proj)
  let signs = range(ps.len()).map(i => {
    let (a, b) = (ps.at(i), ps.at(calc.rem(i + 1, ps.len())))
    (b.at(0) - a.at(0)) * (q.at(1) - a.at(1)) - (b.at(1) - a.at(1)) * (q.at(0) - a.at(0))
  })
  let inside = signs.all(x => x > 1e-6) or signs.all(x => x < -1e-6)
  let n = _cross(_sub(poly.at(1), poly.at(0)), _sub(poly.at(2), poly.at(0)))
  let towards = _dot(n, _frame-view)
  inside and calc.abs(towards) > 1e-9 and _dot(n, _sub(poly.at(0), p)) / towards > 1e-6
})
#let space(
  points: (:), segments: (), lines: (), planes: (), vectors: (), guides: (), faces: (),
  origin: "O", units: ($arrow(i)$, $arrow(j)$, $arrow(k)$), axes: ($x$, $y$, $z$),
) = {
  for (name, p) in points {
    if type(p) != array or p.len() != 3 or p.any(x => type(x) not in (int, float)) {
      panic("points: " + name + ": its three coordinates (x, y, z), numbers, not " + repr(p))
    }
  }
  let all = points
  if origin != none and origin not in all { all.insert(origin, (0, 0, 0)) }
  let at(name) = {
    if name not in all { panic("a point not in points: " + repr(name) + " (points: " + all.keys().join(", ") + ")") }
    all.at(name)
  }
  let coords = all.values() + ((1, 1, 1),)
  let lo = range(3).map(i => calc.min(0, ..coords.map(p => p.at(i))))
  let hi = range(3).map(i => calc.max(..coords.map(p => p.at(i))))
  let reach = calc.max(..range(3).map(i => (hi.at(i) - lo.at(i)) * if i == 0 { _k } else { 1 }))
  let s = calc.min(if faces.len() > 0 { 4 } else { 1.5 }, 4.5 / reach) // a unit at most 1.5 cm, a solid's 4 cm
  let to(p) = _frame-proj(p).map(x => x * s)
  // a solid's faces (a cube's, by its vertices' names): those turned to the viewer hide
  // what is behind them, as a plane does
  let solid = faces.map(names => names.map(at))
  let centre = if solid.len() > 0 { _mean(solid.flatten().chunks(3)) } else { none }
  let front = solid.filter(f => {
    let n = _cross(_sub(f.at(1), f.at(0)), _sub(f.at(2), f.at(0)))
    if _dot(n, _sub(_mean(f), centre)) < 0 { n = n.map(x => -x) }
    _dot(n, _frame-view) > 1e-9
  })
  let corners = faces.flatten()
  let fills = planes.map(names => names.map(at))
  let polys = fills + front
  // a segment cut where it goes behind a plane or comes out: its runs, each seen or hidden
  let pieces(a, b) = {
    let n = 60
    let point(t) = a.zip(b).map(((u, v)) => u + t * (v - u))
    let runs = ()
    for i in range(n) {
      let hidden = _behind(point((i + 0.5) / n), polys)
      if runs.len() > 0 and runs.last().at(2) == hidden {
        runs.last().at(1) = point((i + 1) / n)
      } else {
        runs.push((point(i / n), point((i + 1) / n), hidden))
      }
    }
    runs
  }
  let drawn = () // the page's segments, for the names
  let named = () // (where, name, a point's dot): set once every line is drawn
  cetz.canvas({
    import cetz.draw: *
    let stroked(a, b, width, mark: none) = {
      let ps = pieces(a, b)
      for (i, (u, v, hidden)) in ps.enumerate() {
        line(to(u), to(v), stroke: if hidden { (thickness: width, dash: "dashed") } else { width },
          mark: if mark != none and i == ps.len() - 1 { mark } else { none })
      }
    }
    for poly in fills {
      line(..poly.map(to), close: true, fill: luma(230), stroke: none)
    }
    // the axes, a unit past the farthest point (and past 0 below), their unit vectors
    for i in range(3) {
      let e = range(3).map(j => if j == i { 1 } else { 0 })
      let (a, b) = (e.map(x => x * (lo.at(i) - 0.6)), e.map(x => x * (hi.at(i) + 0.9)))
      if axes == none {
        if units != none {
          line(to((0, 0, 0)), to(e), stroke: 1.3pt, mark: (end: ">", fill: black, scale: 0.7))
          named.push((to(e.map(x => x / 2)), units.at(i), false))
        }
        continue
      }
      stroked(a, b, 0.6pt, mark: (end: ">", fill: black, scale: 0.6))
      drawn.push((to(a), to(b)))
      for t in range(int(calc.ceil(lo.at(i))), int(calc.floor(hi.at(i))) + 1).filter(t => t != 0) {
        // a tick across its axis, on the page
        let (c, d) = (to(e.map(x => x * t)), _sub(to(e), to((0, 0, 0))))
        let n = (-d.at(1), d.at(0)).map(x => x / calc.sqrt(_dot(d, d)) * 0.07)
        line(_sub(c, n), c.zip(n).map(((x, y)) => x + y), stroke: 0.5pt)
      }
      content(to(e.map(x => x * (hi.at(i) + 0.9))), text(11pt, axes.at(i)), anchor: ("north-east", "west", "south").at(i), padding: 0.08)
      if units != none {
        line(to((0, 0, 0)), to(e), stroke: 1.3pt, mark: (end: ">", fill: black, scale: 0.7))
        named.push((to(e.map(x => x / 2)), units.at(i), false))
      }
    }
    // a solid's edges, each once, dashed where a face hides it
    let edges = (:)
    for f in faces {
      for j in range(f.len()) {
        let (u, v) = (f.at(j), f.at(calc.rem(j + 1, f.len())))
        edges.insert(if u < v { u + "-" + v } else { v + "-" + u }, (u, v))
      }
    }
    for (u, v) in edges.values() { stroked(at(u), at(v), 1pt); drawn.push((to(at(u)), to(at(v)))) }
    for poly in fills {
      for j in range(poly.len()) { stroked(poly.at(j), poly.at(calc.rem(j + 1, poly.len())), 0.9pt); drawn.push((to(poly.at(j)), to(poly.at(calc.rem(j + 1, poly.len()))))) }
    }
    for (a, b) in segments { stroked(at(a), at(b), 1pt); drawn.push((to(at(a)), to(at(b)))) }
    for (a, b) in lines {
      let (p, q) = (at(a), at(b))
      // a line goes on 1 cm past its two points, on the page
      let d = _sub(q, p)
      let page = _sub(to(q), to(p))
      let past = 1 / calc.max(calc.sqrt(_dot(page, page)), 1e-9)
      let (u, v) = (p.zip(d).map(((x, y)) => x - past * y), q.zip(d).map(((x, y)) => x + past * y))
      stroked(u, v, 1pt)
      drawn.push((to(u), to(v)))
    }
    for vector in vectors {
      let (a, b) = (at(vector.at(0)), at(vector.at(1)))
      stroked(a, b, 1.2pt, mark: (end: ">", fill: black, scale: 0.7))
      drawn.push((to(a), to(b)))
      if vector.len() > 2 { named.push((_mean((to(a), to(b))), vector.at(2), false)) }
    }
    for name in guides {
      let (x, y, z) = at(name)
      let foot = (x, y, 0)
      for (a, b) in ((at(name), foot), (foot, (x, 0, 0)), (foot, (0, y, 0))) {
        line(to(a), to(b), stroke: (thickness: 0.5pt, dash: "dotted"))
        drawn.push((to(a), to(b)))
      }
    }
    // each name in the one of 8 directions around its place farthest from every line drawn
    // and every name already set
    named += all.pairs().map(((name, p)) => (to(p), eval(name, mode: "math"), name not in corners))
    let placed = ()
    for (c, body, dot) in named {
      if dot { circle(c, radius: 0.045, fill: black, stroke: none) }
      let around = range(8).map(k => (c.at(0) + 0.3 * calc.cos(k * 45deg), c.at(1) + 0.3 * calc.sin(k * 45deg)))
      let room(q) = calc.min(..drawn.map(((a, b)) => _gap(q, a, b)), ..placed.map(o => calc.sqrt(_dot(_sub(q, o), _sub(q, o))) / 2))
      let best = around.sorted(key: q => -room(q)).first()
      placed.push(best)
      content(best, text(11pt, body))
    }
  })
}
// A crystal: balls on a cubic lattice in perspective, every place computed, never placed by
// eye. lattice: "simple" (balls at the cube's nodes; two species alternating, a node's
// species by the parity of i + j + k: NaCl), "body-centred" (and one at each cell's centre),
// "face-centred" (and one at each face's centre); cells: the cells along each edge (cells + 1
// balls along it); species: one or two (name, fill, size: relative), the second at the
// centres or the faces' centres; compact: the balls touching (the compact model); cut: each
// ball cut by the block's faces (only what lies inside it: a corner's eighth, a face's half);
// edge-label: the block's edge, a double arrow below it. Drawn back to front: a ball in front
// hides those behind it, the lattice's lines between them; the legend beside it.
// The receding edges at 24°, 0.55 of their length: the nodes of these lattices (simple,
// centred, up to 3 cells) kept farthest from each other on the page (at 45°, halved, a node
// behind another's diagonal neighbour lands on it)
#let _crystal-angle = 24deg
#let _crystal-k = 0.55
#let _crystal-proj(p) = (p.at(0) + _crystal-k * calc.cos(_crystal-angle) * p.at(1), p.at(2) + _crystal-k * calc.sin(_crystal-angle) * p.at(1))
#let _crystal-view = (_crystal-k * calc.cos(_crystal-angle), -1, _crystal-k * calc.sin(_crystal-angle)) // towards the viewer
#let _lattices = (
  simple: "simple", "simple cubic": "simple", sc: "simple", cubic: "simple",
  "body-centred": "body", "body-centered": "body", bcc: "body", centred: "body", centered: "body",
  "face-centred": "face", "face-centered": "face", fcc: "face",
)
// The nodes of `cells`³ cells, in half-cells (integers): (p, species), the second species'
// nodes those of the centres or the faces' centres (or the odd ones of a simple lattice)
#let _crystal-nodes(lattice, cells, two) = {
  let nodes = ()
  for i in range(2 * cells + 1) {
    for j in range(2 * cells + 1) {
      for k in range(2 * cells + 1) {
        let odd = (i, j, k).filter(x => calc.odd(x)).len()
        if odd == 0 {
          let parity = calc.rem(calc.quo(i + j + k, 2), 2)
          nodes.push(((i, j, k), if lattice == "simple" and two { parity } else { 0 }))
        } else if (lattice == "body" and odd == 3) or (lattice == "face" and odd == 2) {
          nodes.push(((i, j, k), if two { 1 } else { 0 }))
        }
      }
    }
  }
  nodes
}
// What a ball cut by the box [0, n]³ keeps, as points of its surface and its flat faces (a
// convex body: its outline on the page their hull), and its flat faces (each a plane's
// points, its outward normal)
#let _hull(ps) = {
  let ps = ps.sorted(key: p => (p.at(0), p.at(1)))
  let turn(o, a, b) = (a.at(0) - o.at(0)) * (b.at(1) - o.at(1)) - (a.at(1) - o.at(1)) * (b.at(0) - o.at(0))
  let half(ps) = {
    let h = ()
    for p in ps {
      while h.len() >= 2 and turn(h.at(-2), h.at(-1), p) <= 1e-12 { let _ = h.pop() }
      h.push(p)
    }
    h
  }
  let (lo, hi) = (half(ps), half(ps.rev()))
  lo.slice(0, -1) + hi.slice(0, -1)
}
#let _cut-ball(c, r, n) = {
  let inside(p) = p.all(x => x >= -1e-9 and x <= n + 1e-9)
  let surface = ()
  for a in range(0, 360, step: 12) {
    for b in range(-84, 90, step: 12) {
      let (t, u) = (a * 1deg, b * 1deg)
      surface.push((c.at(0) + r * calc.cos(u) * calc.cos(t), c.at(1) + r * calc.cos(u) * calc.sin(t), c.at(2) + r * calc.sin(u)))
    }
  }
  surface += ((c.at(0), c.at(1), c.at(2) + r), (c.at(0), c.at(1), c.at(2) - r))
  let points = surface.filter(inside)
  let faces = ()
  for axis in range(3) {
    for (wall, out) in ((0, -1), (n, 1)) {
      let d = calc.abs(c.at(axis) - wall)
      if d >= r - 1e-9 { continue }
      // the disc where the wall cuts the ball, kept inside the box: its circle, its centre,
      // the box's edges across it (sampled)
      let rho = calc.sqrt(r * r - d * d)
      let (u, v) = range(3).filter(x => x != axis)
      let flat = ()
      for s in range(0, 360, step: 6) {
        let q = c.map(x => x)
        q.at(axis) = wall
        q.at(u) = c.at(u) + rho * calc.cos(s * 1deg)
        q.at(v) = c.at(v) + rho * calc.sin(s * 1deg)
        flat.push(q)
        for f in range(1, 8) {
          let m = c.map(x => x)
          m.at(axis) = wall
          m.at(u) = c.at(u) + rho * f / 8 * calc.cos(s * 1deg)
          m.at(v) = c.at(v) + rho * f / 8 * calc.sin(s * 1deg)
          flat.push(m)
        }
      }
      let centre = c.map(x => x)
      centre.at(axis) = wall
      flat = (flat + (centre,)).filter(inside)
      // the box's corners on this wall within the disc: the cut's own corners
      for (a, b) in ((0, 0), (0, n), (n, 0), (n, n)) {
        let q = c.map(x => x)
        q.at(axis) = wall
        q.at(u) = a
        q.at(v) = b
        if _dot(_sub(q, c), _sub(q, c)) <= r * r { flat.push(q) }
      }
      if flat.len() >= 3 {
        let normal = range(3).map(x => if x == axis { out } else { 0 })
        faces.push((points: flat, normal: normal))
        points += flat
      }
    }
  }
  (points: points, faces: faces)
}
#let _colours = (
  black: black, gray: gray, grey: gray, silver: silver, white: white, navy: navy, blue: blue,
  aqua: aqua, teal: teal, eastern: eastern, purple: purple, fuchsia: fuchsia, maroon: maroon,
  red: red, orange: orange, yellow: yellow, olive: olive, green: green, lime: lime,
)
#let crystal(lattice: "simple", cells: 1, species: ((name: none, fill: gray, size: 1),), compact: false, cut: false, edge-label: none, legend: auto) = {
  if lattice not in _lattices {
    panic("lattice: \"simple\", \"body-centred\" or \"face-centred\", not " + repr(lattice))
  }
  let lattice = _lattices.at(lattice)
  if type(cells) != int or cells < 1 or cells > 4 { panic("cells: the cells along each edge, 1 to 4, not " + repr(cells)) }
  let species = if type(species) == dictionary { (species,) } else { species }
  if species.len() not in (1, 2) { panic("species: one or two, each (name: …, fill: …, size: …)") }
  let species = species.map(s => {
    if type(s) != dictionary { panic("species: each (name: …, fill: …, size: …), not " + repr(s)) }
    let fill = s.at("fill", default: s.at("colour", default: s.at("color", default: gray)))
    // a colour written as its name ("purple"): Typst's own
    if type(fill) == str {
      if fill not in _colours { panic("fill: a colour (" + _colours.keys().join(", ") + ", rgb(\"#…\")), not " + repr(fill)) }
      fill = _colours.at(fill)
    }
    if type(fill) != color { panic("fill: a colour, not " + repr(fill)) }
    let size = s.at("size", default: 1)
    if type(size) not in (int, float) or size <= 0 { panic("size: a number, the ball's size relative to the other's, not " + repr(size)) }
    (name: s.at("name", default: none), fill: fill, size: size)
  })
  let two = species.len() == 2
  let nodes = _crystal-nodes(lattice, cells, two).map(((p, sp)) => (p.map(x => x / 2), sp))
  // the balls' radii: their sizes' ratio kept, nearest neighbours (in cells: 1, √3/2, √2/2)
  // filling 0.45 of the gap between them (two of a kind each 0.225 of it), touching when compact
  let near = (simple: 1, body: calc.sqrt(3) / 2, face: calc.sqrt(2) / 2).at(lattice)
  let pairs = if lattice == "simple" { if two { ((0, 1),) } else { ((0, 0),) } } else if not two { ((0, 0),) } else if lattice == "body" { ((0, 1),) } else { ((0, 1), (1, 1)) }
  let widest = calc.max(..pairs.map(((a, b)) => species.at(a).size + species.at(b).size))
  let radius(sp) = species.at(sp).size / widest * near * if compact { 1 } else { 0.45 }
  let s = 4 / cells // cm per cell: the block about 4 cm
  let at(p) = _crystal-proj(p).map(x => x * s)
  let depth(p) = _dot(p, _crystal-view)
  // a ball: its colour, a lighter spot up left (no gradient: every viewer draws it alike)
  let ball(c, r, colour) = {
    cetz.draw.circle(c, radius: r, fill: colour, stroke: (paint: colour.darken(50%), thickness: 0.5pt))
    cetz.draw.circle((c.at(0) - 0.32 * r, c.at(1) + 0.32 * r), radius: 0.3 * r, fill: colour.lighten(60%), stroke: none)
  }
  // what is drawn, each at its depth: the balls, the lattice's lines in short pieces (a line
  // passes in front of a ball and behind the next)
  let items = ()
  for (p, sp) in nodes {
    items.push((depth: depth(p), ball: (p, sp)))
  }
  let lines = ()
  for (p, sp) in nodes.filter(((p, _)) => p.all(x => calc.fract(x) == 0)) {
    for axis in range(3) {
      if p.at(axis) < cells {
        let q = p.map(x => x)
        q.at(axis) += 1
        lines.push((p, q))
      }
    }
  }
  // a line cut where it passes a ball's depth, that ball over it on the page: each piece then
  // wholly in front of it or behind it
  // each line from a ball's surface to the other's (a stick going into the balls)
  let kind = nodes.map(((p, sp)) => (repr(p), sp)).to-dict()
  for (a, b) in lines {
    let (da, db) = (depth(a), depth(b))
    let cuts = (radius(kind.at(repr(a))), 1 - radius(kind.at(repr(b))))
    for (p, sp) in nodes {
      let t = (depth(p) - da) / (db - da)
      if t > cuts.at(0) and t < cuts.at(1) and _gap(at(p), at(a), at(b)) < radius(sp) * s { cuts.push(t) }
    }
    let cuts = cuts.sorted()
    let point(t) = a.zip(b).map(((x, y)) => x + (y - x) * t)
    for i in range(cuts.len() - 1) {
      let (u, v) = (point(cuts.at(i)), point(cuts.at(i + 1)))
      items.push((depth: depth(_mean((u, v))), line: (u, v)))
    }
  }
  let items = items.sorted(key: it => it.depth)
  let largest = calc.max(..species.map(x => x.size))
  cetz.canvas({
    import cetz.draw: *
    for it in items {
      if "line" in it {
        line(at(it.line.at(0)), at(it.line.at(1)), stroke: (paint: luma(110), thickness: 0.6pt, cap: "round"))
      } else {
        let (p, sp) = it.ball
        let r = radius(sp)
        let fill = species.at(sp).fill
        let edge = (paint: fill.darken(50%), thickness: 0.5pt)
        if cut and p.any(x => x < r - 1e-9 or x > cells - r + 1e-9) {
          let piece = _cut-ball(p, r, cells)
          let outline = _hull(piece.points.map(at))
          line(..outline, close: true, fill: fill, stroke: edge)
          for f in piece.faces.filter(f => _dot(f.normal, _crystal-view) > 1e-9) {
            line(.._hull(f.points.map(at)), close: true, fill: fill.lighten(25%), stroke: edge)
          }
        } else {
          ball(at(p), r * s, fill)
        }
      }
    }
    // the block's edge: a double arrow below its front lower edge, clear of the balls
    let out = if cut { 0 } else { calc.max(..nodes.map(((_, sp)) => radius(sp))) * s } // past the block
    let below = out + 0.35
    if edge-label != none {
      let (a, b) = (at((0, 0, 0)), at((cells, 0, 0)))
      _dimension((a.at(0), a.at(1) - below), (b.at(0), b.at(1) - below), edge-label, (0, -0.3))
    }
    // the legend: each species' ball, its size in proportion, and its name, right of the block
    let names = species.enumerate().filter(((_, x)) => x.name != none)
    if legend != none and names.len() > 0 {
      let right = at((cells, cells, 0)).at(0) + out + 0.7
      let top = at((0, cells, cells)).at(1) / 2 + (names.len() - 1) * 0.45
      for (k, (sp, x)) in names.enumerate() {
        let y = top - k * 0.9
        let r = 0.28 * x.size / largest
        ball((right, y), r, x.fill)
        content((right + 0.45, y), text(11pt, x.name), anchor: "west")
      }
    }
  })
}
// ---- What the AI writes, from here (the rule's example: everything above is given)
#cuboid(5, 3, 2, length-label: $L$, width-label: $l$, height-label: $h$)
