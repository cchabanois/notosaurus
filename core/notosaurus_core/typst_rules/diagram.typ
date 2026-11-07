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
  fletcher.diagram(..items, ..args.named(), spacing: (need-x, need-y))
}
// ---- What the AI writes, from here (the rule's example: everything above is given)
#diagram(node-stroke: 0.8pt, spacing: 2em,
  node((0, 0), [Évaporation]), edge("-|>"),
  node((1, 0), [Condensation]), edge("-|>"),
  node((1, 1), [Précipitations]),
)
