#set page(width: auto, height: auto, margin: 6pt)
#import "@preview/alchemist:0.2.0": *
#import "@preview/alchemist:0.2.0" as _alchemist
#import "common.typ": *
// A Lewis structure's non-bonding pairs: their directions computed from the atom's bonds,
// never chosen by eye (an O at the bottom, its bonds going up: its pairs set on them, 2
// times in 3). `pairs(2)` gives an atom its pairs, directionless; `skeletize` below finds
// the directions each atom's bonds leave it in (the bond coming in, those going out, its
// branches': as alchemist turns `angle: n`, `absolute:`, `relative:`), then spreads the
// pairs in the widest gaps they leave, evenly (water's O at the bottom: down-left and
// down-right). A mark written with an angle keeps it, unless it lies on a bond (then it is
// placed as a pair). An atom in a ring is left as written (its bonds' angles are the ring's).
// A link drawn dashed or dotted (a hydrogen bond, an interaction) is no bond its pairs avoid:
// they face it, centred on it, 60° apart (the H of a hydrogen bond arriving between the O's two
// pairs, as textbooks draw it), within the gap its bonds leave there.
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

// A link drawn dashed or dotted: an interaction, not a bond
#let _dashed(link) = {
  let s = link.at("stroke", default: none)
  if type(s) == dictionary { s.at("dash", default: none) not in (none, "solid") } else if type(s) == stroke {
    s.dash not in (none, auto, "solid")
  } else { false }
}

// n directions centred on t, 60° apart, within the gap the bonds leave around t
#let _facing(t, bonds, n) = {
  let t = _turn(t)
  let cw = bonds.map(b => _turn(t - b)).fold(360, calc.min)  // room on the clockwise side
  let ccw = bonds.map(b => _turn(b - t)).fold(360, calc.min)
  let room = calc.min(cw, ccw)
  let step = if n < 2 { 0 } else { calc.min(60, 2 * (room - 30) / (n - 1)) }
  range(n).map(j => _turn(t + (j - (n - 1) / 2) * step))
}

// The atom's marks placed: those without an angle, or on a bond, in the free directions;
// facing an interaction when one arrives (`toward`)
#let _placed(fragment, bonds, toward: ()) = {
  let marks = fragment.at("lewis", default: ())
  if marks.len() == 0 { return fragment }
  let fixed = marks.map(m => m.angle != none and bonds.all(b => _apart(_deg(m.angle), b) >= 30))
  let taken = bonds + marks.zip(fixed).filter(((m, f)) => f).map(((m, _)) => _deg(m.angle))
  let loose = fixed.filter(f => not f).len()
  let free = if toward.len() > 0 { _facing(toward.at(0), taken, loose) } else { _free(taken, loose) }
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
  let dashed = ()  // whether that bond is an interaction (dashed, dotted)
  let out = ()
  for el in body {
    let kind = if type(el) == dictionary { el.at("type", default: none) } else { none }
    if kind == "link" {
      let a = _link-angle(el, rel, default)
      rel = a
      angles.push(a)
      dashed.push(_dashed(el))
      out.push(el)
    } else if kind == "branch" {
      let ba = _link-angle(el.args, rel, default)
      let first = el.body.find(e => type(e) == dictionary and e.at("type", default: none) == "link")
      angles.push(if first == none { none } else { _link-angle(first, rel, ba) })
      dashed.push(first != none and _dashed(first))
      out.push((..el, body: _with-pairs(el.body, rel, ba)))
    } else {
      angles.push(none)
      dashed.push(false)
      out.push(el)
    }
  }
  for i in range(out.len()) {
    let el = out.at(i)
    if type(el) != dictionary or el.at("type", default: none) != "fragment" { continue }
    if el.at("lewis", default: ()).len() == 0 { continue }
    let around = ()  // (angle, dashed) of each link at the atom
    if i > 0 and out.at(i - 1).at("type", default: none) == "link" { around.push((angles.at(i - 1) + 180, dashed.at(i - 1))) }
    let j = i + 1
    while j < out.len() {
      let kind = out.at(j).at("type", default: none)
      if kind == "branch" {
        if angles.at(j) != none { around.push((angles.at(j), dashed.at(j))) }
      } else if kind == "link" {
        around.push((angles.at(j), dashed.at(j)))
        break
      } else if kind == "fragment" or kind == "cycle" { break }
      j += 1
    }
    let bonds = around.filter(((_, d)) => not d).map(((a, _)) => a)
    let toward = around.filter(((_, d)) => d).map(((a, _)) => a)
    out.at(i) = _placed(el, bonds, toward: toward)
  }
  out
}

// A molecule's polarity on the molecule alchemist draws, its atoms designated by their
// fragments' names (fragment("O", name: "O")): partial charges, a bond angle, the molecule's
// dipole moment, a bond's polarisation. Each is computed from where alchemist put the atoms
// and their bonds, never placed by eye: a charge on its atom's free side, opposite its bonds;
// an angle's arc inside the angle, its value inside it; the dipole moment from the charges
// (their barycentres), drawn beside the molecule, parallel to it, clear of everything.
// What the AI writes into skeletize is kept apart (skeletize below) and laid out once the
// molecule is drawn, all together, so that no label lands on a bond, an atom or another label.
#let _mark(kind, ..fields) = ((type: "polarity", kind: kind, ..fields.named()),)
// a partial charge, "δ+", "δ-", "2δ-" (or $delta^+$…), on an atom or on each of several
#let charge(atom, label) = _mark("charge", atoms: if type(atom) == array { atom } else { (atom,) }, label: label)
// the angle between the bonds center–a and center–b, its value `label`
#let bond-angle(a, center, b, label) = _mark("angle", a: a, center: center, b: b, label: label)
// the molecule's dipole moment, from its charges: from the negative pole towards the positive
// one (from: "negative", physics' convention) or the other way (from: "positive"); a null
// moment drawn as nothing, or written p = 0 (zero: true)
#let dipole(from: "negative", zero: false, name: $arrow(p)$) = {
  assert(from in ("negative", "positive"), message: "dipole's from is \"negative\" or \"positive\"")
  _mark("dipole", from: from, zero: zero, name: name)
}
// a bond's polarisation, an arrow beside the bond from a towards b, crossed at its tail
#let bond-dipole(a, b, crossed: true) = _mark("bond-dipole", a: a, b: b, crossed: crossed)

// A charge's label, as a string ("2δ-"), its formula, or its formula's content: its text
#let _label-text(c) = {
  if type(c) == str { return c }
  if type(c) in (int, float) { return str(c) }
  if type(c) != content { return "" }
  if c.has("text") { return c.text }
  if c.func() == math.attach {
    return _label-text(c.base) + _label-text(c.at("tr", default: none)) + _label-text(c.at("t", default: none))
  }
  if c.has("body") { return _label-text(c.body) }
  if c.has("children") { return c.children.map(_label-text).join() }
  if c.func() == symbol { return str(c) }
  ""
}
// its value: δ+ 1, 2δ- -2
#let _charge-value(label) = {
  let t = _label-text(label).replace("delta", "δ").replace(" ", "").replace(",", ".")
  // its sign, before or after it
  let signs = t.clusters().filter(c => c in ("+", "-", "−", "⁺", "⁻"))
  let found = t.replace(regex("[+\-−⁺⁻]"), "").match(regex("^([0-9]*\.?[0-9]*)(δ?)$"))
  assert(
    signs.len() == 1 and found != none,
    message: "a charge is \"δ+\", \"δ-\", \"2δ-\"…, not " + repr(_label-text(label)),
  )
  let (n, delta) = found.captures
  let plus = signs.at(0) in ("+", "⁺")
  let size = if n == "" { 1 } else { float(n) }
  (if plus { size } else { -size }, n, delta, plus)
}
// as drawn: n δ⁺
#let _charge-text(label) = {
  let (_, n, delta, plus) = _charge-value(label)
  let sign = if plus { $+$ } else { $-$ }
  if delta == "" { $#n^#sign$ } else { $#n delta^#sign$ }
}

// a label boxed to its ink (a superscript's sign rises above the line's top): measured and
// drawn so, nothing of it outside the room it was given
#let _tight(c) = text(top-edge: "bounds", bottom-edge: "bounds", box(c))

// What skeletize's body holds, our marks taken out: the body alchemist draws, the marks, each
// fragment's name (alchemist's own when it has none: "fragment-<n>") and its Lewis pairs' angles
#let _split(body, id: 0) = {
  let (kept, marks, frags) = ((), (), ())
  if type(body) != array { body = (body,) }
  for e in body {
    if type(e) == dictionary and e.at("type", default: none) == "polarity" {
      marks.push(e)
      continue
    }
    if type(e) == dictionary and e.at("type", default: none) == "fragment" {
      let name = e.at("name", default: none)
      if name == none {
        name = "fragment-" + str(id)
        id += 1
      }
      frags.push((name: name, lewis: e.at("lewis", default: ()).map(l => {
        let a = l.at("angle", default: none)
        if a == none { 0deg } else if type(a) == angle { a } else { a * 1deg }
      })))
    }
    if type(e) == dictionary and type(e.at("body", default: none)) == array {
      let (k, m, f, i) = _split(e.body, id: id)
      e.body = k
      marks += m
      frags += f
      id = i
    }
    kept.push(e)
  }
  (kept, marks, frags, id)
}

// rectangles (x0, y0, x1, y1)
#let _centre(r) = ((r.at(0) + r.at(2)) / 2, (r.at(1) + r.at(3)) / 2)
#let _inside(p, r, m) = (
  p.at(0) > r.at(0) - m and p.at(0) < r.at(2) + m and p.at(1) > r.at(1) - m and p.at(1) < r.at(3) + m
)
#let _meet(r, s, m) = r.at(0) < s.at(2) + m and s.at(0) < r.at(2) + m and r.at(1) < s.at(3) + m and s.at(1) < r.at(3) + m
// where the ray from a rectangle's centre along u leaves it
#let _exit(r, u) = {
  let (hw, hh) = ((r.at(2) - r.at(0)) / 2, (r.at(3) - r.at(1)) / 2)
  let tx = if calc.abs(u.at(0)) < 1e-9 { 1e9 } else { hw / calc.abs(u.at(0)) }
  let ty = if calc.abs(u.at(1)) < 1e-9 { 1e9 } else { hh / calc.abs(u.at(1)) }
  _add(_centre(r), _mul(u, calc.min(tx, ty)))
}
// a label of size (w, h) set beside p, on the side u points to: its rectangle
#let _beside(p, u, size) = {
  let (w, h) = size
  let c = _add(p, _mul(u, calc.abs(u.at(0)) * w / 2 + calc.abs(u.at(1)) * h / 2))
  (c.at(0) - w / 2, c.at(1) - h / 2, c.at(0) + w / 2, c.at(1) + h / 2)
}
#let _points(a, b, step) = {
  let n = calc.max(2, calc.ceil(_len(_sub(b, a)) / step))
  range(n + 1).map(i => _add(a, _mul(_sub(b, a), i / n)))
}
// nothing in the way: no rectangle met, no point (a bond's, an arc's) inside, `m` apart
#let _clear(r, rects, points, m) = (
  rects.all(s => not _meet(r, s, m)) and points.all(p => not _inside(p, r, m))
)
// an angle brought within (-180°, 180°]
#let _wrap(a) = {
  let d = calc.rem(a.deg() + 540, 360) - 180
  if d <= -180 { d += 360 }
  d * 1deg
}

// Where everything goes, computed from the molecule as alchemist drew it (cetz's context):
// the atoms (their rectangles), the bonds (each from atom to atom), then the marks laid out
// in turn, the angles first, then the charges, the bonds' arrows, the dipole moment last,
// each clear of what is already there
#let _layout(ctx, marks, frags) = {
  let em = cetz.util.resolve-number(ctx, 1em)
  let at(a) = { let p = cetz.coordinate.resolve(ctx, a).at(1); (p.at(0), p.at(1)) }
  let size(c) = { let m = measure(_tight(c)); (m.width / ctx.length, m.height / ctx.length) }
  let names = frags.map(f => f.name)
  let atoms = (:)
  for f in frags {
    if f.name in ctx.nodes {
      let (a, b) = (at(f.name + ".south-west"), at(f.name + ".north-east"))
      atoms.insert(f.name, (a.at(0), a.at(1), b.at(0), b.at(1)))
    }
  }
  let atom(n) = {
    assert(n in atoms, message: "no atom named " + repr(n) + ": name it, fragment(\"O\", name: \"O\")")
    atoms.at(n)
  }
  // the bonds: alchemist's links, each from its start's anchor to its end's (the atoms'
  // centres), drawn from its line's start to its end
  let bonds = ()
  for k in ctx.nodes.keys() {
    if k + "-end-anchor" in ctx.nodes and k not in names {
      let s = if k + "-start-anchor" in ctx.nodes { at(k + "-start-anchor") } else { at(k + ".start") }
      let e = at(k + "-end-anchor")
      let (ls, le) = (at(k + ".start"), at(k + ".end"))
      let ends = (s, e).map(p => names.find(n => n in atoms and _inside(p, atoms.at(n), 0.05 * em)))
      bonds.push((from: s, to: e, line: (ls, le), ends: ends))
    }
  }
  // the bonds leaving an atom: their directions
  let leaving(n) = bonds
    .map(b => if b.ends.at(0) == n { _unit(_sub(b.to, b.from)) } else if b.ends.at(1) == n {
      _unit(_sub(b.from, b.to))
    })
    .filter(d => d != none and d != (0, 0))
  // two atoms' points, at the bond between them when there is one
  let between(a, b) = {
    let found = bonds.find(x => x.ends == (a, b) or x.ends == (b, a))
    if found == none { (_centre(atom(a)), _centre(atom(b))) } else if found.ends.at(0) == a {
      (found.from, found.to)
    } else { (found.to, found.from) }
  }

  // what is drawn so far: rectangles (atoms, labels) and points (bonds, Lewis pairs, arcs)
  let rects = atoms.values()
  let points = ()
  for b in bonds { points += _points(..b.line, 0.1 * em) }
  for f in frags {
    if f.name not in atoms { continue }
    for a in f.lewis {
      let u = _dir(a)
      let t = (-u.at(1), u.at(0))
      // alchemist sets a pair on an ellipse round the atom: the band it may be in
      for out in (0.1, 0.25, 0.4, 0.55) {
        let p = _add(_exit(atoms.at(f.name), u), _mul(u, out * em))
        points += _points(_add(p, _mul(t, -0.4 * em)), _add(p, _mul(t, 0.4 * em)), 0.1 * em)
      }
    }
  }

  let angles = ()
  for m in marks.filter(m => m.kind == "angle") {
    let (c, pa) = between(m.center, m.a)
    let (_, pb) = between(m.center, m.b)
    let (ua, ub) = (_unit(_sub(pa, c)), _unit(_sub(pb, c)))
    let start = _angle(ua)
    let delta = _wrap(_angle(ub) - start)
    let box = atom(m.center)
    let radius = _len(_sub((box.at(2), box.at(3)), _centre(box))) + 0.35 * em
    let arc = range(13).map(i => _add(c, _mul(_dir(start + delta * i / 12), radius)))
    let u = _dir(start + delta / 2)
    let shown = text(size: 0.8em, m.label)
    let s = size(shown)
    let spot = none
    for d in range(0, 20).map(i => radius + (0.15 + 0.15 * i) * em) {
      let r = _beside(_add(c, _mul(u, d)), u, s)
      if _clear(r, rects, points + arc, 0.12 * em) {
        spot = r
        break
      }
    }
    if spot == none { spot = _beside(_add(c, _mul(u, radius + 0.15 * em)), u, s) }
    rects.push(spot)
    points += arc
    angles.push((centre: c, start: start, delta: delta, radius: radius, label: shown, rect: spot))
  }

  let charges = ()
  for m in marks.filter(m => m.kind == "charge") {
    let (q, ..) = _charge-value(m.label)
    let label = _charge-text(m.label)
    let s = size(label)
    for n in m.atoms {
      let box = atom(n)
      let dirs = leaving(n)
      // opposite its bond, or in the widest gap between its bonds (the one nearest the top
      // when two are as wide)
      let free = if dirs.len() == 0 { 90deg } else if dirs.len() == 1 { _angle(_mul(dirs.at(0), -1)) } else {
        let ts = dirs.map(d => calc.rem(_angle(d).deg() + 360, 360)).sorted()
        let best = none
        for (i, t) in ts.enumerate() {
          let next = if i + 1 < ts.len() { ts.at(i + 1) } else { ts.at(0) + 360 }
          let mid = (t + next) / 2
          let score = calc.round(next - t, digits: 1) - calc.abs(_wrap(mid * 1deg - 90deg).deg()) / 1000
          if best == none or score > best.at(0) { best = (score, mid) }
        }
        best.at(1) * 1deg
      }
      let tries = ()
      for (j, gap) in (0.2, 0.4, 0.65, 0.95).enumerate() {
        for (k, turn) in (0, 15, -15, 30, -30, 45, -45, 60, -60, 75, -75, 90, -90).enumerate() {
          tries.push((cost: j * 2.5 + k, angle: free + turn * 1deg, gap: gap))
        }
      }
      let spot = none
      for t in tries.sorted(key: t => t.cost) {
        let u = _dir(t.angle)
        let r = _beside(_add(_exit(box, u), _mul(u, t.gap * em)), u, s)
        if _clear(r, rects, points, 0.06 * em) {
          spot = r
          break
        }
      }
      if spot == none { spot = _beside(_add(_exit(box, _dir(free)), _mul(_dir(free), 0.2 * em)), _dir(free), s) }
      rects.push(spot)
      charges.push((atom: n, value: q, at: _centre(box), label: label, rect: spot, free: free))
    }
  }

  let all-atoms = atoms.values().map(_centre)
  let middle = _mul(all-atoms.fold((0, 0), _add), 1 / calc.max(1, all-atoms.len()))
  let bond-arrows = ()
  for m in marks.filter(m => m.kind == "bond-dipole") {
    let (pa, pb) = between(m.a, m.b)
    let u = _unit(_sub(pb, pa))
    let l = _len(_sub(pb, pa))
    let (tail, head) = (_add(pa, _mul(u, 0.25 * l)), _add(pa, _mul(u, 0.75 * l)))
    let mid = _mul(_add(pa, pb), 0.5)
    let sides = ((-u.at(1), u.at(0)), (u.at(1), -u.at(0))).sorted(key: n => _dot(_sub(middle, mid), n))
    let found = none
    for d in range(12).map(i => (0.7 + 0.15 * i) * em) {
      for n in sides {
        let (t, h) = (_add(tail, _mul(n, d)), _add(head, _mul(n, d)))
        let line = _points(t, h, 0.1 * em)
        let ok = line.all(p => _clear((p.at(0), p.at(1), p.at(0), p.at(1)), rects, points, 0.3 * em))
        if ok {
          found = (t, h, n)
          break
        }
      }
      if found != none { break }
    }
    if found == none {
      let n = sides.at(0)
      found = (_add(tail, _mul(n, 0.7 * em)), _add(head, _mul(n, 0.7 * em)), n)
    }
    let (t, h, n) = found
    points += _points(t, h, 0.1 * em)
    bond-arrows.push((tail: t, head: h, side: n, crossed: m.crossed))
  }

  let moment = none
  let zero = none
  let wanted = marks.find(m => m.kind == "dipole")
  if wanted != none {
    let plus = charges.filter(c => c.value > 0)
    let minus = charges.filter(c => c.value < 0)
    assert(
      plus.len() > 0 and minus.len() > 0,
      message: "dipole() is computed from the charges: charge() on the molecule's atoms, δ+ and δ-",
    )
    let pole(cs) = _mul(cs.map(c => _mul(c.at, calc.abs(c.value))).fold((0, 0), _add), 1 / cs.map(c => calc.abs(c.value)).sum())
    let (gp, gm) = (pole(plus), pole(minus))
    let v = _sub(gp, gm)
    // everything drawn: its rectangles' corners and its points
    let every = points
    for r in rects { every += ((r.at(0), r.at(1)), (r.at(2), r.at(1)), (r.at(0), r.at(3)), (r.at(2), r.at(3))) }
    if _len(v) < 0.15 * em {
      if wanted.zero {
        let low = calc.min(..every.map(p => p.at(1)))
        let (left, right) = (calc.min(..every.map(p => p.at(0))), calc.max(..every.map(p => p.at(0))))
        let shown = $#wanted.name = arrow(0)$
        zero = (label: shown, rect: _beside(((left + right) / 2, low - 0.4 * em), (0, -1), size(shown)))
      }
    } else {
      let u = _unit(v)
      let options = ((-u.at(1), u.at(0)), (u.at(1), -u.at(0))).map(n => {
        let reach = calc.max(..every.map(p => _dot(_sub(p, gm), n)))
        // the right or below preferred, when both sides are as near
        (n: n, offset: reach + 0.55 * em, cost: reach - 0.3 * em * (n.at(0) - n.at(1)))
      })
      let side = options.sorted(key: o => o.cost).at(0)
      let half = calc.max(_len(v) / 2, 1.25 * em)
      let base = _add(_add(gm, _mul(side.n, side.offset)), _mul(u, _len(v) / 2))
      let (a, b) = (_add(base, _mul(u, -half)), _add(base, _mul(u, half)))
      let (tail, head) = if wanted.from == "negative" { (a, b) } else { (b, a) }
      let rect = _beside(_add(base, _mul(side.n, 0.2 * em)), side.n, size(wanted.name))
      moment = (tail: tail, head: head, side: side.n, label: wanted.name, rect: rect, from: wanted.from)
    }
  }
  (atoms: atoms, bonds: bonds, angles: angles, charges: charges, bond-arrows: bond-arrows, moment: moment, zero: zero)
}

#let _draw(marks, frags) = cetz.draw.get-ctx(ctx => {
  import cetz.draw: *
  let em = cetz.util.resolve-number(ctx, 1em)
  let l = _layout(ctx, marks, frags)
  let arrow = (end: "stealth", fill: black, scale: 0.8)
  for a in l.angles {
    arc(a.centre, start: a.start, delta: a.delta, radius: a.radius, anchor: "origin", stroke: 0.6pt)
    content(_centre(a.rect), _tight(a.label))
  }
  for c in l.charges { content(_centre(c.rect), _tight(c.label)) }
  for b in l.bond-arrows {
    line(b.tail, b.head, stroke: 0.8pt, mark: arrow)
    if b.crossed {
      let u = _unit(_sub(b.head, b.tail))
      let p = _add(b.tail, _mul(u, 0.3 * em))
      let n = (-u.at(1), u.at(0))
      line(_add(p, _mul(n, 0.25 * em)), _add(p, _mul(n, -0.25 * em)), stroke: 0.8pt)
    }
  }
  if l.moment != none {
    line(l.moment.tail, l.moment.head, stroke: 1pt, mark: arrow)
    content(_centre(l.moment.rect), _tight(l.moment.label))
  }
  if l.zero != none { content(_centre(l.zero.rect), _tight(l.zero.label)) }
})

// A molecule checked before it is drawn, its atoms and links as alchemist joins them (a link
// from the last atom to the next, a branch from the last atom, one written before any atom from
// the first): a hydrogen bond (a dashed or dotted link) goes from an H, bonded to N, O or F, to
// an atom with non-bonding pairs (N, O, F, or one written with `lewis:`), never between two
// other atoms; an atom written alone, without a charge, has no more bonds than its valence
// (H 1, O 2, N 3, C 4, F, Cl, Br, I 1: S and P, whose valence varies, unchecked; a double bond
// counts 2, a triple 3, a hydrogen bond 0). Groups ("OH", "CH_3"), ions ("O^+", "H_3O^+") and
// atoms of a ring left as written. Refused with what is wrong: the figure is asked again.
#let double(..args) = _alchemist.double(..args).map(e => (..e, bond-order: 2))
#let triple(..args) = _alchemist.triple(..args).map(e => (..e, bond-order: 3))
#let _VALENCE = (H: 1, O: 2, N: 3, C: 4, F: 1, Cl: 1, Br: 1, I: 1)
#let _ACCEPTORS = ("N", "O", "F")
// a fragment's atoms: (symbol, charged) each, from the content alchemist made of its text
#let _atom-of(c) = {
  if type(c) == array { c = c.at(0) }
  if type(c) != content { return ("", false) }
  if c.func() == math.equation { return _atom-of(c.body) }
  if c.func() == math.attach { return (_atom-of(c.base).at(0), c.has("t") or c.has("tr")) }
  if c.has("text") { return (c.text, false) }
  if c.has("children") { return (c.children.map(x => _atom-of(x).at(0)).join(), false) }
  ("", false)
}
// the molecule's atoms (symbols, charged, pairs, ring) and links (a, b, order, dashed)
#let _graph(body, atoms, links, cur, pend) = {
  if type(body) != array { body = (body,) }
  let blank = (symbols: (), charged: false, pairs: false, ring: false)  // a place, no atom written
  for el in body {
    let kind = if type(el) == dictionary { el.at("type", default: none) } else { none }
    if kind == "link" {
      if cur == none {
        atoms.push(blank)
        cur = atoms.len() - 1
      }
      if pend != none {
        atoms.push(blank)
        links.push((pend.from, atoms.len() - 1, pend.order, pend.dashed))
        cur = atoms.len() - 1
      }
      pend = (from: cur, order: el.at("bond-order", default: 1), dashed: _dashed(el))
    } else if kind == "fragment" {
      let found = el.at("atoms", default: ()).map(_atom-of)
      let atom = (
        symbols: found.map(f => f.at(0)),
        charged: found.any(f => f.at(1)),
        pairs: el.at("lewis", default: ()).len() > 0,
        ring: false,
      )
      if pend != none {
        atoms.push(atom)
        links.push((pend.from, atoms.len() - 1, pend.order, pend.dashed))
        pend = none
        cur = atoms.len() - 1
      } else if cur != none and atoms.at(cur).symbols.len() == 0 and not atoms.at(cur).ring {
        atoms.at(cur) = atom  // the atom its branches, written first, start from
      } else {
        atoms.push(atom)
        cur = atoms.len() - 1
      }
    } else if kind == "branch" {
      if cur == none {
        atoms.push(blank)
        cur = atoms.len() - 1
      }
      let (a, l, _, _) = _graph(el.body, atoms, links, cur, none)
      atoms = a
      links = l
    } else if kind == "cycle" {
      if cur == none {
        atoms.push(blank)
        cur = atoms.len() - 1
      }
      atoms.at(cur).ring = true
    }
  }
  (atoms, links, cur, pend)
}
#let _checked(body) = {
  let (atoms, links, _, _) = _graph(body, (), (), none, none)
  let alone(i) = {
    let a = atoms.at(i)
    if a.symbols.len() == 1 and not a.charged and not a.ring { a.symbols.at(0) } else { none }
  }
  for (a, b, _, dashed) in links {
    if not dashed { continue }
    let (sa, sb) = (atoms.at(a).symbols, atoms.at(b).symbols)
    if sa.len() == 0 or sb.len() == 0 { continue }
    let donor(i) = {
      let s = atoms.at(i).symbols
      if s == ("H",) {
        // the H's own bond: to N, O or F
        let next = links.filter(l => not l.at(3) and (l.at(0) == i or l.at(1) == i)).map(l => if l.at(0) == i { l.at(1) } else { l.at(0) })
        next.all(j => alone(j) == none or alone(j) in _ACCEPTORS)
      } else { "H" in s and s.any(x => x in _ACCEPTORS) }
    }
    let acceptor(i) = atoms.at(i).pairs or atoms.at(i).symbols.any(x => x in _ACCEPTORS)
    assert(
      (donor(a) and acceptor(b)) or (donor(b) and acceptor(a)),
      message: "a hydrogen bond (a dashed or dotted link) goes from an H bonded to N, O or F to another atom's non-bonding pair (N, O, F), not " + sa.join() + "…" + sb.join(),
    )
  }
  for i in range(atoms.len()) {
    let s = alone(i)
    if s == none or s not in _VALENCE { continue }
    let n = links.filter(l => not l.at(3) and (l.at(0) == i or l.at(1) == i)).map(l => l.at(2)).sum(default: 0)
    assert(
      n <= _VALENCE.at(s),
      message: s + " has " + str(n) + " bonds, " + str(_VALENCE.at(s)) + " at most: each atom as many bonds as its valence (an ion written with its charge, \"O^+\")",
    )
  }
  body
}

// alchemist's skeletize: the molecule checked, each atom's Lewis pairs set in its free
// directions (above), then the polarity marks in its body laid out once the molecule is drawn,
// seeing those pairs
#let skeletize(..args) = {
  let (kept, marks, frags, _) = _split(_with-pairs(_checked(args.pos().at(0)), 0, 0))
  if marks.len() > 0 { kept += _draw(marks, frags) }
  _alchemist.skeletize(..args.named(), kept)
}
#let draw-skeleton(..args) = _alchemist.draw-skeleton(..args.named(), _with-pairs(_checked(args.pos().at(0)), 0, 0))
// ---- What the AI writes, from here (the rule's example: everything above is given)
#skeletize({
  fragment("CH_3")
  single()
  fragment("CH_2")
  single()
  fragment("OH")
})
