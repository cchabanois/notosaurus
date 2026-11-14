#set page(width: auto, height: auto, margin: 6pt)
#import "common.typ": *
// Sequences aligned to be compared (DNA, RNA, proteins: two alleles, a mutation, species):
// each letter in its column, whatever its width, and the differences with the first row of
// the same kind framed in each of them, computed, never placed by eye. rows: (name, sequence) pairs; a
// sequence is a string of letters (spaces ignored, "-" a gap: an insertion or a deletion),
// or its amino acids ("Met-Pro-Glu", or ("Met", "Pro", "Glu")), one per codon under a
// sequence three times as long; group: the letters gathered by (3: codons; 0: none);
// framed: false when a card asks where they differ; ask: ((name, position), …) the letters
// written "?" (a card asking which one), position from 1 in that row; numbers: the
// positions written above
#let sequences(rows: (), group: 3, framed: true, ask: (), numbers: false) = {
  assert(
    rows.len() > 0 and rows.all(r => type(r) == array and r.len() == 2 and type(r.at(1)) in (str, array)),
    message: "rows are (name, sequence) pairs, a sequence a string or a list of amino acids",
  )
  // a row's letters: one each, or its amino acids when written as words ("Met-Pro-Glu",
  // "MET-PRO-GLU"), told apart by their structure, whatever their case: nucleotides only
  // (A, C, G, T, U, N: "ATG GCA", "atg gca", "AT-GCA" with its gap) are letters; else
  // several words of more than one letter each are amino acids; else letters ("MKV")
  let tokens(s) = if type(s) == array { s.map(t => if type(t) == str { t.trim() } else { t }) } else {
    let words = s.split(regex("[\s\-–]+")).filter(w => w != "")
    let nucleotides = s.match(regex("(?i)^[\s\-–ACGTUN]*$")) != none
    let amino-acids = words.len() > 1 and words.all(w => w.clusters().len() > 1)
    if not nucleotides and amino-acids { words } else { s.clusters().filter(c => c.trim() != "") }
  }
  let seqs = rows.map(r => tokens(r.at(1)))
  let n = calc.max(..seqs.map(s => s.len()))
  // each row's letters span one column, or `group` (an amino acid under its codon)
  let spans = seqs.map(s => if s.len() == n { 1 } else if group > 1 and s.len() * group == n { group } else { 0 })
  for (k, s) in spans.enumerate() {
    assert(
      s > 0,
      message: "the sequences are aligned, as long as each other (a gap written -), or an amino acid per codon: "
        + rows.at(k).at(0) + " has " + str(seqs.at(k).len()) + " for " + str(n),
    )
  }
  for a in ask {
    assert(
      type(a) == array and a.len() == 2 and rows.any(r => r.at(0) == a.at(0)) and type(a.at(1)) == int,
      message: "ask is ((name, position), …), the name a row's, the position a number from 1",
    )
  }
  // a row's kind: its span and its letters (DNA, RNA with its U, amino acids); each kind
  // compared with its first row, a variant of it (most letters shared: a strand and its
  // complement, or its transcript, differ everywhere and are no variants)
  let kind(k) = {
    let letters = seqs.at(k).filter(t => t != "-")
    let caps = letters.map(t => if type(t) == str { upper(t) } else { t })
    let alphabet = if caps.all(t => t in ("A", "C", "G", "T")) { "dna" }
      else if caps.all(t => t in ("A", "C", "G", "U")) { "rna" } else { "other" }
    (spans.at(k), alphabet)
  }
  let kinds = range(rows.len()).map(kind)
  let reference(k) = seqs.at(kinds.position(c => c == kinds.at(k)))
  let different(k) = range(seqs.at(k).len()).filter(i => seqs.at(k).at(i) != reference(k).at(i))
  let variant(k) = kinds.filter(c => c == kinds.at(k)).len() > 1 and different(k).len() <= seqs.at(k).len() / 2
  // a column framed in every row of its kind once one of its variants differs there
  let differs(k, i) = range(rows.len()).any(j => kinds.at(j) == kinds.at(k) and variant(j) and i in different(j))
  // the columns: a letter's, then a narrow gap after each group
  let gap = group > 1
  let col(i) = 1 + i + if gap { calc.quo(i, group) } else { 0 }
  let columns = (auto,)
  for i in range(n) {
    columns.push(0.5cm)
    if gap and calc.rem(i + 1, group) == 0 and i < n - 1 { columns.push(0.22cm) }
  }
  let letter(body) = text(13pt, body)
  let cells = ()
  let top = if numbers { 1 } else { 0 }
  if numbers {
    for i in range(n) {
      if i == 0 or calc.rem(i + 1, if gap { group } else { 5 }) == (if gap { 1 } else { 0 }) {
        cells.push(grid.cell(x: col(i), y: 0, text(8pt, fill: luma(90), str(i + 1))))
      }
    }
  }
  for (k, (name, _)) in rows.enumerate() {
    let y = top + k
    cells.push(grid.cell(x: 0, y: y, align: left + horizon, inset: (right: 10pt), text(10pt, name)))
    let span = spans.at(k)
    for (i, t) in seqs.at(k).enumerate() {
      let first = col(i * span)
      let last = col(i * span + span - 1)
      let asked = ask.any(a => a.at(0) == name and a.at(1) == i + 1)
      let marked = framed and differs(k, i)
      cells.push(grid.cell(
        x: first, y: y, colspan: last - first + 1,
        fill: if marked { _highlight } else { none },
        stroke: if marked { 1.2pt + black } else { none },
        letter(if asked { "?" } else if t == "-" { "–" } else { t }),
      ))
    }
  }
  set text(font: "DejaVu Sans")
  grid(columns: columns, rows: 0.75cm, align: center + horizon, row-gutter: 3pt, ..cells)
}
// A double strand, its two strands face to face and each base joined to its pair: the top
// strand's bases as given, the bottom strand computed (A–T, G–C; A–U against RNA), or given
// and checked (a pair that isn't complementary refused, saying where); "-" a base not there
// yet (a strand being made), drawn empty, joined to nothing. Each strand's backbone a line;
// names: the strands' names, as the description gives them; ends: their 5' and 3' ends
// written, the two strands running opposite ways; bonds: the hydrogen bonds counted (two
// between A and T, three between G and C), else one link a pair; ask: ((strand, position),
// …) the bases written "?", the strand "top" or "bottom" (or its name), its position from 1
#let strands(top: "", bottom: auto, rna: false, names: (), ends: false, bonds: false, ask: ()) = {
  let bases(s) = s.clusters().filter(c => c.trim() != "").map(upper)
  assert(type(top) == str and bases(top).len() > 0, message: "strands' top is a strand's bases, \"ATG CCA\"")
  let up = bases(top)
  let pair = (A: if rna { "U" } else { "T" }, T: "A", U: "A", G: "C", C: "G")
  for (i, b) in up.enumerate() {
    assert(b in pair or b == "-", message: "a base is A, T, G, C or U, not " + b + " (top, position " + str(i + 1) + ")")
  }
  let down = if bottom == auto { up.map(b => if b == "-" { "-" } else { pair.at(b) }) } else {
    assert(type(bottom) == str, message: "strands' bottom is the other strand's bases, or left out (computed)")
    bases(bottom)
  }
  assert(
    down.len() == up.len(),
    message: "the two strands face to face have as many bases, a base not there yet written -: top "
      + str(up.len()) + ", bottom " + str(down.len()),
  )
  // U is RNA's: only against an RNA (rna: true), a DNA strand being made has T
  for (k, list) in ((0, up), (1, down)) {
    let at = list.position(b => b == "U")
    assert(
      rna or at == none,
      message: "U is an RNA's base: rna: true for an RNA facing the DNA (a transcription), else T ("
        + ("top", "bottom").at(k) + ", position " + str(if at == none { 0 } else { at + 1 }) + ")",
    )
  }
  for i in range(up.len()) {
    let (a, b) = (up.at(i), down.at(i))
    if a != "-" and b != "-" {
      assert(
        b in pair and (pair.at(a) == b or (a == "A" and b == "U") or (a == "U" and b == "A")),
        message: "position " + str(i + 1) + ": " + a + " faces " + b + ", no pair (A–T or A–U, G–C)",
      )
    }
  }
  assert(type(names) == array and names.len() in (0, 2), message: "names are the two strands' names, (top, bottom)")
  let label(k) = if names.len() == 2 { names.at(k) } else { none }
  let asked(k, i) = ask.any(a => (a.at(0) == ("top", "bottom").at(k) or a.at(0) == label(k)) and a.at(1) == i + 1)
  let n = up.len()
  let w = 0.6cm
  let link(a, b) = {
    if a == "-" or b == "-" { return none }
    let count = if not bonds { 1 } else if a in ("G", "C") { 3 } else { 2 }
    let stroke = if bonds { (paint: luma(40), thickness: 1.1pt, dash: (2pt, 1.5pt)) } else { 0.9pt + luma(60) }
    stack(dir: ltr, spacing: 3pt, ..range(count).map(_ => line(length: 0.5cm, angle: 90deg, stroke: stroke)))
  }
  let letter(k, i, b) = text(13pt, if asked(k, i) { "?" } else if b == "-" { "" } else { b })
  let end(t) = text(9pt, fill: luma(80), t)
  let cells = ()
  // columns: the name, an end, the bases, an end
  for (k, row) in ((0, 1), (1, 3)) {
    if label(k) != none { cells.push(grid.cell(x: 0, y: row, align: right + horizon, inset: (right: 8pt), text(10pt, label(k)))) }
    if ends {
      cells.push(grid.cell(x: 1, y: row, end(if k == 0 { "5'" } else { "3'" })))
      cells.push(grid.cell(x: n + 2, y: row, end(if k == 0 { "3'" } else { "5'" })))
    }
    for i in range(n) { cells.push(grid.cell(x: i + 2, y: row, letter(k, i, (up, down).at(k).at(i)))) }
  }
  for i in range(n) {
    let l = link(up.at(i), down.at(i))
    if l != none { cells.push(grid.cell(x: i + 2, y: 2, l)) }
  }
  // the backbones: above the top strand, under the bottom one, along the bases there
  let along(y, list) = {
    let present = range(n).filter(i => list.at(i) != "-")
    if present.len() == 0 { return () }
    (grid.hline(y: y, start: present.first() + 2, end: present.last() + 3, stroke: 2pt + luma(40)),)
  }
  set text(font: "DejaVu Sans")
  grid(
    columns: (auto, auto) + range(n).map(_ => w) + (auto,),
    rows: (4pt, 0.7cm, 0.6cm, 0.7cm, 4pt),
    align: center + horizon,
    ..cells,
    ..along(1, up),
    ..along(4, down),
  )
}
// ---- What the AI writes, from here (the rule's example: everything above is given)
#sequences(rows: (
  ("Allèle 1", "ATG GCA TTC"),
  ("Allèle 2", "ATG GCG TTC"),
))
