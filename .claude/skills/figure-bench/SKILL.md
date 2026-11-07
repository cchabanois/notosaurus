---
name: figure-bench
description: Measure AI-drawn figures with the real AI, before and after a change to a figure family (a Typst rule, a preamble, a function), or over a school syllabus's figures. Use when changing anything in core/notosaurus_core/typst_rules/ or how figures are made, or when asked how well figures come out for a subject.
---

# Figure bench

A change to how figures are drawn is judged on real drawings, not on the rule's example:
the AI reads a rule its own way. `tools/bench_figures.py` draws each description several
times, judges each drawing by code (it renders, fills its picture, no label hidden) and, when
`BENCH_JUDGE_PROJECT` is set, by the AI looking at it, then writes a sheet of every drawing.

## 1. The cases

A JSON list of `{"id": "v10", "description": "…"}`, the descriptions written as the cards'
AI writes them (a sentence saying what to draw, its labels and values): the figures that
went wrong, or a syllabus's figures (one or two per chapter, the kinds it calls for). Ids
short and stable: the runs are compared by id. A case may also say its `"kind"` (a family,
as the cards' AI gives it: not asked again; the same description under two kinds compares
two families) and its `"front"` (`"question → answer"`, the card the figure goes on the
front of: nothing on it may give the answer away). Both with `--local` only: the relay's
`/v1/figure` takes a description alone. Keep the file outside git (your scratch
folder, or the maintainer's private bench folder), and nothing from a user's lesson in it.

## 2. Before

```sh
.venv/bin/python tools/bench_figures.py --bench <scratch> --cases <cases.json> --local --times 3
```

- `--local`: drawn in this checkout with the AI of the app's settings (`--app <checkout>`
  for the one holding `data/` and `.env`; a worktree has neither), so a rule is judged
  before it is deployed. Without it, drawn by the test relay: what the apps get today, that
  is the core version the relay pins, often several pull requests behind `main`.
- `--times 3` at least: one drawing says little; a family is right when every drawing is.
- `--local` spends real credits on the app's keys: cases × times calls, and more for the
  drawings drawn again; keep the cases to what the change touches.
- Several cases run at once (`--jobs`); keep the default unless the provider allows more.

## 3. Look at every drawing

Open the run's `sheet.html` and look at each figure, not only the verdicts: code doesn't see
a wrong value, a label on the wrong thing, a crossing arrow, text too small to read. Note
what is wrong and how often (2 of 3). Then find the cause in the run's `<case>-<n>.typ`
(what the AI wrote): the rule misread, a missing function, or the preamble.

## 4. The change

- The rule fixed with a general criterion, never the failing case's words or values.
- What can be computed (positions, angles, hidden edges) done by a function of the
  preamble, the AI giving values only.
- A change that `source()` could make (a spelling the AI keeps writing) normalised there,
  with a test.

## 5. After

- A rule or a family changed: the same command again; the script prints the run before.
- Only a preamble changed (a font, a size, a function's drawing): no AI needed, the same
  drawings compiled again with this checkout's preambles:

  ```sh
  .venv/bin/python tools/bench_figures.py --bench <scratch> --recompile <scratch>/runs/<run>
  ```

Compare case by case, drawing by drawing, and check nothing that was right went wrong (the
cases of other families too when a shared piece changed: `figures_typst.source`, `COMMON`,
`kinds.md`).

## 6. Report

Results as a page the maintainer can look at, published (a claude.ai artifact when you can
publish one) rather than a local `sheet.html`: each case with its description, its drawings
before and after, the counts (`24/26`), what was fixed and what still fails. Update it after
each fix. In the pull request's description: the counts before and after, in a line or two.

## When the problem is upstream

The bench starts from a description. What it doesn't see is decided before: which cards get
a figure, what their description says (one description shared by two cards, the counts the
question asks for written on it), a photo where a map was needed, front or back. When the
drawings are right but the cards are not, judge whole lessons instead, in a test Anki of
your own (CLAUDE.md): `POST /api/extract` with the page, `PUT /api/lessons/<id>`, `POST
/api/lessons/<id>/pictures`; the same pages before and after, plus a page or two the change
should leave alone.
