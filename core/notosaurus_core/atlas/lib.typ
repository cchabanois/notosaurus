// The map of the figures' "map" family (typst_rules/map.md): countries, cities, regions,
// rivers, reliefs and waters from the atlas (made by tools/atlas.py from Natural Earth),
// never placed by the AI. A place is found by any of its names (the page's languages), a
// country by its three-letter code too; one the atlas doesn't have stops the figure, said
// (never placed by guess). Routes and flows go from place to place, a sea route's way
// computed over the sea (ways.json). The frame holds the countries, regions, groups, cities,
// routes and flows asked (else the rivers, reliefs and waters); what is around drawn grey,
// cut to it.

#let atlas = json("atlas.json")

// A name as tools/atlas.py folded it (the same): lower case, its marked letters plain, its
// hyphens, apostrophes and dots spaces, its spaces single
#let fold(name) = {
  let plain = lower(name).clusters().map(c => atlas.letters.at(c, default: c)).join(default: "")
  plain.replace(regex("[-'’.]"), " ").replace(regex("\s+"), " ").trim()
}

#let find-country(name) = {
  let key = fold(name)
  for (code, country) in atlas.countries {
    if key in country.k { return code }
  }
  panic("no country called \"" + name + "\" in the atlas: its usual name, or its three-letter code (\"ESP\")")
}

// A city: among those of the countries shown first, else a place of history lessons (h:
// Cordoue, Spain's, not Argentina's), else the most populated of that name
#let city-index(name, shown) = {
  let key = fold(name)
  let found = atlas.cities.enumerate().filter(((_, c)) => key in c.k)
  if found.len() == 0 { return none }
  let theirs = found.filter(((_, c)) => c.c in shown)
  (if theirs.len() > 0 { theirs } else { found }).sorted(key: ((_, c)) => (-c.at("h", default: 0), -c.p)).first().at(0)
}
#let find-city(name, shown) = {
  let i = city-index(name, shown)
  if i == none {
    panic("no city called \"" + name + "\" in the atlas (a country's capital, its largest cities, the places of history lessons): leave it out")
  }
  atlas.cities.at(i)
}

#let size(b) = (b.at(2) - b.at(0)) * (b.at(3) - b.at(1))
#let touches(b, c) = b.at(2) >= c.at(0) and b.at(0) <= c.at(2) and b.at(3) >= c.at(1) and b.at(1) <= c.at(3)

// A river, relief or water: of that name, those on the countries shown first (`near`, their
// box), the largest of them
#let find-in(items, name, what, near) = {
  let key = fold(name)
  let found = items.filter(i => key in i.k)
  if found.len() == 0 { panic("no " + what + " called \"" + name + "\" in the atlas: leave it out") }
  let theirs = if near == none { () } else { found.filter(i => touches(i.b, near)) }
  (if theirs.len() > 0 { theirs } else { found }).sorted(key: i => -size(i.b)).first()
}

// A region of a country shown: its first-level divisions (a state, a département) or their
// groups (a région); `level` which of the two it is
#let find-region(name, shown) = {
  let key = fold(name)
  for code in shown {
    let file = json("regions/" + code + ".json")
    for level in ("groups", "units") {
      for (i, r) in file.at(level).enumerate() {
        if key in r.k { return (code: code, level: level, index: i) }
      }
    }
  }
  if shown.len() == 0 { panic("a region (\"" + name + "\") is shown with its country: put it in countries") }
  panic("no region called \"" + name + "\" in the atlas for " + shown.join(", ") + ": leave it out")
}

// The groups' colours, one each in their order: Okabe and Ito's, told apart by those who see
// colours differently, light enough for a name on them; the sky blue, nearest the sea's, last
#let palette = ("#e69f00", "#0072b2", "#009e73", "#cc79a7", "#d55e00", "#f0e442", "#56b4e9", "#a6761d").map(rgb)

// Groups as asked, checked: (name, countries: their codes, regions: their names)
#let read-groups(groups) = {
  if type(groups) == dictionary { groups = (groups,) }  // a single group without its comma
  if groups.len() > palette.len() {
    panic("at most " + str(palette.len()) + " groups on a map, one colour each: join some")
  }
  let seen = (:)
  let out = ()
  for g in groups {
    if type(g) != dictionary or "name" not in g {
      panic("a group is (name: \"…\", countries: (…), regions: (…)): its name, for the legend, and what it holds")
    }
    for key in g.keys() {
      if key not in ("name", "countries", "regions") {
        panic("a group holds a name, countries and regions, not \"" + key + "\"")
      }
    }
    let listed(key) = {
      let v = g.at(key, default: ())
      if type(v) == str { (v,) } else { v }
    }
    let codes = listed("countries").map(find-country)
    if codes.len() + listed("regions").len() == 0 {
      panic("the group \"" + g.name + "\" holds no country nor region")
    }
    for (code, name) in codes.zip(listed("countries")) {
      if code in seen {
        panic("\"" + name + "\" is in two groups (\"" + seen.at(code) + "\" and \"" + g.name + "\"): one group each")
      }
      seen.insert(code, g.name)
    }
    out.push((name: g.name, countries: codes, regions: listed("regions")))
  }
  out
}

// Routes and flows: the places they pass found in the atlas, a sea route's way computed
// over the sea ways (ways.json, made by tools/atlas.py: nodes off the coasts and over the
// open sea, each joined to those it sees), never drawn by eye

// A difference of longitude the short way round (the Pacific crossed, not the world)
#let east(dx) = calc.rem-euclid(dx + 180 * atlas.scale, 360 * atlas.scale) - 180 * atlas.scale
// How far apart two points are, as ways.json measures it (a degree of longitude shortened
// by its latitude's cosine)
#let far(a, b) = {
  let dx = east(b.at(0) - a.at(0)) * calc.cos((a.at(1) + b.at(1)) / 2 / atlas.scale * 1deg)
  calc.sqrt(dx * dx + calc.pow(b.at(1) - a.at(1), 2))
}
// Beyond the polar circles the sea is ice: a route goes there only when it names a place there
#let polar = 66.5 * atlas.scale

// The shortest way over the sea from any of `sources` ((node, cost from the place)) to any
// of `targets` (node as a string: its cost to the place), toward `goal` (a point, or none):
// its nodes, or none when the sea joins them nowhere (A*, a heap of (estimate, cost, node))
#let sea-way(ways, sources, targets, goal, icy) = {
  let n = ways.p.len()
  let best = (none,) * n
  let prev = (none,) * n
  let guess(u) = if goal == none { 0 } else { far(ways.p.at(u), goal) * 0.95 }
  let heap = ()
  for (u, c) in sources {
    if best.at(u) == none or c < best.at(u) { best.at(u) = c }
  }
  for (u, c) in sources {
    if c == best.at(u) { heap.push((c + guess(u), c, u)) }
  }
  heap = heap.sorted(key: e => e.at(0))  // sorted, a heap already
  let found = none
  // (a for loop: Typst stops a while loop after ten thousand turns)
  for _ in range(ways.a.map(a => a.len()).sum() + sources.len()) {  // at most a turn per way in
    if heap.len() == 0 { break }
    let top = heap.first()
    if found != none and top.at(0) >= found.at(0) { break }
    let last = heap.pop()
    if heap.len() > 0 {
      heap.at(0) = last
      let i = 0
      let m = heap.len()
      while true {
        let (l, r) = (2 * i + 1, 2 * i + 2)
        let least = i
        if l < m and heap.at(l).at(0) < heap.at(least).at(0) { least = l }
        if r < m and heap.at(r).at(0) < heap.at(least).at(0) { least = r }
        if least == i { break }
        (heap.at(i), heap.at(least)) = (heap.at(least), heap.at(i))
        i = least
      }
    }
    let (_, g, u) = top
    if g > best.at(u) { continue }
    let key = str(u)
    if key in targets {
      let total = g + targets.at(key)
      if found == none or total < found.at(0) { found = (total, u) }
    }
    let next = ways.a.at(u)
    for j in range(0, next.len(), step: 2) {
      let v = next.at(j)
      let d = g + next.at(j + 1)
      if (best.at(v) == none or d < best.at(v)) and (icy or calc.abs(ways.p.at(v).at(1)) <= polar) {
        best.at(v) = d
        prev.at(v) = u
        heap.push((d + guess(v), d, v))
        let i = heap.len() - 1
        while i > 0 {
          let up = calc.div-euclid(i - 1, 2)
          if heap.at(up).at(0) <= heap.at(i).at(0) { break }
          (heap.at(i), heap.at(up)) = (heap.at(up), heap.at(i))
          i = up
        }
      }
    }
  }
  if found == none { return none }
  let u = found.at(1)
  let way = (u,)
  while prev.at(u) != none and way.len() <= n {
    u = prev.at(u)
    way.push(u)
  }
  way.rev()
}

// A place a route or a flow passes, by any of its names: a city (those of the countries
// shown first), a cape, a canal, a sea or strait, a country, a part of the world (a
// continent, an island, a peninsula, a coast); none when the atlas has none
#let find-place(name, shown, ways, waters-all, reliefs-all) = {
  let i = city-index(name, shown)
  if i != none {
    let c = atlas.cities.at(i)
    return (kind: "city", name: name, xy: (c.x, c.y), port: ways.cities.at(i), nodes: (), city: c)
  }
  let key = fold(name)
  for c in ways.capes {
    if key in c.k { return (kind: "cape", name: name, xy: (c.x, c.y), port: c.s, nodes: ()) }
  }
  for c in ways.canals {
    if key in c.k {
      let ((ax, ay), (bx, by)) = c.xy
      return (kind: "canal", name: name, xy: ((ax + bx) / 2, (ay + by) / 2), ends: c.ends, ends-xy: c.xy, port: none, nodes: ())
    }
  }
  let found = waters-all.enumerate().filter(((_, w)) => key in w.k and not w.lake)
  if found.len() > 0 {
    let (i, w) = found.sorted(key: ((_, w)) => -size(w.b)).first()
    return (kind: "water", name: name, xy: w.at.first(), port: none, nodes: ways.waters.at(i))
  }
  for (code, c) in atlas.countries {
    if key in c.k {
      let place = ways.countries.at(code)
      return (kind: "country", name: name, xy: place.at, port: none, nodes: place.s)
    }
  }
  let found = reliefs-all.enumerate().filter(((_, r)) => key in r.k)
  if found.len() > 0 {
    let (i, r) = found.sorted(key: ((_, r)) => -size(r.b)).first()
    return (kind: "relief", name: name, xy: r.at.first(), port: none, nodes: ways.reliefs.at(i))
  }
  none
}

#let place-or-said(name, shown, ways, waters-all, reliefs-all) = {
  if type(name) != str { panic("a place is its name, a string: \"" + repr(name) + "\" is not") }
  let place = find-place(name, shown, ways, waters-all, reliefs-all)
  if place == none {
    panic("no place called \"" + name + "\" in the atlas (a city, a cape, a canal, a sea or strait, a country, a continent or a part of one): name another the route or flow passes, or leave it out")
  }
  place
}

// Points drawn one after the other: each on the side of the 180th meridian nearest the one
// before (a way across the Pacific in one piece)
#let unwrapped(points) = {
  let out = ()
  for (x, y) in points {
    if out.len() > 0 { x = out.last().at(0) + east(x - out.last().at(0)) }
    if out.len() == 0 or out.last() != (x, y) { out.push((x, y)) }
  }
  out
}

// The longitudes boxes span on the world's circle: from the end of the widest gap between
// them round to its start (across the 180th meridian when the gap is elsewhere)
#let spread(boxes) = {
  let full = 360 * atlas.scale
  let spans = boxes.map(b => {
    let turns = calc.floor((b.at(0) + full / 2) / full)
    (b.at(0) - turns * full, b.at(2) - turns * full)
  }).sorted(key: b => b.at(0))
  let merged = ()
  for (a, b) in spans {
    if merged.len() > 0 and a <= merged.last().at(1) {
      merged.last() = (merged.last().at(0), calc.max(merged.last().at(1), b))
    } else { merged.push((a, b)) }
  }
  // The gap before each span (the first's: from the last's end round to it)
  let gaps = merged.enumerate().map(((i, (a, _))) => if i == 0 { a + full - merged.last().at(1) } else { a - merged.at(i - 1).at(1) })
  let widest = range(merged.len()).sorted(key: i => -gaps.at(i)).first()
  if gaps.at(widest) <= 0 { return (-full / 2, full / 2) }  // all the world
  (merged.at(widest).at(0), merged.at(widest - 1).at(1) + if widest == 0 { 0 } else { full })
}

// Routes as asked, checked, their ways found: (name, by, stops: the places, way: its points)
#let read-routes(routes, shown, ways, waters-all, reliefs-all) = {
  if type(routes) == dictionary { routes = (routes,) }
  routes.map(r => {
    if type(r) != dictionary or "name" not in r or "places" not in r {
      panic("a route is (name: \"…\", places: (…), by: \"sea\" or \"land\"): its name, for the legend, and the places it passes in their order")
    }
    for key in r.keys() {
      if key not in ("name", "places", "by") { panic("a route holds a name, places and by, not \"" + key + "\"") }
    }
    let by = r.at("by", default: "sea")
    if by not in ("sea", "land") { panic("a route goes by \"sea\" or by \"land\", not \"" + str(by) + "\"") }
    let names = if type(r.places) == str { (r.places,) } else { r.places }
    if names.len() < 2 {
      panic("the route \"" + r.name + "\" passes fewer than two places: its start and its end at least, in their order")
    }
    let stops = names.map(n => place-or-said(n, shown, ways, waters-all, reliefs-all))
    if by == "land" { return (name: r.name, by: by, stops: stops, way: unwrapped(stops.map(p => p.xy)), at: stops.map(p => p.xy)) }
    // By sea: each place's way in and out (a port and the nodes it sees, or the nodes off a
    // coast, in a sea), the shortest way from one to the next
    let icy = stops.any(p => calc.abs(p.xy.at(1)) > polar)
    for p in stops {
      if p.kind == "water" and p.nodes.len() == 0 {
        panic("no way by sea to \"" + p.name + "\": a sea apart from the oceans (a lake, an inland sea)")
      }
      if p.kind != "canal" and p.port == none and p.nodes.len() == 0 {
        panic("\"" + p.name + "\" is not by the sea: a sea route passes ports, capes, canals, seas and straits, countries or islands by the sea")
      }
    }
    let node-xy(u) = (ways.p.at(u).at(0), ways.p.at(u).at(1))
    let port-ways(port) = {
      let at = (port.at(0), port.at(1))
      port.slice(2).map(u => (u, far(at, node-xy(u))))
    }
    let way = ()
    let at = ()  // where the way meets each place
    let from = none  // the nodes the next leg leaves from, with their cost
    for (i, p) in stops.enumerate() {
      let ends = if p.kind == "canal" { p.ends } else if p.port != none { (p.port,) } else { none }
      if i > 0 {
        let targets = (:)
        if ends != none {
          for port in ends {
            for (u, c) in port-ways(port) { targets.insert(str(u), c) }
          }
        } else {
          for u in p.nodes { targets.insert(str(u), 0) }
        }
        let goal = if ends != none and ends.len() == 1 { (ends.first().at(0), ends.first().at(1)) } else { none }
        let nodes = sea-way(ways, from, targets, goal, icy)
        if nodes == none {
          panic("no way by sea from \"" + stops.at(i - 1).name + "\" to \"" + p.name + "\": they are on seas the sea doesn't join")
        }
        way += nodes.map(node-xy)
        if ends == none {
          at.push(node-xy(nodes.last()))
          from = ((nodes.last(), 0),)
          continue
        }
        // The end it came to (a canal's nearest), then through the canal to the other
        let reached = ends.enumerate().find(((_, port)) => port.slice(2).contains(nodes.last())).at(0)
        if p.kind == "canal" {
          let (into, out) = (ends.at(reached), ends.at(1 - reached))
          way.push((into.at(0), into.at(1)))
          way += (p.ends-xy.at(reached), p.ends-xy.at(1 - reached)).map(((x, y)) => (x, y))
          way.push((out.at(0), out.at(1)))
          at.push(p.xy)
          from = port-ways(out)
          continue
        }
      }
      // A port: in from the sea to the place, out again
      if ends != none {
        let port = ends.first()
        if i > 0 { way.push((port.at(0), port.at(1))) }
        if p.kind == "city" { way.push(p.xy) }
        at.push(if p.kind in ("city", "cape") { p.xy } else { (port.at(0), port.at(1)) })
        if i < stops.len() - 1 {
          way.push((port.at(0), port.at(1)))
          from = port-ways(port)
        }
      } else {
        // a first place that is a coast or a sea: the leg leaves from the nearest of its nodes
        from = p.nodes.map(u => (u, 0))
        at.push(none)
      }
    }
    // A first place met where its leg left it (a country's coast, a sea)
    if at.first() == none { at.at(0) = way.first() }
    (name: r.name, by: by, stops: stops, way: unwrapped(way), at: at)
  })
}

// Flows as asked, checked: (from, to: their points, kind, value, label)
#let read-flows(flows, shown, ways, waters-all, reliefs-all) = {
  if type(flows) == dictionary { flows = (flows,) }
  flows.map(f => {
    if type(f) != dictionary or "from" not in f or "to" not in f {
      panic("a flow is (from: …, to: …, kind: \"…\", value: …, label: \"…\"): where it leaves and where it goes, a place or several, its kind for the legend, its size, what it carries")
    }
    for key in f.keys() {
      if key not in ("from", "to", "kind", "value", "label") {
        panic("a flow holds from, to, kind, value and label, not \"" + key + "\"")
      }
    }
    let value = f.at("value", default: none)
    if value != none and type(value) not in (int, float) {
      panic("a flow's value is a number (its size, the arrow's width), not \"" + repr(value) + "\"")
    }
    let side(names) = {
      let names = if type(names) == str { (names,) } else { names }
      if names.len() == 0 { panic("a flow leaves from a place and goes to a place: none given") }
      let places = names.map(n => place-or-said(n, shown, ways, waters-all, reliefs-all))
      // Several: their middle, each on the side of the first
      let points = unwrapped(places.map(p => p.xy))
      let xy = (points.map(p => p.at(0)).sum() / points.len(), points.map(p => p.at(1)).sum() / points.len())
      (places: places, xy: xy)
    }
    (from: side(f.from), to: side(f.to), kind: f.at("kind", default: none), value: value,
     label: f.at("label", default: none))
  })
}

// countries: shown white and framed (names or codes); cities: a red dot each; regions: of
// the countries shown, coloured, their country's others outlined; rivers: blue lines;
// reliefs (mountains, deserts, plains, peninsulas, islands) and waters (oceans, seas, gulfs,
// lakes): coloured; groups: countries or regions (of a country shown or grouped) coloured by
// group, one colour each, a legend under the map, all framed; routes: (name, places, by: "sea"
// or "land"), each its way in its colour with arrows; flows: (from, to, kind, value, label),
// a curved arrow each, its kind's colour, as wide as its value; routes and flows in the
// legend, framed; each named when labels; width, height: the most the map takes
#let map(countries: (), cities: (), regions: (), rivers: (), reliefs: (), waters: (), groups: (),
  routes: (), flows: (), labels: true, width: 8cm, height: 7cm) = context {
  let shown = countries.map(find-country)
  let sets = read-groups(groups)
  let grouped = sets.map(g => g.countries).join(default: ())
  // The countries the map is about: those shown and those grouped
  let about = shown + grouped.filter(code => code not in shown)
  let towns = cities.map(name => (name: name, city: find-city(name, about)))
  // Routes and flows: the places they pass, a sea route's way over the sea
  let moving = routes.len() + flows.len() > 0
  let (trips, arrows) = ((), ())
  if moving {
    let ways = json("ways.json")
    let (waters-all, reliefs-all) = (json("waters.json"), json("reliefs.json"))
    if routes.len() > 0 { trips = read-routes(routes, about, ways, waters-all, reliefs-all) }
    if flows.len() > 0 { arrows = read-flows(flows, about, ways, waters-all, reliefs-all) }
    // The cities they pass, a red dot each (once)
    let passed = trips.map(t => t.stops).join(default: ()) + arrows.map(f => f.from.places + f.to.places).join(default: ())
    for p in passed.filter(p => p.kind == "city") {
      if towns.all(t => t.city != p.city) { towns.push((name: p.name, city: p.city)) }
    }
  }
  // Their colours, one a route and one a kind of flow, in their order
  let kinds = arrows.map(f => f.kind).dedup()
  if trips.len() + kinds.len() > palette.len() {
    panic("at most " + str(palette.len()) + " routes and kinds of flows on a map, one colour each: join some")
  }
  let ink(i) = palette.at(i).darken(15%)
  let areas = regions.map(name => (name: name, at: find-region(name, shown)))
  let group-areas = sets.enumerate().map(((i, g)) => g.regions.map(name => (name: name, at: find-region(name, about), group: i))).join(default: ())
  let region(a) = json("regions/" + a.at.code + ".json").at(a.at.level).at(a.at.index)
  let near = if about.len() == 0 { none } else {
    let bs = about.map(code => atlas.countries.at(code).b)
    (calc.min(..bs.map(b => b.at(0))), calc.min(..bs.map(b => b.at(1))),
     calc.max(..bs.map(b => b.at(2))), calc.max(..bs.map(b => b.at(3))))
  }
  let lines = if rivers.len() == 0 { () } else {
    let all = json("rivers.json")
    rivers.map(name => (name: name, item: find-in(all, name, "river", near)))
  }
  let lands = if reliefs.len() == 0 { () } else {
    let all = json("reliefs.json")
    reliefs.map(name => (name: name, item: find-in(all, name, "relief", near)))
  }
  let seas = if waters.len() == 0 { () } else {
    let all = json("waters.json")
    waters.map(name => (name: name, item: find-in(all, name, "water", near)))
  }
  let s = atlas.scale
  // The frame: the countries, regions, groups and cities asked; else the rivers, reliefs and waters
  // (an ocean only when nothing smaller is)
  let boxes = shown.map(code => atlas.countries.at(code).f) + areas.map(a => region(a).b)
  boxes += towns.map(t => (t.city.x, t.city.y, t.city.x, t.city.y))
  if sets.len() > 0 {
    boxes += grouped.filter(code => code not in shown).map(code => atlas.countries.at(code).f)
    boxes += group-areas.map(a => region(a).b)
    // An area far larger than all the others together (Russia beside Europe's countries)
    // framed only on its part nearest them, as large as half of them: the others stay
    // large enough to see
    let union(bs) = (calc.min(..bs.map(b => b.at(0))), calc.min(..bs.map(b => b.at(1))),
      calc.max(..bs.map(b => b.at(2))), calc.max(..bs.map(b => b.at(3))))
    // On one axis: the part of (b0, b1) within d of (r0, r1), or its d nearest them
    let nearest(b0, b1, r0, r1, d) = if b1 < r0 - d { (calc.max(b0, b1 - d), b1) } else if b0 > r1 + d {
      (b0, calc.min(b1, b0 + d))
    } else { (calc.max(b0, r0 - d), calc.min(b1, r1 + d)) }
    if boxes.len() > 1 {
      boxes = boxes.enumerate().map(((i, b)) => {
        let rest = union(boxes.enumerate().filter(((j, _)) => j != i).map(((_, c)) => c))
        if size(rest) > 0 and size(b) > 2 * size(rest) and size(union((rest, b))) > 4 * size(rest) {
          let (x0, x1) = nearest(b.at(0), b.at(2), rest.at(0), rest.at(2), (rest.at(2) - rest.at(0)) / 2)
          let (y0, y1) = nearest(b.at(1), b.at(3), rest.at(1), rest.at(3), (rest.at(3) - rest.at(1)) / 2)
          (x0, y0, x1, y1)
        } else { b }
      })
    }
  }
  // Every route's way and every flow's ends framed
  for t in trips {
    let (xs, ys) = (t.way.map(p => p.at(0)), t.way.map(p => p.at(1)))
    boxes.push((calc.min(..xs), calc.min(..ys), calc.max(..xs), calc.max(..ys)))
  }
  for f in arrows {
    for (x, y) in (f.from.xy, f.to.xy) { boxes.push((x, y, x, y)) }
  }
  if boxes.len() == 0 { boxes = lines.map(l => l.item.b) + lands.map(l => l.item.b) }
  if boxes.len() == 0 {
    let small = seas.filter(w => calc.max(w.item.b.at(2) - w.item.b.at(0), w.item.b.at(3) - w.item.b.at(1)) <= 30 * s)
    boxes = (if small.len() > 0 { small } else { seas }).map(w => w.item.b)
  }
  if boxes.len() == 0 { panic("a map shows at least one country, city, region, group, route, flow, river, relief or water") }
  // A river, relief or water asked has a place for its name in the frame: the nearest one
  // added when it has none (the Atlantic beside France)
  let around = (
    calc.min(..boxes.map(b => b.at(0))), calc.min(..boxes.map(b => b.at(1))),
    calc.max(..boxes.map(b => b.at(2))), calc.max(..boxes.map(b => b.at(3))),
  )
  let (mx, my) = ((around.at(0) + around.at(2)) / 2, (around.at(1) + around.at(3)) / 2)
  let within((x, y)) = x >= around.at(0) and x <= around.at(2) and y >= around.at(1) and y <= around.at(3)
  let candidates = seas.map(w => w.item.at) + lands.map(l => l.item.at) + lines.map(l => l.item.l.flatten().chunks(2))
  for places in candidates {
    if places.len() > 0 and not places.any(within) {
      let (x, y) = places.sorted(key: ((x, y)) => calc.abs(x - mx) + calc.abs(y - my)).first()
      boxes.push((x, y, x, y))
    }
  }
  let xs = boxes.map(b => b.at(0)) + boxes.map(b => b.at(2))
  let ys = boxes.map(b => b.at(1)) + boxes.map(b => b.at(3))
  // Equirectangular around the frame's middle latitude: true enough for a country
  let k = calc.cos((calc.min(..ys) + calc.max(..ys)) / 2 / s * 1deg)
  // With routes or flows, the world's smallest part holding them (across the 180th meridian
  // when it is: the Pacific's middle)
  let (x0, x1) = if moving { spread(boxes).map(x => x * k) } else { (calc.min(..xs) * k, calc.max(..xs) * k) }
  let (y0, y1) = (calc.min(..ys), calc.max(..ys))
  // Room around (a tenth, a few degrees at least: a city alone shows its region)
  let least = 4 * s
  let (cx, cy) = ((x0 + x1) / 2, (y0 + y1) / 2)
  let (w, h) = (calc.max(x1 - x0, least) * 1.2, calc.max(y1 - y0, least) * 1.2)
  // Neither a strip nor a band: a long country (Chile) shows its neighbours, its names fit
  let (w, h) = (calc.max(w, h * 0.75), calc.max(h, w * 0.55))
  // Never more than the world once
  let (w, h) = if moving { (calc.min(w, 360 * s * k), calc.min(h, 180 * s)) } else { (w, h) }
  let unit = calc.min(width / w, height / h)  // a length per atlas unit
  let (bw, bh) = (w * unit, h * unit)
  let px(x) = (x * k - (cx - w / 2)) * unit
  let py(y) = ((cy + h / 2) - y) * unit
  let left = (cx - w / 2) / k
  let right = (cx + w / 2) / k
  let frame = (left, cy - h / 2, right, cy + h / 2)
  let inside((x, y)) = x >= left and x <= right and y >= cy - h / 2 and y <= cy + h / 2
  // A ring cut to the frame, a little beyond (Sutherland-Hodgman): what isn't seen isn't
  // drawn, the figure stays light
  let (fx0, fx1) = (left - (right - left) * 0.05, right + (right - left) * 0.05)
  let (fy0, fy1) = (cy - h * 0.55, cy + h * 0.55)
  let cut(points, keep, cross) = {
    let out = ()
    for (i, b) in points.enumerate() {
      let a = points.at(i - 1)
      if keep(b) {
        if not keep(a) { out.push(cross(a, b)) }
        out.push(b)
      } else if keep(a) { out.push(cross(a, b)) }
    }
    out
  }
  let at-x(a, b, x) = (x, a.at(1) + (b.at(1) - a.at(1)) * (x - a.at(0)) / (b.at(0) - a.at(0)))
  let at-y(a, b, y) = (a.at(0) + (b.at(0) - a.at(0)) * (y - a.at(1)) / (b.at(1) - a.at(1)), y)
  let clipped(points) = {
    let p = cut(points, q => q.at(0) >= fx0, (a, b) => at-x(a, b, fx0))
    if p.len() > 0 { p = cut(p, q => q.at(0) <= fx1, (a, b) => at-x(a, b, fx1)) }
    if p.len() > 0 { p = cut(p, q => q.at(1) >= fy0, (a, b) => at-y(a, b, fy0)) }
    if p.len() > 0 { p = cut(p, q => q.at(1) <= fy1, (a, b) => at-y(a, b, fy1)) }
    p
  }
  // Points as drawn, one less than a point from the last kept skipped: a small scale draws
  // no more than the eye sees
  let thinned(points) = {
    let kept = ()
    for q in points {
      let (x, y) = (px(q.at(0)), py(q.at(1)))
      if kept.len() == 0 or calc.abs((x - kept.last().at(0)) / 1pt) + calc.abs((y - kept.last().at(1)) / 1pt) >= 1 {
        kept.push((x, y))
      }
    }
    kept
  }
  // With routes or flows, the world drawn round: what lies a turn east or west drawn there
  // too (Alaska beside Asia on a map of the Pacific)
  let full = 360 * s
  let spans = if moving { (0, full, -full) } else { (0,) }
  let moved(points, d) = if d == 0 { points } else { points.map(((x, y)) => (x + d, y)) }
  let ring(points, fill, stroke) = {
    for d in spans {
      let kept = thinned(clipped(moved(points, d)))
      if kept.len() >= 3 { place(polygon(fill: fill, stroke: stroke, ..kept)) }
    }
  }
  let near-frame(b) = spans.any(d => touches((b.at(0) + d, b.at(1), b.at(2) + d, b.at(3)), (fx0, fy0, fx1, fy1)))
  // A point where it is seen (a turn east or west, with routes or flows)
  let seen-x(x) = {
    let found = spans.map(d => x + d).find(x => x >= fx0 and x <= fx1)
    if found == none { x } else { found }
  }
  // A river's lines: the runs of points within the frame (a little beyond), one point past
  let runs(points) = {
    let out = ()
    let run = ()
    for (i, q) in points.enumerate() {
      let wide = q.at(0) >= fx0 and q.at(0) <= fx1 and q.at(1) >= fy0 and q.at(1) <= fy1
      if wide {
        if run.len() == 0 and i > 0 { run.push(points.at(i - 1)) }
        run.push(q)
      } else if run.len() > 0 {
        run.push(q)
        out.push(run)
        run = ()
      }
    }
    if run.len() > 0 { out.push(run) }
    out.filter(r => r.len() >= 2)
  }
  let others = atlas.countries.pairs().filter(((code, c)) => code not in about and near-frame(c.b))
  // Where a name goes: a region's, relief's or water's first place in the frame; a river's
  // middle point within it
  let place-of(item) = {
    let found = spans.map(d => moved(item.at, d)).join().filter(inside)
    if found.len() == 0 { none } else { found.sorted(key: ((x, y)) => calc.abs(x - (left + right) / 2) / (right - left) + calc.abs(y - cy) / h).first() }
  }
  let river-place(item) = {
    let pts = spans.map(d => item.l.map(p => runs(moved(p, d)))).join().flatten().chunks(2).filter(inside)
    if pts.len() == 0 { none } else { pts.at(calc.div-euclid(pts.len(), 2)) }
  }
  // Labels: cities beside their dot (right, left, above, below); the others on their place
  // (on it, above, below, right, left): the first that stays in the frame and on no other
  // label or dot
  let dot = 2.4pt
  let gap = 2.5pt
  let marks = towns.map(t => (px(seen-x(t.city.x)), py(t.city.y)))
  let wanted = ()
  for (i, t) in towns.enumerate() {
    wanted.push((at: marks.at(i), dot: true, body: text(8pt, weight: if t.city.cap { "bold" } else { "regular" }, t.name)))
  }
  let named(items, find, style) = items.map(it => (it, find(it))).filter(((_, p)) => p != none).map(((it, p)) => (
    at: (px(seen-x(p.at(0))), py(p.at(1))), dot: false, body: style(it.name),
  ))
  wanted += named(areas, a => place-of(region(a)), n => text(7.5pt, fill: luma(40), n))
  wanted += named(lands, l => place-of(l.item), n => text(8pt, style: "italic", fill: rgb("#6b4a1f"), n))
  wanted += named(seas, w => place-of(w.item), n => text(8pt, style: "italic", fill: rgb("#1f5a8f"), n))
  wanted += named(lines, l => river-place(l.item), n => text(7.5pt, style: "italic", fill: rgb("#1f5a8f"), n))
  // Flows: a curved arrow each, from its start to its end (shortened by a dot), as wide as
  // its value is large among theirs; drawn where its middle is seen
  let largest = arrows.filter(f => f.value != none).map(f => f.value)
  let largest = if largest.len() == 0 { none } else { calc.max(..largest) }
  let curves = arrows.map(f => {
    let (ax, ay) = f.from.xy
    let (bx, by) = (ax + east(f.to.xy.at(0) - ax), f.to.xy.at(1))
    let d = seen-x((ax + bx) / 2) - (ax + bx) / 2
    let (a, b) = ((px(ax + d), py(ay)), (px(bx + d), py(by)))
    let (dx, dy) = (b.at(0) - a.at(0), b.at(1) - a.at(1))
    let length = calc.sqrt(calc.pow(dx / 1pt, 2) + calc.pow(dy / 1pt, 2)) * 1pt
    let (ux, uy) = if length > 0pt { (dx / length, dy / length) } else { (1, 0) }
    // Bent to its left by a sixth of its length
    let c = (a.at(0) + dx / 2 + uy * length / 6, a.at(1) + dy / 2 - ux * length / 6)
    let width = if f.value == none or largest == none or largest <= 0 { 2pt } else { 1pt + 3pt * f.value / largest }
    let colour = ink(trips.len() + kinds.position(k => k == f.kind))
    // A city's end short of its dot
    let (ga, gb) = (if f.from.places.len() == 1 and f.from.places.first().kind == "city" { dot + 1.5pt } else { 1pt },
      if f.to.places.len() == 1 and f.to.places.first().kind == "city" { dot + 1pt } else { 1pt })
    (a: a, b: b, c: c, width: width, colour: colour, label: f.label, gaps: (ga, gb), length: length)
  })
  wanted += curves.filter(c => c.label != none).map(c => (
    at: ((c.a.at(0) + 2 * c.c.at(0) + c.b.at(0)) / 4, (c.a.at(1) + 2 * c.c.at(1) + c.b.at(1)) / 4),
    dot: false, body: text(7.5pt, weight: "bold", fill: c.colour.darken(25%), c.label),
  ))
  // The places routes and flows pass, named when they aren't already (a city by its dot):
  // a cape, a canal, a sea or strait where the way goes, a country or a part of the world
  let said = cities + regions + waters + reliefs + towns.map(t => t.name)
  let passed = trips.map(t => t.stops.zip(if t.by == "sea" { t.at } else { t.stops.map(p => p.xy) })).join(default: ())
  passed += arrows.map(f => (f.from.places, f.to.places).filter(ps => ps.len() == 1).map(ps => (ps.first(), ps.first().xy))).join(default: ())
  let water-style(n) = text(7.5pt, style: "italic", fill: rgb("#1f5a8f"), n)
  let ticks = ()  // a cape's small dot
  for (p, at) in passed {
    if p.kind == "city" or p.name in said or at == none { continue }
    said.push(p.name)
    let (x, y) = if p.kind in ("country", "relief") { p.xy } else { at }
    let style = if p.kind in ("country", "relief") { n => text(7.5pt, fill: luma(40), n) } else { water-style }
    wanted.push((at: (px(seen-x(x)), py(y)), dot: p.kind == "cape", body: style(p.name)))
    if p.kind == "cape" { ticks.push((px(seen-x(x)), py(y))) }
  }
  let placed = ()
  let taken = ()
  if labels {
    for (i, want) in wanted.enumerate() {
      let (x, y) = want.at
      let size = measure(want.body)
      let (lw, lh) = (size.width, size.height)
      let tries = if want.dot {
        ((x + dot + gap, y - lh / 2), (x - dot - gap - lw, y - lh / 2),
         (x - lw / 2, y - dot - gap - lh), (x - lw / 2, y + dot + gap))
      } else {
        ((x - lw / 2, y - lh / 2), (x - lw / 2, y - lh * 1.6), (x - lw / 2, y + lh * 0.6),
         (x + gap, y - lh / 2), (x - gap - lw, y - lh / 2))
      }
      // With routes and flows, more names near each other: the corners around, then further
      if moving {
        let (r, l) = (x + dot + gap, x - dot - gap - lw)
        let (above, below) = (y - dot - gap - lh, y + dot + gap)
        tries += ((r, above), (r, below), (l, above), (l, below), (x - lw / 2, above - lh), (x - lw / 2, below + lh),
          (r + lw / 2, y - lh / 2), (l - lw / 2, y - lh / 2))
      }
      let clear((ax, ay)) = (
        ax >= 1pt and ay >= 1pt and ax + lw <= bw - 1pt and ay + lh <= bh - 1pt
          and taken.all(((bx, by, bw2, bh2)) => ax + lw <= bx or bx + bw2 <= ax or ay + lh <= by or by + bh2 <= ay)
          and marks.enumerate().all(((j, (mx, my))) => (want.dot and j == i) or mx + dot <= ax or ax + lw <= mx - dot or my + dot <= ay or ay + lh <= my - dot)
      )
      let at = tries.find(clear)
      if at == none { at = tries.first() }
      taken.push((at.at(0), at.at(1), lw, lh))
      placed.push((at, want.body))
    }
  }
  let tints = (
    mountain: rgb(150, 100, 50, 90), plateau: rgb(190, 150, 90, 80), desert: rgb(235, 200, 110, 130),
    plain: rgb(120, 180, 90, 80), land: rgb(240, 190, 90, 90),
  )
  let water = rgb("#e8f1f8")
  let tint(i) = palette.at(i).lighten(35%)
  let drawn = box(width: bw, height: bh, clip: true, fill: water, {
    for w in seas {
      for points in w.item.r { ring(points, rgb("#b5d2ec"), none) }
    }
    for (code, c) in others {
      for points in c.r { ring(points, luma(228), 0.4pt + luma(160)) }
    }
    for code in shown {
      for points in atlas.countries.at(code).r { ring(points, white, none) }
    }
    // Each group's countries in its colour, their borders seen
    for (i, g) in sets.enumerate() {
      for code in g.countries {
        for points in atlas.countries.at(code).r { ring(points, tint(i), 0.4pt + luma(110)) }
      }
    }
    // The regions asked coloured, their level's others outlined (a région among the régions)
    for (code, level) in (areas + group-areas).map(a => (a.at.code, a.at.level)).dedup() {
      let file = json("regions/" + code + ".json")
      let picked = areas.filter(a => a.at.code == code and a.at.level == level).map(a => a.at.index)
      let in-group = group-areas.filter(a => a.at.code == code and a.at.level == level)
      for (i, r) in file.at(level).enumerate() {
        if near-frame(r.b) {
          let fill = if i in picked { rgb("#fbd38d") } else {
            let found = in-group.find(a => a.at.index == i)
            if found == none { none } else { tint(found.group) }
          }
          for points in r.r { ring(points, fill, 0.4pt + luma(150)) }
        }
      }
    }
    for code in shown {
      for points in atlas.countries.at(code).r { ring(points, none, 0.7pt + black) }
    }
    // A region asked too small to see at this scale (Hawaii beside the United States): a
    // circle around it
    for a in areas {
      let largest = region(a).r.first()  // its largest part (an archipelago's main island)
      let b = (calc.min(..largest.map(p => p.at(0))), calc.min(..largest.map(p => p.at(1))),
               calc.max(..largest.map(p => p.at(0))), calc.max(..largest.map(p => p.at(1))))
      if near-frame(b) and calc.max((b.at(2) - b.at(0)) * k * unit, (b.at(3) - b.at(1)) * unit) < 10pt {
        let (x, y) = (px((b.at(0) + b.at(2)) / 2), py((b.at(1) + b.at(3)) / 2))
        place(dx: x - 9pt, dy: y - 9pt, circle(radius: 9pt, stroke: 1.2pt + rgb("#d9822b")))
      }
    }
    // A grouped country or region too small to see (Malta, Cyprus among Europe's) and apart
    // from its group's others: a circle around it in its group's colour; one beside them
    // shows by their colour (Luxembourg, Lebanon)
    // (a country's main part and those near it, its frame: not its far islands)
    let grouped-parts = sets.enumerate().map(((i, g)) => g.countries.map(code => (atlas.countries.at(code).f, i))).join(default: ())
    grouped-parts += group-areas.map(a => {
      let largest = region(a).r.first()
      ((calc.min(..largest.map(p => p.at(0))), calc.min(..largest.map(p => p.at(1))),
        calc.max(..largest.map(p => p.at(0))), calc.max(..largest.map(p => p.at(1)))), a.group)
    })
    for (n, (b, i)) in grouped-parts.enumerate() {
      let grown = (b.at(0) - s, b.at(1) - s, b.at(2) + s, b.at(3) + s)  // a degree around
      let apart = grouped-parts.enumerate().all(((m, (c, j))) => m == n or j != i or not touches(grown, c))
      if apart and near-frame(b) and calc.max((b.at(2) - b.at(0)) * k * unit, (b.at(3) - b.at(1)) * unit) < 10pt {
        let (x, y) = (px((b.at(0) + b.at(2)) / 2), py((b.at(1) + b.at(3)) / 2))
        place(dx: x - 7pt, dy: y - 7pt, circle(radius: 7pt, stroke: 1.4pt + palette.at(i).darken(20%)))
      }
    }
    for l in lands {
      for points in l.item.r { ring(points, tints.at(l.item.c), none) }
    }
    for lake in atlas.lakes {
      if near-frame(lake.b) {
        for points in lake.r { ring(points, water, 0.3pt + luma(160)) }
      }
    }
    for w in seas.filter(w => w.item.lake) {
      for points in w.item.r { ring(points, rgb("#b5d2ec"), 0.3pt + luma(160)) }
    }
    for l in lines {
      for run in spans.map(d => l.item.l.map(p => runs(moved(p, d)))).join().join(default: ()) {
        let kept = thinned(run)
        if kept.len() >= 2 {
          place(curve(stroke: (paint: rgb("#3b7dc4"), thickness: 1.1pt, join: "round", cap: "round"),
            curve.move(kept.first()), ..kept.slice(1).map(curve.line)))
        }
      }
    }
    // An arrowhead: its tip at `tip`, pointing along (ux, uy)
    let head(tip, ux, uy, size, colour) = {
      let (x, y) = tip
      let (bx, by) = (x - ux * size, y - uy * size)
      place(polygon(fill: colour, (x, y), (bx + uy * size * 0.45, by - ux * size * 0.45), (bx - uy * size * 0.45, by + ux * size * 0.45)))
    }
    let unit-of(a, b) = {
      let (dx, dy) = (b.at(0) - a.at(0), b.at(1) - a.at(1))
      let length = calc.sqrt(calc.pow(dx / 1pt, 2) + calc.pow(dy / 1pt, 2))
      if length == 0 { (1, 0, 0) } else { (dx / 1pt / length, dy / 1pt / length, length) }
    }
    // Routes: each its way in its colour (a land route dashed), an arrowhead at its end and
    // one halfway, seen a turn east or west too
    for (i, t) in trips.enumerate() {
      let colour = ink(i)
      let line = (paint: colour, thickness: 1.5pt, join: "round", cap: "round", dash: if t.by == "land" { "dashed" } else { none })
      for d in range(-2, 3).map(j => j * full) {
        let way = moved(t.way, d)
        let (xs, ys) = (way.map(p => p.at(0)), way.map(p => p.at(1)))
        if not touches((calc.min(..xs), calc.min(..ys), calc.max(..xs), calc.max(..ys)), (fx0, fy0, fx1, fy1)) { continue }
        let kept = thinned(way)
        let last = (px(way.last().at(0)), py(way.last().at(1)))
        if kept.last() != last { kept.push(last) }
        if kept.len() < 2 { continue }
        // Its end short of the place's dot, the arrowhead there, pointing the way it comes
        // from 8pt back (not the last few steps of a port's mouth)
        let back = range(kept.len() - 1).rev().find(j => unit-of(kept.at(j), kept.last()).at(2) >= 8)
        let (ux, uy, _) = unit-of(kept.at(if back == none { 0 } else { back }), kept.last())
        let tip = (kept.last().at(0) - ux * (dot + 0.8pt), kept.last().at(1) - uy * (dot + 0.8pt))
        kept.last() = (tip.at(0) - ux * 4pt, tip.at(1) - uy * 4pt)
        place(curve(stroke: line, curve.move(kept.first()), ..kept.slice(1).map(curve.line)))
        head(tip, ux, uy, 6pt, colour)
        // Halfway along it, its direction
        let lengths = range(1, kept.len()).map(j => unit-of(kept.at(j - 1), kept.at(j)).at(2))
        let (total, run) = (lengths.sum(), 0)
        for (j, l) in lengths.enumerate() {
          if run + l >= total / 2 and l > 0 {
            let (ux, uy, _) = unit-of(kept.at(j), kept.at(j + 1))
            let f = (total / 2 - run) / l
            let a = kept.at(j)
            head((a.at(0) + (kept.at(j + 1).at(0) - a.at(0)) * f + ux * 2.5pt, a.at(1) + (kept.at(j + 1).at(1) - a.at(1)) * f + uy * 2.5pt), ux, uy, 5pt, colour)
            break
          }
          run += l
        }
      }
    }
    // Flows: their curved arrows
    for c in curves {
      let (ux, uy, _) = unit-of(c.c, c.b)
      let (vx, vy, _) = unit-of(c.a, c.c)
      let size = calc.min(calc.max(6pt, c.width * 2.2), c.length / 3)
      let start = (c.a.at(0) + vx * c.gaps.at(0), c.a.at(1) + vy * c.gaps.at(0))
      let tip = (c.b.at(0) - ux * c.gaps.at(1), c.b.at(1) - uy * c.gaps.at(1))
      let end = (tip.at(0) - ux * size * 0.8, tip.at(1) - uy * size * 0.8)
      place(curve(stroke: (paint: c.colour, thickness: c.width, cap: "butt"), curve.move(start), curve.quad(c.c, end)))
      head(tip, ux, uy, size, c.colour)
    }
    for (x, y) in marks {
      place(dx: x - dot, dy: y - dot, circle(radius: dot, fill: rgb("#d62f2f"), stroke: 0.6pt + white))
    }
    for (x, y) in ticks {
      place(dx: x - 1.6pt, dy: y - 1.6pt, circle(radius: 1.6pt, fill: luma(50), stroke: 0.5pt + white))
    }
    for ((ax, ay), body) in placed {
      place(dx: ax, dy: ay, box(fill: white.transparentize(30%), inset: 0pt, body))
    }
  })
  let named-kinds = kinds.enumerate().filter(((_, k)) => k != none)
  if sets.len() + trips.len() + named-kinds.len() == 0 { drawn } else {
    // The legend under the map: each group's colour and its name, each route's line, each
    // kind of flow's arrow, in their order
    let key(sample, name) = box(inset: (right: 5pt), stack(dir: ltr, spacing: 3pt, sample, text(8pt, name)))
    let arrow(colour, thickness, dash) = box(width: 16pt, height: 7pt, {
      place(dy: 3.5pt, line(length: 11pt, stroke: (paint: colour, thickness: thickness, dash: dash)))
      place(dx: 10pt, polygon(fill: colour, (0pt, 0.5pt), (6pt, 3.5pt), (0pt, 6.5pt)))
    })
    let keys = sets.enumerate().map(((i, g)) => key(box(width: 10pt, height: 7pt, fill: tint(i), stroke: 0.5pt + luma(110)), g.name))
    keys += trips.enumerate().map(((i, t)) => key(arrow(ink(i), 1.5pt, if t.by == "land" { "dashed" } else { none }), t.name))
    keys += named-kinds.map(((i, k)) => key(arrow(ink(trips.len() + i), 2pt, none), k))
    stack(spacing: 5pt, drawn, block(width: bw, {
      set text(8pt)
      set par(leading: 0.6em)
      keys.join([ ])
    }))
  }
}
