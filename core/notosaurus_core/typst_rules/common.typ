// What every family's preamble shares: written once, here; inlined where a preamble imports it
// (figures_typst._family), each figure compiled alone, and imported as it is when a family's
// .typ is compiled whole (by the tests, in an editor).

// Numbers written as the figure's language writes them: its decimal separator, set by
// figures_typst.source from the AI's `#set text(lang: …)` (a point when none is said)
#let decimal-separator = "."
// A number as the figure's language writes it: rounded to `digits` decimals and written with as
// few as it needs, or with all of them when `zeros` (a measure's 3,0); its decimal separator, a
// true minus sign, its thousands apart from 10 000 on (a narrow space, as school writes them)
#let written-number(x, digits: 6, zeros: false) = {
  let r = calc.round(float(x), digits: digits)
  let whole = calc.trunc(calc.abs(r))
  let unit = calc.pow(10, digits)
  let part = int(calc.round((calc.abs(r) - whole) * unit))
  if part >= unit { (whole, part) = (whole + 1, 0) }
  let tail = str(part)
  tail = "0" * (digits - tail.len()) + tail
  if not zeros { tail = tail.trim("0", at: end) }
  let w = str(int(whole))
  if w.len() > 4 {
    let n = w.len()
    w = range(n).map(i => (if i > 0 and calc.rem(n - i, 3) == 0 { "\u{202F}" } else { "" }) + w.at(i)).join()
  }
  let s = if tail == "" { w } else { w + decimal-separator + tail }
  if r < 0 and (whole > 0 or part > 0) { "−" + s } else { s }
}
// A graduation's round steps from `low` to `high`, in order: 1, 2, 2.5 and 5 times a power of
// ten, as large or as small as the values need (a city's inhabitants, a probability)
#let round-steps(low, high) = {
  let e = calc.floor(calc.log(low, base: 10))
  let steps = ()
  while e <= calc.ceil(calc.log(high, base: 10)) {
    for b in (1, 2, 2.5, 5) {
      let s = if e >= 0 { b * calc.pow(10, e) } else { calc.round(b / calc.pow(10, -e), digits: 1 - e) }
      if s >= low * (1 - 1e-9) and s <= high * (1 + 1e-9) { steps.push(if calc.fract(s) == 0 { int(s) } else { s }) }
    }
    e += 1
  }
  steps
}
// The smallest round step giving at most `most` steps over `span`
#let round-step(span, most) = if span <= 0 { 1 } else { round-steps(span / most, 10 * span / most).first() }

// Vectors: points and directions as their coordinates, (x, y), or (x, y, z) in a solid
#let _add(a, b) = a.zip(b).map(((x, y)) => x + y)
#let _sub(a, b) = a.zip(b).map(((x, y)) => x - y)
#let _mul(a, k) = a.map(x => x * k)
#let _dot(a, b) = a.zip(b).map(((x, y)) => x * y).sum()
#let _len(a) = calc.sqrt(_dot(a, a))
#let _unit(a) = { let n = _len(a); if n < 1e-9 { a.map(_ => 0) } else { _mul(a, 1 / n) } }
// in the plane: the way at angle t, a vector's angle, the point at distance d from p at angle a
#let _dir(t) = (calc.cos(t), calc.sin(t))
#let _angle(v) = calc.atan2(v.at(0), v.at(1))
#let _off(p, a, d) = (p.at(0) + d * calc.cos(a), p.at(1) + d * calc.sin(a))
// How far a point is from a segment
#let _gap(p, a, b) = {
  let (ab, ap) = (_sub(b, a), _sub(p, a))
  let t = calc.clamp(_dot(ap, ab) / calc.max(_dot(ab, ab), 1e-9), 0, 1)
  let d = _sub(p, a.zip(ab).map(((x, y)) => x + t * y))
  calc.sqrt(_dot(d, d))
}

// A text's characters, to measure or compare it: a name's letters, a space for what has none
#let _plain(c) = if type(c) == str { c } else if c.has("text") { c.text } else if c.has("children") { c.children.map(_plain).join() } else if c.has("body") { _plain(c.body) } else { " " }
