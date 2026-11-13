#set page(width: auto, height: auto, margin: 6pt)
#import "@preview/cetz:0.5.2"
#import "common.typ": *
// Light's rays, computed, never placed by eye: refraction and reflection at a surface
// (Snell-Descartes: n1 sin i1 = n2 sin i2, the refracted ray at that angle; beyond the
// critical angle, total reflection, no refracted ray), and the image of an object by a thin
// converging lens (1/OA' − 1/OA = 1/f', γ = OA'/OA: the image computed, the three rays from
// B drawn through it). Each name placed in the first spot clear of every ray and line and of
// the names already placed; "?" for a name hidden (a card asks it).

#let _txt(body) = text(11pt, body)
// whether a text's box (centre c, its half sizes) is clear of the segments and of the boxes
// already placed (each (centre, half width, half height))
#let _clear(c, hw, hh, segments, placed, pad: 0.08) = {
  let inside(q) = calc.abs(q.at(0) - c.at(0)) < hw + pad and calc.abs(q.at(1) - c.at(1)) < hh + pad
  (
    not segments.any(((a, b)) => range(41).any(k => inside((a.at(0) + (b.at(0) - a.at(0)) * k / 40,
      a.at(1) + (b.at(1) - a.at(1)) * k / 40))))
      and placed.all(((o, ow, oh)) => calc.abs(o.at(0) - c.at(0)) > ow + hw + pad
        or calc.abs(o.at(1) - c.at(1)) > oh + hh + pad)
  )
}
// where a text goes beside a point: the first of the directions (degrees) where its box is
// clear, at `d` from the point (from the box's edge); else the first one: its box (centre,
// half width, half height), drawn by the caller (content(box.at(0), _txt(body)))
#let _spot(p, body, dirs, segments, placed, d: 0.18, fallback: true) = {
  let m = measure(_txt(body))
  let (hw, hh) = (m.width / 1cm / 2, m.height / 1cm / 2)
  let spot(a, d) = {
    let a = a * 1deg
    // the box's centre so that its nearest edge is d from the point, along a
    let (cs, sn) = (calc.cos(a), calc.sin(a))
    let k = calc.min(if calc.abs(cs) > 1e-6 { hw / calc.abs(cs) } else { 1e9 }, if calc.abs(sn) > 1e-6 {
      hh / calc.abs(sn)
    } else { 1e9 })
    _off(p, a, d + k)
  }
  // nearest first: each direction at d, then a little farther
  let found = none
  for dd in (d, d + 0.2, d + 0.45) {
    if found == none { found = dirs.map(a => spot(a, dd)).find(c => _clear(c, hw, hh, segments, placed)) }
  }
  if found == none and not fallback { return none }
  let c = if found == none { spot(dirs.first(), d) } else { found }
  (c, hw, hh)
}
// a ray from p to q, its arrow in its middle (the light's way), dashed when virtual
#let _ray(p, q, dashed: false, arrow: true) = {
  import cetz.draw: *
  let stroke = if dashed { (thickness: 0.7pt, dash: "dashed") } else { 1pt }
  if arrow and not dashed {
    let m = ((p.at(0) + q.at(0)) / 2, (p.at(1) + q.at(1)) / 2)
    line(p, m, stroke: stroke, mark: (end: "stealth", fill: black, scale: 0.7))
    line(m, q, stroke: stroke)
  } else { line(p, q, stroke: stroke) }
}

// The refracted ray's angle from the normal, in degrees (n1 sin i1 = n2 sin i2); none beyond
// the critical angle (total reflection)
#let refracted-angle(n1, n2, i1) = {
  let s = n1 * calc.sin(i1 * 1deg) / n2
  if s > 1 { none } else { calc.asin(s).deg() }
}
// A converging lens's image of the object at OA = xa, of height h: (OA', A'B'), and where the
// three rays from B meet the lens (through O, parallel to the axis, through F), in cm
#let lens-image(f, xa, h) = {
  let xi = 1 / (1 / f + 1 / xa)
  (xi, h * xi / xa, ((0, 0), (0, h), (0, h * f / (f + xa))))
}

// Refraction (and reflection) at a horizontal surface, the light coming from the upper medium
// down to I; mirror: a plane mirror, the light reflected only. incidence: i1 in degrees from the normal. media: the two media's names (upper,
// lower). reflected: the reflected ray drawn too (always beyond the critical angle). names:
// the angles' names; values: their values written (computed); hidden: the names a card asks.
#let refraction(n1: 1.00, n2: 1.33, incidence: 40, media: none, reflected: false,
  names: (i1: $i_1$, i2: $i_2$, r: $r$), values: false, hidden: (), normal: true, point: none, mirror: false) = context {
  let i1 = if type(incidence) == angle { incidence.deg() } else { incidence }
  assert(type(i1) in (int, float) and i1 >= 0 and i1 < 90, message: "incidence is the angle from the normal, in degrees, from 0 to 90")
  assert(type(n1) in (int, float) and type(n2) in (int, float) and n1 > 0 and n2 > 0, message: "n1 and n2 are the media's indices: numbers")
  let media = if type(media) == content { (media,) } else { media }
  assert(media == none or (type(media) == array and media.len() == (if mirror { 1 } else { 2 }) or (mirror and type(media) == array and media.len() == 2)), message: if mirror { "media is the mirror's medium: (its name,)" } else { "media is (the upper medium, the lower one)" })
  let names = (i1: $i_1$, i2: $i_2$, r: $r$) + names
  let i2 = if mirror { none } else { refracted-angle(n1, n2, i1) }
  let total = i2 == none and not mirror
  let L = 2.6
  // as wide as the media's names need, beside the normal
  let wide = calc.max(3, ..(if media == none { () } else { media }).map(m => measure(_txt(m)).width / 1cm + 0.5))
  let I = (0, 0)
  let S = _off(I, (90 + i1) * 1deg, L)  // where the incident ray comes from (upper left)
  let T = if total or mirror { none } else { _off(I, (-90 + i2) * 1deg, L) }  // the refracted ray's end
  let R = if reflected or total or mirror { _off(I, (90 - i1) * 1deg, L) } else { none }  // the reflected one's
  cetz.canvas({
    import cetz.draw: *
    // the lower medium shaded, the surface, the normal
    if mirror {
      // the mirror: its silvered side up, hatched behind
      line((-wide, 0), (wide, 0), stroke: 1.6pt)
      for k in range(int(wide * 2 * 4) + 1) {
        let x = -wide + k / 4
        if x + 0.2 <= wide { line((x + 0.2, 0), (x, -0.2), stroke: 0.5pt) }
      }
    } else {
      // the denser medium shaded (the water, the glass), whichever the light comes from
      if n1 > n2 { rect((-wide, 0), (wide, 2.6), fill: luma(240), stroke: none) } else {
        rect((-wide, -2.6), (wide, 0), fill: luma(240), stroke: none)
      }
      line((-wide, 0), (wide, 0), stroke: 1pt)
    }
    let low = if mirror { 0 } else { -2.6 }
    if normal { line((0, low), (0, 2.6), stroke: (thickness: 0.6pt, dash: "dashed")) }
    _ray(S, I)
    if T != none { _ray(I, T) }
    if R != none { _ray(I, R) }
    let segments = ((S, I), ((-wide, 0), (wide, 0)), ((0, low), (0, 2.6)))
    if mirror { segments.push(((-wide, -0.25), (wide, -0.25))) }  // its hatching
    if T != none { segments.push((I, T)) }
    if R != none { segments.push((I, R)) }
    let placed = ()
    // an angle between the normal (direction n) and a ray (direction n + d), its arc and name
    for (n, d, key, value) in ((90, i1, "i1", i1), (-90, i2, "i2", i2), (90, -i1, "r", i1)) {
      // the reflection's angle only when it is asked (a mirror's, a reflected ray asked): a
      // total reflection's ray drawn, its angle not named unless asked
      if d == none or d == 0 or (key == "i2" and T == none) or (key == "r" and not (reflected or mirror)) { continue }
      let r = 0.75
      arc(I, start: n * 1deg, delta: d * 1deg, radius: r, anchor: "origin", stroke: 0.6pt)
      let label = if key in hidden { [?] } else if values { $#names.at(key) = #written-number(value, digits: 1) degree$ } else { names.at(key) }
      let mid = n + d / 2
      // its name in the angle beyond its arc, farther out when the angle is narrow; else
      // beside it, past the ray or the normal
      let sg = if d > 0 { 1 } else { -1 }
      let box = none
      for rr in (r + 0.12, r + 0.6) {
        if box == none { box = _spot(I, label, (mid, mid + 0.25 * d, mid - 0.25 * d), segments, placed, d: rr, fallback: false) }
      }
      for rr in (r + 0.12, r + 0.6) {
        if box == none {
          box = _spot(I, label, (n + d + sg * 18, n - sg * 18, n + d + sg * 35, n - sg * 35), segments, placed, d: rr,
            fallback: false)
        }
      }
      if box == none { box = _spot(I, label, (mid,), segments, placed, d: r + 0.12) }
      content(box.at(0), _txt(label))
      placed.push(box)
    }
    // the media's names, near the surface, on the side no ray crosses
    if media != none {
      for (body, up) in ((media.at(0), true),) + if mirror { () } else { ((media.at(1), false),) } {
        let y = if up { 0.35 } else { -0.35 }
        let m = measure(_txt(body))
        let (hw, hh) = (m.width / 1cm / 2, m.height / 1cm / 2)
        let e = wide - 0.15
        let spots = (
          (-e + hw, if up { 1.9 } else { -1.9 }), (e - hw, if up { 1.9 } else { -1.9 }),
          (-e + hw, y + if up { hh } else { -hh }), (e - hw, y + if up { hh } else { -hh }),
        )
        let c = spots.find(c => _clear(c, hw, hh, segments, placed))
        if c == none { c = spots.first() }
        content(c, _txt(body))
        placed.push((c, hw, hh))
      }
    }
    if point != none { content(_spot(I, point, (-150, -30, 150, 30, -120, -60), segments, placed, d: 0.12).at(0), _txt(point)) }
  })
}

// The image of an object AB by a thin converging lens: focal f' (cm), the object's place
// OA (algebraic: before the lens, negative) and height AB; the image A'B' computed
// (1/OA' − 1/OA = 1/f'), the three rays from B (through O; parallel to the axis, then through
// F'; through F, then parallel) drawn to B' (a virtual image: the rays' extensions dashed back
// to it). distances: OA and OA' marked under the axis; names: the points' names; hidden: the
// names (or "OA", "OA'") a card asks.
#let lens(focal: 4, object: -6, height: 2, distances: false, unit: "cm", hidden: (), names: (:)) = context {
  assert(type(focal) in (int, float) and focal > 0, message: "focal is the converging lens's f', a positive number")
  assert(type(object) in (int, float) and object < 0, message: "object is OA, before the lens: a negative number (OA = −6 cm: -6)")
  assert(type(height) in (int, float) and height != 0, message: "height is the object's AB, a number")
  assert(calc.abs(object + focal) > 1e-6, message: "an object at F has no image (at infinity)")
  let names = (A: $A$, B: $B$, A2: $A'$, B2: $B'$, F: $F$, F2: $F'$, O: $O$) + names
  let name(key) = if key in hidden or (key == "A2" and "A'" in hidden) or (key == "B2" and "B'" in hidden) or (
    key == "F2" and "F'" in hidden) { [?] } else { names.at(key) }
  let (f, xa, h) = (focal, object, height)
  let (xi, hi, hits) = lens-image(f, xa, h)  // OA', A'B' = γ AB, where the rays meet the lens
  // an object near F: its image so far that the lens, F and the object shrink to nothing
  // (the scale set by OA'): refused beyond 10 f' (an object at OA = −10/9 f' or −10/11 f')
  let r(x) = str(calc.round(x, digits: 2))
  assert(calc.abs(xi) <= 10 * f * (1 + 1e-9), message: "the image is too far to draw (OA' = " + r(xi) + ", beyond 10 f'): the "
    + "object farther from F, OA at most " + r(-10 * f / 9) + " (a real image) or between " + r(-10 * f / 11) + " and 0 (a virtual one)")
  let real = xi > 0
  // one scale for both directions: the figure about 11 cm wide
  let lo = calc.min(xa, -f, xi) - 1.2
  let hi-x = calc.max(f, xi, 0) + 1.6
  let k = 11 / (hi-x - lo)
  let P(x, y) = (x * k, y * k)
  let B = P(xa, h)
  let A = P(xa, 0)
  let B2 = P(xi, hi)
  let A2 = P(xi, 0)
  let top = calc.max(calc.abs(h), calc.abs(hi), 0.8) * k + 0.5
  // the three rays: where each meets the lens
  let (p1, p2, p3) = hits.map(((x, y)) => P(x, y))
  let right = hi-x * k
  // beyond the lens: through B' (real), or away from the lens on the line from B' (virtual)
  let beyond(p) = {
    let (dx, dy) = if real { (B2.at(0) - p.at(0), B2.at(1) - p.at(1)) } else { (p.at(0) - B2.at(0), p.at(1) - B2.at(1)) }
    let t = (right - p.at(0)) / dx
    (p.at(0) + dx * t, p.at(1) + dy * t)
  }
  cetz.canvas({
    import cetz.draw: *
    line((lo * k, 0), (right, 0), stroke: 0.6pt)  // the optical axis
    line((0, -top), (0, top), stroke: 1.2pt, mark: (start: "stealth", end: "stealth", fill: black, scale: 0.8))
    for x in (-f, f) { line(P(x, 0.08 / k), P(x, -0.08 / k), stroke: 1pt) }
    // the object, the image (dashed when virtual)
    line(A, B, stroke: 1.4pt, mark: (end: "stealth", fill: black, scale: 0.8))
    line(A2, B2, stroke: if real { 1.4pt } else { (thickness: 1.2pt, dash: "dashed") },
      mark: (end: "stealth", fill: black, scale: 0.8))
    let segments = ((P(lo, 0), (right, 0)), ((0, -top), (0, top)), (A, B), (A2, B2))
    // from B to the lens (the third through F), then on: through B' (the second through F')
    for p in (p1, p2, p3) {
      let q = beyond(p)
      _ray(B, p)
      segments.push((B, p))
      _ray(p, q)
      segments.push((p, q))
      if not real {
        line(p, B2, stroke: (thickness: 0.6pt, dash: "dashed"))
        segments.push((p, B2))
      }
    }
    let placed = ()
    for (key, p, dirs) in (
      ("O", p1, (-135, -45, 135)),
      ("F", P(-f, 0), (-90, -60, -120, 90)),
      ("F2", P(f, 0), (-90, -60, -120, 90, 60)),
      ("A", A, if h > 0 { (-90, -60, -120) } else { (90, 60, 120) }),
      ("B", B, if h > 0 { (90, 135, 45, 180) } else { (-90, -135, -45, 180) }),
      ("A2", A2, if hi > 0 { (-90, -60, -120) } else { (90, 60, 120) }),
      ("B2", B2, if hi > 0 { (90, 45, 135, 0) } else { (-90, -45, -135, 0) }),
    ) {
      let box = _spot(p, name(key), dirs, segments, placed)
      content(box.at(0), _txt(name(key)))
      placed.push(box)
    }
    // OA and OA', under everything, their lengths in the unit given
    if distances {
      let y = -top - 0.45
      let dim(x0, x1, key, value, row) = {
        let yy = y - row * 0.75
        line((x0, yy), (x1, yy), stroke: 0.6pt, mark: (start: "stealth", end: "stealth", fill: black, scale: 0.55))
        for x in (x0, x1) { line((x, yy + 0.15), (x, yy - 0.15), stroke: 0.5pt) }
        let label = if key in hidden { [?] } else { [#written-number(calc.abs(value), digits: 1) #unit] }
        content(((x0 + x1) / 2, yy - 0.08), _txt(label), anchor: "north")
      }
      dim(A.at(0), 0, "OA", xa, 0)
      dim(0, A2.at(0), "OA'", xi, if real { 0 } else { 1 })
    }
  })
}
// ---- What the AI writes, from here (the rule's example: everything above is given)
#set text(lang: "fr")
#refraction(n1: 1.00, n2: 1.33, incidence: 40, media: ([Air ($n_1 = 1,00$)], [Eau ($n_2 = 1,33$)]))
