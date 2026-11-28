#set page(width: auto, height: auto, margin: 6pt)
#import "common.typ": *
#import "@preview/notosaurus-atlas:0.19.0": map as atlas-map
// The atlas's map, drawing its icons with icon() (common.typ)
#let map = atlas-map.with(icon: icon)
// ---- What the AI writes, from here (the rule's example: everything above is given)
#map(countries: ("France",), cities: ("Paris", "Lyon", "Marseille", "Bordeaux"))
