# Notosaurus: notes for coding agents

What a coding agent most often gets wrong here. The rest is in
[CONTRIBUTING.md](CONTRIBUTING.md) (setup, tests, architecture, languages, releases) and
[android/README.md](android/README.md) (the Android app).

## How to work

- Never commit on `main`: a branch and a pull request per subject. Several agent sessions may
  work on this repository at once: work in a git worktree of your own
  (`.claude/worktrees/<name>`, from `origin/main`), stage files by name (never `git add -A`),
  never a bare `git stash`.
- Before pushing to a pull request or offering to merge it, check that it is still open
  (`gh pr view <n> --json state`): it may have been merged meanwhile. Merged: a new branch
  from `origin/main`, a new pull request.
- A pull request is merged only once every workflow run of its head commit has completed
  with success, and only when the maintainer says so.
- Commit only what the change needs. Folders that are local or private stay out of git
  (`data/`, `.env`, and any folder a maintainer keeps for their own notes).
- Stacked pull requests: merging the parent deletes its branch and closes the child; retarget
  the child to `main` first. Once a pull request is merged, remove its worktree and its local
  branch.

## Before pushing

```sh
.venv/bin/ruff check . && .venv/bin/ruff format --check .
.venv/bin/pyright                      # CI's "types" job: a type error fails the pull request
.venv/bin/pytest                       # tests/page/ too when static/ changes (CONTRIBUTING.md)
node --test tests/frontend/*.test.mjs  # when static/*.js changes
```

`tests/page/` is skipped, without failing, when Playwright isn't installed: check
that it ran.

Android (`android/`): its unit tests (`./gradlew testDebugUnitTest`), and its device tests on
an emulator, never on a personal phone (they uninstall the app and its lessons). Use an
emulator of your own (`ANDROID_SERIAL`), never one another session drives, and timeouts near
a run's normal duration (about 180 s for the device tests) so a hang fails fast.

Testing with Anki on the computer: Anki runs once per user. `anki -b <dir>` starts no second
instance while another Anki is open ("Already running"), and the add-on answering on port
8000 may be another session's. Test in an Anki base of your own, never the maintainer's
profiles; check `GET /api/anki/status` (its profile) before sending, and give your add-on
another `port` in its config when 8000 is taken. `NOTOSAURUS_LLM=fake` (or the settings'
`fake` provider) makes lessons at no cost.

## Conventions

- Code, comments, file names and commit messages in English. Every text the user sees is in
  `static/i18n/<lang>.json` (fr, en, de, es, it, pt), never in the code; errors are codes.
- French addresses the parent as "vous" (interface, documentation); the built-in prompts the
  AI is given keep "tu".
- Every fix ships a test that fails without it (checked by undoing the fix once).
- The changelog goes in the pull request's description, under `## Changelog`
  (`### Added`, `### Changed`, `### Fixed`), never in `CHANGELOG.md`; a pull request with
  nothing worth telling is labelled `no changelog` (CONTRIBUTING.md, Pull requests).
- `requirements.txt` is compiled for every system: `uv pip compile requirements.in --universal
  --python-version 3.13 -o requirements.txt`. Dependabot's own compile drops the platform
  markers (`test_compiled_for_every_system` fails): redo its pull request that way.
- `static/` runs in Android's WebView from version 124 (Chrome 124): no JavaScript, CSS or
  web API newer than that.
- What the app meets was often made by an older version: notes and note types sent by 1.0.0
  (its front/back notes have no `Id`), the computer's page served by an older add-on, an app
  already released talking to today's relay (its API only grows within `/v1`:
  `tests/test_relay_compat.py`). A change to how notes are found, keyed or typed is tried on
  notes as 1.0.0 made them (`git archive v1.0.0`, its add-on in a test Anki), not only on
  today's.

## The AI's rules and figures

- A rule given to the AI (`core/notosaurus_core/rules/`, `typst_rules/`, the built-in
  prompts) is fixed with a general criterion, never with the failing example's specifics.
- Cards use only the lesson's own examples: never ask the AI to invent some.
- Figures are drawn in Typst, one family per kind (`core/notosaurus_core/typst_rules/<family>.md`
  the rule, `<family>.typ` its preamble and example; `figures_typst.FAMILIES`). What can be
  computed (a clock's hands, a solid's hidden edges, a current's arrow) is done by a function
  of the preamble, the AI giving only the values: never placed by the AI's eye.
- A new family: its `<family>.md` and `<family>.typ` (the example after the `EXAMPLE` marker,
  compiled by the tests), its name in `FAMILIES` and `FigureKind`, its kind described in
  `typst_rules/kinds.md` (what picks it, what doesn't), its packages credited.
- Judge a change to a figure family by drawing real descriptions with the real AI, before
  and after, several times each, and looking at every drawing: the `figure-bench` skill
  (`tools/bench_figures.py`).
- The maps' atlas is a Typst package of ours, its data in its archive
  (`core/notosaurus_core/typst/notosaurus-atlas-<version>.tar.gz`), made by `tools/atlas.py`
  (its docstring: sources, `--refresh-history`). Any change to it raises its `VERSION` (and
  the version `typst_rules/map.typ` imports, and `static/licences.js`): the packages are
  unpacked once into a cache named after the archives, so an archive rebuilt under the same
  name is never read again.
- Every Typst package or data source shipped is credited in `static/licences.js` with its
  licence, and its licence's notice ships with it when the licence asks
  (`tests/test_licences.py`).
