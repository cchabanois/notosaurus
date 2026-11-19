// The figures' icons: a pictogram named by an English word, drawn at the size of the text
// around it (built by tools/icons.py: Maki's, Temaki's, ours, game-icons.net's, Phosphor's; their words in
// index.json, their plurals and singulars with them).

#let _ink = "#010203"
#let _halo = "#fefefd"
#let _mark = "<!--notosaurus-icon-->"
// What stands for an icon not drawn (a word no icon has, an SVG of one's own not drawable): an
// image of nothing, its reason in it for the app to read and take away (figures_typst)
#let _missing(why) = box(width: 0pt, height: 0pt, image(
  bytes("<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 1 1\"><!--notosaurus-icon-missing:" + why.replace("-", "‐").replace(">", "›") + "--></svg>"),
  format: "svg", width: 0.01pt, height: 0.01pt))
// A word as the index keys it: lower case, `-` and `_` as spaces
#let _key(w) = lower(w).replace("_", " ").replace("-", " ").split(" ").filter(p => p != "").join(" ")

// An icon's name for a word: the word as the index has it (its plurals and singulars there
// too), none else: never an icon guessed (a phrase's last word isn't its thing: a sperm cell
// isn't a cell, a lab stand isn't a lectern)
#let _found(words, k) = if k in words { words.at(k) } else { none }

// An SVG of the AI's own, for what no icon shows: simple shapes only (no text, image, link,
// script or style), one colour, at most 40 shapes; none when it isn't (not drawn)
#let _cleaned(svg) = {
  if type(svg) != str or svg.len() > 6000 { return none }
  let low = lower(svg)
  for bad in ("<text", "<script", "href", "<image", "<foreignobject", "<style", "style=", "url(", "<use", "<a ", "<animate", "<set", "@import", "javascript") {
    if low.contains(bad) { return none }
  }
  let tags = low.matches(regex("<\s*([a-z][a-z0-9:-]*)")).map(m => m.captures.at(0))
  if tags.any(t => t not in ("svg", "g", "path", "circle", "ellipse", "rect", "line", "polyline", "polygon")) { return none }
  if tags.filter(t => t not in ("svg", "g")).len() > 40 or not low.contains("viewbox") { return none }
  // one colour: each colour given, the icon's; none kept
  let s = svg.replace(regex("(fill|stroke)\s*=\s*\"([^\"]*)\""), m => {
    if lower(m.captures.at(1)).trim() == "none" { m.text } else { m.captures.at(0) + "=\"" + _ink + "\"" }
  })
  s.replace(regex("<svg\b"), "<svg fill=\"" + _ink + "\"", count: 1).replace(regex("(<svg\b[^>]*>)"), m => m.text + _mark, count: 1)
}

// icon("factory"): the icon an English word names (its name, or what it shows: port, battle,
// wheat, microscope), `size` high (the text's 1.4 times), in `fill`, a white halo round it
// (none: `halo: false`); icon(svg: "<svg …>"): an SVG of one's own, cleaned, when no icon shows
// it. A word no icon has, an SVG that can't be drawn: nothing drawn, the text beside it kept.
// The word only chooses: it is never written.
#let icon(..args, svg: none, size: 1.4em, fill: black, halo: true) = {
  let word = args.pos().at(0, default: none)
  let body = if svg != none { _cleaned(svg) } else {
    assert(type(word) == str, message: "icon(\"factory\"): an English word, as a string: the icon's name or what it shows")
    let index = json("index.json")
    let name = _found(index.words, _key(word))
    if name != none { read("icons/" + name + ".svg") }
  }
  if body == none { return _missing(if svg != none { "svg" } else { word }) }
  let ink = if type(fill) == color { fill.to-hex() } else { "#000000" }
  let svg-text = body.replace(_ink, ink).replace(_halo, if halo { "#ffffff" } else { "none" })
  box(baseline: 20%, image(bytes(svg-text), format: "svg", height: size, width: size, fit: "contain"))
}
