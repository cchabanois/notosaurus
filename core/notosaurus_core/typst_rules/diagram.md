You draw a diagram of boxes and arrows (a flowchart, a cycle, a chain, a tree) in Typst with fletcher 0.5. Answer the Typst only, exactly so:
{example}
- `node((column, row), [text])` on a grid of cells; `edge("-|>")` from the node before to the node after; `edge((0, 1), (0, 0), "-|>", [label])` between two cells; `"<|-|>"` both ways, `"--"` a plain line, `bend: 30deg` curved;
- a node's shape: `shape: circle`, `corner-radius: 4pt`; texts as the description gives them.
