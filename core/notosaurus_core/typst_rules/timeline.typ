#set page(width: auto, height: auto, margin: 6pt)
#import "@preview/cetz:0.5.2"
#let timeline(start: 0, end: 10, step: 1, width: 12, events: (), periods: ()) = context {
  let unit = width / (end - start)
  // a date: its year, or (year, month, day): placed within its year
  let at(date) = if type(date) == array {
    (date.at(0) + (date.at(1, default: 1) - 1) / 12 + (date.at(2, default: 1) - 1) / 365 - start) * unit
  } else { (date - start) * unit }
  let gap = 0.25
  let shown(body) = {
    let t = text(9pt, body)
    if measure(t).width > 3cm { block(width: 3cm, t) } else { t }
  }
  let items = (
    events.map(e => (x: at(e.at(0)), body: shown(e.at(1))))
      + periods.map(p => (x: at(p.at(0)), body: shown(p.at(2))))
  ).sorted(key: i => -i.x)
  // From the right: each text starts at its date, above the line, on the first row where it
  // reaches no text on its row and passes over the lines of those it reaches: no line
  // crosses a text
  let placed = ()
  for item in items {
    let size = measure(item.body)
    let right = item.x + 0.1 + size.width / 1cm
    let row = 1
    while not placed.all(q => right + gap <= q.x or row > q.row) { row += 1 }
    placed.push((..item, h: size.height / 1cm, row: row))
  }
  let tall = calc.max(0.4, ..placed.map(p => p.h)) + 0.2
  let y(row) = 0.3 + (row - 1) * tall
  cetz.canvas({
    import cetz.draw: *
    for p in periods {
      rect((at(p.at(0)), -0.14), (at(p.at(1)), 0.14), fill: luma(225), stroke: 0.6pt)
    }
    line((-0.3, 0), (width + 0.6, 0), stroke: 0.8pt, mark: (end: ">", fill: black))
    let year = start
    while year <= end {
      line((at(year), -0.1), (at(year), 0.1), stroke: 0.6pt)
      content((at(year), -0.2), text(8pt, if year < 0 { "−" + str(-year) } else { str(year) }), anchor: "north")
      year += step
    }
    for p in placed {
      line((p.x, 0.14), (p.x, y(p.row) + p.h), stroke: 0.4pt)
      content((p.x + 0.1, y(p.row)), p.body, anchor: "south-west")
    }
    for e in events { circle((at(e.at(0)), 0), radius: 0.07, fill: black) }
  })
}
// ---- What the AI writes, from here (the rule's example: everything above is given)
#timeline(start: 1788, end: 1800, step: 2,
  events: (((1789, 7, 14), "Prise de la Bastille, 14 juillet 1789"), (1792, "Proclamation de la République")),
  periods: ((1793, 1794, "La Terreur"),),
)
