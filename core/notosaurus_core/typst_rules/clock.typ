#set page(width: auto, height: auto, margin: 6pt)
#import "@preview/cetz:0.5.2"
// A clock's face at hour:minute: its hands placed by the time, never by eye (the hour hand
// between its two hours as the minutes go by). numbers: the 12 hours written; minutes: the
// minutes written around it every 5 (5, 10… 55, to read "twenty past"); the hands' colours
// when the lesson gives them (a red hour hand)
#let clock(hour, minute, numbers: true, minutes: false, hour-color: black, minute-color: black) = {
  assert(type(hour) == int and 0 <= hour and hour < 24, message: "the hour is a whole number from 0 to 23")
  assert(type(minute) == int and 0 <= minute and minute < 60, message: "the minute is a whole number from 0 to 59")
  let r = 2
  // a point at a clock's angle (0: twelve o'clock, clockwise) and a distance from its centre
  let at(turns, length) = {
    let a = 90deg - turns * 360deg
    (length * calc.cos(a), length * calc.sin(a))
  }
  cetz.canvas({
    import cetz.draw: *
    circle((0, 0), radius: r, stroke: 1.4pt)
    for i in range(60) {
      let five = calc.rem(i, 5) == 0
      line(at(i / 60, if five { r * 0.86 } else { r * 0.93 }), at(i / 60, r), stroke: if five { 1.2pt } else { 0.5pt })
    }
    let hand(turns, length, width, color) = line((0, 0), at(turns, length), stroke: (paint: color, thickness: width, cap: "round"))
    hand((calc.rem(hour, 12) + minute / 60) / 12, r * 0.50, 3.2pt, hour-color)
    hand(minute / 60, r * 0.90, 1.8pt, minute-color)  // to the minutes' marks, under the numbers
    circle((0, 0), radius: 0.07, fill: black, stroke: none)
    // the numbers over the hands, on white: a hand never hides one, it passes under it
    if numbers {
      for h in range(1, 13) {
        content(at(h / 12, r * 0.70), text(13pt, font: "DejaVu Sans", str(h)), frame: "rect", fill: white, stroke: none, padding: 0.03)
      }
    }
    if minutes {
      for m in range(5, 60, step: 5) { content(at(m / 60, r * 1.16), text(8pt, font: "DejaVu Sans", fill: luma(90), str(m))) }
    }
  })
}
// ---- What the AI writes, from here (the rule's example: everything above is given)
#clock(10, 25)
