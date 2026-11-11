#set page(width: auto, height: auto, margin: 6pt)
#import "@preview/cetz:0.5.2"
// A body and the vectors at it (forces, a velocity, an acceleration, a Frenet frame), each
// given by its direction, never placed by eye, in its scene: on a circle (an orbit: the body
// at `at` degrees, the centre's body named `centre`), on a horizontal plane, on a slope rising
// at `angle` degrees, on a pendulum (hanging from `centre` by a string named `radius`, at
// `angle` degrees from the vertical, `theta` the angle's name), in a liquid, or alone; with
// `other`, a second body facing it (two bodies acting on each other), `others` the vectors
// at it, `distance` the distance between them. A direction is "up", "down", "left", "right",
// "normal" (out of the support), "along" (the way the body moves: the circle's tangent, the
// plane's or the slope's way up), "back" (against it), "uphill", "downhill" (a slope's,
// whichever way the body moves), "centre", "outward", "towards", "away" (the other body), or
// a number of degrees counterclockwise from the right; its length a factor (1 by default),
// or with `scale: (2, "N")` (1 cm for 2 N) the vector's value. Vectors going the same way are
// drawn side by side. Each vector's name at its tip, written with an arrow over it (arrows:
// false: plain), "?" when hidden; radius: the circle's radius drawn and named; body: the
// body's name, a name of one letter the name of its point (G); shape: "block", "ball" or
// "point"; string: the body hangs from a string; marked: the vectors whose angle with the
// support's way is marked (its value, or the name given: (F: $alpha$)); path: the body's
// displacement on the plane, from its first point to its second ((A, B), or (A, B, its length));
// clockwise: the body turning clockwise on its circle
// a slope rising at `angle` degrees: its foot, the body's foot at the origin on it
#let slope-foot(angle) = (-2.5 * calc.cos(angle * 1deg), -2.5 * calc.sin(angle * 1deg))
// the point of a body resting on that slope, `half` its half height
#let on-slope(angle, half) = (-half * calc.sin(angle * 1deg), half * calc.cos(angle * 1deg))
#let mechanics(support: none, vectors: (), at: 60, centre: none, radius: none, angle: 30, body: none,
  clockwise: false, arrows: true, hidden: (), theta: none, other: none, others: (), distance: none,
  shape: auto, string: false, marked: (), path: none, scale: none) = context {
  assert(
    support in (none, "circle", "plane", "slope", "pendulum", "liquid"),
    message: "support is none, \"circle\", \"plane\", \"slope\", \"pendulum\" or \"liquid\"",
  )
  assert(shape in (auto, "block", "ball", "point"), message: "shape is \"block\", \"ball\" or \"point\"")
  assert(
    other == none or support == none,
    message: "two bodies facing each other stand alone: no support",
  )
  assert(path == none or support == "plane", message: "a path is the body's displacement on a plane")
  assert(
    scale == none or (type(scale) == array and scale.len() == 2 and type(scale.at(0)) in (int, float)),
    message: "scale is (the value for 1 cm, its unit): (2, \"N\")",
  )
  let words = ("up", "down", "left", "right", "normal", "along", "back", "centre", "outward", "uphill",
    "downhill", "towards", "away")
  for v in vectors + others {
    assert(
      type(v) == array and v.len() in (2, 3) and (v.at(1) in words or type(v.at(1)) in (int, float))
        and (v.len() == 2 or type(v.at(2)) in (int, float)),
      message: "vectors are (name, direction) or (name, direction, length): a direction is one of "
        + words.join(", ") + ", or a number of degrees",
    )
    assert(
      not (v.at(1) in ("uphill", "downhill") and support != "slope"),
      message: "\"uphill\" and \"downhill\" are a slope's directions",
    )
    assert(
      not (v.at(1) in ("centre", "outward") and support not in ("circle", "pendulum")),
      message: "\"centre\" and \"outward\" are a circle's or a pendulum's directions",
    )
    assert(
      not (v.at(1) in ("towards", "away") and other == none),
      message: "\"towards\" and \"away\" point to the other body: give it with other",
    )
  }
  assert(others.len() == 0 or other != none, message: "others are the vectors at the other body: give it with other")
  // the vectors' names as the AI writes them: their marked angles by name
  let marks = if type(marked) == dictionary { marked } else if type(marked) == array {
    marked.map(m => (str(m), none)).to-dict()
  } else { (str(marked): none) }
  let txt(body) = text(11pt, body)
  let greek = ("alpha", "beta", "gamma", "Gamma", "delta", "Delta", "theta", "lambda", "mu", "pi", "Pi",
    "rho", "sigma", "tau", "phi", "omega", "Omega")
  // what the AI wraps a vector's index in, written plainly: F_(text(T)\/L) is F, T/L under it
  let plain(sub) = {
    let s = sub.trim()
    if s.starts-with("(") and s.ends-with(")") { s = s.slice(1, -1) }
    s = s.replace(regex("(text|upright|italic)\(([^()]*)\)"), m => m.captures.at(1))
    s.replace("\\/", "/").replace(regex("\s*\bslash\b\s*"), "/").replace("\"", "")
  }
  // a vector's name: its letter with an arrow over it (Pi: Π), what follows _ under it (u_t)
  let named(name) = {
    if name in hidden { return txt[?] }
    if type(name) != str or not arrows { return txt(name) }
    // a little larger than the text: the arrow over the letter stays readable
    let (base, ..sub) = name.split("_")
    let base = base.trim()
    // one letter as math sets it (F italic, Π upright), a Greek letter by its name
    let letter = math.arrow(if base in greek or base.match(regex("^\p{L}$")) != none { eval(base, mode: "math") }
    else { math.italic(base) })
    text(13pt, if sub.len() > 0 { math.equation(math.attach(letter, br: math.upright(plain(sub.join("_"))))) }
    else { math.equation(letter) })
  }
  // a body's name of one letter names its point (G, M), a longer one the body itself
  let point-name(n) = n != none and (if type(n) == str { n } else { n.at("text", default: "") }).clusters().len() == 1
  let shape = if shape != auto { shape } else if support in ("plane", "slope", "liquid") { "block" } else if (
    other != none
  ) { "ball" } else { "point" }
  // the body's half height above its support
  let half = if shape == "ball" { 0.5 } else { 0.45 }
  let r = 3.2  // the circle's radius
  let l = 3.4  // the pendulum's string
  // a pendulum: its string's angle from its pivot, the body at its end
  let hang = 270 + if support == "pendulum" { angle } else { 0 }
  // the body's point, and the support's way (degrees)
  let (p, way) = if support == "circle" {
    ((r * calc.cos(at * 1deg), r * calc.sin(at * 1deg)), at + if clockwise { -90 } else { 90 })
  } else if support == "pendulum" {
    ((l * calc.cos(hang * 1deg), l * calc.sin(hang * 1deg)), hang + if clockwise { -90 } else { 90 })
  } else if support == "plane" { ((0, half), 0) } else if support == "slope" {
    (on-slope(angle, half), angle)
  } else if support == "liquid" { ((0, -0.6), 0) } else { ((0, 0), 0) }
  // the other body, facing it on the right: far enough for the names over the arrows between them
  let wide(vs) = calc.max(0, ..vs.map(v => measure(named(v.at(0))).width / 1cm))
  let q = (p.at(0) + calc.max(5.5, 1.9 + wide(vectors) + wide(others)), p.at(1))
  // out of the support: a circle's outward, a pendulum's string away from its pivot
  let at = if support == "pendulum" { hang } else { at }
  let normal = if support in ("circle", "pendulum") { at } else { way + 90 }
  let degrees(d, from: p) = if type(d) != str { d } else {
    (up: 90, down: 270, left: 180, right: 0, normal: normal, along: way, back: way + 180,
      centre: at + 180, outward: at, uphill: way, downhill: way + 180,
      towards: if from == p { 0 } else { 180 }, away: if from == p { 180 } else { 0 }).at(d)
  }
  // cetz.draw has a scale of its own
  let per-cm = scale
  let unit = 1.5
  let length(v) = if scale != none { if v.len() == 3 { v.at(2) / scale.at(0) } else { unit } } else {
    unit * if v.len() == 3 { v.at(2) } else { 1 }
  }
  let off(q, a, d) = (q.at(0) + d * calc.cos(a), q.at(1) + d * calc.sin(a))
  // each vector's start and tip: vectors going the same way from one point side by side
  let arrows-at(from, vs) = {
    let ways = vs.map(v => calc.rem-euclid(degrees(v.at(1), from: from), 360))
    vs.enumerate().map(((i, v)) => {
      let a = ways.at(i)
      let same = ways.enumerate().filter(((j, w)) => calc.abs(w - a) < 1).map(((j, w)) => j)
      let k = same.position(j => j == i)
      // several up along the string the body hangs from: on either side of it (one alone on it)
      let side = if string and from == p and calc.abs(a - 90) < 1 and same.len() > 1 {
        0.3 * (calc.quo(k, 2) + 1) * if calc.rem(k, 2) == 0 { -1 } else { 1 }
      } else { 0.28 * (k - (same.len() - 1) / 2) }
      let s = off(from, (a + 90) * 1deg, side)
      (v, a, s, off(s, a * 1deg, length(v)))
    })
  }
  let drawn = arrows-at(p, vectors) + arrows-at(q, others)
  // where nothing but the scene may go: the lines a name must stay clear of
  let lines = ()
  let ceiling = p.at(1) + 3.2
  // the string from the body's top, from the point itself when the body is one
  let hook = p.at(1) + if shape == "point" { 0 } else { half }
  let hung = string or support == "pendulum"
  if string { lines.push(((p.at(0), hook), (p.at(0), ceiling))) }
  if support == "pendulum" { lines.push(((0, 0), p)) }
  cetz.canvas({
    import cetz.draw: *
    let hatch(y, from, to) = {
      line((from, y), (to, y), stroke: 1pt)
      for k in range(int((to - from) / 0.4)) { line((from + 0.1 + k * 0.4, y), (from + 0.3 + k * 0.4, y + 0.2), stroke: 0.5pt) }
    }
    if support == "circle" {
      circle((0, 0), radius: r, stroke: (thickness: 0.8pt, dash: "dashed"))
      if radius != none {
        // on the side away from the body, under the centre's body
        let a = (at + 180 - 45) * 1deg
        line((0, 0), (r * calc.cos(a), r * calc.sin(a)), stroke: 0.6pt)
        content((r / 2 * calc.cos(a) + 0.25 * calc.cos(a + 90deg), r / 2 * calc.sin(a) + 0.25 * calc.sin(a + 90deg)),
          txt(radius))
      }
      // a centre named by one letter is a point (O), else a body (the Earth)
      if centre != none and not point-name(centre) {
        circle((0, 0), radius: 0.65, fill: luma(225), stroke: 0.8pt)
        content((0, 0), txt(centre))
      } else {
        circle((0, 0), radius: 0.06, fill: black)
        if centre != none { content(off((0, 0), (at + 180 + 90) * 1deg, 0.3), txt(centre)) }
      }
    } else if support == "pendulum" {
      // the pivot under a hatched ceiling, the vertical dashed, the string, its angle
      line((-1, 0), (1, 0), stroke: 1pt)
      for k in range(5) { line((-0.9 + k * 0.4, 0), (-0.7 + k * 0.4, 0.2), stroke: 0.5pt) }
      line((0, 0), (0, -l - 0.3), stroke: (thickness: 0.6pt, dash: "dashed"))
      line((0, 0), p, stroke: 1pt)
      circle((0, 0), radius: 0.06, fill: black)
      // the pivot's name on the side the string doesn't go
      if centre != none {
        content((if angle >= 0 { -0.15 } else { 0.15 }, -0.05), txt(centre),
          anchor: if angle >= 0 { "north-east" } else { "north-west" })
      }
      if radius != none {
        let m = (p.at(0) / 2, p.at(1) / 2)
        let side = (hang + if angle >= 0 { 90 } else { -90 }) * 1deg
        content((m.at(0) + 0.3 * calc.cos(side), m.at(1) + 0.3 * calc.sin(side)), txt(radius))
      }
      if angle != 0 {
        arc((0, 0), start: 270deg, stop: hang * 1deg, radius: 1.1, anchor: "origin", stroke: 0.6pt)
        if theta != none {
          let mid = (270 + angle / 2) * 1deg
          content((1.45 * calc.cos(mid), 1.45 * calc.sin(mid)), txt(theta))
        }
      }
    } else if support == "plane" {
      let right = if path != none { 4.2 } else if other != none { q.at(0) + 2.8 } else { 2.8 }
      hatch(0, -2.8, right)
    } else if support == "slope" {
      let a = angle * 1deg
      let (c, s) = (calc.cos(a), calc.sin(a))
      // the slope from its foot at the left, through the body's foot (the origin)
      let foot = slope-foot(angle)
      let top = (foot.at(0) + 5 * c, foot.at(1) + 5 * s)
      line(foot, top, (top.at(0), foot.at(1)), close: true, stroke: 1pt, fill: luma(240))
      arc(foot, start: 0deg, stop: a, radius: 0.9, anchor: "origin", stroke: 0.6pt)
      content((foot.at(0) + 1.25 * calc.cos(a / 2), foot.at(1) + 1.25 * calc.sin(a / 2)),
        txt(math.equation(math.alpha)))
    } else if support == "liquid" {
      // a container, the liquid up to near its brim, the body in it
      rect((-2, -1.5), (2, 0.4), fill: rgb("#dceefb"), stroke: none)
      line((-2, 1.0), (-2, -1.5), (2, -1.5), (2, 1.0), stroke: 1pt)
      line((-2, 0.4), (2, 0.4), stroke: 0.6pt + rgb("#3a7bc8"))
    }
    if string {
      line((p.at(0), hook), (p.at(0), ceiling), stroke: 0.8pt)
      hatch(ceiling, p.at(0) - 1, p.at(0) + 1)
    }
    if path != none {
      // the displacement under the ground, from the body's point to the second one
      let (a, b) = (path.at(0), path.at(1))
      let y = -0.6
      line((0, y), (3.4, y), stroke: 1pt, mark: (end: "stealth", fill: black, scale: 0.8))
      for x in (0, 3.4) { line((x, y - 0.1), (x, y + 0.1), stroke: 0.8pt) }
      content((-0.15, y), txt(a), anchor: "east")
      content((3.55, y), txt(b), anchor: "west")
      if path.len() > 2 { content((1.7, y - 0.15), txt(path.at(2)), anchor: "north") }
    }
    // the bodies: a block, a ball or a point
    let draw-body(c, name, size) = {
      let a = (if support == "slope" { angle } else { 0 }) * 1deg
      if shape == "block" {
        let corner(u, v) = (c.at(0) + size * (u * calc.cos(a) - v * calc.sin(a)),
          c.at(1) + size * (u * calc.sin(a) + v * calc.cos(a)))
        line(corner(-0.6, -0.45), corner(0.6, -0.45), corner(0.6, 0.45), corner(-0.6, 0.45), close: true,
          fill: luma(215), stroke: 0.8pt)
      } else if shape == "ball" {
        circle(c, radius: half * size, fill: luma(225), stroke: 0.8pt)
      }
      circle(c, radius: if support == "pendulum" { 0.16 } else { 0.07 },
        fill: if support == "pendulum" { luma(120) } else { black })
    }
    draw-body(p, body, 1)
    if other != none { draw-body(q, other, 1) }
    // the marked angles: from the support's way to the vector, its value or its name
    for (v, a, s, t) in drawn {
      let name = if type(v.at(0)) == str { v.at(0) } else { repr(v.at(0)) }
      if name in marks {
        let w = calc.rem-euclid(way, 360)
        let d = calc.rem-euclid(a - w + 180, 360) - 180
        line(s, off(s, w * 1deg, 1.4), stroke: (thickness: 0.6pt, dash: "dashed"))
        arc(s, start: w * 1deg, delta: d * 1deg, radius: 0.95, anchor: "origin", stroke: 0.6pt)
        let label = marks.at(name)
        content(off(s, (w + d / 2) * 1deg, 1.35),
          txt(if label != none { label } else { str(calc.round(calc.abs(d), digits: 1)) + "°" }))
      }
    }
    // the arrows, then their names: each beyond its tip, else beside its tip, else beside its
    // middle, the first spot clear of every arrow, of the scene's lines and of the names
    // already placed
    let segments = drawn.map(((v, a, s, t)) => (s, t))
    // how far a point is from a segment
    let gap(q, (a, b)) = {
      let (dx, dy) = (b.at(0) - a.at(0), b.at(1) - a.at(1))
      let k = calc.clamp(((q.at(0) - a.at(0)) * dx + (q.at(1) - a.at(1)) * dy) / (dx * dx + dy * dy), 0, 1)
      calc.sqrt(calc.pow(q.at(0) - a.at(0) - k * dx, 2) + calc.pow(q.at(1) - a.at(1) - k * dy, 2))
    }
    let placed = ()
    for (i, (v, a, s, t)) in drawn.enumerate() {
      let a = a * 1deg
      line(s, t, stroke: 1.1pt, mark: (end: "stealth", fill: black, scale: 0.8))
      let m = ((s.at(0) + t.at(0)) / 2, (s.at(1) + t.at(1)) / 2)
      // two bodies facing each other: each name over its arrow, from its middle towards the
      // space between the bodies (shared by the two names)
      if other != none {
        content((m.at(0), m.at(1) + 0.3), named(v.at(0)), anchor: if calc.cos(a) >= 0 { "south-west" } else { "south-east" })
        continue
      }
      let spots = (off(t, a, 0.34), off(t, a + 90deg, 0.4), off(t, a - 90deg, 0.4), off(m, a + 90deg, 0.4),
        off(m, a - 90deg, 0.4))
      let clear(q) = (
        segments.enumerate().all(((j, sg)) => j == i or gap(q, sg) > 0.36)
          and lines.all(sg => gap(q, sg) > 0.36)
          and placed.all(o => calc.abs(o.at(0) - q.at(0)) > 0.5 or calc.abs(o.at(1) - q.at(1)) > 0.4)
          and (support != "circle" or centre == none or point-name(centre)
            or calc.sqrt(q.at(0) * q.at(0) + q.at(1) * q.at(1)) > 0.95)
      )
      let spot = spots.find(clear)
      if spot == none { spot = spots.first() }
      placed.push(spot)
      content(spot, named(v.at(0)))
    }
    // a body's name in the widest gap between its vectors (and the support), clear of them:
    // a point's name close to it, a body's beyond its shape
    let name-body(c, name, vs) = {
      let taken = vs.map(((v, a, s, t)) => a).sorted()
      if support in ("plane", "slope") {
        taken = (taken + (calc.rem-euclid(way + 180, 360), calc.rem-euclid(way, 360), calc.rem-euclid(normal + 180, 360))).sorted()
      }
      if support == "circle" and centre != none or hung { taken = (taken + (calc.rem-euclid(at + 180, 360),)).sorted() }
      if string { taken = (taken + (90,)).sorted() }
      let a = if taken.len() == 0 { -90 } else {
        let gaps = taken.enumerate().map(((k, d)) => {
          let next = if k + 1 < taken.len() { taken.at(k + 1) } else { taken.first() + 360 }
          (next - d, d + (next - d) / 2)
        })
        gaps.sorted(key: g => -g.at(0)).first().at(1)
      }
      let d = if point-name(name) { 0.1 } else if shape == "block" { 1.15 } else if shape == "ball" { 0.75 } else if (
        support == "pendulum"
      ) { 0.55 } else { 0.5 }
      let n = off(c, a * 1deg, d)
      let (cs, sn) = (calc.cos(a * 1deg), calc.sin(a * 1deg))
      // a point's name in the gap's quarter, off the point; a body's beyond it
      let anchor = if point-name(name) { (if sn >= 0 { "south-" } else { "north-" }) + if cs >= 0 { "west" } else { "east" } } else if (
        calc.abs(cs) > 0.4
      ) { if cs > 0 { "west" } else { "east" } } else if sn > 0 { "south" } else { "north" }
      content(n, txt(name), anchor: anchor)
    }
    if other != none {
      // two bodies: each name under it, then the distance between their centres
      let low = p.at(1) - half - if shape == "point" { 0.3 } else { 0.2 }
      for (c, name) in ((p, body), (q, other)) {
        if name != none { content((c.at(0), low), txt(name), anchor: "north") }
      }
      if distance != none {
        let y = low - 0.75
        line((p.at(0), y), (q.at(0), y), stroke: 0.6pt, mark: (start: "stealth", end: "stealth", fill: black, scale: 0.6))
        for c in (p, q) { line((c.at(0), y - 0.12), (c.at(0), y + 0.12), stroke: 0.6pt) }
        content(((p.at(0) + q.at(0)) / 2, y - 0.1), txt(distance), anchor: "north")
      }
    } else if body != none {
      name-body(p, body, drawn)
    }
    if per-cm != none {
      // the scale: 1 cm, under the scene on the right, its value over it
      let (x, y) = (if other != none { q.at(0) + 1.2 } else { p.at(0) + 2.2 }, p.at(1) - 1.4)
      line((x, y), (x + 1, y), stroke: 1pt)
      for e in (x, x + 1) { line((e, y - 0.08), (e, y + 0.08), stroke: 1pt) }
      content((x + 0.5, y + 0.1), txt[#per-cm.at(0) #per-cm.at(1)], anchor: "south")
      content((x + 0.5, y - 0.1), txt[1 cm], anchor: "north")
    }
  })
}
// A chronophotography's motion: its place and its velocity at a time t in [0, 1], unscaled
#let chrono-motion(motion, angle) = {
  let a = angle * 1deg
  if motion == "thrown" {
    let (vx, vy) = (calc.cos(a), calc.sin(a))
    let T = 2 * vy
    (t => (vx * t * T, vy * t * T - calc.pow(t * T, 2) / 2), t => (vx, vy - t * T))
  } else if motion == "falling" {
    (t => (0, -t * t), t => (0, -2 * t))
  } else if motion == "uniform" {
    (t => (t, 0), t => (1, 0))
  } else if motion == "accelerated" {
    // already moving: its first two positions apart, the gaps still growing
    (t => (t + t * t, 0), t => (1 + 2 * t, 0))
  } else {
    (t => (calc.cos(t * 360deg), calc.sin(t * 360deg)), t => (-calc.sin(t * 360deg), calc.cos(t * 360deg)))
  }
}
// its positions' times (from 0 to 1, a circle's last one step before its first), its scale
// (7 cm wide, 6 cm high for a fall, a circle 5 cm across) and its positions, in cm
#let chrono-places(motion, n, angle: 60) = {
  let (place, speed) = chrono-motion(motion, angle)
  let times = range(n).map(i => i / if motion == "circle" { n } else { n - 1 })
  let raw = times.map(place)
  let xs = raw.map(p => p.at(0))
  let ys = raw.map(p => p.at(1))
  let (w, h) = (calc.max(..xs) - calc.min(..xs), calc.max(..ys) - calc.min(..ys))
  let k = if motion == "falling" { 6 / h } else if motion == "circle" { 2.5 } else { 7 / w }
  (times, k, raw.map(p => (k * p.at(0), k * p.at(1))))
}
// A chronophotography: a body's positions at equal times, computed from its motion, never
// placed by eye. motion: "thrown" (a parabola launched at `angle` degrees, from its launch to
// its landing), "falling" (from rest, straight down), "uniform" or "accelerated" (along a
// straight line to the right, its gaps equal or growing), "circle" (uniform, counterclockwise
// from the right, on a circle of centre `centre`). n: the positions' count; names: their letter
// ("M": M0, M1…, counted from `first`), numbered: their numbers instead; trajectory: the curve
// through them, dashed; label: its name beside it; velocity: the positions (their numbers, as
// named) where the velocity is drawn, along the trajectory, as long as its speed; change: where
// the change of velocity is drawn (between the positions around it); arrows: false, the
// vectors' names without an arrow over them.
#let chronophotography(motion: "thrown", n: 7, names: none, first: 0, numbered: false, angle: 60,
  trajectory: true, label: none, velocity: (), change: (), centre: none, arrows: true) = context {
  let motions = ("thrown", "falling", "uniform", "accelerated", "circle")
  assert(motion in motions, message: "motion is one of " + motions.join(", "))
  assert(type(n) == int and n >= 2 and n <= 20, message: "n is the positions' count, 2 to 20")
  let numbers = range(first, first + n)
  for k in velocity + change {
    assert(k in numbers, message: "velocity and change are positions' numbers, from " + str(first) + " to "
      + str(first + n - 1) + " (" + repr(k) + ")")
  }
  for k in change {
    assert(k != first and k != first + n - 1, message: "a change of velocity is drawn between the positions around it: never at the first or the last")
  }
  let txt(body) = text(11pt, body)
  let (place, speed) = chrono-motion(motion, angle)
  let (times, k, pts) = chrono-places(motion, n, angle: angle)
  let off(q, d, l) = (q.at(0) + l * calc.cos(d), q.at(1) + l * calc.sin(d))
  let way(t) = { let v = speed(t); calc.atan2(v.at(0), v.at(1)) }
  // the side a name goes: away from the curve's hollow, else below a line, right of a fall
  let side(i) = if motion == "thrown" { way(times.at(i)) + 90deg } else if motion == "circle" {
    calc.atan2(pts.at(i).at(0), pts.at(i).at(1))
  } else if motion == "falling" { 0deg } else { -90deg }
  // two names closer than they are wide: every other one on the other side
  let gaps = range(n - 1).map(i => calc.sqrt(calc.pow(pts.at(i + 1).at(0) - pts.at(i).at(0), 2)
    + calc.pow(pts.at(i + 1).at(1) - pts.at(i).at(1), 2)))
  let tight = gaps.len() > 0 and calc.min(..gaps) < (if motion in ("uniform", "accelerated") { 0.75 } else { 0.45 })
  let name(i) = if numbered { str(first + i) } else if names != none {
    math.equation(math.attach(math.upright(names), br: str(first + i)))
  } else { none }
  let vec(letter, i, delta: false) = {
    let base = if arrows { math.arrow(letter) } else { letter }
    math.equation(math.attach(if delta { $Delta$ + base } else { base }, br: str(i)))
  }
  let top = calc.max(..velocity.map(i => {
    let v = speed(times.at(i - first)); calc.sqrt(v.at(0) * v.at(0) + v.at(1) * v.at(1))
  }), 0)
  cetz.canvas({
    import cetz.draw: *
    if trajectory {
      let fine = if motion == "circle" { range(121).map(j => j / 120) } else { range(121).map(j => j / 120 * times.last()) }
      let curve = fine.map(t => { let p = place(t); (k * p.at(0), k * p.at(1)) })
      line(..curve, stroke: (thickness: 0.7pt, dash: "dashed", paint: luma(110)))
      if label != none {
        // between two positions, clear of their names
        let j = calc.min(n - 2, int(calc.round(0.75 * (n - 1))))
        let t = if motion == "circle" { (calc.floor(n / 8) + 0.5) / n } else { (times.at(j) + times.at(j + 1)) / 2 }
        let p = place(t)
        let q = (k * p.at(0), k * p.at(1))
        let d = if motion == "thrown" { way(t) + 90deg } else if motion == "circle" { calc.atan2(p.at(0), p.at(1)) } else if (
          motion == "falling") { 180deg } else { 90deg }
        let e = off(q, d, 0.8)
        line(off(q, d, 0.1), e, stroke: 0.5pt)
        let (c, s) = (calc.cos(d), calc.sin(d))
        content(e, txt(label), anchor: if calc.abs(c) > 0.4 { if c > 0 { "west" } else { "east" } } else if s > 0 { "south" } else { "north" })
      }
    }
    if motion == "circle" {
      circle((0, 0), radius: 0.05, fill: black)
      if centre != none { content((0.12, -0.12), txt(centre), anchor: "north-west") }
    }
    for (i, p) in pts.enumerate() {
      circle(p, radius: 0.08, fill: black)
      let l = name(i)
      if l != none {
        let d = side(i) + if tight and calc.odd(i) { 180deg } else { 0deg }
        let (c, s) = (calc.cos(d), calc.sin(d))
        content(off(p, d, 0.2), txt(l), anchor: if calc.abs(c) > 0.4 { if c > 0 { "west" } else { "east" } } else if s > 0 { "south" } else { "north" })
      }
    }
    // the velocities along the trajectory, as long as their speeds; a change of velocity
    // between the positions around it, 1 cm long
    for i in velocity {
      let v = speed(times.at(i - first))
      // the fastest as long as most of the shortest step: clear of the next position
      let l = calc.min(1.4, 0.75 * calc.min(..gaps)) * calc.sqrt(v.at(0) * v.at(0) + v.at(1) * v.at(1)) / top
      let d = calc.atan2(v.at(0), v.at(1))
      let p = pts.at(i - first)
      let t = off(p, d, l)
      line(p, t, stroke: 1.1pt + rgb("#1f5fbf"), mark: (end: "stealth", fill: rgb("#1f5fbf"), scale: 0.8))
      // its name beside its middle, on the side the position's name isn't
      let m = ((p.at(0) + t.at(0)) / 2, (p.at(1) + t.at(1)) / 2)
      let away = side(i - first) + if tight and calc.odd(i - first) { 180deg } else { 0deg }
      let across = if calc.cos(d + 90deg - away) > 0 { d - 90deg } else { d + 90deg }
      content(off(m, across, 0.32), text(fill: rgb("#1f5fbf"), txt(vec($v$, i))))
    }
    for i in change {
      let (u, w) = (speed(times.at(i - first + 1)), speed(times.at(i - first - 1)))
      let d = calc.atan2(u.at(0) - w.at(0), u.at(1) - w.at(1))
      let p = pts.at(i - first)
      let t = off(p, d, 1)
      line(p, t, stroke: 1.1pt + rgb("#b3261e"), mark: (end: "stealth", fill: rgb("#b3261e"), scale: 0.8))
      content(off(off(t, d, 0.1), d + 90deg, 0.35), text(fill: rgb("#b3261e"), txt(vec($v$, i, delta: true))))
    }
  })
}
// ---- What the AI writes, from here (the rule's example: everything above is given)
#mechanics(support: "circle", centre: [Terre], at: 60, radius: $r$, body: [S], vectors: (
  ("v", "along"),
  ("F", "centre"),
))
