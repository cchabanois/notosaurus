#set page(width: auto, height: auto, margin: 6pt)
// Numbers written as the figure's language writes them: its decimal separator, set by
// figures_typst.source from the AI's `#set text(lang: …)` (a point when none is said)
#import "common.typ": *
// A table of values (a two-way table and its totals, a proportionality table and its
// multipliers, a conversion table, a frequency table): each column as wide as its widest
// cell (the values' columns alike) and each row as high as its highest, measured, never
// guessed; the totals summed; the arrows beside it (× 3 from a row to the next, × 2 from a
// column to another) drawn from the rows and columns they join, never placed by eye.
// rows: each row's cells (a text, a number, maths), its name first when the rows have one;
// header: the columns' names (their corner first when the rows have names: "" or left
// out); names: whether each row's first cell is its name (auto: when every first cell is a
// text that is no number); totals: "Total" (a column of each row's total and a row of each
// column's, the grand total in their corner), (right: "Total") the column only, (below:
// "Total") the row only, all summed; right / left: ((row, row, label), …) curved arrows
// from a row to another at that side; above / below: ((column, column, label), …) from a
// column to another; marked: ((row, column), …) cells highlighted. Rows and columns are
// counted from 1 among the values: the header and the names not counted. legend: a sentence
// under the table, written as a text cell is.
// A text cell as the AI writes it in quotes, shown as meant: its maths between `$` set as
// maths (a word math doesn't know, mol, written as text in it, LaTeX's \text{mol} too), and in its text an index or
// an exponent after a sign (H_2, x_(max), Cu^2+) and an arrow (->) drawn, never shown raw
#let _math-words = dictionary(sym).keys() + dictionary(math).keys()
#let _math-part(s) = eval(
  // LaTeX's text in a formula (\text{m}, its \t a tab once in a string) as Typst's: "m"
  s.replace(regex("(?:\\\\text|\\\\mathrm|\text)\{([^}]*)\}"), m => "\"" + m.captures.first() + "\"")
  .replace(regex("\"[^\"]*\"|\.?[A-Za-z]{2,}"), m => if m.text.starts-with("\"") or m.text.starts-with(".")
    or m.text in _math-words { m.text } else { "\"" + m.text + "\"" }),
  mode: "math",
)
#let _text-part(s) = {
  let s = s.replace("->", "→").replace("<-", "←")
  let out = ()
  let last = 0
  for m in s.matches(regex("(\S)([_^])(\([^)]*\)|\{[^}]*\}|\d+[+−-]?|[+−-]|[A-Za-z]+)")) {
    out.push(s.slice(last, m.start) + m.captures.at(0))
    let v = m.captures.at(2)
    if v.starts-with("(") or v.starts-with("{") { v = v.slice(1, -1) }
    out.push(if m.captures.at(1) == "_" { sub(v) } else { super(v) })
    last = m.end
  }
  out.push(s.slice(last))
  out.join()
}
#let _rich(s) = {
  let parts = s.split("$")
  if parts.len() < 3 or calc.rem(parts.len(), 2) == 0 { return _text-part(s) }
  // no empty text around a cell's maths: set alone, as a formula is
  parts.enumerate().filter(((k, p)) => p != "").map(((k, p)) => if calc.odd(k) { math.equation(_math-part(p)) }
  else { _text-part(p) }).join()
}
#let value-table(
  rows: (),
  header: none,
  names: auto,
  totals: none,
  right: (),
  left: (),
  above: (),
  below: (),
  marked: (),
  legend: none,
) = {
  assert(
    type(rows) == array and rows.len() > 0 and rows.all(r => type(r) == array),
    message: "rows is a list of rows, each a list of cells: rows: ((\"Fille\", 70, 30), (\"Garçon\", 60, 40))",
  )
  assert(header == none or type(header) == array, message: "header is a list of the columns' names")
  let numeric = regex("^\s*[−-]?\d+(?:[.,]\d+)?\s*$")
  let is-number(c) = type(c) in (int, float) or (type(c) == str and c.match(numeric) != none)
  let value(c) = if type(c) in (int, float) { c } else {
    let s = c.trim().replace("−", "-").replace(",", ".")
    if s.contains(".") { float(s) } else { int(s) }
  }
  // a number as the figure's language writes it: whole, or with its decimal separator; with
  // `digits` decimals, its zeros kept (a measure's 3,0), else as few as it needs
  let num(x, digits: none) = {
    let kept = digits != none and digits > 0
    written-number(x, digits: if kept { digits } else { 6 }, zeros: kept)
  }
  // the decimals a number is written with ("3,0": 1), none for a number given as a number
  let decimals(c) = if type(c) == str and c.match(numeric) != none {
    let parts = c.trim().split(regex("[.,]"))
    if parts.len() > 1 { parts.at(1).len() } else { 0 }
  } else { none }
  let named = if names == auto {
    rows.all(r => r.len() > 1 and type(r.at(0)) in (str, content) and r.at(0) != "" and not is-number(r.at(0)))
  } else { names }
  let first = if named { 1 } else { 0 }
  let width = calc.max(..rows.map(r => r.len()), if header == none { 0 } else { header.len() + if named and header.len() < calc.max(..rows.map(r => r.len())) { 1 } else { 0 } })
  let grid-rows = rows.map(r => r + ("",) * (width - r.len()))
  let head = if header == none { none } else {
    let h = if named and header.len() == width - 1 { ("",) + header } else { header }
    h + ("",) * (width - h.len())
  }
  // the totals: a column at the right (each row's), a row below (each column's)
  let (sum-right, sum-below) = if totals == none { (none, none) } else if type(totals) in (str, content) {
    (totals, totals)
  } else {
    assert(type(totals) == dictionary, message: "totals is \"Total\", (right: \"Total\") or (below: \"Total\")")
    (totals.at("right", default: none), totals.at("below", default: none))
  }
  let total(cells) = {
    assert(
      cells.all(c => c == "" or is-number(c)),
      message: "totals sum numbers: every value of the table is a number (" + repr(cells.find(c => c != "" and not is-number(c))) + ")",
    )
    let given = cells.filter(c => c != "")
    let sum = given.map(value).fold(0, (a, b) => a + b)
    // as many decimals as the numbers summed are written with
    let ds = given.map(decimals).filter(d => d != none)
    num(sum, digits: if ds.len() > 0 { calc.max(..ds) } else { none })
  }
  if sum-right != none {
    grid-rows = grid-rows.map(r => r + (total(r.slice(first)),))
    // its name above it, in a header row of its own when the table has none
    head = (if head == none { ("",) * width } else { head }) + (sum-right,)
  }
  if sum-below != none {
    let n = grid-rows.at(0).len()
    let last = (if named { (sum-below,) } else { () }) + range(first, n).map(j => {
      total(rows.map(r => r.at(j, default: "")))
    })
    // the grand total: the sum of the right column
    if sum-right != none { last.at(n - 1) = total(grid-rows.map(r => r.at(n - 1))) }
    grid-rows.push(last)
  }
  let n = grid-rows.at(0).len()
  let top = if head == none { 0 } else { 1 }
  let corner = std.top + std.left // `left` is a side's arrows here
  let all = (if head == none { () } else { (head,) }) + grid-rows
  // a digit with the number's comma after it (a conversion table's "3,"): the digit in the
  // middle of its column, the comma on the column's right edge, between it and the next
  let show-cell(c) = if type(c) == str and c.trim().match(regex("^\d[.,]$")) != none {
    c.trim().first() + place(std.right + std.horizon, dx: 2pt, dy: -1pt, text(weight: "bold", decimal-separator))
  } else if type(c) in (int, float) { num(c) } else if type(c) == str and c.match(numeric) != none {
    num(value(c), digits: decimals(c)) // as written, the language's separator
  } else if type(c) == str { _rich(c) } else { c }
  let txt(body, strong: false) = text(11pt, weight: if strong { "bold" } else { "regular" }, body)
  let rows-n = rows.len()
  let check(pairs, count, what) = for p in pairs {
    assert(
      type(p) == array and p.len() == 3 and type(p.at(0)) == int and type(p.at(1)) == int
        and p.at(0) >= 1 and p.at(1) >= 1 and p.at(0) <= count and p.at(1) <= count,
      message: what + " are ((from, to, label), …), from and to counted from 1 among the values' " + what + " (" + str(count) + ")",
    )
  }
  context {
    let pad-x = 7pt
    let pad-y = 5pt
    let cell(i, j) = {
      let c = all.at(i).at(j)
      let strong = (head != none and i == 0) or (named and j == 0)
      txt(show-cell(c), strong: strong)
    }
    let natural = range(n).map(j => calc.max(0.9cm, ..range(all.len()).map(i => measure(cell(i, j)).width + 2 * pad-x)))
    // the values' columns alike, as wide as the widest: the names' its own
    let value-width = calc.max(..natural.slice(first))
    let widths = range(n).map(j => if j < first { natural.at(j) } else { value-width })
    let heights = range(all.len()).map(i => calc.max(0.7cm, ..range(n).map(j => measure(cell(i, j)).height + 2 * pad-y)))
    let x-at(j) = widths.slice(0, j).sum(default: 0pt)
    let y-at(i) = heights.slice(0, i).sum(default: 0pt)
    let W = widths.sum()
    let H = heights.sum()
    // a value's row and column (from 1) as drawn
    let row-y(r) = y-at(top + r - 1) + heights.at(top + r - 1) / 2
    let col-x(c) = x-at(first + c - 1) + widths.at(first + c - 1) / 2
    check(right + left, rows-n, "rows")
    check(above + below, n - first - if sum-right != none { 1 } else { 0 }, "columns")
    let label(l) = txt(if type(l) in (int, float) { num(l) } else { l })
    let gap = 3pt
    let bulge(a, b) = 0.45cm + 0.12cm * calc.abs(a - b)
    let side-width(arrows) = arrows.fold(0pt, (m, a) => calc.max(m, bulge(a.at(0), a.at(1)) * 0.75 + measure(label(a.at(2))).width + 3 * gap))
    let side-height(arrows) = arrows.fold(0pt, (m, a) => calc.max(m, bulge(a.at(0), a.at(1)) * 0.75 + measure(label(a.at(2))).height + 3 * gap))
    let pl = side-width(left)
    let pr = side-width(right)
    let pt = side-height(above)
    let pb = side-height(below)
    let marks = marked.map(m => (top + m.at(0) - 1, first + m.at(1) - 1))
    let body = table(
      columns: widths,
      rows: heights,
      inset: 0pt,
      align: center + horizon,
      stroke: 0.7pt + black,
      fill: (j, i) => if (i, j) in marks { rgb("#fde68a") } else if (head != none and i == 0) or (named and j == 0) {
        luma(235)
      } else { none },
      ..range(all.len()).map(i => range(n).map(j => cell(i, j))).flatten(),
    )
    let stroke = 0.9pt + black
    // a curved arrow from p0 to p1, bulging toward d (a unit vector), its head at p1
    let arrow(p0, p1, d, b) = {
      let c0 = (p0.at(0) + d.at(0) * b, p0.at(1) + d.at(1) * b)
      let c1 = (p1.at(0) + d.at(0) * b, p1.at(1) + d.at(1) * b)
      place(corner, curve(stroke: stroke, curve.move(p0), curve.cubic(c0, c1, p1)))
      // the head along the curve's last tangent (from c1 to p1: against d)
      let (ux, uy) = (-d.at(0), -d.at(1))
      let (vx, vy) = (-uy, ux)
      let h = 5pt
      let w = 2.6pt
      place(corner, curve(
        fill: black,
        stroke: none,
        curve.move(p1),
        curve.line((p1.at(0) - ux * h + vx * w, p1.at(1) - uy * h + vy * w)),
        curve.line((p1.at(0) - ux * h - vx * w, p1.at(1) - uy * h - vy * w)),
        curve.close(),
      ))
    }
    let put(content, x, y) = place(corner, dx: x, dy: y, content)
    let drawn = block(width: pl + W + pr, height: pt + H + pb, {
      put(body, pl, pt)
      for (a, b, l) in right {
        let x = pl + W + gap
        let (y0, y1) = (pt + row-y(a), pt + row-y(b))
        let k = bulge(a, b)
        arrow((x, y0), (x, y1), (1, 0), k)
        let s = measure(label(l))
        put(label(l), x + k * 0.75 + gap, (y0 + y1) / 2 - s.height / 2)
      }
      for (a, b, l) in left {
        let x = pl - gap
        let (y0, y1) = (pt + row-y(a), pt + row-y(b))
        let k = bulge(a, b)
        arrow((x, y0), (x, y1), (-1, 0), k)
        let s = measure(label(l))
        put(label(l), x - k * 0.75 - gap - s.width, (y0 + y1) / 2 - s.height / 2)
      }
      for (a, b, l) in above {
        let y = pt - gap
        let (x0, x1) = (pl + col-x(a), pl + col-x(b))
        let k = bulge(a, b)
        arrow((x0, y), (x1, y), (0, -1), k)
        let s = measure(label(l))
        put(label(l), (x0 + x1) / 2 - s.width / 2, y - k * 0.75 - gap - s.height)
      }
      for (a, b, l) in below {
        let y = pt + H + gap
        let (x0, x1) = (pl + col-x(a), pl + col-x(b))
        let k = bulge(a, b)
        arrow((x0, y), (x1, y), (0, 1), k)
        let s = measure(label(l))
        put(label(l), (x0 + x1) / 2 - s.width / 2, y + k * 0.75 + gap)
      }
    })
    if legend == none { drawn } else {
      stack(spacing: 8pt, drawn, txt(if type(legend) == str { _rich(legend) } else { legend }))
    }
  }
}
// ---- What the AI writes, from here (the rule's example: everything above is given)
#set text(lang: "fr")
#value-table(
  header: ("", "Demi-pensionnaire", "Externe"),
  rows: (("Fille", 70, 30), ("Garçon", 60, 40)),
  totals: "Total",
)
