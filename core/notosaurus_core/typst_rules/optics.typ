#set page(width: auto, height: auto, margin: 6pt)
#import "@preview/cetz:0.5.2"
#import "common.typ": *
// Light's rays, computed, never placed by eye: refraction and reflection at a surface
// (Snell-Descartes: n1 sin i1 = n2 sin i2, the refracted ray at that angle; beyond the
// critical angle, total reflection, no refracted ray), and the image of an object by a thin
// converging lens (1/OA' − 1/OA = 1/f', γ = OA'/OA: the image computed, the three rays from
// B drawn through it), and an afocal telescope's ray path (telescope). Each name placed in
// the first spot clear of every ray and line and of the names already placed; "?" for a name
// hidden (a card asks it).

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
// a ray from p to q, its arrow in its middle (the light's way), dashed when virtual; `paint`
// its colour (the description's)
#let _ray(p, q, dashed: false, arrow: true, paint: black) = {
  import cetz.draw: *
  let stroke = if dashed { (thickness: 0.7pt, dash: "dashed", paint: paint) } else { 1pt + paint }
  if arrow and not dashed {
    let m = ((p.at(0) + q.at(0)) / 2, (p.at(1) + q.at(1)) / 2)
    line(p, m, stroke: stroke, mark: (end: "stealth", fill: paint, scale: 0.7))
    line(m, q, stroke: stroke)
  } else { line(p, q, stroke: stroke) }
}
// the rays' colours the description gives, by their names (`keys`: the function's rays): each
// one's colour, black when not given
#let _colours(colours, keys, what) = {
  assert(type(colours) == dictionary and colours.pairs().all(((k, c)) => k in keys and type(c) == color),
    message: "colours: " + what + " by name, each a colour: (" + keys.map(k => k + ": red").join(", ") + "), not " + repr(colours))
  keys.map(k => (k, colours.at(k, default: black))).to-dict()
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
  names: (i1: $i_1$, i2: $i_2$, r: $r$), values: false, hidden: (), normal: true, point: none, mirror: false, colours: (:)) = context {
  let paint = _colours(colours, ("incident", "refracted", "reflected"), "the rays")
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
    _ray(S, I, paint: paint.incident)
    if T != none { _ray(I, T, paint: paint.refracted) }
    if R != none { _ray(I, R, paint: paint.reflected) }
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
#let lens(focal: 4, object: -6, height: 2, distances: false, unit: "cm", hidden: (), names: (:), colours: (:)) = context {
  // the three rays from B: through O ("centre"), parallel to the axis then through F' ("parallel"),
  // through F then parallel ("focal")
  let paint = _colours(colours, ("centre", "parallel", "focal"), "the rays")
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
    for (p, key) in ((p1, "centre"), (p2, "parallel"), (p3, "focal")) {
      let q = beyond(p)
      _ray(B, p, paint: paint.at(key))
      segments.push((B, p))
      _ray(p, q, paint: paint.at(key))
      segments.push((p, q))
      if not real {
        line(p, B2, stroke: (thickness: 0.6pt, dash: "dashed", paint: paint.at(key)))
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
// An afocal telescope's ray path, as it is drawn (never to scale: a real telescope, f1 = 900
// mm, f2 = 10 mm, α = 0,5°, would shrink its eyepiece and its rays to nothing): f1 / f2 at most
// 5, α at least 5° and α' at most 60°. (f1, f2, α in degrees, tan α, B1's height under the axis
// −f1 tan α, tan α' = (f1 / f2) tan α)
#let afocal-path(focal1, focal2, angle) = {
  let (f1, f2) = (float(focal1), calc.max(float(focal2), focal1 / 5))
  let t = calc.min(calc.tan(calc.max(angle, 5) * 1deg), calc.tan(60deg) * f2 / f1)
  (f1: f1, f2: f2, angle: calc.atan(t).deg(), t: t, b: -f1 * t, t2: f1 / f2 * t)
}
// An afocal astronomical telescope: the objective L1 (focal f1, at O1) and the eyepiece L2
// (focal f2, at O2), F1' and F2 one point; a beam of parallel rays from a star, at `angle`
// (degrees) from the axis, coming down from the left. Computed: the beam converges at B1 in
// the focal plane (A1B1 = f1 tan α), then leaves L2 parallel to (B1 O2), at α' with
// tan α' = (f1 / f2) tan α. Its three rays (one through O1); α at O1, α' at O2 on the line
// from B1 through O2 (dashed). names: the points' and angles' names; hidden: those a card asks.
#let telescope(focal1: 5, focal2: 1, angle: 10, names: (:), hidden: (), colour: black) = context {
  assert(type(colour) == color, message: "colour is the beam's colour: red, not " + repr(colour))
  let number(x) = type(x) in (int, float)
  assert(number(focal1) and number(focal2) and focal1 > 0 and focal2 > 0,
    message: "focal1 and focal2 are the objective's and the eyepiece's focal lengths, positive numbers")
  assert(focal1 > focal2, message: "an astronomical telescope's objective has the longer focal length: focal1 > focal2")
  assert(number(angle) and angle > 0 and angle < 30, message: "angle is the beam's α from the axis, in degrees, between 0 and 30")
  let names = (L1: $L_1$, L2: $L_2$, O1: $O_1$, O2: $O_2$, F: $F'_1 = F_2$, A1: $A_1$, B1: $B_1$,
    alpha: $alpha$, alpha2: $alpha'$) + names
  let name(key) = if key in hidden { [?] } else { names.at(key) }
  let (f1, f2, angle, t, b, t2) = afocal-path(focal1, focal2, angle)
  let x2 = f1 + f2  // O2
  // the beam: three rays, one through O1, the others d above and below it
  let d = calc.max(0.15 * (f1 + f2), 0.6)
  let heights = (d, 0, -d)
  let before = 0.4 * x2  // how far the beam is drawn before L1
  // where each ray meets L2: on its line from L1 through B1
  let at2(y1) = y1 + (b - y1) * x2 / f1
  let after = calc.min(0.4 * x2, 0.3 * x2 / t2)  // how far the rays are drawn past L2: rising 0.3 x2 at most
  let k = 11 / (before + x2 + after)  // the figure about 11 cm wide
  let P(x, y) = (x * k, y * k)
  let top1 = (d + before * t) * k + 0.4
  let top2 = calc.max(..heights.map(y => calc.abs(at2(y)))) * k + 0.4
  cetz.canvas({
    import cetz.draw: *
    line(P(-before, 0), P(x2 + after, 0), stroke: 0.6pt)  // the optical axis
    for (x, top) in ((0, top1), (x2, top2)) {
      line((x * k, -top), (x * k, top), stroke: 1.2pt, mark: (start: "stealth", end: "stealth", fill: black, scale: 0.8))
    }
    line(P(f1, 0.08 / k), P(f1, -0.08 / k), stroke: 1pt)  // F1' = F2
    // the intermediate image A1B1
    line(P(f1, 0), P(f1, b), stroke: 1.4pt, mark: (end: "stealth", fill: black, scale: 0.8))
    let segments = ((P(-before, 0), P(x2 + after, 0)), ((0, -top1), (0, top1)), ((x2 * k, -top2), (x2 * k, top2)), (P(f1, 0), P(f1, b)))
    for y1 in heights {
      let start = P(-before, y1 + before * t)
      let p1 = P(0, y1)
      let y2 = at2(y1)
      let p2 = P(x2, y2)
      let out = P(x2 + after, y2 + after * t2)
      _ray(start, p1, paint: colour)
      _ray(p1, p2, paint: colour)
      _ray(p2, out, paint: colour)
      segments += ((start, p1), (p1, p2), (p2, out))
    }
    // the line from B1 through O2, which the rays leaving L2 are parallel to
    let O2 = P(x2, 0)
    let guide = P(x2 + after * 0.8, after * 0.8 * t2)
    line(P(f1, b), guide, stroke: (thickness: 0.6pt, dash: "dashed"))
    segments.push((P(f1, b), guide))
    // α at O1 (between the axis and the ray through O1), α' at O2 (between the axis and the line)
    let r = 0.9
    arc((0, 0), start: 180deg, delta: -angle * 1deg, radius: r, anchor: "origin", stroke: 0.6pt)
    let alpha2 = calc.atan(t2).deg()
    arc(O2, start: 0deg, delta: alpha2 * 1deg, radius: r, anchor: "origin", stroke: 0.6pt)
    // each angle's name by its arc, in the first spot clear of the rays: its middle first,
    // then beyond its side away from the rays (above the line for α', below the axis for α)
    let placed = ()
    for (key, p, dirs) in (
      ("alpha", (0, 0), (180 - angle / 2, 180 - angle - 12, 180 - angle - 25, 180 + angle / 2 + 8)),
      ("alpha2", O2, (alpha2 / 2, alpha2 + 12, alpha2 + 25, alpha2 + 40, -12)),
    ) {
      let box = _spot(p, name(key), dirs, segments, placed, d: r + 0.05)
      content(box.at(0), _txt(name(key)))
      placed.push(box)
    }
    for (key, p, dirs) in (
      ("L1", (0, top1), (90,)),
      ("L2", (x2 * k, top2), (90,)),
      ("O1", (0, 0), (-30, -150, -60, -120, 30, 150, -90, 60, 120)),
      ("O2", O2, (-30, -150, -60, -120, -90, 150, 120)),
      ("F", P(f1, 0), (90, 60, 120, 45, 135)),
      ("B1", P(f1, b), (-90, -45, -135, 0)),
    ) {
      let box = _spot(p, name(key), dirs, segments, placed)
      content(box.at(0), _txt(name(key)))
      placed.push(box)
    }
  })
}
// ---- What the AI writes, from here (the rule's example: everything above is given)
#set text(lang: "fr")
#refraction(n1: 1.00, n2: 1.33, incidence: 40, media: ([Air ($n_1 = 1,00$)], [Eau ($n_2 = 1,33$)]))
