You draw a set (Venn) diagram in Typst with cetz-venn 0.2 (two or three sets). Answer the Typst only, exactly so:
{example}
- `cetz-venn.venn2(...)` or `cetz-venn.venn3(...)`; its parts: `a`, `b`, `c`, `ab`, `ac`, `bc`, `abc`, `not-ab` (outside them, in the frame), `not-abc`: `ab-fill: hatch` (hatched, given), `a-fill: luma(225)` (shaded), never drawn by hand;
- a part's label at its anchor: `content("v.ab", [$x$])`, the sets' names at `"v.a"`, `"v.b"`.
