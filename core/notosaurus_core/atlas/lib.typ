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

#let country-code(name, all: atlas.countries) = {
  let key = fold(name)
  for (code, country) in all {
    if key in country.k { return code }
  }
  none
}
// The borders of a year (tools/atlas.py, borders/<year>.json): those of the atlas's years
// whose time it falls in (1914's from 1914 to 1918, 1960's from 1949 to 1991), today's from
// 1992; another year refused, said (never a past map drawn with the wrong borders)
#let today-from = 1992
#let borders(year) = {
  if year == none or year >= today-from { return atlas.countries }
  let found = atlas.years.find(((_, from, to)) => year >= from and year <= to)
  if found == none {
    let spans = atlas.years.map(((_, from, to)) => str(from) + "–" + str(to)).join(", ")
    panic("no borders of " + str(year) + " in the atlas: it has those of " + spans + " and today's (from " + str(today-from) + "); no year for another time")
  }
  json("borders/" + str(found.first()) + ".json").countries
}

// A part of the world (East Asia, Latin America, the Maghreb: tools/atlas.py's AREAS): its
// countries' codes; none when the name is no part's
#let area-codes(name) = {
  let key = fold(name)
  let found = atlas.at("areas", default: ()).find(a => key in a.k)
  if found == none { none } else { found.c }
}

// What a name the map refuses is when the atlas knows it otherwise, said in the refusal (the
// next try right): a country or a country's far part, a part of the world, a region of a
// country, a state of a past year, a city; none else. `asked`: what it was asked as
#let what-is(name, asked) = {
  let key = fold(name)
  let quoted = "\"" + name + "\""
  let code = if asked == "country" { none } else { country-code(name) }
  if code != none {
    let c = atlas.countries.at(code)
    if "t" in c {
      return quoted + " is a part of " + atlas.countries.at(c.o).n.first() + " the atlas draws as a country: in countries"
    }
    return quoted + " is a country: in countries"
  }
  if area-codes(name) != none {
    return quoted + " is a part of the world, its countries in the atlas: in countries (shown), a group's countries (coloured) or a flow's from or to"
  }
  let names = json("names.json")
  let held = names.regions.at(key, default: ())
  if held.len() > 0 {
    let countries = held.map(code => atlas.countries.at(code, default: (n: (code,))).n.first())
    return quoted + " is a region of " + countries.join(", ") + ": that country in countries, it in regions"
  }
  let years = names.states.at(key, default: ())
  if years.len() > 0 {
    return quoted + " is a state of the past in the atlas: year: a year of its time (the atlas has it in " + years.map(str).join(", ") + "); before 1815, today's countries on its land"
  }
  if asked != "city" and atlas.cities.any(c => key in c.k) { return quoted + " is a city: in cities" }
  none
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
    let said = what-is(name, "city")
    if said != none { panic("no city called \"" + name + "\" in the atlas: " + said) }
    panic("no city called \"" + name + "\" in the atlas (a country's capital, its largest cities, the places of history lessons): leave it out")
  }
  atlas.cities.at(i)
}

#let size(b) = (b.at(2) - b.at(0)) * (b.at(3) - b.at(1))
// The box around rings of points (x0, y0, x1, y1); none for no point
#let bounds(rings) = {
  let pts = rings.join(default: ())
  if pts.len() == 0 { return (0, 0, 0, 0) }
  (calc.min(..pts.map(q => q.at(0))), calc.min(..pts.map(q => q.at(1))),
   calc.max(..pts.map(q => q.at(0))), calc.max(..pts.map(q => q.at(1))))
}
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
// How many letters one name differs from another by (Levenshtein's distance), at most `most`
// (more: none)
#let distance(a, b, most) = {
  let (a, b) = (a.clusters(), b.clusters())
  if calc.abs(a.len() - b.len()) > most { return none }
  let row = range(b.len() + 1)
  for (i, ca) in a.enumerate() {
    let next = (i + 1,)
    for (j, cb) in b.enumerate() {
      next.push(calc.min(row.at(j + 1) + 1, next.at(j) + 1, row.at(j) + if ca == cb { 0 } else { 1 }))
    }
    if calc.min(..next) > most { return none }
    row = next
  }
  if row.last() > most { none } else { row.last() }
}
// The words a name of a place shares with others of its kind ("détroit", "strait", "mer",
// "golfe", "de"): what is left is its own ("ormuz" of "détroit d'Ormuz")
#let common-words = ("detroit", "detroits", "strait", "straits", "channel", "passage", "pas", "canal", "canale",
  "canals", "kanal", "strasse", "stretto", "estrecho", "estreito", "golfe", "gulf", "golfo", "baie", "bay", "bahia",
  "bucht", "mer", "sea", "mar", "mare", "meer", "see", "ocean", "oceano", "lac", "lake", "lago", "fleuve", "river",
  "riviere", "rio", "fluss", "fiume", "mont", "monts", "mount", "mountains", "montagne", "montagnes", "massif",
  "monte", "montes", "monti", "gebirge", "desert", "deserto", "desierto", "wuste", "plaine", "plain", "ile", "iles",
  "island", "islands", "isla", "isola", "insel", "ilha", "peninsule", "peninsula", "of", "the", "de", "du", "des",
  "d", "la", "le", "les", "l", "di", "del", "della", "dei", "do", "da", "dos", "das", "von", "der", "die")
#let own-words(key) = key.split(" ").filter(w => w not in common-words).join(" ", default: "")
// The places the atlas has nearest a name it lacks, each by its name nearest it: a letter or
// two apart, or its own words a letter or two from theirs ("Hormuz", "Ormuz"); at most three,
// the nearest first
#let nearest-names(items, key) = {
  let own = own-words(key)
  let (whole, part) = (calc.max(1, calc.div-euclid(key.len(), 6)), calc.max(1, calc.div-euclid(own.len(), 4)))
  let found = ()
  for item in items {
    // (its keys, folded already: a name folded again only when it is kept; a key too long or
    // too short to be near never measured)
    let best = none
    for k in item.k {
      let d = if calc.abs(k.len() - key.len()) > whole { none } else { distance(key, k, whole) }
      if d == none and own.len() >= 4 and k.len() + part >= own.len() {
        let o = own-words(k)
        if o.len() > 0 and calc.abs(o.len() - own.len()) <= part { d = distance(own, o, part) }
      }
      if d != none and (best == none or d < best.at(0)) { best = (d, (k,)) } else if d != none and d == best.at(0) {
        best.at(1).push(k)
      }
    }
    if best != none {
      // the first of its names (the page's languages first) folded to one of the nearest
      // keys; else its first
      let name = item.n.find(n => fold(n) in best.at(1))
      let name = if name == none { item.n.first() } else { name }
      if found.all(((_, m)) => m != name) { found.push((best.at(0), name)) }
    }
  }
  found.sorted(key: ((d, _)) => d).slice(0, calc.min(3, found.len())).map(((_, n)) => n)
}
#let find-in(items, name, what, near) = {
  let key = fold(name)
  let found = items.filter(i => key in i.k)
  if found.len() == 0 {
    let said = what-is(name, what)
    if said != none { panic("no " + what + " called \"" + name + "\" in the atlas: " + said) }
    let close = nearest-names(items, key)
    if close.len() == 0 { panic("no " + what + " called \"" + name + "\" in the atlas: leave it out") }
    panic("no " + what + " called \"" + name + "\" in the atlas; it has " + close.map(n => "\"" + n + "\"").join(", ")
      + ": one of them when it is that place written otherwise, else leave it out")
  }
  let theirs = if near == none { () } else { found.filter(i => touches(i.b, near)) }
  let top = (if theirs.len() > 0 { theirs } else { found }).sorted(key: i => -size(i.b)).first()
  if what != "water" { return top }
  let all = range(items.len()).filter(i => key in items.at(i).k)
  joined(items, all, all.find(i => items.at(i) == top)).item
}

// Whether a point is within rings (an even number of their sides crossed on its left: out)
#let within-rings((x, y), rings) = rings.any(r => {
  let crossed = false
  for (i, (bx, by)) in r.enumerate() {
    let (ax, ay) = r.at(i - 1)
    if (ay > y) != (by > y) and x < ax + (bx - ax) * (y - ay) / (by - ay) { crossed = not crossed }
  }
  crossed
})
// A year's states on a country of today's land, the most of it first (Poland in 1942: the
// Reich's): its frame's points within it, each in the state it is in
#let states-on(code, all) = {
  let today = atlas.countries.at(code)
  let (x0, y0, x1, y1) = today.f
  let points = range(1, 8).map(i => range(1, 8).map(j => (x0 + (x1 - x0) * i / 8, y0 + (y1 - y0) * j / 8))).join()
    .filter(q => within-rings(q, today.r))
  let near = all.pairs().filter(((_, c)) => c.n.len() > 0 and touches(c.b, today.f))
  let counts = near.map(((k, c)) => (c.n.first(), points.filter(q => within-rings(q, c.r)).len())).filter(((_, n)) => n > 0)
  counts.sorted(key: ((_, n)) => -n).map(((name, _)) => name)
}

#let find-country(name, all: atlas.countries, year: none) = {
  let code = country-code(name, all: all)
  if code == none and year != none {
    // A country of today: the year's states on its land, said
    let today = country-code(name)
    if today != none and "t" not in atlas.countries.at(today) {
      let on = states-on(today, all)
      if on.len() > 0 {
        panic("no state called \"" + name + "\" in " + str(year) + " in the atlas: its land was then " + on.slice(0, calc.min(4, on.len())).map(n => "\"" + n + "\"").join(", ") + "; those, as they were named")
      }
    }
    // (the year's states sharing a word with it: the name to write, said)
    let words = fold(name).split(" ").filter(w => w.len() > 3)
    let near = all.values().filter(c => c.n.len() > 0 and words.any(w => c.k.any(k => w in k.split(" ")))).map(c => c.n.first())
    let hint = if near.len() > 0 { ": maybe " + near.slice(0, calc.min(5, near.len())).map(n => "\"" + n + "\"").join(", ") } else {
      ": its name then (\"Autriche-Hongrie\", \"URSS\", \"Afrique-Occidentale française\")"
    }
    panic("no state called \"" + name + "\" in " + str(year) + " in the atlas" + hint)
  }
  if code == none {
    let said = what-is(name, "country")
    if said != none { panic("no country called \"" + name + "\" in the atlas: " + said) }
    let close = nearest-names(all.values(), fold(name))
    if close.len() > 0 {
      panic("no country called \"" + name + "\" in the atlas; it has " + close.map(n => "\"" + n + "\"").join(", ") + ": one of them when it is that place written otherwise, else its usual name or its three-letter code (\"ESP\")")
    }
    panic("no country called \"" + name + "\" in the atlas: its usual name, or its three-letter code (\"ESP\")")
  }
  code
}

// A region of a country shown: its first-level divisions (a state, a département) or their
// groups (a région); `level` which of the two it is
#let region-of(name, shown) = {
  let key = fold(name)
  for code in shown.filter(c => "t" not in atlas.countries.at(c, default: (:))) {
    let file = json("regions/" + code + ".json")
    for level in ("groups", "units") {
      for (i, r) in file.at(level).enumerate() {
        if key in r.k { return (code: code, level: level, index: i) }
      }
    }
  }
  none
}
#let find-region(name, shown) = {
  let found = region-of(name, shown)
  if found != none { return found }
  if shown.len() == 0 { panic("a region (\"" + name + "\") is shown with its country: put it in countries") }
  let said = what-is(name, "region")
  if said != none { panic("no region called \"" + name + "\" in the atlas for " + shown.join(", ") + ": " + said) }
  panic("no region called \"" + name + "\" in the atlas for " + shown.join(", ") + ": leave it out")
}

// The groups' colours, one each in their order: Okabe and Ito's, told apart by those who see
// colours differently, light enough for a name on them; the sky blue, nearest the sea's, last
#let palette = ("#e69f00", "#0072b2", "#009e73", "#cc79a7", "#d55e00", "#f0e442", "#56b4e9", "#a6761d").map(rgb)

// Groups as asked, checked: (name, countries: their codes, regions: their names); a past
// year's `empire`: a state and every land it ruled then (its colonies, protectorates)
#let read-groups(groups, all: atlas.countries, year: none) = {
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
      if key not in ("name", "countries", "regions", "empire") {
        panic("a group holds a name, countries and regions, not \"" + key + "\"")
      }
    }
    let listed(key) = {
      let v = g.at(key, default: ())
      if type(v) == str { (v,) } else { v }
    }
    // (a part of the world: its countries, today's; each once)
    let wanted = listed("countries").map(n => {
      let part = if year == none and country-code(n, all: all) == none { area-codes(n) } else { none }
      if part == none { ((n, find-country(n, all: all, year: year)),) } else { part.map(c => (all.at(c).n.first(), c)) }
    }).join(default: ())
    let wanted = wanted.enumerate().filter(((i, (_, c))) => wanted.slice(0, i).all(((_, d)) => d != c)).map(((_, w)) => w)
    let codes = wanted.map(((_, c)) => c)
    let names = wanted.map(((n, _)) => n)
    let ruled = ()  // (an empire's lands: never circled, too many small ones on a world map)
    if "empire" in g {
      if year == none { panic("an empire is a past year's (year: 1914): today's countries rule no colonies in the atlas") }
      let ruler = find-country(g.empire, all: all, year: year)
      let lands = all.pairs().filter(((_, c)) => c.at("o", default: none) == ruler).map(((code, _)) => code)
      for code in (ruler, ..lands).filter(c => c not in codes) {
        codes.push(code)
        names.push(all.at(code).n.first(default: code))  // (a land of no name: its code)
        if code != ruler { ruled.push(code) }
      }
    }
    if codes.len() + listed("regions").len() == 0 {
      panic("the group \"" + g.name + "\" holds no country nor region")
    }
    for (code, name) in codes.zip(names) {
      if code in seen {
        panic("\"" + name + "\" is in two groups (\"" + seen.at(code) + "\" and \"" + g.name + "\"): one group each")
      }
      seen.insert(code, g.name)
    }
    out.push((name: g.name, countries: codes, regions: listed("regions"), ruled: ruled))
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
#let country-place(code, name, ways, all: none) = {
  if all != none and code not in ways.countries {  // a past year's state: from its inmost point, by land
    let c = all.at(code)
    return (kind: "country", name: name, code: code, xy: c.at, port: none, nodes: (), rings: c.r, f: c.f)
  }
  let place = ways.countries.at(code)
  let c = atlas.countries.at(code)
  (kind: "country", name: name, code: code, xy: place.at, port: none, nodes: place.s, rings: c.r, f: c.f)
}
#let relief-place(i, name, ways, reliefs-all) = {
  let r = reliefs-all.at(i)
  (kind: "relief", name: name, xy: r.at.first(), port: none, nodes: ways.reliefs.at(i), rings: r.r)
}
#let find-place(name, shown, ways, waters-all, reliefs-all, all: none) = {
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
  for (code, c) in (if all == none { atlas.countries } else { all }) {
    if key in c.k { return country-place(code, name, ways, all: all) }
  }
  let found = reliefs-all.enumerate().filter(((_, r)) => key in r.k)
  if found.len() > 0 {
    return relief-place(found.sorted(key: ((_, r)) => -size(r.b)).first().at(0), name, ways, reliefs-all)
  }
  none
}

#let place-or-said(name, shown, ways, waters-all, reliefs-all, all: none) = {
  if type(name) != str { panic("a place is its name, a string: \"" + repr(name) + "\" is not") }
  let place = find-place(name, shown, ways, waters-all, reliefs-all, all: all)
  if place == none {
    let said = what-is(name, "place")
    if said != none and said.contains("region of") { panic("no place called \"" + name + "\" in the atlas: " + said.replace(": that country in countries, it in regions", ": that country instead")) }
    panic("no place called \"" + name + "\" in the atlas (a city, a cape, a canal, a sea or strait, a country, a continent or a part of one): name another the route or flow passes, or leave it out")
  }
  place
}

// Every place of routes or flows the atlas lacks, said at once (the AI's next try fixes them
// all, not one a try)
#let all-said(names, shown, ways, waters-all, reliefs-all, all: none) = {
  let missing = names.filter(n => type(n) == str and not n.contains(",")).dedup()
    .filter(n => (all != none or area-codes(n) == none) and find-place(n, shown, ways, waters-all, reliefs-all, all: all) == none)
  if missing.len() > 1 {
    panic("no places called " + missing.map(n => "\"" + n + "\"").join(", ") + " in the atlas (a city, a cape, a canal, a sea or strait, a country, a continent or a part of one): name others the routes or flows pass, or leave them out")
  }
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
#let read-routes(routes, shown, ways, waters-all, reliefs-all, all: none) = {
  if type(routes) == dictionary { routes = (routes,) }
  let names = routes.filter(r => type(r) == dictionary).map(r => r.at("places", default: ())).map(p => if type(p) == str { (p,) } else { p })
  all-said(names.join(default: ()), shown, ways, waters-all, reliefs-all, all: all)
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
    let stops = names.map(n => place-or-said(n, shown, ways, waters-all, reliefs-all, all: all))
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
#let read-flows(flows, shown, ways, waters-all, reliefs-all, all: none) = {
  if type(flows) == dictionary { flows = (flows,) }
  let ends = flows.filter(f => type(f) == dictionary).map(f => (f.at("from", default: ()), f.at("to", default: ())))
  all-said(ends.join(default: ()).map(e => if type(e) == str { (e,) } else { e }).join(default: ()), shown, ways, waters-all, reliefs-all, all: all)
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
      // A part of the world the atlas has no place for (East Asia, Latin America): its
      // countries, the region they make named as it was
      let part = if all == none and names.len() == 1 and type(names.first()) == str and area-codes(names.first()) != none and find-place(names.first(), shown, ways, waters-all, reliefs-all) == none { area-codes(names.first()) } else { none }
      if part != none {
        if name == none { name = names.first() }
        names = part.map(c => atlas.countries.at(c).n.first())
      }
      if names.len() > 1 and name == none {
        panic("a flow's " + end + " is several places (" + names.map(repr).join(", ") + "): name the region they make, " + end + "-name: \"…\", written on the map")
      }
      // Several places making a region: a name that is a country's too is the country (Kuwait,
      // Singapore), not its city
      let places = names.map(n => {
        let code = if names.len() > 1 { country-code(n, all: if all == none { atlas.countries } else { all }) } else { none }
        if code != none { country-place(code, n, ways, all: all) } else { place-or-said(n, shown, ways, waters-all, reliefs-all, all: all) }
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

// A point within a ring (even-odd: a ray to its east crossing its sides an odd number of times)
#let on-land(ring, (x, y)) = {
  let inside = false
  for (i, b) in ring.enumerate() {
    let a = ring.at(i - 1)
    if (a.at(1) > y) != (b.at(1) > y) and x < a.at(0) + (y - a.at(1)) * (b.at(0) - a.at(0)) / (b.at(1) - a.at(1)) {
      inside = not inside
    }
  }
  inside
}

// A round number for a legend: 1, 2 or 5 times a power of ten, the largest not above v
#let round-below(v) = {
  let p = calc.pow(10.0, calc.floor(calc.log(v)))
  let n = (5, 2, 1).find(m => m * p <= v)
  let r = (if n == none { 1 } else { n }) * p
  if r >= 1 { int(calc.round(r)) } else { r }
}

// The outline of a few points spread on the page (a zone a few cities span: a megalopolis),
// rounded `r` around them: their convex hull, each corner an arc (one point: a circle; two:
// a band with round ends)
#let rounded-hull(points, r) = {
  let pts = points.dedup()
  // (Andrew's monotone chain)
  let cross(o, a, b) = ((a.at(0) - o.at(0)) / 1pt * (b.at(1) - o.at(1)) / 1pt - (a.at(1) - o.at(1)) / 1pt * (b.at(0) - o.at(0)) / 1pt)
  let sorted = pts.sorted(key: q => (q.at(0) / 1pt, q.at(1) / 1pt))
  let half(seq) = {
    let out = ()
    for q in seq {
      while out.len() >= 2 and cross(out.at(-2), out.at(-1), q) <= 0 { let _ = out.pop() }
      out.push(q)
    }
    out
  }
  let hull = if sorted.len() <= 1 { sorted } else {
    let (lower, upper) = (half(sorted), half(sorted.rev()))
    lower.slice(0, -1) + upper.slice(0, -1)
  }
  if hull.len() == 0 { return () }
  let n = hull.len()
  let (mx, my) = (hull.map(q => q.at(0)).sum() / n, hull.map(q => q.at(1)).sum() / n)
  // An edge's normal, away from the middle
  let normal(a, b) = {
    let (dx, dy) = ((b.at(0) - a.at(0)) / 1pt, (b.at(1) - a.at(1)) / 1pt)
    let l = calc.sqrt(dx * dx + dy * dy)
    let (nx, ny) = if l == 0 { (1.0, 0.0) } else { (dy / l, -dx / l) }
    let (ex, ey) = (((a.at(0) + b.at(0)) / 2 - mx) / 1pt, ((a.at(1) + b.at(1)) / 2 - my) / 1pt)
    if nx * ex + ny * ey < 0 { (-nx, -ny) } else { (nx, ny) }
  }
  let arc(v, from, sweep) = {
    let steps = calc.max(2, calc.ceil(calc.abs(sweep) / 15deg))
    range(steps + 1).map(j => {
      let a = from + sweep * j / steps
      (v.at(0) + r * calc.cos(a), v.at(1) + r * calc.sin(a))
    })
  }
  if n == 1 { return arc(hull.first(), 0deg, 360deg).slice(0, -1) }
  if n == 2 {
    // each end a half circle away from the other
    let (a, b) = (hull.first(), hull.last())
    let side(v, u) = {
      let out = calc.atan2((v.at(0) - u.at(0)) / 1pt, (v.at(1) - u.at(1)) / 1pt)
      arc(v, out - 90deg, 180deg)
    }
    return side(b, a) + side(a, b)
  }
  let out = ()
  for i in range(n) {
    let v = hull.at(i)
    let a1 = calc.atan2(..normal(hull.at(i - 1), v))
    let a2 = calc.atan2(..normal(v, hull.at(calc.rem(i + 1, n))))
    // the short way from one to the other (a convex corner turns less than half a turn)
    let d = a2 - a1
    let d = d - calc.round(d / 360deg) * 360deg
    out += arc(v, a1, d)
  }
  out
}

// countries: shown white and framed (names or codes); cities: a red dot each; regions: of
// the countries shown, coloured, their country's others outlined; rivers: blue lines;
// reliefs (mountains, deserts, plains, peninsulas, islands) and waters (oceans, seas, gulfs,
// straits, canals, lakes): coloured, a ring when too small to see; groups: countries or regions (of a country shown or grouped) coloured by
// group, one colour each, a legend under the map, all framed; routes: (name, places, by: "sea"
// or "land"), each its way in its colour with arrows; flows: (from, to, kind, value, label),
// a curved arrow each, its kind's colour, as wide as its value; routes and flows in the
// legend, framed; each named when labels; width, height: the most the map takes
#let one-map(countries: (), cities: (), regions: (), rivers: (), reliefs: (), waters: (), groups: (),
  routes: (), flows: (), year: none, pole: none, labels: true, values: (:), unit: none, zones: (),
  names: auto, frame: none, width: 8cm, height: 7cm, least: 4) = context {
  // (the values' unit, its name kept: the map's own `unit` is the length of an atlas unit)
  let value-unit = unit
  if pole not in (none, "north", "south") { panic("pole is \"north\" or \"south\" (a map centred on it), not " + repr(pole)) }
  // The states drawn: a past year's (its borders), else today's countries
  let all = borders(year)
  let past = year != none and year < today-from
  // (a part of the world: its countries, today's)
  let shown = countries.map(n => {
    let part = if not past and country-code(n) == none { area-codes(n) } else { none }
    if part == none { (find-country(n, all: all, year: if past { year }),) } else { part }
  }).join(default: ()).dedup()
  // A region that is no region of the countries shown but a country of the atlas, shown as
  // one (Greenland among Denmark's regions: its own country in the atlas)
  let as-country = if past { () } else {
    regions.filter(n => type(n) == str and region-of(n, shown) == none and country-code(n) != none)
  }
  shown += as-country.map(n => country-code(n)).filter(c => c not in shown)
  let regions = regions.filter(n => n not in as-country)
  let sets = read-groups(groups, all: all, year: if past { year })
  let grouped = sets.map(g => g.countries).join(default: ())
  // Zones: an area that is no country nor region of the atlas (a country's emptiest part, a
  // megalopolis, a basin), made of the countries or regions it covers, or spanning a few
  // cities; outlined and tinted over the map, its name in the legend
  let zones = if type(zones) == dictionary { (zones,) } else { zones }
  let zone-sets = zones.map(z => {
    if type(z) != dictionary or "name" not in z {
      panic("a zone is (name: \"…\", regions: (…), countries: (…), places: (…)): its name, for the legend, and what it covers")
    }
    for key in z.keys() {
      if key not in ("name", "countries", "regions", "places") {
        panic("a zone holds a name, countries, regions and places, not \"" + key + "\"")
      }
    }
    let listed(key) = { let v = z.at(key, default: ()); if type(v) == str { (v,) } else { v } }
    if listed("countries").len() + listed("regions").len() + listed("places").len() == 0 {
      panic("the zone \"" + z.name + "\" covers nothing: the regions or countries it covers, or the cities it spans")
    }
    (name: z.name, countries: listed("countries").map(n => find-country(n, all: all, year: if past { year })),
      regions: listed("regions"), places: listed("places"))
  })
  if sets.len() + zone-sets.len() > palette.len() {
    panic("at most " + str(palette.len()) + " groups and zones on a map, one colour each: join some")
  }
  if past and zone-sets.any(z => z.regions.len() > 0) {
    panic("no regions on a map of a past year: the atlas's regions are today's; its states only")
  }
  // The countries the map is about: those shown, grouped or in a zone
  let about = shown + grouped.filter(code => code not in shown)
  about += zone-sets.map(z => z.countries).join(default: ()).filter(code => code not in about).dedup()
  // Values: a city's circle, its area as its value (proportional circles: the largest cities'
  // population); the cities valued are shown. "population": each city's of the atlas, in
  // millions (Natural Earth's, its urban area's), when the description gives none
  let values = if values == "population" {
    let found = cities.map(name => (name, find-city(name, shown + sets.map(g => g.countries).join(default: ()))))
    found.map(((name, c)) => (name, calc.max(0.1, calc.round(c.p / 1000000, digits: 1)))).to-dict()
  } else { values }
  if values != (:) and value-unit == none {
    panic("values need their unit, as the legend writes it (unit: \"millions d'habitants\")")
  }
  if type(values) != dictionary {
    panic("values is a dictionary, a city's name and its value: (\"Tokyo\": 37.4, \"Delhi\": 32.9), or \"population\"")
  }
  for (name, v) in values {
    if type(v) not in (int, float) or v <= 0 { panic("a value is a number above 0: \"" + name + "\": " + repr(v)) }
  }
  let cities = cities + values.keys().filter(n => n not in cities)
  let towns = cities.map(name => (name: name, city: find-city(name, about)))
  // Routes and flows: the places they pass, a sea route's way over the sea
  let moving = routes.len() + flows.len() > 0
  let (trips, arrows) = ((), ())
  if moving {
    let ways = json("ways.json")
    let (waters-all, reliefs-all) = (json("waters.json"), json("reliefs.json"))
    // (a past year's states the places they pass, by their names then)
    let then = if past { all } else { none }
    if routes.len() > 0 { trips = read-routes(routes, about, ways, waters-all, reliefs-all, all: then) }
    if flows.len() > 0 { arrows = read-flows(flows, about, ways, waters-all, reliefs-all, all: then) }
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
  if past and (regions.len() > 0 or sets.any(g => g.regions.len() > 0)) {
    panic("no regions on a map of a past year: the atlas's regions are today's; its states only")
  }
  let areas = regions.map(name => (name: name, at: find-region(name, shown)))
  let group-areas = sets.enumerate().map(((i, g)) => g.regions.map(name => (name: name, at: find-region(name, about), group: i))).join(default: ())
  let zone-areas = zone-sets.map(z => z.regions.map(name => (name: name, at: find-region(name, about)))) 
  let zone-towns = zone-sets.map(z => z.places.map(name => find-city(name, about)))
  let region(a) = json("regions/" + a.at.code + ".json").at(a.at.level).at(a.at.index)
  let near = if about.len() == 0 { none } else {
    let bs = about.map(code => all.at(code).b)
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
  let boxes = shown.map(code => all.at(code).f) + areas.map(a => region(a).b)
  let points = towns.map(t => (t.city.x, t.city.y, t.city.x, t.city.y))
  // (with groups, the cities weighed with the areas, as ever; shown countries alone weighed
  // against each other only: a country is never cut to its cities)
  let weighed = sets.len() > 0 or shown.len() + areas.len() > 1
  if sets.len() > 0 {
    boxes += points
    boxes += grouped.filter(code => code not in shown).map(code => all.at(code).f)
    boxes += group-areas.map(a => region(a).b)
  }
  // An area far larger than all the others together (Russia beside Europe's countries, in a
  // group or shown: the Russian Empire beside the Congress of Vienna's Europe) framed only on
  // its part nearest them, as large as half of them: the others stay large enough to see
  if weighed {
    let union(bs) = (calc.min(..bs.map(b => b.at(0))), calc.min(..bs.map(b => b.at(1))),
      calc.max(..bs.map(b => b.at(2))), calc.max(..bs.map(b => b.at(3))))
    // On one axis: the part of (b0, b1) within d of (r0, r1), or its d nearest them
    let nearest(b0, b1, r0, r1, d) = if b1 < r0 - d { (calc.max(b0, b1 - d), b1) } else if b0 > r1 + d {
      (b0, calc.min(b1, b0 + d))
    } else { (calc.max(b0, r0 - d), calc.min(b1, r1 + d)) }
    if boxes.len() > 1 {
      boxes = boxes.enumerate().map(((i, b)) => {
        let rest = union(boxes.enumerate().filter(((j, _)) => j != i).map(((_, c)) => c))
        // (shown countries alone: only one spanning a continent, Russia, Canada, China; never
        // France beside Haiti, nor a country holding the others, the United States and its states)
        let holds = b.at(0) <= rest.at(0) and b.at(1) <= rest.at(1) and b.at(2) >= rest.at(2) and b.at(3) >= rest.at(3)
        let sprawling = sets.len() > 0 or (b.at(2) - b.at(0) > 40 * atlas.scale and not holds)
        if sprawling and size(rest) > 0 and size(b) > 2 * size(rest) and size(union((rest, b))) > 4 * size(rest) {
          let (x0, x1) = nearest(b.at(0), b.at(2), rest.at(0), rest.at(2), (rest.at(2) - rest.at(0)) / 2)
          let (y0, y1) = nearest(b.at(1), b.at(3), rest.at(1), rest.at(3), (rest.at(3) - rest.at(1)) / 2)
          (x0, y0, x1, y1)
        } else { b }
      })
    }
  }
  if sets.len() == 0 { boxes += points }
  // Zones framed whole
  for (z, (zas, zts)) in zone-sets.zip(zone-areas.zip(zone-towns)) {
    boxes += z.countries.map(code => all.at(code).f) + zas.map(a => region(a).b)
    boxes += zts.map(c => (c.x, c.y, c.x, c.y))
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
      boxes.push(if p.kind == "country" { p.f } else { (..p.xy, ..p.xy) })
    }
  }
  if boxes.len() == 0 { boxes = lines.map(l => l.item.b) + lands.map(l => l.item.b) }
  if boxes.len() == 0 {
    let small = seas.filter(w => calc.max(w.item.b.at(2) - w.item.b.at(0), w.item.b.at(3) - w.item.b.at(1)) <= 30 * s)
    boxes = (if small.len() > 0 { small } else { seas }).map(w => w.item.b)
  }
  // A frame asked (a continent, a part of the world, a country, a region, a sea): it alone,
  // whatever else is drawn (an empire's lands in Africa framed on Africa, the rest cut)
  let framed = frame != none
  if framed {
    let asked = if type(frame) == str { (frame,) } else { frame }
    let (reliefs-all, waters-all) = (json("reliefs.json"), json("waters.json"))
    boxes = asked.map(name => {
      let key = fold(name)
      let code = country-code(name, all: all)
      if code != none { return all.at(code).f }
      let found = reliefs-all.filter(x => key in x.k) + waters-all.filter(x => key in x.k)
      let r = if past or found.len() > 0 { none } else { region-of(name, about) }
      if r != none { return region((at: r)).b }
      if found.len() == 0 {
        panic("no place called \"" + name + "\" to frame the map on (a continent or a part of one, a country, a region of a country shown, a sea): another, or leave the frame out")
      }
      found.sorted(key: x => -size(x.b)).first().b
    })
  }
  if boxes.len() == 0 { panic("a map shows at least one country, city, region, group, zone, route, flow, river, relief or water") }
  // A river, relief or water asked has a place for its name in the frame: the nearest one
  // added when it has none (the Atlantic beside France)
  let around = (
    calc.min(..boxes.map(b => b.at(0))), calc.min(..boxes.map(b => b.at(1))),
    calc.max(..boxes.map(b => b.at(2))), calc.max(..boxes.map(b => b.at(3))),
  )
  let (mx, my) = ((around.at(0) + around.at(2)) / 2, (around.at(1) + around.at(3)) / 2)
  let within((x, y)) = x >= around.at(0) and x <= around.at(2) and y >= around.at(1) and y <= around.at(3)
  let candidates = seas.map(w => w.item.at) + lands.map(l => l.item.at) + lines.map(l => l.item.l.flatten().chunks(2))
  for places in if framed { () } else { candidates } {
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
  let least = least * s
  let (cx, cy) = ((x0 + x1) / 2, (y0 + y1) / 2)
  let (w, h) = (calc.max(x1 - x0, least) * 1.2, calc.max(y1 - y0, least) * 1.2)
  // Neither a strip nor a band: a long country (Chile) shows its neighbours, its names fit
  let (w, h) = (calc.max(w, h * 0.75), calc.max(h, w * 0.55))
  // Never more than the world once
  let (w, h) = if moving { (calc.min(w, 360 * s * k), calc.min(h, 180 * s)) } else { (w, h) }
  // With routes and flows, the names of the places they pass whole within the frame: grown
  // until each has room around its place (half its width each side, its height above and
  // below), the scale found again each time
  if moving and pole == none and not framed {
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
  // Centred on a pole (the Arctic, Antarctica): azimuthal equidistant, a point as far from
  // the middle as from the pole, in the direction of its longitude (Greenwich down for the
  // north, up for the south); framed on what is shown, down to 50° of latitude at most
  let sign = if pole == "south" { -1 } else { 1 }
  let flat((x, y)) = {
    let (r, a) = (90 * s - sign * y, x / s * 1deg)
    (r * calc.sin(a), -sign * r * calc.cos(a))
  }
  // (a long side cut every degree first: a parallel, the 49th between the United States and
  // Canada, drawn as the arc it is)
  let curved(points, closed: true) = {
    let out = ()
    for (i, b) in points.enumerate() {
      if i > 0 or closed {
        let a = points.at(i - 1)
        let n = calc.ceil(calc.max(calc.abs(b.at(0) - a.at(0)), calc.abs(b.at(1) - a.at(1))) / s)
        for j in range(1, n) { out.push((a.at(0) + (b.at(0) - a.at(0)) * j / n, a.at(1) + (b.at(1) - a.at(1)) * j / n)) }
      }
      out.push(b)
    }
    out
  }
  let reach = if pole == none { 0 } else {
    calc.min(calc.max(..boxes.map(b => 90 * s - sign * (if sign > 0 { b.at(1) } else { b.at(3) }))), 40 * s)
  }
  if pole != none {
    // (each box's edges along its parallels, cut to that reach, as drawn)
    let points = boxes.map(b => range(13).map(i => b.at(0) + (b.at(2) - b.at(0)) * i / 12).map(x => (b.at(1), b.at(3))
      .map(y => (x, if sign > 0 { calc.max(y, 90 * s - reach) } else { calc.min(y, reach - 90 * s) })))).flatten().chunks(2)
      .map(flat)
    let (xs, ys) = (points.map(q => q.at(0)), points.map(q => q.at(1)))
    (cx, cy) = ((calc.min(..xs) + calc.max(..xs)) / 2, (calc.min(..ys) + calc.max(..ys)) / 2)
    (w, h) = ((calc.max(..xs) - calc.min(..xs)) * 1.1, (calc.max(..ys) - calc.min(..ys)) * 1.1)
    (w, h) = (calc.max(w, h * 0.75, 8 * s), calc.max(h, w * 0.55, 8 * s))
    k = 1
  }
  let unit = calc.min(width / w, height / h)  // a length per atlas unit
  let (bw, bh) = (w * unit, h * unit)
  let px(x) = (x * k - (cx - w / 2)) * unit
  let py(y) = ((cy + h / 2) - y) * unit
  let left = (cx - w / 2) / k
  let right = (cx + w / 2) / k
  let frame = (left, cy - h / 2, right, cy + h / 2)
  // (a point of the atlas within the frame: as drawn, when centred on a pole)
  let inside(q) = {
    let (x, y) = if pole == none { q } else { flat(q) }
    x >= left and x <= right and y >= cy - h / 2 and y <= cy + h / 2
  }
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
  // (centred on a pole, every coast of the Arctic in the frame: a point and a half)
  let step = if pole != none { 1.6 } else { 1 }
  let thinned(points) = {
    let kept = ()
    for q in points {
      let (x, y) = (px(q.at(0)), py(q.at(1)))
      if kept.len() == 0 or calc.abs((x - kept.last().at(0)) / 1pt) + calc.abs((y - kept.last().at(1)) / 1pt) >= step {
        kept.push((x, y))
      }
    }
    kept
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
  // With routes or flows, the world drawn round: what lies a turn east or west drawn there
  // too (Alaska beside Asia on a map of the Pacific)
  let full = 360 * s
  let spans = if moving and pole == none { (0, full, -full) } else { (0,) }
  let moved(points, d) = if d == 0 { points } else { points.map(((x, y)) => (x + d, y)) }
  let ring(points, fill, stroke) = if pole != none {
    // (its seams: the sides along the 180th meridian or on the pole, where Natural Earth cuts
    // a ring round the world; its outline drawn apart then, without them: a line from
    // Antarctica's coast to the pole, along Chukotka's edge else)
    let seam(a, b) = (calc.abs(a.at(0)) >= 179.99 * s and calc.abs(b.at(0)) >= 179.99 * s) or (
      sign * a.at(1) >= 89.9 * s and sign * b.at(1) >= 89.9 * s)
    let sides = (..points, points.first()).windows(2)
    let seamed = stroke != none and sides.any(((a, b)) => seam(a, b))
    let kept = thinned(clipped(curved(points).map(flat)))
    if kept.len() >= 3 { place(polygon(fill: fill, stroke: if seamed { none } else { stroke }, ..kept)) }
    if seamed and kept.len() >= 3 {
      let pieces = ((points.first(),),)
      for (a, b) in sides {
        if seam(a, b) { pieces.push((b,)) } else { pieces.last().push(b) }
      }
      for piece in pieces.filter(p => p.len() >= 2) {
        for run in runs(curved(piece, closed: false).map(flat)) {
          let line = thinned(run)
          if line.len() >= 2 { place(curve(stroke: stroke, curve.move(line.first()), ..line.slice(1).map(curve.line))) }
        }
      }
    }
  } else {
    for d in spans {
      let kept = thinned(clipped(moved(points, d)))
      if kept.len() >= 3 { place(polygon(fill: fill, stroke: stroke, ..kept)) }
    }
  }
  let near-frame(b) = if pole != none {
    // (centred on a pole: what comes within the frame's corners of it)
    90 * s - sign * (if sign > 0 { b.at(3) } else { b.at(1) }) <= calc.sqrt(calc.pow(calc.abs(cx) + w / 2, 2) + calc.pow(calc.abs(cy) + h / 2, 2))
  } else { spans.any(d => touches((b.at(0) + d, b.at(1), b.at(2) + d, b.at(3)), (fx0, fy0, fx1, fy1))) }
  // A point where it is seen (a turn east or west, with routes or flows)
  let seen-x(x) = if pole != none { x } else {
    let found = spans.map(d => x + d).find(x => x >= fx0 and x <= fx1)
    if found == none { x } else { found }
  }
  // A point of the atlas on the page
  let page((x, y)) = if pole != none { let (u, v) = flat((x, y)); (px(u), py(v)) } else { (px(seen-x(x)), py(y)) }
  // (a country's far part drawn with it: its rings are its country's)
  let others = all.pairs().filter(((code, c)) => code not in about and "t" not in c and near-frame(c.b))
  // Where a name goes: a region's, relief's or water's first place in the frame; a river's
  // middle point within it
  let place-of(item) = {
    let found = spans.map(d => moved(item.at, d)).join().filter(inside)
    // (the one nearest the frame's middle)
    let off(q) = {
      let (x, y) = if pole != none { flat(q) } else { (q.at(0) * k, q.at(1)) }
      calc.abs(x - cx) / w + calc.abs(y - cy) / h
    }
    if found.len() == 0 { none } else { found.sorted(key: off).first() }
  }
  let river-place(item) = {
    let pts = if pole != none { item.l.join().filter(inside) } else {
      spans.map(d => item.l.map(p => runs(moved(p, d)))).join().flatten().chunks(2).filter(inside)
    }
    if pts.len() == 0 { none } else { pts.at(calc.div-euclid(pts.len(), 2)) }
  }
  // Labels: cities beside their dot (right, left, above, below); the others on their place
  // (on it, above, below, right, left): the first that stays in the frame and on no other
  // label or dot
  let dot = 2.4pt
  let gap = 2.5pt
  let marks = towns.map(t => page((t.city.x, t.city.y)))
  // Proportional circles: the largest value's 11pt its radius, each other's area as
  // its value (its radius as the root of its share), never smaller than a dot
  let most-valued = if values.len() == 0 { none } else { calc.max(..values.values()) }
  let bubble-r(v) = calc.max(dot, 11pt * calc.sqrt(v / most-valued))
  let bubbles = towns.enumerate().filter(((_, t)) => t.name in values).map(((i, t)) => (
    index: i, at: marks.at(i), r: bubble-r(values.at(t.name)),
  ))
  let wanted = ()
  for (i, t) in towns.enumerate() {
    let mark = bubbles.find(b => b.index == i)
    wanted.push((at: marks.at(i), dot: true, mark: if mark == none { dot } else { calc.max(dot, mark.r) },
      body: text(8pt, weight: if t.city.cap { "bold" } else { "regular" }, t.name)))
  }
  let named(items, find, style) = items.map(it => (it, find(it))).filter(((_, p)) => p != none).map(((it, p)) => (
    at: page(p), dot: false, body: style(it.name),
  ))
  // A region asked too small to see at this scale (Hawaii beside the United States, an
  // island far from its country): a circle around it, its name beside the circle
  let circled(a) = {
    let largest = region(a).r.first()  // its largest part (an archipelago's main island)
    let b = (calc.min(..largest.map(p => p.at(0))), calc.min(..largest.map(p => p.at(1))),
             calc.max(..largest.map(p => p.at(0))), calc.max(..largest.map(p => p.at(1))))
    if near-frame(b) and calc.max((b.at(2) - b.at(0)) * k * unit, (b.at(3) - b.at(1)) * unit) < 10pt {
      page(((b.at(0) + b.at(2)) / 2, (b.at(1) + b.at(3)) / 2))
    } else { none }
  }
  let circle-size = 9pt
  let circles-at = areas.map(circled).filter(c => c != none)
  for a in areas {
    let c = circled(a)
    if c != none {
      wanted.push((at: c, dot: true, mark: circle-size, crowd: true, body: text(7.5pt, fill: luma(40), a.name)))
    } else {
      wanted += named((a,), a => place-of(region(a)), n => text(7.5pt, fill: luma(40), n))
    }
  }
  wanted += named(lands, l => place-of(l.item), n => text(8pt, style: "italic", fill: rgb("#6b4a1f"), n))
  // A water too small to see at this scale (a strait, a canal, a lake on a world map: less
  // than 10pt across), or a point (a passage the atlas has no area for): a ring at its place,
  // its name beside it, further off if need be, a line leading to it
  let ring-size = 4pt
  let small-water(item) = item.r.len() == 0 or calc.max((item.b.at(2) - item.b.at(0)) * k * unit, (item.b.at(3) - item.b.at(1)) * unit) < 10pt
  let sea-places = seas.map(w => (w, place-of(w.item))).filter(((_, p)) => p != none)
  let rings-at = sea-places.filter(((w, _)) => small-water(w.item)).map(((_, p)) => page(p))
  wanted += sea-places.map(((w, p)) => {
    let small = small-water(w.item)
    (at: page(p), dot: small, mark: if small { ring-size } else { dot }, crowd: small,
      body: text(8pt, style: "italic", fill: rgb("#1f5a8f"), w.name))
  })
  wanted += named(lines, l => river-place(l.item), n => text(7.5pt, style: "italic", fill: rgb("#1f5a8f"), n))
  // Flows: a curved arrow each, from its start to its end (shortened by a dot), drawn where
  // its middle is seen; as wide as its value ranks among theirs (the least the thinnest, the
  // largest the widest: told apart at a glance); never shorter than its arrowhead's reach
  let flowing = arrows.filter(f => f.value != none).map(f => f.value)
  let (least, most) = if flowing.len() == 0 { (none, none) } else { (calc.min(..flowing), calc.max(..flowing)) }
  let shortest = 22pt
  let curves = arrows.map(f => {
    let (ax, ay) = f.from.at
    let (bx, by) = (ax + east(f.to.at.at(0) - ax), f.to.at.at(1))
    let d = seen-x((ax + bx) / 2) - (ax + bx) / 2
    let (a, b) = if pole != none { (page(f.from.at), page(f.to.at)) } else { ((px(ax + d), py(ay)), (px(bx + d), py(by))) }
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
      let weights = s.places.map(p => if p.kind == "country" { size(p.f) } else { 0 } + 1)
      let total = weights.sum()
      let (x, y) = range(2).map(e => points.zip(weights).map(((q, w)) => q.at(e) * w).sum() / total)
      zones.push((name: s.name, places: s.places, colour: c.colour))
      wanted.push((at: page((x, y)), dot: false, body: wrapped(text(7.5pt, weight: "bold", fill: c.colour.darken(35%), s.name))))
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
    // (a strait or a canal too small to see: a ring at its place, as waters' are, its name
    // beside it, not over the way)
    let small = p.kind == "canal" or (p.kind == "water" and small-water((r: p.rings, b: bounds(p.rings))))
    if small { rings-at.push(page((x, y))) }
    wanted.push((at: page((x, y)), dot: p.kind == "cape" or small, mark: if small { ring-size } else { dot }, crowd: small,
      body: style(p.name)))
    if p.kind == "cape" { ticks.push(page((x, y))) }
  }
  // The countries' names (a map of several countries: Southern Africa's; asked with
  // `names: true`, the grouped ones too): on their land, else beside it with a line
  let to-name = if names == false { () } else {
    let listed = countries.zip(shown.slice(0, countries.len()))
    if names == true {
      listed += sets.map(g => g.countries.filter(c => c not in g.ruled and c not in shown)).join(default: ())
        .map(c => (all.at(c).n.first(), c))
      listed += zone-sets.map(z => z.countries).join(default: ()).filter(c => c not in shown).map(c => (all.at(c).n.first(), c))
    }
    if names == auto and countries.len() < 2 { () } else { listed.dedup(key: ((_, c)) => c) }
  }
  if to-name.len() > 0 {
    let inmost = if past { none } else { json("ways.json").countries }
    for (name, code) in to-name {
      let c = all.at(code)
      let at = if past { c.at } else if inmost != none and code in inmost { inmost.at(code).at } else {
        ((c.f.at(0) + c.f.at(2)) / 2, (c.f.at(1) + c.f.at(3)) / 2)
      }
      let (tl, br) = (page((c.f.at(0), c.f.at(3))), page((c.f.at(2), c.f.at(1))))
      // (on its land, else beside it with a line: too small for its name)
      wanted.push((at: page(at), dot: false, optional: true, country: code, within: if pole == none { (..tl, ..br) } else { none },
        land: if pole == none { c.r } else { none }, body: text(7pt, fill: luma(55), name)))
      wanted.push((at: page(at), dot: false, optional: true, country: code, far: true, body: text(7pt, fill: luma(55), name)))
    }
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
  let countries-named = ()
  if labels {
    for (i, want) in wanted.enumerate() {
      // (a country named already, at a larger size or on its land)
      if want.at("country", default: none) in countries-named { continue }
      let (x, y) = want.at
      let size = measure(want.body)
      let (lw, lh) = (size.width, size.height)
      // (a dot's or a ring's size; a ring's name, with routes and flows, may go further)
      let rad = want.at("mark", default: dot)
      let crowd = moving or want.at("crowd", default: false)
      let tries = if want.dot {
        ((x + rad + gap, y - lh / 2), (x - rad - gap - lw, y - lh / 2),
         (x - lw / 2, y - rad - gap - lh), (x - lw / 2, y + rad + gap))
      } else if want.at("far", default: false) {
        // (a country too small for its name: beside it, further each time, a line to it)
        let out = ()
        for d in (1.2, 2, 3) {
          for (ex, ey) in ((1, 0), (-1, 0), (0, -1), (0, 1), (1, -1), (-1, -1), (1, 1), (-1, 1)) {
            out.push((x + ex * (d * lh + lw / 2) - lw / 2, y + ey * d * lh * 1.5 - lh / 2))
          }
        }
        out
      } else if want.at("land", default: none) != none {
        // (a country's name: on its inmost point, else moved about it, nearest first)
        let around = ()
        for dy in (0, -1, 1, -2, 2) {
          for dx in (0, -0.5, 0.5, -1, 1) { around.push((dx, dy)) }
        }
        around.sorted(key: ((dx, dy)) => calc.abs(dx) * 2 + calc.abs(dy)).map(((dx, dy)) => (x - lw / 2 + dx * lw / 2, y - lh / 2 + dy * lh))
      } else {
        ((x - lw / 2, y - lh / 2), (x - lw / 2, y - lh * 1.6), (x - lw / 2, y + lh * 0.6),
         (x + gap, y - lh / 2), (x - gap - lw, y - lh / 2))
      }
      // With routes and flows, more names near each other: the corners around, then further,
      // then further still in eight directions, a thin line then leading to the place
      let near = if want.at("far", default: false) { 0 } else { tries.len() }
      if crowd and not want.at("far", default: false) {
        let (r, l) = (x + rad + gap, x - rad - gap - lw)
        let (above, below) = (y - rad - gap - lh, y + rad + gap)
        tries += ((r, above), (r, below), (l, above), (l, below), (x - lw / 2, above - lh), (x - lw / 2, below + lh),
          (r + lw / 2, y - lh / 2), (l - lw / 2, y - lh / 2))
        near = tries.len()
      }
      // Every map: none of those clear (names of places close together, a dot on the frame's
      // edge), further off in eight directions, a little further each time, a thin line then
      // leading to the place
      for f in (1.6, 2.5, 3.6) {
        for (ex, ey) in ((1, 0), (-1, 0), (0, -1), (0, 1), (1, -1), (-1, -1), (1, 1), (-1, 1)) {
          tries.push((x + ex * (f * lh + lw / 2) - lw / 2, y + ey * f * lh - lh / 2))
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
      // A name further off read as its own place's: nearer it than any other dot, ring or circle
      let reach((ax, ay), (qx, qy)) = calc.max(ax - qx, qx - ax - lw, 0pt) + calc.max(ay - qy, qy - ay - lh, 0pt)
      let others-at = (marks.enumerate().filter(((m, q)) => not (want.dot and m == i)).map(((_, q)) => q)
        + rings-at.filter(q => q != (x, y)) + circles-at.filter(q => q != (x, y)))
      let own((ax, ay)) = others-at.all(q => reach((ax, ay), q) > reach((ax, ay), (x, y)))
      let clear(j) = {
        let (ax, ay) = tries.at(j)
        (
          inside-frame((ax, ay))
            and taken.all(b => apart-name((ax, ay), b))
            and marks.enumerate().all(((m, (mx, my))) => (want.dot and m == i) or mx + dot <= ax or ax + lw <= mx - dot or my + dot <= ay or ay + lh <= my - dot)
            and strokes.all(b => apart((ax, ay), b))
            and rings-at.all(((qx, qy)) => (qx == x and qy == y) or qx + ring-size <= ax or ax + lw <= qx - ring-size
              or qy + ring-size <= ay or ay + lh <= qy - ring-size)
            and circles-at.all(((qx, qy)) => (qx == x and qy == y) or qx + circle-size <= ax or ax + lw <= qx - circle-size
              or qy + circle-size <= ay or ay + lh <= qy - circle-size)
            and (j < near or (lead((ax, ay)) and own((ax, ay))))
            and (want.at("within", default: none) == none or {
              let (x0, y0, x1, y1) = want.within
              ax >= x0 and ay >= y0 and ax + lw <= x1 and ay + lh <= y1
            })
            // (a country's name on its land: its corners and its sides' middles within it)
            and (want.at("land", default: none) == none or {
              let back((qx, qy)) = (((qx / unit) + cx - w / 2) / k, cy + h / 2 - qy / unit)
              let probes = ((ax, ay), (ax + lw / 2, ay), (ax + lw, ay), (ax, ay + lh), (ax + lw / 2, ay + lh), (ax + lw, ay + lh))
              probes.map(back).all(q => want.land.any(r => on-land(r, q)))
            })
        )
      }
      // A city or a ring whose place the frame leaves out: not named (its name, moved in, would
      // name another place)
      if want.dot and (x < 0pt or x > bw or y < 0pt or y > bh) { continue }
      let k = range(tries.len()).find(clear)
      // A name that may be left out (a country's): only where it is clear
      if k == none and want.at("optional", default: false) { continue }
      if want.at("country", default: none) != none { countries-named.push(want.country) }
      // Never cut by the frame: moved in
      let within((ax, ay)) = (calc.max(1pt, calc.min(ax, bw - 1pt - lw)), calc.max(1pt, calc.min(ay, bh - 1pt - lh)))
      // None clear: the spot where it covers least (another name or a dot far worse than an
      // arrow or a way), the nearer the better; one the frame doesn't cut first (a spot moved
      // in lands on its neighbours: the West's cities stacked on the frame's edge)
      if k == none {
        // (a name or a dot covered far worse than an arrow, a few points further worse still)
        let spots = marks.map(((mx, my)) => (mx - dot, my - dot, 2 * dot, 2 * dot))
        spots += rings-at.map(((mx, my)) => (mx - ring-size, my - ring-size, 2 * ring-size, 2 * ring-size))
        spots += circles-at.filter(q => q != (x, y)).map(((mx, my)) => (mx - circle-size, my - circle-size, 2 * circle-size, 2 * circle-size))
        let cost(j) = {
          let (ax, ay) = within(tries.at(j))
          let here = (ax, ay, lw, lh)
          (20 * (taken + spots).map(o => overlap(here, o)).sum(default: 0) + strokes.map(o => overlap(here, o)).sum(default: 0)
            + 8 * (calc.abs(ax + lw / 2 - x) / 1pt + calc.abs(ay + lh / 2 - y) / 1pt)
            + if own((ax, ay)) { 0 } else { 400 })
        }
        let whole = range(tries.len()).filter(j => inside-frame(tries.at(j)))
        k = (if whole.len() > 0 { whole } else { range(tries.len()) }).sorted(key: cost).first()
      }
      let at = within(tries.at(if k == none { 0 } else { k }))
      taken.push((at.at(0), at.at(1), lw, lh))
      // (a thin line to its place when it stands off it: beyond its near spots, or further
      // than beside its dot)
      let off = k != none and (k >= near or reach(at, (x, y)) > rad + 2 * gap + 1pt)
      placed.push((at, want.body, if off { (x, y) } else { none }, (lw, lh)))
    }
  }
  let tints = (
    mountain: rgb(150, 100, 50, 90), plateau: rgb(190, 150, 90, 80), desert: rgb(235, 200, 110, 130),
    plain: rgb(120, 180, 90, 80), land: rgb(240, 190, 90, 90),
  )
  let water = rgb("#e8f1f8")
  let tint(i) = palette.at(i).lighten(35%)
  // A zone's colours: those the groups leave, the blues and purple first (an orange zone
  // would read as a relief's tint)
  let zone-colours = (1, 3, 2, 4, 0, 5, 6, 7).filter(j => j >= sets.len())
  let zone-ink(i) = palette.at(zone-colours.at(i)).darken(20%)
  let zone-tint(i) = palette.at(zone-colours.at(i)).transparentize(60%)
  let drawn = box(width: bw, height: bh, clip: true, fill: water, {
    for w in seas {
      for points in w.item.r { ring(points, rgb("#b5d2ec"), none) }
    }
    for (code, c) in others {
      for points in c.r { ring(points, luma(228), 0.4pt + luma(160)) }
    }
    for code in shown {
      for points in all.at(code).r { ring(points, white, none) }
    }
    // Each group's countries in its colour, their borders seen
    for (i, g) in sets.enumerate() {
      for code in g.countries {
        for points in all.at(code).r { ring(points, tint(i), 0.4pt + luma(110)) }
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
    // Zones: tinted, their outline dashed (the borders between their parts left out: one
    // area); one spanning cities rounded around them
    for (i, (z, (zas, zts))) in zone-sets.zip(zone-areas.zip(zone-towns)).enumerate() {
      let colour = zone-ink(i)
      let line = (paint: colour, thickness: 1.3pt, dash: "dashed", join: "round")
      let rings = z.countries.map(code => all.at(code).r).join(default: ()) + zas.map(a => region(a).r).join(default: ())
      for points in rings { ring(points, zone-tint(i), none) }
      // (an edge two of its parts share is inside it)
      let key(a, b) = if (a.at(0), a.at(1)) < (b.at(0), b.at(1)) { repr((a, b)) } else { repr((b, a)) }
      let count = (:)
      for points in rings {
        for (a, b) in (..points, points.first()).windows(2) { let k = key(a, b); count.insert(k, count.at(k, default: 0) + 1) }
      }
      for points in rings {
        let run = ()
        for (a, b) in (..points, points.first()).windows(2) {
          if count.at(key(a, b)) == 1 {
            if run.len() == 0 { run.push(page(a)) }
            run.push(page(b))
          } else if run.len() > 0 {
            if run.len() >= 2 { place(curve(stroke: line, curve.move(run.first()), ..run.slice(1).map(curve.line))) }
            run = ()
          }
        }
        if run.len() >= 2 { place(curve(stroke: line, curve.move(run.first()), ..run.slice(1).map(curve.line))) }
      }
      if zts.len() > 0 {
        let outline = rounded-hull(zts.map(c => page((c.x, c.y))), 9pt)
        place(polygon(fill: zone-tint(i), stroke: line, ..outline))
      }
    }
    // The regions flows leave from or go to, in their flow's colour
    for z in zones {
      for p in z.places.filter(p => "rings" in p) {
        for points in p.rings { ring(points, z.colour.lighten(72%), 0.5pt + z.colour.lighten(20%)) }
      }
    }
    for code in shown {
      for points in all.at(code).r { ring(points, none, 0.7pt + black) }
    }
    // Centred on a pole: its polar circle, dashed
    if pole != none {
      let circle-points = thinned(range(181).map(i => (i * 2 * s - 180 * s, sign * 66.56 * s)).map(flat))
      place(curve(stroke: (paint: rgb("#1f5a8f"), thickness: 0.6pt, dash: "dashed"),
        curve.move(circle-points.first()), ..circle-points.slice(1).map(curve.line)))
    }
    // A region asked too small to see at this scale (Hawaii beside the United States): a
    // circle around it
    for (x, y) in circles-at {
      place(dx: x - circle-size, dy: y - circle-size, circle(radius: circle-size, stroke: 1.2pt + rgb("#d9822b")))
    }
    // A grouped country or region too small to see (Malta, Cyprus among Europe's) and apart
    // from its group's others: a circle around it in its group's colour; one beside them
    // shows by their colour (Luxembourg, Lebanon)
    // (a country's main part and those near it, its frame: not its far islands)
    let grouped-parts = sets.enumerate().map(((i, g)) => g.countries.filter(c => c not in g.ruled).map(code => (all.at(code).f, i))).join(default: ())
    grouped-parts += group-areas.map(a => {
      let largest = region(a).r.first()
      ((calc.min(..largest.map(p => p.at(0))), calc.min(..largest.map(p => p.at(1))),
        calc.max(..largest.map(p => p.at(0))), calc.max(..largest.map(p => p.at(1)))), a.group)
    })
    for (n, (b, i)) in grouped-parts.enumerate() {
      let grown = (b.at(0) - s, b.at(1) - s, b.at(2) + s, b.at(3) + s)  // a degree around
      let apart = grouped-parts.enumerate().all(((m, (c, j))) => m == n or j != i or not touches(grown, c))
      if apart and near-frame(b) and calc.max((b.at(2) - b.at(0)) * k * unit, (b.at(3) - b.at(1)) * unit) < 10pt {
        let (x, y) = page(((b.at(0) + b.at(2)) / 2, (b.at(1) + b.at(3)) / 2))
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
      let all-runs = if pole != none { l.item.l.map(p => runs(p.map(flat))).join(default: ()) } else {
        spans.map(d => l.item.l.map(p => runs(moved(p, d)))).join().join(default: ())
      }
      for run in all-runs {
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
      for d in if pole != none { (0,) } else { range(-2, 3).map(j => j * full) } {
        // (centred on a pole, the way as drawn: the clip of the page cuts it)
        let way = if pole != none { curved(t.way, closed: false).map(flat) } else { moved(t.way, d) }
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
    // Proportional circles, the largest under
    for b in bubbles.sorted(key: b => -b.r / 1pt) {
      let (x, y) = b.at
      place(dx: x - b.r, dy: y - b.r, circle(radius: b.r, fill: rgb(214, 47, 47, 70), stroke: 0.8pt + rgb("#b52020")))
    }
    for (x, y) in rings-at {
      place(dx: x - ring-size, dy: y - ring-size, circle(radius: ring-size, fill: rgb("#b5d2ec"), stroke: 1.2pt + rgb("#1f5a8f")))
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
  if sets.len() + zone-sets.len() + trips.len() + named-kinds.len() + values.len() == 0 { drawn } else {
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
    keys += zone-sets.enumerate().map(((i, z)) => key(box(width: 10pt, height: 7pt, fill: zone-tint(i),
      stroke: (paint: zone-ink(i), thickness: 1pt, dash: "dashed")), z.name))
    // The circles: the largest value's and a round one below it, each its number
    if values.len() > 0 {
      let written(v) = {
        let t = if type(v) == float and v == calc.round(v) { str(int(v)) } else { str(v) }
        if text.lang in ("fr", "de", "es", "it", "pt") { t.replace(".", ",") } else { t }
      }
      let small = round-below(most-valued / 4)
      let sample(v) = {
        let r = bubble-r(v)
        box(grid(columns: 2, column-gutter: 3pt, align: horizon,
          circle(radius: r, fill: rgb(214, 47, 47, 70), stroke: 0.8pt + rgb("#b52020")), text(8pt, written(v))))
      }
      keys += (box(inset: (right: 5pt), grid(columns: 3, column-gutter: 6pt, align: horizon, sample(most-valued),
        sample(small), if value-unit != none { text(8pt, value-unit) })),)
    }
    stack(spacing: 5pt, drawn, block(width: bw, {
      set text(8pt)
      set par(leading: 0.6em)
      keys.join([ ])
    }))
  }
}

// A country with its far parts or lands (its overseas departments, its archipelagos across
// the sea, Greenland beside Denmark): the country's map, each far one in an inset under it,
// named, at its own scale (an island seen, half a degree around it at least), its cities in it; `insets: false` draws them where they are (the
// world). Else, and with routes, flows, groups, a year or a pole, one map
#let map(countries: (), cities: (), regions: (), rivers: (), reliefs: (), waters: (), groups: (),
  routes: (), flows: (), year: none, pole: none, labels: true, insets: auto, width: 8cm, height: 7cm) = {
  let countries = if type(countries) == str { (countries,) } else { countries }
  let regions = if type(regions) == str { (regions,) } else { regions }
  let cities = if type(cities) == str { (cities,) } else { cities }
  let one = one-map.with(rivers: rivers, reliefs: reliefs, waters: waters, groups: groups, routes: routes,
    flows: flows, year: year, pole: pole, labels: labels)
  let whole() = one(countries: countries, cities: cities, regions: regions, width: width, height: height)
  if insets == false or year != none or pole != none or routes.len() + flows.len() + groups.len() > 0 { return whole() }
  let held = countries.map(n => country-code(n)).filter(c => c != none)
  // Far: a country's part ("t"), or a land it holds ("o") whose frame lies farther than 3° from
  // the country's (the Faroes, not Jersey), the country shown too; asked in countries, or in
  // regions (Guadeloupe among France's)
  let far-from(code) = {
    let c = atlas.countries.at(code)
    let of = c.at("o", default: none)
    if of == none or of not in held { return false }
    if "t" in c { return true }
    let (a, b) = (c.f, atlas.countries.at(of).f)
    calc.max(a.at(0) - b.at(2), b.at(0) - a.at(2), a.at(1) - b.at(3), b.at(1) - a.at(3)) > 3 * atlas.scale
  }
  // (a region of a country shown stays one, coloured among the others: Hawaii among the states)
  let asked = countries + regions.filter(n => type(n) == str and region-of(n, held) == none and country-code(n) != none and "t" in atlas.countries.at(country-code(n)))
  let far = asked.filter(n => type(n) == str and country-code(n) != none and far-from(country-code(n)))
  if far.len() == 0 { return whole() }
  // Each city in the inset whose land holds it (a degree around), else the main map's
  let home(name) = {
    let i = city-index(name, held)
    if i == none { return none }
    let c = atlas.cities.at(i)
    far.find(n => {
      let b = atlas.countries.at(country-code(n)).b
      c.x >= b.at(0) - atlas.scale and c.x <= b.at(2) + atlas.scale and c.y >= b.at(1) - atlas.scale and c.y <= b.at(3) + atlas.scale
    })
  }
  let homes = cities.map(home)
  let main = one(countries: countries.filter(n => n not in far), regions: regions.filter(n => n not in far),
    cities: cities.zip(homes).filter(((_, h)) => h == none).map(((c, _)) => c), width: width, height: height)
  let columns = calc.min(far.len(), 3)
  let gutter = 4pt
  let iw = (width - gutter * (columns - 1)) / columns
  let insets = far.map(n => block(stroke: 0.5pt + luma(110), inset: 2pt, breakable: false, stack(spacing: 2pt,
    text(7.5pt, weight: "bold", n),
    one(countries: (n,), cities: cities.zip(homes).filter(((_, h)) => h == n).map(((c, _)) => c),
      width: iw - 4pt, height: (iw - 4pt) * 0.75, least: 0.5),
  )))
  stack(spacing: 6pt, main, grid(columns: columns, gutter: gutter, ..insets))
}
