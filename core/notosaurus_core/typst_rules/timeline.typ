#set page(width: auto, height: auto, margin: 6pt)
#import "@preview/cetz:0.5.2"
#import "common.typ": *
// A line of dates: events above it (a dot, a text on its line, an icon before it when given),
// periods under it, each a bar
// in its own colour from its start to its end, its name on it; the years on the line's round
// multiples of `step` (1500, 1600, never 1453, 1553). A line of moments without dates (a
// verb's tenses), 0 the present: `step: none` writes no year; `now` the present's text, under
// its mark across the line at 0; `past` and `future` written under the line's two ends.
// A colour the description gives: a period's (start, end, name, red) its bar in it (lightened,
// its name read on it); an event's (date, text, red), with or without its icon, its dot, line
// and text in it
#let timeline(
  start: 0, end: 10, step: 1, width: 12, events: (), periods: (), now: none, past: none, future: none,
) = context {
  assert(type(start) in (int, float) and type(end) in (int, float) and end > start, message: "end is after start: the line's two years, end greater than start")
  assert(step == none or (type(step) in (int, float) and step > 0), message: "step is the years between two numbers written, a positive number, or none")
  // one event or period written without its trailing comma, ((1789, "…")): Typst's pair, not
  // a list of one (its last item its text, a list's last item an event)
  let events = if events.len() > 0 and type(events.last()) != array { (events,) } else { events }
  let periods = if periods.len() > 0 and type(periods.last()) != array { (periods,) } else { periods }
  for p in periods {
    if type(p) != array or p.len() not in (3, 4) or (p.len() == 4 and type(p.at(3)) != color) {
      panic("periods: each (start, end, name) or (start, end, name, red), not " + repr(p))
    }
  }
  // an event's icon (a word) and colour, after its text, either or both
  let icon-of(e) = e.slice(2).find(x => type(x) == str)
  let colour-of(e) = e.slice(2).find(x => type(x) == color)
  for e in events {
    if type(e) != array or e.len() < 2 or e.len() > 4 or e.slice(2).any(x => type(x) not in (str, color)) {
      panic("events: each (date, text), (date, text, \"icon\"), (date, text, red) or (date, text, \"icon\", red), not " + repr(e))
    }
  }
  // a date: its year, or (year, month, day): placed within its year
  let year(date) = if type(date) == array { date.at(0) } else { date }
  let when(date) = if type(date) == array {
    date.at(0) + (date.at(1, default: 1) - 1) / 12 + (date.at(2, default: 1) - 1) / 365
  } else { date }
  // a period's end: a period of one year, (1914, 1914), lasts that year
  let until(p) = if p.at(1) == p.at(0) and type(p.at(1)) != array { p.at(1) + 1 } else { p.at(1) }
  // the line holds every date it is given, a start or an end given too short
  let dates = events.map(e => when(e.at(0))) + periods.map(p => when(p.at(0))) + periods.map(p => when(until(p)))
  let start = calc.min(start, ..dates)
  let end = calc.max(end, ..dates)
  let unit = width / (end - start)
  let at(date) = (when(date) - start) * unit
  let written-year(y) = written-number(y)
  // A dated line's texts keep their year: written by the function after a text that doesn't
  // have it (its digits, whatever the spaces), never asked of the AI
  let dated = step != none
  let has-year(body, y) = {
    let s = _plain(body).replace(" ", "").replace("\u{202F}", "").replace("\u{A0}", "").replace("\u{2009}", "")
    s.contains(str(calc.abs(int(y))))
  }
  let gap = 0.25
  let shown(body) = {
    let t = text(11pt, body)
    if measure(t).width > 3.7cm { block(width: 3.7cm, t) } else { t }
  }
  // a number's groups of three digits kept together (−18 000 never cut at its space)
  let kept(body) = if type(body) == str { body.replace(regex("(\d) (\d{3})\b"), m => m.captures.at(0) + "\u{202F}" + m.captures.at(1)) } else { body }
  let items = events.map(e => {
    let y = year(e.at(0))
    let body = if dated and calc.fract(y) == 0 and not has-year(e.at(1), y) { [#kept(e.at(1)) (#written-year(y))] } else { kept(e.at(1)) }
    // an event's icon (an English word: icon()), before its text; its colour, its text's
    if icon-of(e) != none { body = [#icon(icon-of(e)) #body] }
    let paint = colour-of(e)
    (x: at(e.at(0)), body: shown(if paint == none { body } else { text(fill: paint, body) }), paint: paint)
  }).sorted(key: i => -i.x)
  // From the right: each text starts at its date, above the line, over every text it reaches
  // (and so over their lines): no line crosses a text, no text on another
  let placed = ()
  for item in items {
    let size = measure(item.body)
    let right = item.x + 0.1 + size.width / 1cm
    let y = 0.3
    for q in placed { if q.x < right + gap { y = calc.max(y, q.y + q.h + 0.3) } }
    placed.push((..item, h: size.height / 1cm, y: y))
  }
  // Under the line: what is written there (its years, now, past, future), then the periods'
  // lanes
  let under = calc.max(
    0.3,
    if dated { 0.2 + measure(text(10pt, [0])).height / 1cm + 0.25 } else { 0 },
    if (now, past, future).any(t => t != none) { 0.4 + measure(text(11pt, [Ag])).height / 1cm + 0.25 } else { 0 },
  )
  let palette = (
    rgb("#9cc9e8"), rgb("#f6c76b"), rgb("#a5d18f"), rgb("#f2a7ad"), rgb("#c3b1e1"), rgb("#f3e08a"),
    rgb("#8fd3c9"), rgb("#e8b48f"),
  )
  // A period: its bar from its start to its end (a period of one year, (1914, 1914), that
  // year); its name on it, centred, on two lines when it is too long for one; its years under
  // its name when the name hasn't them. A bar too short for its name's longest word: the name
  // under the lanes, on a line from the bar, placed as the events are (no text on another)
  let pad = 0.06
  let bars = periods.enumerate().map(((i, p)) => {
    let x0 = at(p.at(0))
    let x1 = at(until(p))
    if x1 < x0 + 0.12 { x1 = x0 + 0.12 }
    let (y0, y1) = (year(p.at(0)), year(p.at(1)))
    let years = if dated and calc.fract(y0) == 0 and calc.fract(y1) == 0 and not has-year(p.at(2), y0) {
      text(10pt, if y1 <= y0 { written-year(y0) } else if y0 < 0 or y1 < 0 { written-year(y0) + " – " + written-year(y1) } else { written-year(y0) + "–" + written-year(y1) })
    }
    let name = { set par(leading: 0.4em); text(11pt, kept(p.at(2))) }
    // the name and its years, `w` wide (cm), aligned `where`
    let named(w, where) = block(width: w * 1cm, if years == none { align(where, name) } else {
      stack(spacing: 2pt, align(where, name), align(where, years))
    })
    let one = calc.max(measure(name).width, if years != none { measure(years).width } else { 0pt }) / 1cm
    let inner = x1 - x0 - 2 * pad
    let words = _plain(kept(p.at(2))).split(" ").map(w => measure(text(11pt, w)).width / 1cm)
    let widest = calc.max(0, ..words, ..if years != none { (measure(years).width / 1cm,) })
    let (body, inside) = if one <= inner { (named(one + 0.05, center), true) } else if widest <= inner and measure(block(width: inner * 1cm, name)).height <= measure(name).height * 3 {
      (named(inner, center), true)
    } else {
      (named(if one > 4.5 { 3.7 } else { one + 0.05 }, left), false)
    }
    let size = measure(body)
    (i: i, x0: x0, x1: x1, body: body, inside: inside, w: size.width / 1cm, h: size.height / 1cm, paint: p.at(3, default: none))
  })
  // Lanes: in order of start, each bar on the first lane where it overlaps none: periods that
  // overlap on different lanes, as few lanes as there are periods at once; periods that
  // follow each other on one
  let lanes = ()
  let lane-of = (:)
  for b in bars.sorted(key: b => (b.x0, -b.x1)) {
    let k = lanes.position(last => last <= b.x0 + 1e-6)
    if k == none { lanes.push(b.x1); k = lanes.len() - 1 } else { lanes.at(k) = b.x1 }
    lane-of.insert(str(b.i), k)
  }
  let lane-h = range(lanes.len()).map(k => {
    let inside = bars.filter(b => lane-of.at(str(b.i)) == k and b.inside).map(b => b.h)
    calc.max(0.5, ..inside.map(h => h + 0.2))
  })
  let lane-top(k) = -under - lane-h.slice(0, k).sum(default: 0) - 0.1 * k
  let bottom = lane-top(lanes.len())
  // The names written under the lanes: from the right, each from its bar's middle, under
  // every name it reaches
  let notes = ()
  for b in bars.filter(b => not b.inside).sorted(key: b => -(b.x0 + b.x1)) {
    let x = (b.x0 + b.x1) / 2
    let y = bottom - 0.2
    for q in notes { if q.x < x + 0.1 + b.w + gap { y = calc.min(y, q.y - q.h - gap) } }
    notes.push((x: x, y: y, h: b.h, body: b.body, i: b.i))
  }
  cetz.canvas({
    import cetz.draw: *
    line((-0.3, 0), (width + 0.6, 0), stroke: 0.8pt, mark: (end: ">", fill: black))
    if dated {
      let first = calc.ceil(start / step - 1e-9)
      let n = first
      while n * step <= end + 1e-9 * calc.abs(step) {
        let y = n * step
        line((at(y), -0.1), (at(y), 0.1), stroke: 0.6pt)
        content((at(y), -0.2), text(10pt, written-number(y)), anchor: "north")
        n += 1
      }
    }
    if now != none {
      line((at(0), -0.3), (at(0), 0.3), stroke: 1.6pt)
      content((at(0), -0.4), text(11pt, now), anchor: "north")
    }
    if past != none { content((-0.3, -0.4), text(11pt, past), anchor: "north-west") }
    if future != none { content((width + 0.6, -0.4), text(11pt, future), anchor: "north-east") }
    for b in bars {
      let k = lane-of.at(str(b.i))
      let (top, h) = (lane-top(k), lane-h.at(k))
      let fill = if b.paint == none { palette.at(calc.rem(b.i, palette.len())) } else { b.paint.lighten(35%) }
      rect((b.x0, top), (b.x1, top - h), fill: fill, stroke: 0.5pt + luma(80))
      if b.inside { content(((b.x0 + b.x1) / 2, top - h / 2), b.body, anchor: "center") }
    }
    for n in notes {
      let k = lane-of.at(str(n.i))
      line((n.x, lane-top(k) - lane-h.at(k)), (n.x, n.y - n.h), stroke: 0.4pt)
      content((n.x + 0.1, n.y), n.body, anchor: "north-west")
    }
    for p in placed {
      line((p.x, 0.14), (p.x, p.y + p.h), stroke: 0.4pt + if p.paint == none { black } else { p.paint })
      content((p.x + 0.1, p.y), p.body, anchor: "south-west")
    }
    for e in events {
      let paint = if colour-of(e) == none { black } else { colour-of(e) }
      circle((at(e.at(0)), 0), radius: 0.07, fill: paint, stroke: paint)
    }
  })
}
// ---- What the AI writes, from here (the rule's example: everything above is given)
#timeline(start: 1788, end: 1800, step: 2,
  events: (((1789, 7, 14), "Prise de la Bastille, 14 juillet 1789"), (1792, "Proclamation de la République")),
  periods: ((1793, 1794, "La Terreur"),),
)
