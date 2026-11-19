#set page(width: auto, height: auto, margin: 6pt)
#import "@preview/fletcher:0.5.8" as fletcher: diagram, edge
#import "@preview/cetz:0.5.2"
#import "common.typ": *
// A node's text wider than its column may be goes on to the next line by itself (diagram
// sets that width): a newline typed in it is only a space, and a long text on one line makes
// the whole diagram tiny
#let node = fletcher.node
// A diagram fits a card: past 12 cm wide, shrunk to a phone's width, its text was too small
// to read (four boxes of two lines on a row: 22 cm). Its nodes' texts on more lines, all
// wrapped at the widest width that makes the whole fit, measured; never under a text's
// longest word (2 cm at least), never over 4.5 cm whatever the room.
#let _card-width = 12cm
// a text's longest word, as wide as it is drawn
#let _longest-word(body) = {
  let words = _plain(body)
  if type(words) != str { return 0pt }
  calc.max(0pt, ..words.replace(regex("(\\w)\\("), m => m.captures.first() + " (").split(regex("\\s+")).map(w => measure(w).width))
}
// The gaps between columns and rows wide enough for every arrow's label: measured, never
// the AI's guess (a long label on a short arrow lay on the boxes it joins). A label needs
// its width along a row (its height down a column), shared by the cells its arrow crosses;
// beside an arrow going straight down, its width across (its height beside one going
// across); a slanting arrow's label, in the middle of the gap, leaves room there for those,
// and goes along its arrow (across it, a long one lay on the line).
#let _cell(c) = if type(c) == array and c.len() == 2 and c.all(v => type(v) in (int, float)) { c } else { none }
#let diagram(..args) = context {
  let items = args.pos()
  let slanting = ()
  let at(i) = {
    let m = items.at(i)
    if type(m) == content and m.func() == metadata and type(m.value) == dictionary { m.value } else { none }
  }
  let node-cell(i, step) = {
    let j = i + step
    while j >= 0 and j < items.len() {
      let v = at(j)
      if v != none and v.at("class", default: none) == "node" { return _cell(v.pos.raw) }
      j += step
    }
    none
  }
  let given = args.named().at("spacing", default: 3em)
  let (gx, gy) = if type(given) == array { given } else { (given, given) }
  let (need-x, need-y) = (gx.to-absolute(), gy.to-absolute())
  let pad = 1.2em.to-absolute()
  // labels beside a straight arrow (their width across a column gap, height across a row
  // gap) and on slanting ones (in the middle of both)
  let (beside-x, beside-y, slant-w, slant-h) = (0pt, 0pt, 0pt, 0pt)
  // an edge from a node to itself, drawn as a loop over it, its words on the node's own: what
  // a node does by itself is written in it
  for i in range(items.len()) {
    let e = at(i)
    if e == none or e.at("class", default: none) != "edge" { continue }
    let v = e.vertices.map(_cell)
    if v.len() == 2 and v.first() != none and v.first() == v.last() {
      panic("diagram: an edge from the node at " + repr(v.first()) + " to itself: what a node does by itself is written in its box, never an arrow (a graph's loop: network)")
    }
  }
  // an edge whose end is on no node (a cell with no node, or `edge("-|>")` with no node after
  // it): an arrow into the void, from or to nothing. Its ends found as fletcher finds them: an
  // end not given the node before (after), a relative one from the vertex before it, a name
  // its node's; a node's cells its own and those it encloses. An end that can't be known (a
  // node placed otherwise) is never refused.
  let cells = ()
  let names = (:)
  let known = true
  for i in range(items.len()) {
    let v = at(i)
    if v == none or v.at("class", default: none) != "node" { continue }
    let c = _cell(v.pos.at("raw", default: none))
    if c == none { known = false; continue }
    cells.push(c)
    cells += v.at("enclose", default: ()).map(_cell).filter(x => x != none)
    if v.at("name", default: none) != none { names.insert(repr(v.name), c) }
  }
  let same(a, b) = calc.abs(a.at(0) - b.at(0)) < 0.01 and calc.abs(a.at(1) - b.at(1)) < 0.01
  let on-node(c) = cells.any(n => same(n, c))
  // each edge's vertices, resolved: none for a missing node, "unknown" when it can't be known
  let resolved = (:)
  for i in range(items.len()) {
    let e = at(i)
    if not known or e == none or e.at("class", default: none) != "edge" { continue }
    let v = e.vertices
    if v.len() < 2 { continue }
    let found = ()
    let prev = none
    for (k, x) in v.enumerate() {
      let c = if x == auto { node-cell(i, if k == 0 { -1 } else { 1 }) }
        else if type(x) == label { names.at(repr(x), default: "unknown") }
        else if type(x) == dictionary and "rel" in x and prev != none and prev != "unknown" and _cell(x.rel) != none {
          (prev.at(0) + x.rel.at(0), prev.at(1) + x.rel.at(1))
        } else if _cell(x) != none { _cell(x) } else { "unknown" }
      found.push(c)
      prev = c
    }
    resolved.insert(str(i), found)
  }
  // an empty cell where another edge ends or turns is a junction (two edges joined end to end
  // at a corner, an algorithm's branch meeting another), not the void
  let joined(i, c) = resolved.pairs().any(((j, vs)) => j != str(i) and vs.any(x => type(x) == array and same(x, c)))
  for (key, found) in resolved.pairs() {
    let i = int(key)
    let e = at(i)
    let words = e.at("label", default: none)
    let named = if words == none or type(_plain(words)) != str { "an edge" } else { "the edge « " + _plain(words) + " »" }
    for (side, c) in (("from", found.first()), ("to", found.last())) {
      if c == "unknown" { continue }
      if c == none {
        panic("diagram: " + named + " " + side + " no node (`edge(\"-|>\")` " + if side == "from" { "before the first node" } else { "after the last node" } + "): an arrow joins two nodes, never " + side + " nothing; join it to the node it goes " + side + ", or leave it out")
      }
      if not on-node(c) and not joined(i, c) {
        panic("diagram: " + named + " " + side + " the cell " + repr(c) + ", where no node stands: an arrow joins two nodes' cells, never an empty cell (an arrow into the void); give it the cell of the node it goes " + side + ", or leave it out")
      }
    }
  }
  for i in range(items.len()) {
    let e = at(i)
    if e == none or e.at("class", default: none) != "edge" or e.at("label", default: none) == none { continue }
    // an end not given (`edge("-|>")` between two nodes): the node before, the node after
    let v = e.vertices.map(_cell)
    let from = if v.len() >= 2 and v.first() != none { v.first() } else { node-cell(i, -1) }
    let to = if v.len() >= 1 and v.last() != none { v.last() } else { node-cell(i, 1) }
    if from == none or to == none { continue }
    let size = measure(e.label)
    let (dx, dy) = (calc.abs(to.at(0) - from.at(0)), calc.abs(to.at(1) - from.at(1)))
    if dx > 0 and dy > 0 {
      need-x = calc.max(need-x, (size.width + 2 * pad) / dx)
      need-y = calc.max(need-y, (size.height + 2 * pad) / dy)
      slant-w = calc.max(slant-w, size.width)
      slant-h = calc.max(slant-h, size.height)
      slanting.push(i)
    } else if dx > 0 {
      need-x = calc.max(need-x, (size.width + pad) / dx)
      beside-y = calc.max(beside-y, size.height)
    } else if dy > 0 {
      need-y = calc.max(need-y, (size.height + pad) / dy)
      beside-x = calc.max(beside-x, size.width)
    }
  }
  // a slanting label in the middle of a gap, one beside a straight arrow on either side of it
  if slant-w > 0pt { need-x = calc.max(need-x, 2 * beside-x + slant-w + 2 * pad) }
  if slant-h > 0pt { need-y = calc.max(need-y, 2 * beside-y + slant-h + 2 * pad) }
  for i in slanting { items.at(i) = metadata((..at(i), label-angle: auto)) }
  // every node's text wrapped at `most`, on more lines, still a box (fletcher makes a
  // squarish node a circle); a bracket glued to its word ("Plasmocytes(anticorps)") a place
  // to break
  let wrapped(most) = range(items.len()).map(i => {
    let v = at(i)
    if v == none or v.at("class", default: none) != "node" or v.label == none { return items.at(i) }
    let width = calc.max(most, _longest-word(v.label))
    if measure(v.label).width <= width { return items.at(i) }
    let body = v.label
    body = { show regex("\\w\\("): it => it.text.clusters().first() + sym.zws + "("; body }
    let shape = if v.at("shape", default: auto) == auto { fletcher.shapes.rect } else { v.shape }
    metadata((..v, label: block(width: width, align(center, body)), shape: shape))
  })
  let drawn(most) = fletcher.diagram(..wrapped(most), ..args.named(), spacing: (need-x, need-y))
  let fits(most) = measure(drawn(most)).width <= _card-width
  let most = if fits(4.5cm) { 4.5cm } else if not fits(2cm) { 2cm } else {
    let (low, high) = (2cm, 4.5cm)
    for _ in range(8) {
      let mid = (low + high) / 2
      if fits(mid) { low = mid } else { high = mid }
    }
    low
  }
  drawn(most)
}
// A tree (a probability tree): its places computed, never the AI's: each leaf on a row of
// its own, each node halfway between its first and its last child, each level a column, the
// rows close (a wide gap made 8 leaves a tall, narrow strip, unreadable once fitted); a
// branch's label (its probability) beside it, above the upper branch, below the lower.
// branches: (name, label, children) each, its children the same, none at a leaf; root: the
// root's name (none: the branches start from a point)
#let _tree-branch(b) = {
  if type(b) != array or b.len() not in (2, 3) {
    panic("tree: each branch (name, label) or (name, label, (its branches…)), not " + repr(b))
  }
  b
}
#let _tree-place(b, depth, row) = {
  let (name, label, ..rest) = _tree-branch(b)
  let children = rest.at(0, default: ())
  if children.len() == 0 { return (nodes: (((depth, row), name),), edges: (), row: row + 1, y: row) }
  let (nodes, edges, r, ys) = ((), (), row, ())
  for c in children {
    let placed = _tree-place(c, depth + 1, r)
    nodes += placed.nodes
    edges += placed.edges
    r = placed.row
    ys.push(placed.y)
  }
  let y = (ys.first() + ys.last()) / 2
  for (k, c) in children.enumerate() {
    // the first branch's label above it, the last's below; a middle one's above, farther along
    // (between its branch and the one above, the gap widens towards the children)
    let last = k == children.len() - 1 and k > 0
    let middle = k > 0 and not last
    edges.push(((depth, y), (depth + 1, ys.at(k)), c.at(1), if last { right } else { left }, if middle { 0.85 } else { 0.65 }))
  }
  (nodes: nodes + (((depth, y), name),), edges: edges, row: r, y: y)
}
#let tree(..branches, root: none) = context {
  let placed = _tree-place((root, none, branches.pos()), 0, 0)
  // the columns as wide as the widest label and more; the rows as far apart as a label is
  // high (two leaves' labels, one below a branch, one above the next, between them)
  let sizes = placed.edges.map(e => measure(e.at(2)))
  let widest = calc.max(0pt, ..sizes.map(z => z.width))
  let highest = calc.max(0pt, ..sizes.map(z => z.height))
  fletcher.diagram(
    spacing: (widest + 2.5em, 1.5 * highest),
    node-inset: 5pt,
    ..placed.nodes.map(((at, name)) => fletcher.node(at, if name == none { [] } else { name })),
    // each label near the branch's end, where branches are farthest apart
    ..placed.edges.map(((from, to, label, side, along)) => fletcher.edge(
      from, to, "-", label, label-side: side, label-sep: 2pt, label-pos: along,
    )),
  )
}
// A graph of graph theory (vertices joined by edges, weighted, directed): its vertices'
// places computed, never the AI's: on a circle, in the order around it that crosses the
// fewest edges (then joins the most neighbours), the order given when it's as good. Each
// weight on its edge, in a white box, moved along it when another weight is there; two
// edges between the same vertices bent apart; a loop outside its vertex, away from the others.
// vertices: their names; edges: (from, to) or (from, to, weight) each, from and to as the
// vertices are named; directed: arrows
#let _net-key(v) = {
  if type(v) == str { v.trim() }
  else if type(v) == content and v.has("text") { v.text.trim() }
  else if type(v) == content and v.has("body") { _net-key(v.body) }
  else if type(v) == content and v.has("children") { v.children.map(_net-key).join() }
  else { repr(v) }
}
#let _net-orders(rest) = {
  if rest.len() <= 1 { return (rest,) }
  let all = ()
  for (k, first) in rest.enumerate() {
    let others = rest.slice(0, k) + rest.slice(k + 1)
    for o in _net-orders(others) { all.push((first,) + o) }
  }
  all
}
// crossings of the edges (pairs of indices) with the vertices in `order` around a circle, and
// the edges joining two neighbours on it
#let _net-score(order, pairs, n) = {
  let at = range(n).map(i => order.position(v => v == i))
  let chords = pairs.filter(((a, b)) => a != b).map(((a, b)) => {
    let (p, q) = (at.at(a), at.at(b))
    if p < q { (p, q) } else { (q, p) }
  })
  let crossings = 0
  for (i, (a, b)) in chords.enumerate() {
    for (c, d) in chords.slice(i + 1) {
      if a != c and a != d and b != c and b != d and ((a < c and c < b) != (a < d and d < b)) { crossings += 1 }
    }
  }
  let sides = chords.filter(((a, b)) => b - a == 1 or (a == 0 and b == n - 1)).len()
  (crossings, -sides)
}
#let network(vertices: (), edges: (), directed: false) = context {
  import cetz.draw: *
  let n = vertices.len()
  if n == 0 { panic("network: no vertices: vertices: (\"A\", \"B\", …)") }
  let keys = vertices.map(_net-key)
  let index(v) = {
    let i = keys.position(k => k == _net-key(v))
    if i == none { panic("network: an edge names " + repr(v) + ", not one of the vertices " + repr(keys)) }
    i
  }
  let edges = edges.map(e => {
    if type(e) != array or e.len() not in (2, 3) {
      panic("network: each edge (from, to) or (from, to, weight), not " + repr(e))
    }
    (index(e.at(0)), index(e.at(1)), e.at(2, default: none))
  })
  let pairs = edges.map(e => (e.at(0), e.at(1)))
  // the order around the circle: every order tried, up to 7 vertices
  let order = range(n)
  if n >= 4 and n <= 7 {
    let best = _net-score(order, pairs, n)
    for o in _net-orders(range(1, n)) {
      let s = _net-score((0,) + o, pairs, n)
      if s.at(0) < best.at(0) or (s.at(0) == best.at(0) and s.at(1) < best.at(1)) { (best, order) = (s, (0,) + o) }
    }
  }
  let names = vertices.map(v => if type(v) == str { [#v] } else { v })
  let size = calc.max(..names.map(m => calc.max(measure(m).width, measure(m).height)))
  let r = (size / 2 + 4pt) / 1cm
  // neighbours on the circle 2.4 cm apart (edge to edge), the circle 1.2 cm across at least
  let radius = if n == 1 { 0 } else { calc.max(0.9, (2 * r + 1.6) / (2 * calc.sin(180deg / n))) }
  let start = if n == 2 { 180deg } else if calc.even(n) { 90deg + 180deg / n } else { 90deg }
  let place = range(n).map(i => {
    let a = start - order.position(v => v == i) * 360deg / n
    (radius * calc.cos(a), radius * calc.sin(a))
  })
  let add((x, y), (u, v), k) = (x + k * u, y + k * v)
  let unit((x, y)) = {
    let l = calc.sqrt(x * x + y * y)
    if l == 0 { (0, 1) } else { (x / l, y / l) }
  }
  let mark = if directed { (end: "straight", scale: 0.9) } else { none }
  let labels = ()
  let placed = ()
  cetz.canvas({
    set-style(stroke: 0.8pt)
    for (k, (a, b, w)) in edges.enumerate() {
      let (p, q) = (place.at(a), place.at(b))
      if a == b {
        // a loop: outside its vertex, away from the circle's middle
        let out = if n == 1 { (0, 1) } else { unit(p) }
        let side = (-out.at(1), out.at(0))
        let from = add(add(p, out, r * 0.8), side, r * 0.6)
        let to = add(add(p, out, r * 0.8), side, -r * 0.6)
        let top = add(p, out, r + 0.75)
        bezier(from, to, add(top, side, 0.55), add(top, side, -0.55), mark: mark)
        if w != none { labels.push((add(p, out, r + 0.62), w, "loop", out)) }
        continue
      }
      // bent when another edge joins the same two vertices (either way): each to its own left
      let twins = pairs.enumerate().filter(((j, (c, d))) => (c == a and d == b) or (c == b and d == a))
      let bend = if twins.len() > 1 {
        let rank = twins.position(((j, _)) => j == k)
        let c0 = twins.at(0).at(1).at(0)
        // the same way as the first: alternately each side; the other way: its left is the other side
        let s = if c0 == a { 1 } else { -1 }
        0.45 * s * (if calc.even(rank) { 1 } else { -1 }) * (calc.floor(rank / 2) + 1)
      } else { 0 }
      let d = unit((q.at(0) - p.at(0), q.at(1) - p.at(1)))
      let normal = (-d.at(1), d.at(0))
      let mid = add(((p.at(0) + q.at(0)) / 2, (p.at(1) + q.at(1)) / 2), normal, bend)
      // ends on the vertices' circles, towards the curve's middle
      let from = add(p, unit((mid.at(0) - p.at(0), mid.at(1) - p.at(1))), r)
      let to = add(q, unit((mid.at(0) - q.at(0), mid.at(1) - q.at(1))), r)
      if bend == 0 { line(from, to, mark: mark) } else {
        // through mid: a quadratic curve's control point twice as far out
        let ctrl = add(((p.at(0) + q.at(0)) / 2, (p.at(1) + q.at(1)) / 2), normal, 2 * bend)
        bezier(from, to, ctrl, mark: mark)
      }
      if w != none {
        // along the edge: its middle, or farther along when another weight is near there
        let at(t) = {
          let (x0, y0) = from
          let (x1, y1) = to
          if bend == 0 { (x0 + t * (x1 - x0), y0 + t * (y1 - y0)) } else {
            let ctrl = add(((p.at(0) + q.at(0)) / 2, (p.at(1) + q.at(1)) / 2), normal, 2 * bend)
            let s = 1 - t
            (s * s * x0 + 2 * s * t * ctrl.at(0) + t * t * x1, s * s * y0 + 2 * s * t * ctrl.at(1) + t * t * y1)
          }
        }
        let box = measure(w)
        let room = (calc.max(box.width, box.height) + 6pt) / 1cm
        let spot = none
        for t in (0.5, 0.35, 0.65, 0.25, 0.75) {
          let c = at(t)
          if placed.all(o => calc.sqrt(calc.pow(o.at(0) - c.at(0), 2) + calc.pow(o.at(1) - c.at(1), 2)) > room) {
            spot = c
            break
          }
        }
        if spot == none { spot = at(0.5) }
        placed.push(spot)
        labels.push((spot, w, "edge", none))
      }
    }
    for (i, at) in place.enumerate() {
      circle(at, radius: r, fill: white)
      content(at, names.at(i))
    }
    for (at, w, kind, out) in labels {
      if kind == "loop" {
        let anchor = if calc.abs(out.at(0)) > calc.abs(out.at(1)) { if out.at(0) > 0 { "west" } else { "east" } } else { if out.at(1) > 0 { "south" } else { "north" } }
        content(at, w, anchor: anchor, padding: 0.05)
      } else {
        content(at, box(fill: white, inset: 1.5pt, w))
      }
    }
  })
}
// A scheme (boxes and who acts on whom: institutions, an organisation and its parts, a
// hierarchy): its places computed, never the AI's, which crossed its arrows, laid their words
// on one another and spread it so wide that its text fell to 4 px on a phone. Its boxes in
// layers, each arrow going from one layer to a next (down, or up with `flow: "up"`), an arrow
// that goes back up (one of two each way) drawn the same way between the same layers; a layer
// of more boxes than the card holds goes on below; boxes of a layer ordered to cross the
// fewest arrows (each box at its neighbours' middle, layer by layer), then each placed at its
// neighbours' middle as near as they leave room. Each arrow straight from its box's border to
// the other's (an elbowed line, its words on a layer of their own, zigzagged and was hard to
// follow on a phone); a soft curve, one only, round a box in its way, through the room its
// layer kept for it; arrows on one side of a box spread along it in the order of their other
// ends, two between the same boxes one straight and one bowed. Each arrow's words on its line,
// on a white ground, clear of every other word, arrow and box and of its own ends; the gap
// between two layers grown, that one only, until they are. Its texts wrapped at the
// widest width that makes its text the largest on a card (figures_typst.CARD_PX: 320 × 400
// px); an arrow from a box to itself refused, told why.
// boxes: (name: [its text], …); arrows: (from, to) or (from, to, [its words]) each, from and to
// boxes' names, "<|-|>" (both ways), "-" (a line), "--" (dashed) or ".." (dotted) after them
#let _sch-card = (320, 400) // figures_typst.CARD_PX
#let _sch-is-style(v) = type(v) == str and v.len() > 0 and v.match(regex("^[-<>|. ]+$")) != none
#let _sch-style(s) = (
  dash: if s.contains("..") { "dotted" } else if s.contains("--") or s.contains("- -") { "dashed" } else { none },
  start: s.trim().starts-with("<"),
  end: s.trim().ends-with(">"),
)
// the non-decreasing values nearest `targets` (least squares): adjacent violators pooled
#let _sch-pav(targets) = {
  let blocks = ()
  for t in targets {
    blocks.push((t, 1))
    while blocks.len() > 1 {
      let (s2, c2) = blocks.at(-1)
      let (s1, c1) = blocks.at(-2)
      if s1 / c1 <= s2 / c2 { break }
      let _ = blocks.pop()
      blocks.at(-1) = (s1 + s2, c1 + c2)
    }
  }
  let out = ()
  for (s, c) in blocks { out += range(c).map(_ => s / c) }
  out
}
// the segment p–q meets the rectangle (x0, y0, x1, y1)
#let _sch-hits(p, q, r) = {
  let (x0, y0, x1, y1) = r
  let (dx, dy) = (q.at(0) - p.at(0), q.at(1) - p.at(1))
  let (t0, t1) = (0.0, 1.0)
  for (a, b) in ((-dx, p.at(0) - x0), (dx, x1 - p.at(0)), (-dy, p.at(1) - y0), (dy, y1 - p.at(1))) {
    if a == 0 {
      if b < 0 { return false }
    } else {
      let t = b / a
      if a < 0 { t0 = calc.max(t0, t) } else { t1 = calc.min(t1, t) }
    }
  }
  t0 <= t1
}
#let _sch-meet(a, b) = a.at(0) < b.at(2) and b.at(0) < a.at(2) and a.at(1) < b.at(3) and b.at(1) < a.at(3)
#let _sch-grow(r, d) = (r.at(0) - d, r.at(1) - d, r.at(2) + d, r.at(3) + d)
// each node's layer (a node a box's index, or an arrow's point in a layer it crosses: the
// first its words' place) and each arrow's chain of nodes from its upper end to its lower;
// `cap` boxes a layer at most. The boxes on even layers, the arrows' words on the odd ones
// between them: each arrow crosses one at least.
#let _sch-layers(n, dag, cap) = {
  let rank = range(n).map(_ => 0)
  for _ in range(n) {
    for (a, b) in dag { if rank.at(b) < rank.at(a) + 1 { rank.at(b) = rank.at(a) + 1 } }
  }
  // a box only at the start of arrows: just above the nearest box they go to
  for v in range(n) {
    let succ = dag.filter(((a, b)) => a == v).map(((a, b)) => rank.at(b))
    if succ.len() > 0 and dag.all(((a, b)) => b != v) { rank.at(v) = calc.min(..succ) - 1 }
  }
  let dense(rank) = {
    let values = rank.dedup().sorted()
    rank.map(r => values.position(x => x == r))
  }
  rank = dense(rank)
  // a layer of more than `cap` boxes: the boxes no arrow leaves (then the last ones) a layer below
  let full = true
  while full {
    full = false
    for r in range(calc.max(..rank) + 1) {
      let these = range(n).filter(v => rank.at(v) == r)
      if these.len() > cap {
        let leaving(v) = if dag.any(((a, b)) => a == v) { 0 } else { 1 }
        let moved = these.sorted(key: v => leaving(v) * n + v).slice(cap)
        for v in moved { rank.at(v) = r + 0.5 }
        rank = dense(rank)
        full = true
        break
      }
    }
  }
  let layer-of = rank.map(r => 2 * r)
  let chains = ()
  for (a, b) in dag {
    let chain = (a,)
    for r in range(layer-of.at(a) + 1, layer-of.at(b)) {
      chain.push(layer-of.len())
      layer-of.push(r)
    }
    chains.push(chain + (b,))
  }
  (layer-of, chains)
}
// each layer's nodes, ordered to cross the fewest arrows (barycentres, layer by layer, down
// and up, then neighbours swapped)
#let _sch-order(layer-of, chains) = {
  let count = layer-of.len()
  let depth = calc.max(..layer-of) + 1
  let up = range(count).map(_ => ())
  let down = range(count).map(_ => ())
  for chain in chains {
    for i in range(chain.len() - 1) {
      down.at(chain.at(i)).push(chain.at(i + 1))
      up.at(chain.at(i + 1)).push(chain.at(i))
    }
  }
  let layers = range(depth).map(r => range(count).filter(v => layer-of.at(v) == r))
  let where(layers) = {
    let at = range(count).map(_ => 0)
    for l in layers { for (i, v) in l.enumerate() { at.at(v) = i } }
    at
  }
  let crossings(layers) = {
    let at = where(layers)
    let total = 0
    for r in range(depth - 1) {
      let segs = ()
      for v in layers.at(r) { for w in down.at(v) { segs.push((at.at(v), at.at(w))) } }
      for i in range(segs.len()) {
        for j in range(i + 1, segs.len()) {
          let (a, b) = segs.at(i)
          let (c, d) = segs.at(j)
          if (a - c) * (b - d) < 0 { total += 1 }
        }
      }
    }
    total
  }
  let sweep(layers, r, by) = {
    let at = where(layers)
    let key(v) = {
      let ns = by.at(v)
      let b = if ns.len() == 0 { at.at(v) } else { ns.map(w => at.at(w)).sum() / ns.len() }
      b + at.at(v) * 0.001
    }
    layers.at(r) = layers.at(r).sorted(key: key)
    layers
  }
  // from the order given, and from its reverse: the order that crosses fewer
  let (best, fewest) = (layers, crossings(layers))
  for start in (layers, layers.map(l => l.rev())) {
    let layers = start
    for round in range(8) {
      if fewest == 0 { break }
      for r in range(1, depth) { layers = sweep(layers, r, up) }
      for r in range(depth - 2, -1, step: -1) { layers = sweep(layers, r, down) }
      let now = crossings(layers)
      for r in range(depth) {
        for i in range(layers.at(r).len() - 1) {
          let swapped = layers
          let l = swapped.at(r)
          (l.at(i), l.at(i + 1)) = (l.at(i + 1), l.at(i))
          swapped.at(r) = l
          let c = crossings(swapped)
          if c < now { (layers, now) = (swapped, c) }
        }
      }
      if now < fewest { (best, fewest) = (layers, now) }
    }
  }
  // then each node tried at every place in its layer, kept where it crosses fewest
  let layers = best
  let moved = fewest > 0
  for pass in range(4) {
    if not moved { break }
    moved = false
    for r in range(depth) {
      for v in layers.at(r) {
        let others = layers.at(r).filter(w => w != v)
        for place in range(others.len() + 1) {
          let tried = layers
          tried.at(r) = others.slice(0, place) + (v,) + others.slice(place)
          let c = crossings(tried)
          if c < fewest { (layers, fewest, moved) = (tried, c, true) }
        }
      }
    }
  }
  (layers, up, down)
}
// a scheme's layout (context: its texts measured): its size; each box (its rectangle, x0, y0,
// x1, y1, and its framed text), each arrow's words (rectangle, content, none without words),
// each arrow (its points from its start to its end, its style), in pt
#let _sch-layout(boxes, arrows, flow) = {
  if type(boxes) != dictionary or boxes.len() == 0 {
    panic("scheme: boxes: (name: [its text], …), a box each, not " + repr(boxes))
  }
  if flow not in ("down", "up") { panic("scheme: flow: \"down\" or \"up\", not " + repr(flow)) }
  let names = boxes.keys()
  let n = names.len()
  let index(k) = {
    let i = names.position(x => x == _net-key(k))
    if i == none { panic("scheme: an arrow names " + repr(k) + ", not one of the boxes " + repr(names)) }
    i
  }
  let edges = ()
  for a in arrows {
    if type(a) != array or a.len() < 2 or a.len() > 4 {
      panic("scheme: each arrow (from, to), (from, to, [its words]) or (from, to, [its words], \"--\"), not " + repr(a))
    }
    let (u, v) = (index(a.at(0)), index(a.at(1)))
    if u == v {
      panic("scheme: an arrow from " + repr(a.at(0)) + " to itself: what a box does by itself is written in its box (its words under its name), never an arrow")
    }
    let label = none
    let style = "-|>"
    // words of no letter (a dash, "[-]"): none
    for x in a.slice(2) { if _sch-is-style(x) { style = x } else if x != none and _net-key(x).match(regex("\\w")) != none { label = x } }
    edges.push((u: u, v: v, label: if type(label) == str { [#label] } else { label }, style: _sch-style(style)))
  }
  // the arrows' directions without a loop: an arrow that closes one with the arrows given
  // before it (a government named by those it answers to) laid the other way, between the same
  // layers, its head where it is
  let back = edges.map(_ => false)
  let kept = ()
  for (k, e) in edges.enumerate() {
    let (seen, todo, found) = ((e.v,), (e.v,), false)
    while todo.len() > 0 and not found {
      let at = todo.pop()
      if at == e.u { found = true }
      for (a, b) in kept { if a == at and b not in seen { seen.push(b); todo.push(b) } }
    }
    back.at(k) = found
    kept.push(if found { (e.v, e.u) } else { (e.u, e.v) })
  }
  let dag = edges.enumerate().map(((k, e)) => if back.at(k) { (e.v, e.u) } else { (e.u, e.v) })
  let size = text.size / 1pt
  let bodies = names.map(k => {
    let b = boxes.at(k)
    if type(b) == str { [#b] } else { b }
  })
  let framed(body, most) = {
    let width = calc.max(most, _longest-word(body))
    let inner = if measure(body).width <= width { body } else {
      block(width: width, align(center, { show regex("\\w\\("): it => it.text.clusters().first() + sym.zws + "("; body }))
    }
    box(stroke: 0.8pt, radius: 4pt, inset: (x: 5pt, y: 4pt), fill: white, align(center, inner))
  }
  // an arrow's words on it, in a white box, wrapped past 2.8 cm
  let labels = edges.map(e => if e.label == none { none } else {
    let inner = if measure(e.label).width <= 2.8cm { e.label } else {
      block(width: calc.max(2.8cm, _longest-word(e.label)), align(center, e.label))
    }
    box(fill: white, radius: 3pt, inset: (x: 3pt, y: 2pt), inner)
  })
  let label-dims = labels.map(l => if l == none { (0, 0) } else {
    let m = measure(l)
    (m.width / 1pt, m.height / 1pt)
  })
  // a layout: its layers (at most `cap` boxes each), its boxes wrapped at `most`
  let ordered = (4, 3, 2).map(cap => {
    let (layer-of, chains) = _sch-layers(n, dag, cap)
    (layer-of, chains) + _sch-order(layer-of, chains)
  })
  let laid(cap, most) = {
    let (layer-of, chains, layers, up, down) = ordered.at(4 - cap)
    let count = layer-of.len()
    let worded = range(count).map(_ => none)
    // an arrow's words kept room at its middle, where they go: in the gap of an arrow to the
    // next layer, beside the boxes of the layer a longer one crosses
    for (k, chain) in chains.enumerate() { if labels.at(k) != none { worded.at(chain.at(int(chain.len() / 2))) = k } }
    let framed-boxes = bodies.map(b => framed(b, most))
    let dims = range(count).map(v => if v < n {
      let m = measure(framed-boxes.at(v))
      (m.width / 1pt, m.height / 1pt)
    } else if worded.at(v) != none { label-dims.at(worded.at(v)) } else { (0, 0) })
    let solid(v) = v < n or worded.at(v) != none
    let gap(a, b) = if a < n and b < n { 1.6 * size } else if solid(a) and solid(b) { 0.8 * size } else if a < n or b < n { 1.2 * size } else if solid(a) or solid(b) { 0.6 * size } else { 0.5 * size }
    // x: packed, then each node at its neighbours' middle as near as its layer leaves room
    let x = range(count).map(_ => 0.0)
    for l in layers {
      let at = 0.0
      for (i, v) in l.enumerate() {
        if i > 0 { at += dims.at(l.at(i - 1)).at(0) / 2 + gap(l.at(i - 1), v) + dims.at(v).at(0) / 2 }
        x.at(v) = at
      }
      for v in l { x.at(v) -= at / 2 }
    }
    for round in range(12) {
      let order = if calc.even(round) { range(layers.len()) } else { range(layers.len()).rev() }
      for r in order {
        let l = layers.at(r)
        if l.len() == 0 { continue }
        let want = l.map(v => {
          let ns = up.at(v) + down.at(v)
          if ns.len() == 0 { x.at(v) } else { ns.map(w => x.at(w)).sum() / ns.len() }
        })
        let offset = (0.0,)
        for i in range(1, l.len()) {
          offset.push(offset.at(-1) + dims.at(l.at(i - 1)).at(0) / 2 + gap(l.at(i - 1), l.at(i)) + dims.at(l.at(i)).at(0) / 2)
        }
        let fitted = _sch-pav(range(l.len()).map(i => want.at(i) - offset.at(i)))
        for (i, v) in l.enumerate() { x.at(v) = fitted.at(i) + offset.at(i) }
      }
    }
    let left = calc.min(..range(count).map(v => x.at(v) - dims.at(v).at(0) / 2))
    x = x.map(c => c - left)
    let width = calc.max(..range(count).map(v => x.at(v) + dims.at(v).at(0) / 2))
    let heights = layers.map(l => calc.max(0, ..l.map(v => dims.at(v).at(1))))
    // between a layer of boxes and one of words: room for the arrows to slant
    let height = heights.sum() + (layers.len() - 1) * 1.1 * size
    (layers: layers, chains: chains, up: up, down: down, x: x, dims: dims, width: width, height: height, heights: heights, framed: framed-boxes, count: count, worded: worded)
  }
  // the layout whose text is the largest once fitted to a card (its boxes the widest, the
  // fewest layers, when several are as large)
  let shown(w, h) = size * calc.min(1, _sch-card.at(0) / w, _sch-card.at(1) / h)
  let best = none
  let best-px = -1
  for cap in (4, 3, 2) {
    for most in (4.5cm, 4cm, 3.5cm, 3cm, 2.5cm, 2cm) {
      let l = laid(cap, most)
      let px = shown(l.width, l.height)
      if px > best-px + 0.05 { (best, best-px) = (l, px) }
    }
  }
  let (layers, chains, x, dims, heights, worded) = (best.layers, best.chains, best.x, best.dims, best.heights, best.worded)
  let count = best.count
  let rank = range(count).map(v => layers.position(l => v in l))
  let center(r) = ((r.at(0) + r.at(2)) / 2, (r.at(1) + r.at(3)) / 2)
  let quad(p, c, q, t) = (
    (1 - t) * (1 - t) * p.at(0) + 2 * (1 - t) * t * c.at(0) + t * t * q.at(0),
    (1 - t) * (1 - t) * p.at(1) + 2 * (1 - t) * t * c.at(1) + t * t * q.at(1),
  )
  let along(path, t) = {
    let (p, c, q) = path
    if c == none { (p.at(0) + t * (q.at(0) - p.at(0)), p.at(1) + t * (q.at(1) - p.at(1))) } else { quad(p, c, q, t) }
  }
  let sample(path) = if path.at(1) == none { (path.at(0), path.at(2)) } else { range(17).map(i => along(path, i / 16)) }
  // within the boxes' width (an arrow's own half a letter past it is still drawn whole)
  let inside(pts) = pts.all(pt => pt.at(0) >= -size / 2 and pt.at(0) <= best.width + size / 2)
  let clear-of(pts, rects) = range(pts.len() - 1).all(i => rects.all(r => not _sch-hits(pts.at(i), pts.at(i + 1), r)))
  // the gap each arrow's words go in: its middle's
  let gap-of = edges.map(e => int((rank.at(e.u) + rank.at(e.v)) / 2))
  // the layout with `extra` more between each two layers: the boxes, each arrow straight from its
  // box's side to the other's (a curve bowing round a box in its way, never an elbow), its
  // words on it where nothing else is; whether every word found such a place
  let place-all(extra, within, staggered) = {
    let tops = (0,)
    for r in range(1, layers.len()) { tops.push(tops.at(-1) + heights.at(r - 1) + 1.1 * size + extra.at(r - 1)) }
    let total-h = best.height + extra.sum(default: 0)
    let flip(y) = if flow == "up" { total-h - y } else { y }
    let cy(v) = tops.at(rank.at(v)) + heights.at(rank.at(v)) / 2
    let rects = range(n).map(v => {
      let (w, h) = dims.at(v)
      (x.at(v) - w / 2, flip(cy(v)) - h / 2, x.at(v) + w / 2, flip(cy(v)) + h / 2)
    })
    // each arrow leaves the side of its box that faces the other box, enters the other's
    // facing side
    let sides = edges.map(e => if center(rects.at(e.v)).at(1) > center(rects.at(e.u)).at(1) { ("bottom", "top") } else { ("top", "bottom") })
    // the arrows on one side of a box spread along it, in the order of their other ends, so
    // that they never cross there; two between the same boxes side by side
    let port = (:)
    for b in range(n) {
      for side in ("top", "bottom") {
        let segs = ()
        for (k, e) in edges.enumerate() {
          if e.u == b and sides.at(k).at(0) == side { segs.push((k, "s", center(rects.at(e.v)).at(0))) }
          if e.v == b and sides.at(k).at(1) == side { segs.push((k, "t", center(rects.at(e.u)).at(0))) }
        }
        let segs = segs.sorted(key: s => s.at(2) * 1000 + s.at(0))
        let m = segs.len()
        let r = rects.at(b)
        let w = r.at(2) - r.at(0)
        let step = if m < 2 { 0 } else { calc.min(1.6 * size, (w - 10) / (m - 1)) }
        let y = if side == "top" { r.at(1) } else { r.at(3) }
        for (i, sg) in segs.enumerate() {
          port.insert(str(sg.at(0)) + sg.at(1), ((r.at(0) + r.at(2)) / 2 + (i - (m - 1) / 2) * step, y))
        }
      }
    }
    // straight, or one curve bowing round the boxes in its way: its middle moved aside, the
    // least that clears them
    let paths = ()
    for (k, e) in edges.enumerate() {
      let (p, q) = (port.at(str(k) + "s"), port.at(str(k) + "t"))
      // the other boxes, and its own two too (a curve must leave them outwards)
      let others = range(n).map(b => if b == e.u or b == e.v { _sch-grow(rects.at(b), -1) } else { _sch-grow(rects.at(b), 3) })
      let ctrl = none
      // across a layer of boxes: through the room the ordering kept it there (its words' when it
      // has some), when that clears the boxes
      let chain = best.chains.at(k)
      if chain.len() > 3 and (labels.at(k) != none or not clear-of((p, q), others)) {
        let m = chain.at(int(chain.len() / 2))
        let (mx, my) = (x.at(m), flip(cy(m)))
        let c = (2 * mx - (p.at(0) + q.at(0)) / 2, 2 * my - (p.at(1) + q.at(1)) / 2)
        let sm = sample((p, c, q))
        if clear-of(sm, others) and inside(sm) { ctrl = c }
      }
      if ctrl == none and not clear-of((p, q), others) {
        let mid = ((p.at(0) + q.at(0)) / 2, (p.at(1) + q.at(1)) / 2)
        let (dx, dy) = (q.at(0) - p.at(0), q.at(1) - p.at(1))
        let l = calc.max(1, calc.sqrt(dx * dx + dy * dy))
        let nrm = (-dy / l, dx / l)
        // the least bow that clears them, within the drawing's width if one does
        let kept = none
        for d in (15, 25, 40, 60, 85, 115, 150, 200) {
          for sd in (1, -1) {
            if kept != none { continue }
            let c = (mid.at(0) + sd * 2 * d * nrm.at(0), mid.at(1) + sd * 2 * d * nrm.at(1))
            let sm = sample((p, c, q))
            if not clear-of(sm, others) { continue }
            if ctrl == none { ctrl = c }
            if inside(sm) { kept = c }
          }
        }
        if kept != none { ctrl = kept }
      }
      paths.push((p, ctrl, q))
    }
    // two arrows between the same boxes (one each way, or two the same way): the first
    // straight, the second bowed aside by the room its words and the first's take (less where
    // that meets a box), to the side where it crosses the fewest other arrows
    let cross(a, b) = {
      let d(p, q, r) = (q.at(0) - p.at(0)) * (r.at(1) - p.at(1)) - (q.at(1) - p.at(1)) * (r.at(0) - p.at(0))
      let count = 0
      for i in range(a.len() - 1) {
        for j in range(b.len() - 1) {
          let (p, q, r, t) = (a.at(i), a.at(i + 1), b.at(j), b.at(j + 1))
          if d(p, q, r) * d(p, q, t) < 0 and d(r, t, p) * d(r, t, q) < 0 { count += 1 }
        }
      }
      count
    }
    for (k, e) in edges.enumerate() {
      let first = edges.enumerate().find(((j, f)) => j < k and ((f.u == e.u and f.v == e.v) or (f.u == e.v and f.v == e.u)))
      if first == none { continue }
      let (j, f) = first
      let (p, _, q) = paths.at(k)
      // the other boxes, and its own two too (a curve must leave them outwards)
      let others = range(n).map(b => if b == e.u or b == e.v { _sch-grow(rects.at(b), -1) } else { _sch-grow(rects.at(b), 3) })
      let mid = ((p.at(0) + q.at(0)) / 2, (p.at(1) + q.at(1)) / 2)
      let (dx, dy) = (q.at(0) - p.at(0), q.at(1) - p.at(1))
      let l = calc.max(1, calc.sqrt(dx * dx + dy * dy))
      let room = (label-dims.at(k).at(0) + label-dims.at(j).at(0)) / 2 + 8
      let tried = ()
      for d in (room, room * 0.8, room * 0.6, room * 0.45, room * 0.3) {
        for sd in (1, -1) {
          let c = (mid.at(0) - sd * 2 * d * dy / l, mid.at(1) + sd * 2 * d * dx / l)
          let sm = sample((p, c, q))
          if not clear-of(sm, others) { continue }
          let crossings = range(paths.len()).filter(i => i != k).map(i => cross(sm, sample(paths.at(i)))).sum()
          let out = if inside(sm) { 0 } else { 1 }
          tried.push((out * 100000 + crossings * 1000 - d, c))
        }
      }
      if tried.len() > 0 { paths.at(k) = (p, tried.sorted(key: t => t.at(0)).first().at(1), q) }
    }
    let samples = paths.map(sample)
    // each arrow's words on it, near its middle, clear of the boxes, the other words and the
    // other arrows
    let words = edges.map(_ => none)
    // staggered, the words of one gap, from left to right, one higher and the next lower on
    // their arrows, where side by side they meet
    let sharing = range(edges.len()).map(k => range(edges.len())
      .filter(j => labels.at(j) != none and gap-of.at(j) == gap-of.at(k))
      .sorted(key: j => along(paths.at(j), 0.5).at(0)))
    let placed = ()
    let failed = ()
    for (k, e) in edges.enumerate() {
      if labels.at(k) == none { continue }
      let (lw, lh) = label-dims.at(k)
      let at(t) = {
        let m = along(paths.at(k), t)
        (m.at(0) - lw / 2, m.at(1) - lh / 2, m.at(0) + lw / 2, m.at(1) + lh / 2)
      }
      let found = none
      let crossing = none
      let near = none
      let first = if not staggered { 0.5 } else if calc.even(sharing.at(k).position(j => j == k)) { 0.36 } else { 0.64 }
      let ts = (0, -0.06, 0.06, -0.12, 0.12, -0.18, 0.18, -0.24, 0.24, -0.3, 0.3).map(d => first + d).filter(t => t >= 0.15 and t <= 0.85)
      for t in ts {
        if found != none { continue }
        let r = at(t)
        if within and (r.at(0) < 0 or r.at(2) > best.width) { continue }
        let g = _sch-grow(r, 2)
        // a bit of its line seen on either side, its head too
        let ends = _sch-grow(r, 1.2 * size)
        let alone = rects.all(b => not _sch-meet(g, b)) and placed.all(o => not _sch-meet(g, o))
        let apart = alone and (paths.at(k).first(), paths.at(k).last()).all(p => not _sch-meet(ends, (p.at(0), p.at(1), p.at(0), p.at(1))))
        if alone and near == none { near = r }
        if apart and crossing == none { crossing = r }
        if apart and samples.enumerate().all(((j, sm)) => j == k or clear-of(sm, (r,))) { found = r }
      }
      if found == none {
        failed.push(k)
        // no room: over another arrow, its white ground hiding it there, or nearer an end,
        // never over words or a box
        found = if crossing != none { crossing } else if near != none { near } else { at(0.5) }
      }
      placed.push(found)
      words.at(k) = (found, labels.at(k))
    }
    (rects: rects, paths: paths, samples: samples, words: words, ok: failed.len() == 0, failed: failed, height: total-h, extra: extra)
  }
  let laid = none
  // more room only between the layers whose arrows found none for their words; when room
  // never comes, the layout where the fewest words lie over another arrow, the lowest
  let extra = range(layers.len() - 1).map(_ => 0)
  let tried = none
  for _ in range(8) {
    if tried != none and tried.ok { continue }
    // its words within the boxes' width, or past it when they find no room there
    for (within, staggered) in ((true, false), (false, false), (true, true), (false, true)) {
      if tried != none and tried.ok and tried.extra == extra { continue }
      let these = place-all(extra, within, staggered)
      if tried == none or tried.extra != extra or these.failed.len() < tried.failed.len() { tried = these }
    }
    if laid == none or tried.failed.len() < laid.failed.len() { laid = tried }
    // the gap at the middle of each such arrow, where its words go
    for g in tried.failed.map(k => gap-of.at(k)).dedup() { extra.at(calc.min(g, extra.len() - 1)) += 0.8 * size }
  }
  // everything within the drawing: a curve or a word past its edges moves it all
  let pts = laid.rects.map(r => ((r.at(0), r.at(1)), (r.at(2), r.at(3)))).flatten().chunks(2)
  for sm in laid.samples { pts += sm }
  for w in laid.words { if w != none { pts += ((w.at(0).at(0), w.at(0).at(1)), (w.at(0).at(2), w.at(0).at(3))) } }
  let (x0, y0) = (calc.min(0, ..pts.map(p => p.at(0))), calc.min(0, ..pts.map(p => p.at(1))))
  let (x1, y1) = (calc.max(best.width, ..pts.map(p => p.at(0))), calc.max(laid.height, ..pts.map(p => p.at(1))))
  let mv(p) = (p.at(0) - x0, p.at(1) - y0)
  let mr(r) = (r.at(0) - x0, r.at(1) - y0, r.at(2) - x0, r.at(3) - y0)
  (
    width: x1 - x0,
    height: y1 - y0,
    boxes: range(n).map(v => (mr(laid.rects.at(v)), best.framed.at(v))),
    words: laid.words.map(w => if w == none { none } else { (mr(w.at(0)), w.at(1)) }),
    // from the arrow's own start to its end: its points (two when straight, along it when it
    // bows), its style, its curve (start, control or none, end)
    arrows: edges.enumerate().map(((k, e)) => (
      laid.samples.at(k).map(mv),
      e.style,
      laid.paths.at(k).map(p => if p == none { none } else { mv(p) }),
    )),
  )
}
#let scheme(boxes: (:), arrows: (), flow: "down") = context {
  let laid = _sch-layout(boxes, arrows, flow)
  let pt(p) = (p.at(0) * 1pt, p.at(1) * 1pt)
  // a head readable at a card's size, its line ending under it
  let head = 7.5
  box(width: laid.width * 1pt, height: laid.height * 1pt, {
    for (pts, style, path) in laid.arrows {
      let (p, c, q) = path
      let stroke = (thickness: 1.1pt, dash: style.dash)
      if c == none {
        place(top + left, curve(stroke: stroke, curve.move(pt(p)), curve.line(pt(q))))
      } else {
        place(top + left, curve(stroke: stroke, curve.move(pt(p)), curve.quad(pt(c), pt(q))))
      }
      for (on, tip, from) in ((style.end, q, if c == none { p } else { c }), (style.start, p, if c == none { q } else { c })) {
        if not on { continue }
        let (ux, uy) = (tip.at(0) - from.at(0), tip.at(1) - from.at(1))
        let l = calc.sqrt(ux * ux + uy * uy)
        if l == 0 { continue }
        let (ux, uy) = (ux / l, uy / l)
        let base = (tip.at(0) - ux * head, tip.at(1) - uy * head)
        place(top + left, polygon(fill: black, stroke: none, pt(tip),
          pt((base.at(0) - uy * head * 0.45, base.at(1) + ux * head * 0.45)),
          pt((base.at(0) + uy * head * 0.45, base.at(1) - ux * head * 0.45))))
      }
    }
    // its words on it, on a white ground the line goes under
    for w in laid.words {
      if w != none { place(top + left, dx: w.at(0).at(0) * 1pt, dy: w.at(0).at(1) * 1pt, w.at(1)) }
    }
    for (r, framed) in laid.boxes { place(top + left, dx: r.at(0) * 1pt, dy: r.at(1) * 1pt, framed) }
  })
}
// ---- What the AI writes, from here (the rule's example: everything above is given)
#diagram(node-stroke: 0.8pt, spacing: 2em,
  node((0, 0), [Évaporation]), edge("-|>"),
  node((1, 0), [Condensation]), edge("-|>"),
  node((1, 1), [Précipitations]), edge("-|>"),
  node((0, 1), [Ruissellement]),
  edge((0, 1), (0, 0), "-|>"),
)
