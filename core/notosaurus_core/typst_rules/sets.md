You draw a set (Venn) diagram in Typst with cetz-venn 0.2 (two or three sets), or sets inside one another. Answer the Typst only, exactly so:
{example}
- `cetz-venn.venn2(...)` or `cetz-venn.venn3(...)`; its parts: `a`, `b`, `c`, `ab`, `ac`, `bc`, `abc`, `not-ab` (outside them, in the frame), `not-abc`: `ab-fill: hatch` (hatched, given), `a-fill: luma(225)` (shaded), never drawn by hand;
- a part's label at its anchor: `content("v.ab", [$x$])`, the sets' names at `"v.a"`, `"v.b"`.
- sets inside one another (ℕ ⊂ ℤ ⊂ ℝ, a classification's groups each inside the next), with or without their elements: `#nested-sets(($NN$, ($3$,)), ($ZZ$, ($-5$,)), ($RR$, ($sqrt(2)$, $pi$)))` alone, no canvas (from the smallest to the largest, each its name and its own elements, those of no smaller one, as the description writes them; `()` none), every ring and element placed by it, never drawn by hand.
