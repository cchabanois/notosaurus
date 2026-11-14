// The map of the figures' "map" family (typst_rules/map.md): countries, cities, regions,
// rivers, reliefs and waters from the atlas (made by tools/atlas.py from Natural Earth),
// never placed by the AI. A place is found by any of its names (the page's languages), a
// country by its three-letter code too; one the atlas doesn't have stops the figure, said
// (never placed by guess). The frame holds the countries, regions, groups and cities asked
// (else the rivers, reliefs and waters); what is around drawn grey, cut to it.

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
#let find-city(name, shown) = {
  let key = fold(name)
  let found = atlas.cities.filter(c => key in c.k)
  if found.len() == 0 {
    panic("no city called \"" + name + "\" in the atlas (a country's capital, its largest cities, the places of history lessons): leave it out")
  }
  let theirs = found.filter(c => c.c in shown)
  (if theirs.len() > 0 { theirs } else { found }).sorted(key: c => (-c.at("h", default: 0), -c.p)).first()
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

// countries: shown white and framed (names or codes); cities: a red dot each; regions: of
// the countries shown, coloured, their country's others outlined; rivers: blue lines;
// reliefs (mountains, deserts, plains, peninsulas, islands) and waters (oceans, seas, gulfs,
// lakes): coloured; groups: countries or regions (of a country shown or grouped) coloured by
// group, one colour each, a legend under the map, all framed; each named when labels; width,
// height: the most the map takes
#let map(countries: (), cities: (), regions: (), rivers: (), reliefs: (), waters: (), groups: (),
  labels: true, width: 8cm, height: 7cm) = context {
  let shown = countries.map(find-country)
  let sets = read-groups(groups)
  let grouped = sets.map(g => g.countries).join(default: ())
  // The countries the map is about: those shown and those grouped
  let about = shown + grouped.filter(code => code not in shown)
  let towns = cities.map(name => (name: name, city: find-city(name, about)))
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
  if boxes.len() == 0 { boxes = lines.map(l => l.item.b) + lands.map(l => l.item.b) }
  if boxes.len() == 0 {
    let small = seas.filter(w => calc.max(w.item.b.at(2) - w.item.b.at(0), w.item.b.at(3) - w.item.b.at(1)) <= 30 * s)
    boxes = (if small.len() > 0 { small } else { seas }).map(w => w.item.b)
  }
  if boxes.len() == 0 { panic("a map shows at least one country, city, region, group, river, relief or water") }
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
  let (x0, x1) = (calc.min(..xs) * k, calc.max(..xs) * k)
  let (y0, y1) = (calc.min(..ys), calc.max(..ys))
  // Room around (a tenth, a few degrees at least: a city alone shows its region)
  let least = 4 * s
  let (cx, cy) = ((x0 + x1) / 2, (y0 + y1) / 2)
  let (w, h) = (calc.max(x1 - x0, least) * 1.2, calc.max(y1 - y0, least) * 1.2)
  // Neither a strip nor a band: a long country (Chile) shows its neighbours, its names fit
  let (w, h) = (calc.max(w, h * 0.75), calc.max(h, w * 0.55))
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
  let ring(points, fill, stroke) = {
    let kept = thinned(clipped(points))
    if kept.len() >= 3 { place(polygon(fill: fill, stroke: stroke, ..kept)) }
  }
  let near-frame(b) = touches(b, (fx0, fy0, fx1, fy1))
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
    let found = item.at.filter(inside)
    if found.len() == 0 { none } else { found.sorted(key: ((x, y)) => calc.abs(x - (left + right) / 2) / (right - left) + calc.abs(y - cy) / h).first() }
  }
  let river-place(item) = {
    let pts = item.l.map(runs).flatten().chunks(2).filter(inside)
    if pts.len() == 0 { none } else { pts.at(calc.div-euclid(pts.len(), 2)) }
  }
  // Labels: cities beside their dot (right, left, above, below); the others on their place
  // (on it, above, below, right, left): the first that stays in the frame and on no other
  // label or dot
  let dot = 2.4pt
  let gap = 2.5pt
  let marks = towns.map(t => (px(t.city.x), py(t.city.y)))
  let wanted = ()
  for (i, t) in towns.enumerate() {
    wanted.push((at: marks.at(i), dot: true, body: text(8pt, weight: if t.city.cap { "bold" } else { "regular" }, t.name)))
  }
  let named(items, find, style) = items.map(it => (it, find(it))).filter(((_, p)) => p != none).map(((it, p)) => (
    at: (px(p.at(0)), py(p.at(1))), dot: false, body: style(it.name),
  ))
  wanted += named(areas, a => place-of(region(a)), n => text(7.5pt, fill: luma(40), n))
  wanted += named(lands, l => place-of(l.item), n => text(8pt, style: "italic", fill: rgb("#6b4a1f"), n))
  wanted += named(seas, w => place-of(w.item), n => text(8pt, style: "italic", fill: rgb("#1f5a8f"), n))
  wanted += named(lines, l => river-place(l.item), n => text(7.5pt, style: "italic", fill: rgb("#1f5a8f"), n))
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
      for run in l.item.l.map(runs).join(default: ()) {
        let kept = thinned(run)
        if kept.len() >= 2 {
          place(curve(stroke: (paint: rgb("#3b7dc4"), thickness: 1.1pt, join: "round", cap: "round"),
            curve.move(kept.first()), ..kept.slice(1).map(curve.line)))
        }
      }
    }
    for (x, y) in marks {
      place(dx: x - dot, dy: y - dot, circle(radius: dot, fill: rgb("#d62f2f"), stroke: 0.6pt + white))
    }
    for ((ax, ay), body) in placed {
      place(dx: ax, dy: ay, box(fill: white.transparentize(30%), inset: 0pt, body))
    }
  })
  if sets.len() == 0 { drawn } else {
    // The legend under the map: each group's colour and its name, in their order
    let key(i, g) = box(inset: (right: 5pt), stack(dir: ltr, spacing: 3pt,
      box(width: 10pt, height: 7pt, fill: tint(i), stroke: 0.5pt + luma(110)), text(8pt, g.name)))
    stack(spacing: 5pt, drawn, block(width: bw, {
      set text(8pt)
      set par(leading: 0.6em)
      sets.enumerate().map(((i, g)) => key(i, g)).join([ ])
    }))
  }
}
