You draw a statistics chart in Typst with the chart function given (cetz): its bars' heights and its sectors' angles are computed from the counts. Answer the Typst only, exactly so:
{example}
- `kind`: `"bars"` for a bar chart (diagramme en bâtons), `"pie"` for a pie chart (diagramme circulaire), `"semi"` for a half pie (diagramme semi-circulaire);
- `values`: each value's label and its count, `("Chat", 12)`, as the description gives them, in its order; never an angle, a percentage or a height of your own: the chart computes them;
- `written`: the labels whose count is written on the chart, or `"all"`; none unless the description says them written (a card asking a count, a frequency or an angle must not show it); `degrees: true` writes a sector's angle with its count, only when the description asks for it;
- `axis`: the bars' axis title as the description writes it (`axis: "Effectif"`); `step` only when it gives the graduation (`step: 5`), else every unit up to 12, then 2, 5, 10…
