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

#let country-code(name) = {
  let key = fold(name)
  for (code, country) in atlas.countries {
    if key in country.k { return code }
  }
  none
}
#let find-country(name) = {
  let code = country-code(name)
  if code == none {
    panic("no country called \"" + name + "\" in the atlas: its usual name, or its three-letter code (\"ESP\")")
  }
  code
}

// A place's name and the country it was said in, when one follows it after a comma (a name
// several places share: "San Salvador, Bahamas"); none else
#let qualified(name) = {
  let parts = name.split(",")
  if parts.len() < 2 { return (name, none) }
  let code = country-code(parts.last().trim())
  if code == none { (name, none) } else { (parts.slice(0, -1).join(",").trim(), code) }
}

// The cities of a name, the likeliest first: in the country said after a comma; among those
// of the countries shown first, else a place of history lessons (h: Cordoue, Spain's, not
// Argentina's), else the most populated of that name
#let city-indices(name, shown) = {
  let (bare, code) = qualified(name)
  let key = fold(bare)
  let found = atlas.cities.enumerate().filter(((_, c)) => key in c.k and (code == none or c.c == code))
  let theirs = found.filter(((_, c)) => c.c in shown)
  (if theirs.len() > 0 { theirs } else { found }).sorted(key: ((_, c)) => (-c.at("h", default: 0), -c.p)).map(((i, _)) => i)
}
#let city-index(name, shown) = {
  let found = city-indices(name, shown)
  if found.len() == 0 { none } else { found.first() }
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
// A water with the others of its name it touches (an ocean's north and south parts): one
// water, all its parts drawn; `parts` their indices
#let joined(items, found, top) = {
  let parts = found.filter(i => i == top or touches(items.at(i).b, items.at(top).b))
  if parts.len() == 1 { return (item: items.at(top), parts: parts) }
  let bs = parts.map(i => items.at(i).b)
  (item: items.at(top) + (
    r: parts.map(i => items.at(i).r).join(), at: parts.map(i => items.at(i).at).join(),
    b: (calc.min(..bs.map(b => b.at(0))), calc.min(..bs.map(b => b.at(1))),
        calc.max(..bs.map(b => b.at(2))), calc.max(..bs.map(b => b.at(3)))),
  ), parts: parts)
}
#let find-in(items, name, what, near) = {
  let key = fold(name)
  let found = items.filter(i => key in i.k)
  if found.len() == 0 { panic("no " + what + " called \"" + name + "\" in the atlas: leave it out") }
  let theirs = if near == none { () } else { found.filter(i => touches(i.b, near)) }
  let top = (if theirs.len() > 0 { theirs } else { found }).sorted(key: i => -size(i.b)).first()
  if what != "water" { return top }
  let all = range(items.len()).filter(i => key in items.at(i).k)
  joined(items, all, all.find(i => items.at(i) == top)).item
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
// continent, an island, a peninsula, a coast); none when the atlas has none. With a country
// after a comma, a city, cape or part of the world in it, else that country (the place the
// atlas lacks there: said, its country offered instead, never guessed). A city's `others`:
// the other cities of its name
#let city-place(i, name, ways, others) = {
  let c = atlas.cities.at(i)
  (kind: "city", name: name, xy: (c.x, c.y), port: ways.cities.at(i), nodes: (), city: c, index: i, others: others)
}
#let country-place(code, name, ways) = {
  let place = ways.countries.at(code)
  (kind: "country", name: name, code: code, xy: place.at, port: none, nodes: place.s, rings: atlas.countries.at(code).r)
}
#let relief-place(i, name, ways, reliefs-all) = {
  let r = reliefs-all.at(i)
  (kind: "relief", name: name, xy: r.at.first(), port: none, nodes: ways.reliefs.at(i), rings: r.r)
}
#let find-place(name, shown, ways, waters-all, reliefs-all) = {
  let (bare, code) = qualified(name)
  let cities = city-indices(name, shown)
  if cities.len() > 0 { return city-place(cities.first(), bare, ways, cities.slice(1)) }
  let key = fold(bare)
  if code != none {
    // In the country said: a cape or a part of the world on it
    let b = atlas.countries.at(code).b
    let within((x, y)) = x >= b.at(0) and x <= b.at(2) and y >= b.at(1) and y <= b.at(3)
    for c in ways.capes {
      if key in c.k and within((c.x, c.y)) { return (kind: "cape", name: bare, xy: (c.x, c.y), port: c.s, nodes: ()) }
    }
    let found = reliefs-all.enumerate().filter(((_, r)) => key in r.k and touches(r.b, b))
    if found.len() > 0 { return relief-place(found.sorted(key: ((_, r)) => -size(r.b)).first().at(0), bare, ways, reliefs-all) }
    let country = name.split(",").last().trim()
    panic("no place called \"" + bare + "\" in " + country + " in the atlas: name the country (\"" + country + "\") or another place the route or flow passes, or leave it out")
  }
  for c in ways.capes {
    if key in c.k { return (kind: "cape", name: name, xy: (c.x, c.y), port: c.s, nodes: ()) }
  }
  for c in ways.canals {
    if key in c.k {
      let ((ax, ay), (bx, by)) = c.xy
      return (kind: "canal", name: name, xy: ((ax + bx) / 2, (ay + by) / 2), ends: c.ends, ends-xy: c.xy, port: none, nodes: ())
    }
  }
  let found = range(waters-all.len()).filter(i => key in waters-all.at(i).k and not waters-all.at(i).lake)
  if found.len() > 0 {
    let top = found.sorted(key: i => -size(waters-all.at(i).b)).first()
    let (item, parts) = joined(waters-all, found, top)
    // (an ocean's parts: its ways in all of them)
    return (kind: "water", name: name, xy: item.at.first(), port: none, nodes: parts.map(i => ways.waters.at(i)).join(), rings: item.r, spots: item.at)
  }
  for (code, c) in atlas.countries {
    if key in c.k { return country-place(code, name, ways) }
  }
  let found = reliefs-all.enumerate().filter(((_, r)) => key in r.k)
  if found.len() > 0 {
    return relief-place(found.sorted(key: ((_, r)) => -size(r.b)).first().at(0), name, ways, reliefs-all)
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
    // A city whose name others share: the one nearest the places before and after it on the
    // route (Tripoli after Beirut, Lebanon's; after Tunis, Libya's)
    stops = stops.enumerate().map(((i, p)) => {
      if p.kind != "city" or p.others.len() == 0 { return p }
      let near = stops.enumerate().filter(((j, _)) => j == i - 1 or j == i + 1).map(((_, q)) => q.xy)
      let best = (p.index,) + p.others
      let best = best.sorted(key: j => near.map(q => far((atlas.cities.at(j).x, atlas.cities.at(j).y), q)).sum()).first()
      if best == p.index { p } else { city-place(best, p.name, ways, ()) }
    })
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
    // A port at a canal's mouth (Suez, Colón): the canal open from it, its other mouth a way
    // in and out too
    let mouth(p) = if p.kind != "city" { none } else {
      let found = ways.canals.find(c => c.xy.contains(p.xy))
      if found == none { none } else {
        let j = found.xy.position(e => e == p.xy)
        (other: found.ends.at(1 - j), xy: (found.xy.at(j), found.xy.at(1 - j)))
      }
    }
    let way = ()
    let at = ()  // where the way meets each place
    let from = none  // the nodes the next leg leaves from, with their cost
    let beyond = none  // the canal the last place opens: its other mouth, the leg's own nodes
    for (i, p) in stops.enumerate() {
      let ends = if p.kind == "canal" { p.ends } else if p.port != none { (p.port,) } else { none }
      let m = mouth(p)
      if i > 0 {
        let targets = (:)
        if ends != none {
          for port in ends {
            for (u, c) in port-ways(port) { targets.insert(str(u), c) }
          }
        } else {
          for u in p.nodes { targets.insert(str(u), 0) }
        }
        if m != none {
          for (u, c) in port-ways(m.other) {
            if str(u) not in targets { targets.insert(str(u), c) }
          }
        }
        let goal = if m == none and ends != none and ends.len() == 1 { (ends.first().at(0), ends.first().at(1)) } else { none }
        let nodes = sea-way(ways, from, targets, goal, icy)
        if nodes == none {
          panic("no way by sea from \"" + stops.at(i - 1).name + "\" to \"" + p.name + "\": they are on seas the sea doesn't join")
        }
        // Left by the canal the place before opens: through it first
        if beyond != none and beyond.other.slice(2).contains(nodes.first()) and not beyond.own.contains(nodes.first()) {
          way += (beyond.xy.at(0), beyond.xy.at(1), (beyond.other.at(0), beyond.other.at(1)))
        }
        beyond = none
        way += nodes.map(node-xy)
        if ends == none {
          at.push(node-xy(nodes.last()))
          from = ((nodes.last(), 0),)
          continue
        }
        // Come to the canal's other mouth: through it to the place
        if m != none and m.other.slice(2).contains(nodes.last()) and not ends.first().slice(2).contains(nodes.last()) {
          way.push((m.other.at(0), m.other.at(1)))
          way += (m.xy.at(1), m.xy.at(0))
        }
        if p.kind == "canal" {
          // The end it came to (the nearest), then through the canal to the other
          let reached = ends.enumerate().find(((_, port)) => port.slice(2).contains(nodes.last())).at(0)
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
          if m != none {
            from += port-ways(m.other)
            beyond = (other: m.other, own: port.slice(2), xy: m.xy)
          }
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

// Flows as asked, checked: (from, to: each its places, its middle `xy`, the point the arrow
// leaves or reaches `at`, its name when several places make it; kind, value, label)
#let read-flows(flows, shown, ways, waters-all, reliefs-all) = {
  if type(flows) == dictionary { flows = (flows,) }
  flows.map(f => {
    if type(f) != dictionary or "from" not in f or "to" not in f {
      panic("a flow is (from: …, to: …, kind: \"…\", value: …, label: \"…\"): where it leaves and where it goes, a place or several, its kind for the legend, its size, what it carries")
    }
    for key in f.keys() {
      if key not in ("from", "to", "from-name", "to-name", "kind", "value", "label") {
        panic("a flow holds from, to, from-name, to-name, kind, value and label, not \"" + key + "\"")
      }
    }
    let value = f.at("value", default: none)
    if value != none and type(value) not in (int, float) {
      panic("a flow's value is a number (its size, the arrow's width), not \"" + repr(value) + "\"")
    }
    let side(end) = {
      let names = f.at(end)
      let names = if type(names) == str { (names,) } else { names }
      if names.len() == 0 { panic("a flow leaves from a place and goes to a place: none given") }
      let name = f.at(end + "-name", default: none)
      if names.len() > 1 and name == none {
        panic("a flow's " + end + " is several places (" + names.map(repr).join(", ") + "): name the region they make, " + end + "-name: \"…\", written on the map")
      }
      // Several places making a region: a name that is a country's too is the country (Kuwait,
      // Singapore), not its city
      let places = names.map(n => {
        let code = if names.len() > 1 { country-code(n) } else { none }
        if code != none { country-place(code, n, ways) } else { place-or-said(n, shown, ways, waters-all, reliefs-all) }
      })
      // Several: their middle, each on the side of the first
      let points = unwrapped(places.map(p => p.xy))
      let xy = (points.map(p => p.at(0)).sum() / points.len(), points.map(p => p.at(1)).sum() / points.len())
      (places: places, xy: xy, name: if places.len() > 1 { name } else { none })
    }
    let (from, to) = (side("from"), side("to"))
    // A region's arrow leaves from (reaches) its place nearest the other end: Mexico's for
    // Latin America toward the United States, the arrow from the region's edge
    let nearest(s, other) = s.places.map(p => p.xy).sorted(key: q => far(q, other)).first()
    (from: from + (at: nearest(from, to.xy)), to: to + (at: nearest(to, from.xy)),
     kind: f.at("kind", default: none), value: value, label: f.at("label", default: none))
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
    for (x, y) in (f.from.at, f.to.at) { boxes.push((x, y, x, y)) }
    // A region's places whole (a country's main part)
    for p in (f.from, f.to).filter(s => s.name != none).map(s => s.places).join(default: ()) {
      boxes.push(if p.kind == "country" { atlas.countries.at(p.code).f } else { (..p.xy, ..p.xy) })
    }
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
  // With routes and flows, the names of the places they pass whole within the frame: grown
  // until each has room around its place (half its width each side, its height above and
  // below), the scale found again each time
  if moving {
    let names = towns.map(t => (t.city.x, t.city.y, t.name))
    names += trips.map(t => t.stops.zip(if t.by == "sea" { t.at } else { t.stops.map(p => p.xy) })
      .filter(((p, at)) => p.kind != "city" and at != none).map(((p, at)) => (..at, p.name))).join(default: ())
    names += arrows.map(f => (f.from, f.to).map(e => (..e.at, if e.name != none { e.name } else { e.places.first().name })))
      .join(default: ()).filter(n => towns.all(t => t.name != n.at(2)))
    let sizes = names.map(n => measure(text(8pt, n.at(2))))
    for _ in range(2) {
      let unit = calc.min(width / w, height / h)
      let (l, r, b, t) = (cx - w / 2, cx + w / 2, cy - h / 2, cy + h / 2)
      for ((x, y, _), m) in names.zip(sizes) {
        let x = x * k
        let x = x + calc.round((cx - x) / (360 * s * k)) * 360 * s * k  // the turn nearest the frame
        let (dx, dy) = ((m.width / 2 + 3pt) / unit, (m.height + 6pt) / unit)
        (l, r, b, t) = (calc.min(l, x - dx), calc.max(r, x + dx), calc.min(b, y - dy), calc.max(t, y + dy))
      }
      (cx, cy) = ((l + r) / 2, (b + t) / 2)
      (w, h) = (calc.min(r - l, 360 * s * k), calc.min(t - b, 180 * s))
    }
  }
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
  // Flows: a curved arrow each, from its start to its end (shortened by a dot), drawn where
  // its middle is seen; as wide as its value ranks among theirs (the least the thinnest, the
  // largest the widest: told apart at a glance); never shorter than its arrowhead's reach
  let values = arrows.filter(f => f.value != none).map(f => f.value)
  let (least, most) = if values.len() == 0 { (none, none) } else { (calc.min(..values), calc.max(..values)) }
  let shortest = 22pt
  let curves = arrows.map(f => {
    let (ax, ay) = f.from.at
    let (bx, by) = (ax + east(f.to.at.at(0) - ax), f.to.at.at(1))
    let d = seen-x((ax + bx) / 2) - (ax + bx) / 2
    let (a, b) = ((px(ax + d), py(ay)), (px(bx + d), py(by)))
    let (dx, dy) = (b.at(0) - a.at(0), b.at(1) - a.at(1))
    let length = calc.sqrt(calc.pow(dx / 1pt, 2) + calc.pow(dy / 1pt, 2)) * 1pt
    let (ux, uy) = if length > 0pt { (dx / length, dy / length) } else { (1, 0) }
    // Too short to see (neighbours on a world map): lengthened both ways along it
    if length < shortest {
      let (mx, my) = (a.at(0) + dx / 2, a.at(1) + dy / 2)
      (a, b) = ((mx - ux * shortest / 2, my - uy * shortest / 2), (mx + ux * shortest / 2, my + uy * shortest / 2))
      (dx, dy, length) = (ux * shortest, uy * shortest, shortest)
    }
    // Bent to its left by a sixth of its length
    let c = (a.at(0) + dx / 2 + uy * length / 6, a.at(1) + dy / 2 - ux * length / 6)
    let width = if f.value == none or least == none { 2pt } else if most == least { 3pt } else {
      1.5pt + 4pt * (f.value - least) / (most - least)
    }
    let colour = ink(trips.len() + kinds.position(k => k == f.kind))
    // A city's end short of its dot
    let (ga, gb) = (if f.from.places.len() == 1 and f.from.places.first().kind == "city" { dot + 1.5pt } else { 1pt },
      if f.to.places.len() == 1 and f.to.places.first().kind == "city" { dot + 1pt } else { 1pt })
    (a: a, b: b, c: c, width: width, colour: colour, label: f.label, gaps: (ga, gb), length: length)
  })
  // A long name (a region's, a flow's) on two lines: a world map is narrow for it
  let wrapped(body) = {
    let wide = measure(body).width
    if wide <= 75pt { body } else { box(width: wide / 2 + 12pt, align(center, text(hyphenate: false, body))) }
  }
  wanted += curves.filter(c => c.label != none).map(c => (
    at: ((c.a.at(0) + 2 * c.c.at(0) + c.b.at(0)) / 4, (c.a.at(1) + 2 * c.c.at(1) + c.b.at(1)) / 4),
    dot: false, body: wrapped(text(7.5pt, weight: "bold", fill: c.colour.darken(25%), c.label)),
  ))
  // A region several places make: tinted in its flow's colour, named at its places' middle,
  // each weighed by its size (a country's main part; another place a little)
  let zones = ()
  for (f, c) in arrows.zip(curves) {
    for s in (f.from, f.to).filter(s => s.name != none) {
      if zones.any(z => z.name == s.name) { continue }
      let points = unwrapped(s.places.map(p => p.xy))
      let weights = s.places.map(p => if p.kind == "country" { size(atlas.countries.at(p.code).f) } else { 0 } + 1)
      let total = weights.sum()
      let (x, y) = range(2).map(e => points.zip(weights).map(((q, w)) => q.at(e) * w).sum() / total)
      zones.push((name: s.name, places: s.places, colour: c.colour))
      wanted.push((at: (px(seen-x(x)), py(y)), dot: false, body: wrapped(text(7.5pt, weight: "bold", fill: c.colour.darken(35%), s.name))))
    }
  }
  // The places routes and flows pass, named when they aren't already (a city by its dot):
  // a cape, a canal, a sea or strait where the way goes, a country or a part of the world
  let said = cities + regions + waters + reliefs + towns.map(t => t.name)
  // (each with the point it is named nearest: a sea between two places, halfway from one to
  // the other; else where the way meets it)
  let passed = trips.map(t => {
    let at = if t.by == "sea" { t.at } else { t.stops.map(p => p.xy) }
    t.stops.zip(at).enumerate().map(((i, (p, a))) => {
      let (before, after) = (at.at(i - 1, default: none), at.at(i + 1, default: none))
      let toward = if i == 0 or before == none or after == none or a == none { a } else {
        (before.at(0) + east(after.at(0) - before.at(0)) / 2, (before.at(1) + after.at(1)) / 2)
      }
      (p, a, toward)
    })
  }).join(default: ())
  passed += arrows.map(f => (f.from.places, f.to.places).filter(ps => ps.len() == 1).map(ps => (ps.first(), ps.first().xy, ps.first().xy))).join(default: ())
  let water-style(n) = text(7.5pt, style: "italic", fill: rgb("#1f5a8f"), n)
  let ticks = ()  // a cape's small dot
  for (p, at, toward) in passed {
    if p.kind == "city" or p.name in said or at == none { continue }
    said.push(p.name)
    // (a sea or an ocean named on itself: its own place nearest that point, in the frame; a
    // strait's is the strait)
    let (x, y) = if p.kind in ("country", "relief") { p.xy } else if p.kind == "water" {
      let spots = p.spots.map(((sx, sy)) => (toward.at(0) + east(sx - toward.at(0)), sy))
      let seen = spots.filter(((sx, sy)) => inside((seen-x(sx), sy)))
      (if seen.len() > 0 { seen } else { (at,) }).sorted(key: q => far(q, toward)).first()
    } else { at }
    let style = if p.kind in ("country", "relief") { n => text(7.5pt, fill: luma(40), n) } else { water-style }
    wanted.push((at: (px(seen-x(x)), py(y)), dot: p.kind == "cape", body: style(p.name)))
    if p.kind == "cape" { ticks.push((px(seen-x(x)), py(y))) }
  }
  let placed = ()
  let taken = ()
  // The flows' arrows: boxes along them, no name on them
  let strokes = ()
  for c in curves {
    let n = calc.max(2, calc.ceil(c.length / 4pt))
    for j in range(n + 1) {
      let t = j / n
      let (x, y) = range(2).map(e => calc.pow(1 - t, 2) * c.a.at(e) + 2 * (1 - t) * t * c.c.at(e) + t * t * c.b.at(e))
      let r = c.width / 2 + 1pt
      strokes.push((x - r, y - r, 2 * r, 2 * r))
    }
  }
  let overlap((ax, ay, aw, ah), (bx, by, bw2, bh2)) = (
    calc.max(0pt, calc.min(ax + aw, bx + bw2) - calc.max(ax, bx)) / 1pt * calc.max(0pt, calc.min(ay + ah, by + bh2) - calc.max(ay, by)) / 1pt
  )
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
      // With routes and flows, more names near each other: the corners around, then further,
      // then further still in eight directions, a thin line then leading to the place
      let near = tries.len()
      if moving {
        let (r, l) = (x + dot + gap, x - dot - gap - lw)
        let (above, below) = (y - dot - gap - lh, y + dot + gap)
        tries += ((r, above), (r, below), (l, above), (l, below), (x - lw / 2, above - lh), (x - lw / 2, below + lh),
          (r + lw / 2, y - lh / 2), (l - lw / 2, y - lh / 2))
        near = tries.len()
        for (ex, ey) in ((1, 0), (-1, 0), (0, -1), (0, 1), (1, -1), (-1, -1), (1, 1), (-1, 1)) {
          tries.push((x + ex * (2.5 * lh + lw / 2) - lw / 2, y + ey * 2.5 * lh - lh / 2))
        }
      }
      let inside-frame((ax, ay)) = ax >= 1pt and ay >= 1pt and ax + lw <= bw - 1pt and ay + lh <= bh - 1pt
      let apart((ax, ay), (bx, by, bw2, bh2)) = ax + lw <= bx or bx + bw2 <= ax or ay + lh <= by or by + bh2 <= ay
      // (with routes and flows, names a little apart: two side by side read as one)
      let room = if moving { 2pt } else { 0pt }
      let apart-name((ax, ay), (bx, by, bw2, bh2)) = apart((ax, ay), (bx - room, by - room / 2, bw2 + 2 * room, bh2 + room))
      // A name further off: its line to its place over no other name
      let lead((ax, ay)) = {
        let to = (calc.max(ax, calc.min(x, ax + lw)), calc.max(ay, calc.min(y, ay + lh)))
        let n = calc.max(2, calc.ceil(calc.abs(to.at(0) - x) / 2pt + calc.abs(to.at(1) - y) / 2pt))
        range(n).map(j => (x + (to.at(0) - x) * j / n, y + (to.at(1) - y) * j / n)).all(((qx, qy)) =>
          taken.all(((bx, by, bw2, bh2)) => qx < bx or qx > bx + bw2 or qy < by or qy > by + bh2))
      }
      let clear(j) = {
        let (ax, ay) = tries.at(j)
        (
          inside-frame((ax, ay))
            and taken.all(b => apart-name((ax, ay), b))
            and marks.enumerate().all(((m, (mx, my))) => (want.dot and m == i) or mx + dot <= ax or ax + lw <= mx - dot or my + dot <= ay or ay + lh <= my - dot)
            and strokes.all(b => apart((ax, ay), b))
            and (j < near or lead((ax, ay)))
        )
      }
      let k = range(tries.len()).find(clear)
      // Never cut by the frame: moved in
      let within((ax, ay)) = (calc.max(1pt, calc.min(ax, bw - 1pt - lw)), calc.max(1pt, calc.min(ay, bh - 1pt - lh)))
      // None clear: with routes and flows, the place near it where it covers least, moved in
      if k == none and moving {
        // (a name or a dot covered far worse than an arrow, a few points further worse still)
        let spots = marks.map(((mx, my)) => (mx - dot, my - dot, 2 * dot, 2 * dot))
        let cost(j) = {
          let (ax, ay) = within(tries.at(j))
          let here = (ax, ay, lw, lh)
          (20 * (taken + spots).map(o => overlap(here, o)).sum(default: 0) + strokes.map(o => overlap(here, o)).sum(default: 0)
            + 8 * (calc.abs(ax + lw / 2 - x) / 1pt + calc.abs(ay + lh / 2 - y) / 1pt))
        }
        k = range(near).sorted(key: cost).first()
      }
      let at = within(tries.at(if k == none { 0 } else { k }))
      taken.push((at.at(0), at.at(1), lw, lh))
      placed.push((at, want.body, if k != none and k >= near { (x, y) } else { none }, (lw, lh)))
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
    // The regions flows leave from or go to, in their flow's colour
    for z in zones {
      for p in z.places.filter(p => "rings" in p) {
        for points in p.rings { ring(points, z.colour.lighten(72%), 0.5pt + z.colour.lighten(20%)) }
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
    // A name placed further: a thin line from its place to it
    for ((ax, ay), _, from, (lw, lh)) in placed.filter(p => p.at(2) != none) {
      let (x, y) = from
      let to = (calc.max(ax, calc.min(x, ax + lw)), calc.max(ay, calc.min(y, ay + lh)))
      place(line(start: from, end: to, stroke: 0.5pt + luma(90)))
    }
    for ((ax, ay), body, ..) in placed {
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
