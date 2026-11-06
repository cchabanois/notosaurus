// The map of the figures' "map" family (typst_rules/map.md): countries and cities from
// the atlas (atlas.json, Natural Earth, made by tools/atlas.py), never placed by the AI.
// A country or a city is found by any of its names (the page's languages) or a country by
// its three-letter code; one the atlas doesn't have stops the figure, said (never placed by
// guess). The frame holds what is asked; the countries around it drawn grey.

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

// A city: among those of the countries shown first, else the most populated of that name
#let find-city(name, shown) = {
  let key = fold(name)
  let found = atlas.cities.filter(c => key in c.k)
  if found.len() == 0 {
    panic("no city called \"" + name + "\" in the atlas (a country's capital and its largest cities): leave it out")
  }
  let theirs = found.filter(c => c.c in shown)
  (if theirs.len() > 0 { theirs } else { found }).sorted(key: c => -c.p).first()
}

// countries: shown white and framed (names or codes); cities: a red dot each, named when
// labels; width, height: the most the map takes
#let map(countries: (), cities: (), labels: true, width: 8cm, height: 7cm) = context {
  let shown = countries.map(find-country)
  let towns = cities.map(name => (name: name, city: find-city(name, shown)))
  let xs = ()
  let ys = ()
  for code in shown {
    let f = atlas.countries.at(code).f
    xs += (f.at(0), f.at(2))
    ys += (f.at(1), f.at(3))
  }
  for t in towns {
    xs.push(t.city.x)
    ys.push(t.city.y)
  }
  if xs.len() == 0 { panic("a map shows at least one country or one city") }
  let s = atlas.scale
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
  let near(b) = b.at(2) >= left and b.at(0) <= right and b.at(3) >= cy - h / 2 and b.at(1) <= cy + h / 2
  // A ring cut to the frame, a little beyond (Sutherland-Hodgman): what isn't seen isn't
  // drawn, the figure stays light
  let (fx0, fx1) = (left - (right - left) * 0.05, right + (right - left) * 0.05)
  let (fy0, fy1) = (cy - h * 0.55, cy + h * 0.55)
  let cut(points, inside, cross) = {
    let out = ()
    for (i, b) in points.enumerate() {
      let a = points.at(i - 1)
      if inside(b) {
        if not inside(a) { out.push(cross(a, b)) }
        out.push(b)
      } else if inside(a) { out.push(cross(a, b)) }
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
  // Its points as drawn, one less than a point from the last kept skipped: a small
  // scale draws no more than the eye sees
  let ring(points, fill, stroke) = {
    let kept = ()
    for q in clipped(points) {
      let (x, y) = (px(q.at(0)), py(q.at(1)))
      if kept.len() == 0 or calc.abs((x - kept.last().at(0)) / 1pt) + calc.abs((y - kept.last().at(1)) / 1pt) >= 1 {
        kept.push((x, y))
      }
    }
    if kept.len() >= 3 { place(polygon(fill: fill, stroke: stroke, ..kept)) }
  }
  let others = atlas.countries.pairs().filter(((code, c)) => code not in shown and near(c.b))
  // Labels: beside their dot, right, left, above or below, the first that stays in the
  // frame and on no other label or dot
  let dot = 2.4pt
  let gap = 2.5pt
  let placed = ()
  let marks = towns.map(t => (px(t.city.x), py(t.city.y)))
  let boxes = ()
  if labels {
    for (i, t) in towns.enumerate() {
      let (x, y) = marks.at(i)
      let body = text(8pt, weight: if t.city.cap { "bold" } else { "regular" }, t.name)
      let size = measure(body)
      let (lw, lh) = (size.width, size.height)
      let tries = (
        (x + dot + gap, y - lh / 2),
        (x - dot - gap - lw, y - lh / 2),
        (x - lw / 2, y - dot - gap - lh),
        (x - lw / 2, y + dot + gap),
      )
      let clear((ax, ay)) = (
        ax >= 1pt and ay >= 1pt and ax + lw <= bw - 1pt and ay + lh <= bh - 1pt
          and boxes.all(((bx, by, bw2, bh2)) => ax + lw <= bx or bx + bw2 <= ax or ay + lh <= by or by + bh2 <= ay)
          and marks.enumerate().all(((j, (mx, my))) => j == i or mx + dot <= ax or ax + lw <= mx - dot or my + dot <= ay or ay + lh <= my - dot)
      )
      let at = tries.find(clear)
      if at == none { at = tries.first() }
      boxes.push((at.at(0), at.at(1), lw, lh))
      placed.push((at, body))
    }
  }
  box(width: bw, height: bh, clip: true, fill: rgb("#e8f1f8"), {
    for (code, c) in others {
      for points in c.r { ring(points, luma(228), 0.4pt + luma(160)) }
    }
    for code in shown {
      for points in atlas.countries.at(code).r { ring(points, white, 0.7pt + black) }
    }
    for (x, y) in marks {
      place(dx: x - dot, dy: y - dot, circle(radius: dot, fill: rgb("#d62f2f"), stroke: 0.6pt + white))
    }
    for ((ax, ay), body) in placed {
      place(dx: ax, dy: ay, box(fill: white.transparentize(30%), inset: 0pt, body))
    }
  })
}
