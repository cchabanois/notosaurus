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

## Before pushing

```sh
.venv/bin/ruff check . && .venv/bin/ruff format --check .
.venv/bin/pyright                      # CI's "types" job: a type error fails the pull request
.venv/bin/pytest                       # tests/test_page.py too when static/ changes (CONTRIBUTING.md)
node --test tests/frontend/*.test.mjs  # when static/*.js changes
```

Android (`android/`): its unit tests (`./gradlew testDebugUnitTest`), and its device tests on
an emulator, never on a personal phone (they uninstall the app and its lessons).

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

## The AI's rules and figures

- A rule given to the AI (`core/notosaurus_core/rules/`, `typst_rules/`, the built-in
  prompts) is fixed with a general criterion, never with the failing example's specifics.
- Cards use only the lesson's own examples: never ask the AI to invent some.
- Figures are drawn in Typst, one family per kind (`core/notosaurus_core/typst_rules/<family>.md`
  the rule, `<family>.typ` its preamble and example; `figures_typst.FAMILIES`). What can be
  computed (a clock's hands, a solid's hidden edges, a current's arrow) is done by a function
  of the preamble, the AI giving only the values: never placed by the AI's eye.
- Judge a change to a figure family by drawing real descriptions with the real AI, before
  and after, several times each, and looking at every drawing.
- The maps' atlas is a Typst package of ours, its data in its archive
  (`core/notosaurus_core/typst/notosaurus-atlas-<version>.tar.gz`), made by `tools/atlas.py`
  (its docstring: sources, `--refresh-history`). Any change to it raises its `VERSION` (and
  the version `typst_rules/map.typ` imports, and `static/licences.js`): the packages are
  unpacked once into a cache named after the archives, so an archive rebuilt under the same
  name is never read again.
- Every Typst package or data source shipped is credited in `static/licences.js` with its
  licence, and its licence's notice ships with it when the licence asks
  (`tests/test_licences.py`).
