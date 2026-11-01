"""Put a merged pull request's changelog entries under Unreleased in CHANGELOG.md.

A pull request says what it changes under a `## Changelog` heading of its description, in
Keep a Changelog's subsections, one bullet per entry (a bullet may run over several lines):

    ## Changelog
    ### Added
    - 💾 **Back up or move my lessons** (the settings): every lesson in one file…
    ### Fixed
    - A licence key refused is no longer kept.

Squash-merged, that description is the commit's message on main: the Changelog workflow
(.github/workflows/changelog.yml) runs this on it and pushes CHANGELOG.md. No pull request
touches CHANGELOG.md itself, so two of them never conflict on it, and none is rebased, nor
tested again, for a line of changelog. The release pull request still renames Unreleased.

Usage:
  python tools/changelog_add.py < message         the entries added under Unreleased, each said
  python tools/changelog_add.py --check < body    parsed only: fails when there is no entry
"""

import re
import sys
from pathlib import Path

CHANGELOG = Path(__file__).resolve().parent.parent / "CHANGELOG.md"

# Keep a Changelog's subsections, in its order (a missing one is created at its place)
SECTIONS = ("Added", "Changed", "Deprecated", "Removed", "Fixed", "Security")

_CHANGELOG_HEADING = re.compile(r"^##\s+Changelog\s*$", re.M | re.I)
_HEADING = re.compile(r"^(#{1,3})\s+(.*?)\s*$")
_BULLET = re.compile(r"^[-*]\s+(.*)$")


def entries(message: str) -> list[tuple[str, str]]:
    """The (section, text) entries of a pull request's description (or of the squash commit's
    message, the same text): those under its "## Changelog" heading, each bullet one line."""
    heading = _CHANGELOG_HEADING.search(message)
    if heading is None:
        return []
    found: list[tuple[str, str]] = []
    section = None
    for line in message[heading.end() :].splitlines():
        title = _HEADING.match(line)
        if title and len(title.group(1)) <= 2:
            break  # the description's next part
        if title:
            name = title.group(2).strip("*_ ").capitalize()
            section = name if name in SECTIONS else None
            continue
        bullet = _BULLET.match(line)
        if bullet and section:
            found.append((section, bullet.group(1).strip()))
        elif line.strip() and found and section and not line.startswith("#"):
            kind, text = found[-1]
            found[-1] = (kind, f"{text} {line.strip()}")  # a bullet wrapped over several lines
    return found


def added(text: str, new: list[tuple[str, str]]) -> tuple[str, list[tuple[str, str]]]:
    """The changelog with `new` under Unreleased, each entry first in its subsection (the
    newest on top, as the file is kept), a missing subsection made at its place; an entry
    already there is not added twice. Returns the text and what was added."""
    start = re.search(r"^## \[Unreleased\][^\n]*\n", text, re.M)
    if start is None:
        raise SystemExit("CHANGELOG.md has no '## [Unreleased]' section")
    end = re.compile(r"^## |^\[[^\]]+\]: ", re.M).search(text, start.end())
    stop = end.start() if end else len(text)
    block = text[start.end() : stop]
    done = [(section, entry) for section, entry in new if f"- {entry}" not in block]
    for section in SECTIONS:
        lines = [entry for kind, entry in done if kind == section]
        if lines:
            block = _with(block, section, lines)
    return text[: start.end()] + block + text[stop:], done


def _with(block: str, section: str, lines: list[str]) -> str:
    """The Unreleased block with these entries first under `### section`, in their order."""
    bullets = "".join(f"- {line}\n" for line in lines)
    heading = re.search(rf"^### {section}[^\n]*\n", block, re.M)
    if heading:
        return block[: heading.end()] + "\n" + bullets + block[heading.end() :].lstrip("\n")
    # Not there yet: before the first subsection that comes after it in SECTIONS, else at the end
    later = SECTIONS[SECTIONS.index(section) + 1 :]
    following = re.search(rf"^### (?:{'|'.join(later)})[^\n]*\n", block, re.M) if later else None
    at = following.start() if following else len(block)
    before = block[:at].rstrip("\n")
    after = block[at:].lstrip("\n")
    made = f"### {section}\n\n{bullets}\n"  # a blank line before what follows, the next version's heading too
    return (f"{before}\n\n" if before else "\n") + made + after


def main(argv: list[str]) -> None:
    message = sys.stdin.read()
    found = entries(message)
    if "--check" in argv:
        if not found:
            raise SystemExit(
                "No changelog entry: say what changes under a '## Changelog' heading of the pull request's"
                " description (### Added, ### Fixed…), or label it 'no changelog'."
            )
        for section, entry in found:
            print(f"{section}: {entry}")
        return
    if not found:
        print("No '## Changelog' in the message: nothing to add.")
        return
    text, done = added(CHANGELOG.read_text(encoding="utf-8"), found)
    CHANGELOG.write_text(text, encoding="utf-8")
    for section, entry in done:
        print(f"Added under {section}: {entry}")
    if not done:
        print("Every entry is there already.")


if __name__ == "__main__":
    main(sys.argv[1:])
