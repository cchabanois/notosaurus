#set page(width: auto, height: auto, margin: 6pt)
#import "@preview/alchemist:0.2.0": *
#import "@preview/alchemist:0.2.0" as _alchemist
// A Lewis structure's non-bonding pairs: their directions computed from the atom's bonds,
// never chosen by eye (an O at the bottom, its bonds going up: its pairs set on them, 2
// times in 3). `pairs(2)` gives an atom its pairs, directionless; `skeletize` below finds
// the directions each atom's bonds leave it in (the bond coming in, those going out, its
// branches': as alchemist turns `angle: n`, `absolute:`, `relative:`), then spreads the
// pairs in the widest gaps they leave, evenly (water's O at the bottom: down-left and
// down-right). A mark written with an angle keeps it, unless it lies on a bond (then it is
// placed as a pair). An atom in a ring is left as written (its bonds' angles are the ring's).
#let pairs(n, kind: lewis-line) = range(n).map(_ => kind())

#let _deg(a) = if type(a) == angle { a.deg() } else { a }
#let _turn(a) = calc.rem(calc.rem(a, 360) + 360, 360)
#let _apart(a, b) = { let d = calc.abs(_turn(a) - _turn(b)); calc.min(d, 360 - d) }
#let _link-angle(link, rel, default) = {
  if "relative" in link { _deg(link.relative) + rel } else if "absolute" in link { _deg(link.absolute) } else if (
    "angle" in link
  ) { link.angle * 45 } else { default }
}

// n directions in the gaps the taken ones leave: each pair to the gap whose parts are the
// widest, every gap then cut in equal parts
#let _free(taken, n) = {
  if n == 0 { return () }
  let t = taken.map(_turn).sorted().dedup()
  if t.len() == 0 { return range(n).map(i => _turn(90 + 360 * i / n)) }
  let gaps = range(t.len()).map(i => (
    t.at(i),
    if t.len() == 1 { 360 } else { _turn(t.at(calc.rem(i + 1, t.len())) - t.at(i)) },
  ))
  let k = gaps.map(_ => 0)
  for _ in range(n) {
    let best = 0
    for i in range(gaps.len()) {
      if gaps.at(i).at(1) / (k.at(i) + 1) > gaps.at(best).at(1) / (k.at(best) + 1) + 1e-6 { best = i }
    }
    k.at(best) += 1
  }
  let out = ()
  for i in range(gaps.len()) {
    let (start, size) = gaps.at(i)
    for j in range(1, k.at(i) + 1) { out.push(_turn(start + size * j / (k.at(i) + 1))) }
  }
  out
}

// The atom's marks placed: those without an angle, or on a bond, in the free directions
#let _placed(fragment, bonds) = {
  let marks = fragment.at("lewis", default: ())
  if marks.len() == 0 { return fragment }
  let fixed = marks.map(m => m.angle != none and bonds.all(b => _apart(_deg(m.angle), b) >= 30))
  let taken = bonds + marks.zip(fixed).filter(((m, f)) => f).map(((m, _)) => _deg(m.angle))
  let free = _free(taken, fixed.filter(f => not f).len())
  let i = 0
  let out = ()
  for (m, f) in marks.zip(fixed) {
    if f { out.push(m) } else {
      out.push((..m, angle: free.at(i) * 1deg))
      i += 1
    }
  }
  (..fragment, lewis: out)
}

// A list of elements (a skeleton, a branch's body): each element's bond angle known as
// alchemist reckons it (rel: the last bond's angle, default: the angle a bond takes unsaid)
#let _with-pairs(body, rel, default) = {
  if type(body) != array { return body }
  let angles = ()  // a bond's angle; a branch's first bond's; none otherwise
  let out = ()
  for el in body {
    let kind = if type(el) == dictionary { el.at("type", default: none) } else { none }
    if kind == "link" {
      let a = _link-angle(el, rel, default)
      rel = a
      angles.push(a)
      out.push(el)
    } else if kind == "branch" {
      let ba = _link-angle(el.args, rel, default)
      let first = el.body.find(e => type(e) == dictionary and e.at("type", default: none) == "link")
      angles.push(if first == none { none } else { _link-angle(first, rel, ba) })
      out.push((..el, body: _with-pairs(el.body, rel, ba)))
    } else {
      angles.push(none)
      out.push(el)
    }
  }
  for i in range(out.len()) {
    let el = out.at(i)
    if type(el) != dictionary or el.at("type", default: none) != "fragment" { continue }
    if el.at("lewis", default: ()).len() == 0 { continue }
    let bonds = ()
    if i > 0 and out.at(i - 1).at("type", default: none) == "link" { bonds.push(angles.at(i - 1) + 180) }
    let j = i + 1
    while j < out.len() {
      let kind = out.at(j).at("type", default: none)
      if kind == "branch" {
        if angles.at(j) != none { bonds.push(angles.at(j)) }
      } else if kind == "link" {
        bonds.push(angles.at(j))
        break
      } else if kind == "fragment" or kind == "cycle" { break }
      j += 1
    }
    out.at(i) = _placed(el, bonds)
  }
  out
}

#let skeletize(..args) = _alchemist.skeletize(..args.named(), _with-pairs(args.pos().at(0), 0, 0))
#let draw-skeleton(..args) = _alchemist.draw-skeleton(..args.named(), _with-pairs(args.pos().at(0), 0, 0))
// ---- What the AI writes, from here (the rule's example: everything above is given)
#skeletize({
  fragment("CH_3")
  single()
  fragment("CH_2")
  single()
  fragment("OH")
})
