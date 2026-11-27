#!/usr/bin/env bash
# The changelog entries of a merged pull request (the squash commit $1's message: its
# "## Changelog") put under Unreleased in CHANGELOG.md on main AS IT IS NOW, committed and
# pushed (the Changelog workflow, .github/workflows/changelog.yml). Main moved meanwhile
# (another merge, or its changelog commit): fetched again and done again, 3 times at most.
#
# main as it is now, not the checkout's origin/main: actions/checkout sets that to the commit
# that ran the workflow, behind main once another merge landed (#821's entry was refused so,
# twice: "rejected (fetch first)", then "non-fast-forward" on its rerun, 2026-11-27).
#
#   tools/changelog_push.sh <merged commit>      (REMOTE: the remote, default origin; PYTHON: python)
set -euo pipefail

sha=${1:?usage: tools/changelog_push.sh <merged commit>}
remote=${REMOTE:-origin}
message=$(git log -1 --format=%B "$sha")
subject=$(git log -1 --format=%s "$sha")

for attempt in 1 2 3; do
  git fetch -q "$remote" main
  git checkout -q --detach FETCH_HEAD
  printf '%s\n' "$message" | "${PYTHON:-python}" tools/changelog_add.py
  if git diff --quiet -- CHANGELOG.md; then
    echo "No changelog entry to add."
    exit 0
  fi
  git add CHANGELOG.md
  git commit -q -m "📝 Changelog: $subject" -m "[skip ci]"
  if git push -q "$remote" HEAD:main; then
    exit 0
  fi
  echo "main moved meanwhile: its entries added again on it ($attempt)" >&2
  sleep $((attempt * 2))
done
echo "main kept moving: not pushed" >&2
exit 1
