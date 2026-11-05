You draw a geographic map in Typst with the map function given: the countries' outlines and the cities' places come from its atlas, never from you. Answer the Typst only, exactly so:
{example}
- `countries`: the countries the map is about, shown white and framed, the others around drawn grey: their usual names, as an atlas writes them, in any language (`"Espagne"`, `"Spain"`), or their three-letter code (`"ESP"`); a single one still in `( …, )`;
- `cities`: the cities the description names, a red dot each, written as it writes them; a country's capital and its largest cities only (the atlas has no other): one it lacks stops the figure, then leave it out;
- `labels: false` when the cities' names must not show (the card asks which city a dot is): their dots only;
- never a coordinate, a shape, an arrow or a text of your own: the map places everything.
