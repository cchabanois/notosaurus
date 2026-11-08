#set page(width: auto, height: auto, margin: 6pt)
#import "@preview/cetz:0.5.2"
// A body and the vectors at it (forces, a velocity, an acceleration, a Frenet frame), each
// given by its direction, never placed by eye: on a circle (an orbit: the body at `at`
// degrees, the centre's body named `centre`), on a horizontal plane, on a slope rising at
// `angle` degrees, on a pendulum (hanging from `centre` by a string named `radius`, at
// `angle` degrees from the vertical, `theta` the angle's name), or alone. A direction is "up", "down", "left", "right", "normal" (out
// of the support), "along" (the way the body moves: the circle's tangent, the plane's or
// the slope's way up), "back" (against it), "uphill", "downhill" (a slope's, whichever way
// the body moves), "centre", "outward", or a number of degrees
// counterclockwise from the right; its length a factor (1 by default). Each vector's name
// at its tip, written with an arrow over it (arrows: false: plain), "?" when hidden;
// radius: the circle's radius drawn and named; body: the body's name;
// clockwise: the body turning clockwise on its circle
#let mechanics(support: none, vectors: (), at: 60, centre: none, radius: none, angle: 30, body: none,
  clockwise: false, arrows: true, hidden: (), theta: none) = context {
  assert(
    support in (none, "circle", "plane", "slope", "pendulum"),
    message: "support is none, \"circle\", \"plane\", \"slope\" or \"pendulum\"",
  )
  let words = ("up", "down", "left", "right", "normal", "along", "back", "centre", "outward", "uphill", "downhill")
  assert(
    vectors.all(v => type(v) == array and v.len() in (2, 3) and (v.at(1) in words or type(v.at(1)) in (int, float))
      and (v.len() == 2 or type(v.at(2)) in (int, float))),
    message: "vectors are (name, direction) or (name, direction, length): a direction is one of " + words.join(", ")
      + ", or a number of degrees",
  )
  for v in vectors {
    assert(
      not (v.at(1) in ("uphill", "downhill") and support != "slope"),
      message: "\"uphill\" and \"downhill\" are a slope's directions",
    )
    assert(
      not (v.at(1) in ("centre", "outward") and support not in ("circle", "pendulum")),
      message: "\"centre\" and \"outward\" are a circle's or a pendulum's directions",
    )
  }
  let txt(body) = text(11pt, body)
  // a vector's name: its letter with an arrow over it, what follows _ under it (u_t)
  let named(name) = {
    if name in hidden { return txt[?] }
    if type(name) != str or not arrows { return txt(name) }
    // a little larger than the text: the arrow over the letter stays readable
    let (base, ..sub) = name.split("_")
    let letter = math.arrow(math.italic(base))
    text(13pt, if sub.len() > 0 { math.equation(math.attach(letter, br: sub.join("_"))) } else { math.equation(letter) })
  }
  let r = 3.2  // the circle's radius
  let l = 3.4  // the pendulum's string
  // a pendulum: its string's angle from its pivot, the body at its end
  let hang = 270 + if support == "pendulum" { angle } else { 0 }
  // the body's point, and the support's way (degrees)
  let (p, way) = if support == "circle" {
    ((r * calc.cos(at * 1deg), r * calc.sin(at * 1deg)), at + if clockwise { -90 } else { 90 })
  } else if support == "pendulum" {
    ((l * calc.cos(hang * 1deg), l * calc.sin(hang * 1deg)), hang + if clockwise { -90 } else { 90 })
  } else if support == "plane" { ((0, 0.45), 0) } else if support == "slope" {
    ((-0.45 * calc.sin(angle * 1deg), 0.45 * calc.cos(angle * 1deg)), angle)
  } else { ((0, 0), 0) }
  // out of the support: a circle's outward, a pendulum's string away from its pivot
  let at = if support == "pendulum" { hang } else { at }
  let normal = if support in ("circle", "pendulum") { at } else { way + 90 }
  let degrees(d) = if type(d) != str { d } else {
    (up: 90, down: 270, left: 180, right: 0, normal: normal, along: way, back: way + 180,
      centre: at + 180, outward: at, uphill: way, downhill: way + 180).at(d)
  }
  let unit = 1.5
  let tip(v) = {
    let a = degrees(v.at(1)) * 1deg
    let l = unit * if v.len() == 3 { v.at(2) } else { 1 }
    (p.at(0) + l * calc.cos(a), p.at(1) + l * calc.sin(a))
  }
  cetz.canvas({
    import cetz.draw: *
    if support == "circle" {
      circle((0, 0), radius: r, stroke: (thickness: 0.8pt, dash: "dashed"))
      if radius != none {
        // on the side away from the body, under the centre's body
        let a = (at + 180 - 45) * 1deg
        line((0, 0), (r * calc.cos(a), r * calc.sin(a)), stroke: 0.6pt)
        content((r / 2 * calc.cos(a) + 0.25 * calc.cos(a + 90deg), r / 2 * calc.sin(a) + 0.25 * calc.sin(a + 90deg)),
          txt(radius))
      }
      if centre != none {
        circle((0, 0), radius: 0.65, fill: luma(225), stroke: 0.8pt)
        content((0, 0), txt(centre))
      } else { circle((0, 0), radius: 0.04, fill: black) }
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
      line((-2.8, 0), (2.8, 0), stroke: 1pt)
      for k in range(14) { line((-2.7 + k * 0.4, 0), (-2.9 + k * 0.4, -0.2), stroke: 0.5pt) }
    } else if support == "slope" {
      let a = angle * 1deg
      let (c, s) = (calc.cos(a), calc.sin(a))
      // the slope from its foot at the left, the ground under it
      let foot = (-2.2 * c - 1.4, -2.2 * s)
      let top = (foot.at(0) + 5 * c, foot.at(1) + 5 * s)
      line(foot, top, (top.at(0), foot.at(1)), close: true, stroke: 1pt, fill: luma(240))
      arc(foot, start: 0deg, stop: a, radius: 0.9, anchor: "origin", stroke: 0.6pt)
      content((foot.at(0) + 1.25 * calc.cos(a / 2), foot.at(1) + 1.25 * calc.sin(a / 2)),
        txt(math.equation(math.alpha)))
    }
    // the body: a block on a plane or a slope, a point otherwise
    if support in ("plane", "slope") {
      let a = (if support == "slope" { angle } else { 0 }) * 1deg
      let corner(u, v) = (p.at(0) + u * calc.cos(a) - v * calc.sin(a), p.at(1) + u * calc.sin(a) + v * calc.cos(a))
      line(corner(-0.6, -0.45), corner(0.6, -0.45), corner(0.6, 0.45), corner(-0.6, 0.45), close: true,
        fill: luma(215), stroke: 0.8pt)
    }
    circle(p, radius: if support == "pendulum" { 0.16 } else { 0.07 }, fill: if support == "pendulum" { luma(120) } else { black })
    // the arrows, then their names: each beyond its tip, else beside its tip, else beside its
    // middle, the first spot clear of every arrow and of the names already placed
    let segments = vectors.map(v => (p, tip(v)))
    let off(q, a, d) = (q.at(0) + d * calc.cos(a), q.at(1) + d * calc.sin(a))
    // how far a point is from a segment
    let gap(q, (a, b)) = {
      let (dx, dy) = (b.at(0) - a.at(0), b.at(1) - a.at(1))
      let k = calc.clamp(((q.at(0) - a.at(0)) * dx + (q.at(1) - a.at(1)) * dy) / (dx * dx + dy * dy), 0, 1)
      calc.sqrt(calc.pow(q.at(0) - a.at(0) - k * dx, 2) + calc.pow(q.at(1) - a.at(1) - k * dy, 2))
    }
    let placed = ()
    for (i, v) in vectors.enumerate() {
      let a = degrees(v.at(1)) * 1deg
      let t = tip(v)
      line(p, t, stroke: 1.1pt, mark: (end: "stealth", fill: black, scale: 0.8))
      let m = ((p.at(0) + t.at(0)) / 2, (p.at(1) + t.at(1)) / 2)
      let spots = (off(t, a, 0.34), off(t, a + 90deg, 0.4), off(t, a - 90deg, 0.4), off(m, a + 90deg, 0.4),
        off(m, a - 90deg, 0.4))
      let clear(q) = (
        segments.enumerate().all(((j, sg)) => j == i or gap(q, sg) > 0.36)
          and (support != "pendulum" or gap(q, ((0, 0), p)) > 0.36)
          and placed.all(o => calc.abs(o.at(0) - q.at(0)) > 0.5 or calc.abs(o.at(1) - q.at(1)) > 0.4)
          and (support != "circle" or centre == none or calc.sqrt(q.at(0) * q.at(0) + q.at(1) * q.at(1)) > 0.95)
      )
      let spot = spots.find(clear)
      if spot == none { spot = spots.first() }
      placed.push(spot)
      content(spot, named(v.at(0)))
    }
    // the body's name in the widest gap between its vectors (and the support), clear of them
    if body != none {
      let taken = vectors.map(v => calc.rem-euclid(degrees(v.at(1)), 360)).sorted()
      if support in ("plane", "slope") { taken = (taken + (calc.rem-euclid(way + 180, 360), calc.rem-euclid(way, 360), calc.rem-euclid(normal + 180, 360))).sorted() }
      if support == "circle" and centre != none or support == "pendulum" {
        taken = (taken + (calc.rem-euclid(at + 180, 360),)).sorted()
      }
      let a = if taken.len() == 0 { -90 } else {
        let gaps = taken.enumerate().map(((k, d)) => {
          let next = if k + 1 < taken.len() { taken.at(k + 1) } else { taken.first() + 360 }
          (next - d, d + (next - d) / 2)
        })
        gaps.sorted(key: g => -g.at(0)).first().at(1)
      }
      let d = if support in ("plane", "slope") { 1.15 } else if support == "pendulum" { 0.55 } else { 0.5 }
      let q = off(p, a * 1deg, d)
      let (c, sn) = (calc.cos(a * 1deg), calc.sin(a * 1deg))
      let anchor = if calc.abs(c) > 0.4 { if c > 0 { "west" } else { "east" } } else if sn > 0 { "south" } else { "north" }
      content(q, txt(body), anchor: anchor)
    }
  })
}
// ---- What the AI writes, from here (the rule's example: everything above is given)
#mechanics(support: "circle", centre: [Terre], at: 60, radius: $r$, body: [S], vectors: (
  ("v", "along"),
  ("F", "centre"),
))
