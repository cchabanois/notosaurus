// The figures' icons: a pictogram named by an English word, drawn at the size of the text
// around it (built by tools/icons.py: Maki's, Temaki's, ours; their tags in index.json).

#let _ink = "#010203"
#let _halo = "#fefefd"
#let _mark = "<!--notosaurus-icon-->"
// A word as the index keys it: lower case, `-` and `_` as spaces
#let _key(w) = lower(w).replace("_", " ").replace("-", " ").split(" ").filter(p => p != "").join(" ")

// An icon's name for a word: the word itself, or without its plural's s (factories: factory)
#let _found(words, k) = {
  let tries = (k,)
  if k.ends-with("ies") { tries.push(k.slice(0, -3) + "y") }
  if k.ends-with("es") { tries.push(k.slice(0, -2)) }
  if k.ends-with("s") { tries.push(k.slice(0, -1)) }
  for t in tries { if t in words { return words.at(t) } }
  none
}

// The icons whose words come nearest to an unknown one (sharing its beginning, or one within
// the other): their names and first words, for the refusal
#let _nearest(index, k) = {
  let head = k.slice(0, calc.min(3, k.len()))
  let near = index.words.keys().filter(w => w.starts-with(head) or (k.len() >= 4 and w.len() >= 4 and (w.contains(k) or k.contains(w))))
  near.map(w => index.words.at(w)).dedup().slice(0, calc.min(8, near.map(w => index.words.at(w)).dedup().len()))
}

// An SVG of the AI's own, for what no icon shows: simple shapes only (no text, image, link,
// script or style), one colour, at most 40 shapes
#let _cleaned(svg) = {
  assert(type(svg) == str and svg.len() <= 6000, message: "icon(svg: …): an SVG as a string, 6000 characters at most, its simple shapes")
  let low = lower(svg)
  for bad in ("<text", "<script", "href", "<image", "<foreignobject", "<style", "style=", "url(", "<use", "<a ", "<animate", "<set", "@import", "javascript") {
    if low.contains(bad) { panic("icon(svg: …): simple shapes only (path, circle, ellipse, rect, line, polyline, polygon, g), never " + bad.trim("<").trim()) }
  }
  let tags = low.matches(regex("<\s*([a-z][a-z0-9:-]*)")).map(m => m.captures.at(0))
  let other = tags.filter(t => t not in ("svg", "g", "path", "circle", "ellipse", "rect", "line", "polyline", "polygon"))
  if other.len() > 0 { panic("icon(svg: …): simple shapes only (path, circle, ellipse, rect, line, polyline, polygon, g), never " + other.first()) }
  if tags.filter(t => t not in ("svg", "g")).len() > 40 { panic("icon(svg: …): 40 shapes at most: a simpler icon") }
  if not low.contains("viewbox") { panic("icon(svg: …): its <svg> has a viewBox") }
  // one colour: each colour given, the icon's; none kept
  let s = svg.replace(regex("(fill|stroke)\s*=\s*\"([^\"]*)\""), m => {
    if lower(m.captures.at(1)).trim() == "none" { m.text } else { m.captures.at(0) + "=\"" + _ink + "\"" }
  })
  s.replace(regex("<svg\b"), "<svg fill=\"" + _ink + "\"", count: 1).replace(regex("(<svg\b[^>]*>)"), m => m.text + _mark, count: 1)
}

// icon("factory"): the icon an English word names (its name, or what it shows: port, battle,
// wheat), `size` high (the text's 1.4 times), in `fill`, a white halo round it (none: `halo:
// false`); icon(svg: "<svg …>"): an SVG of one's own, cleaned, when no icon shows it. The word
// only chooses: it is never written.
#let icon(..args, svg: none, size: 1.4em, fill: black, halo: true) = {
  let word = args.pos().at(0, default: none)
  let body = if svg != none { _cleaned(svg) } else {
    assert(type(word) == str, message: "icon(\"factory\"): an English word, as a string: the icon's name or what it shows")
    let index = json("index.json")
    let k = _key(word)
    let name = _found(index.words, k)
    if name == none {
      let near = _nearest(index, k)
      panic("no icon for \"" + word + "\": name it by an English word, what it shows" + if near.len() > 0 {
        " (near: " + near.map(n => n + " (" + index.icons.at(n) + ")").join(", ") + ")"
      } else { " (factory, port, battle, castle, church, wheat)" })
    }
    read("icons/" + name + ".svg")
  }
  let ink = if type(fill) == color { fill.to-hex() } else { "#000000" }
  let svg-text = body.replace(_ink, ink).replace(_halo, if halo { "#ffffff" } else { "none" })
  box(baseline: 20%, image(bytes(svg-text), format: "svg", height: size, width: size, fit: "contain"))
}
