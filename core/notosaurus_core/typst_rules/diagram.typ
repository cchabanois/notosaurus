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
// ---- What the AI writes, from here (the rule's example: everything above is given)
#diagram(node-stroke: 0.8pt, spacing: 2em,
  node((0, 0), [Évaporation]), edge("-|>"),
  node((1, 0), [Condensation]), edge("-|>"),
  node((1, 1), [Précipitations]),
)
