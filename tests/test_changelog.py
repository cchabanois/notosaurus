"""The changelog written after the merge (tools/changelog_add.py): a pull request's entries,
read from its description, put under Unreleased without any pull request touching the file."""

import pytest

from tools import changelog_add

BODY = """\
Why this change, at length.

## Changelog
### Added
- 💾 **Back up my lessons**: every lesson in one file,
  taken in again anywhere.
- A second thing.
### Fixed
- A key refused is not kept.

## Tests
Some text with - a dash, not an entry.
"""

CHANGELOG = """\
# Changelog

Intro.

## [Unreleased]

### Added

- Older addition.

### Fixed

- Older fix.

## [1.0.0] - 2026-10-04

### Added

- First.

[Unreleased]: https://example.org/compare/v1.0.0...HEAD
[1.0.0]: https://example.org/releases/tag/v1.0.0
"""


def test_the_entries_read_from_the_description():
    assert changelog_add.entries(BODY) == [
        ("Added", "💾 **Back up my lessons**: every lesson in one file, taken in again anywhere."),
        ("Added", "A second thing."),
        ("Fixed", "A key refused is not kept."),
    ]
    assert changelog_add.entries("No section here.\n- a bullet") == []
    # A subsection the format doesn't have is left out; the heading's case doesn't matter
    assert changelog_add.entries("## changelog\n### Notes\n- x\n### FIXED\n- y") == [("Fixed", "y")]


def test_the_entries_put_first_in_their_subsection():
    text, done = changelog_add.added(CHANGELOG, changelog_add.entries(BODY))
    assert done == changelog_add.entries(BODY)
    unreleased = text.split("## [1.0.0]")[0]
    assert "### Added\n\n- 💾 **Back up my lessons**" in unreleased
    assert unreleased.index("A second thing.") < unreleased.index("Older addition.")
    assert "### Fixed\n\n- A key refused is not kept.\n- Older fix." in unreleased
    assert text.endswith("[1.0.0]: https://example.org/releases/tag/v1.0.0\n")  # the rest untouched
    assert "First." in text.split("## [1.0.0]")[1]


def test_a_missing_subsection_made_at_its_place():
    text, _ = changelog_add.added(CHANGELOG, [("Changed", "Something changed."), ("Security", "A hole closed.")])
    unreleased = text.split("## [1.0.0]")[0]
    order = [unreleased.index(f"### {s}") for s in ("Added", "Changed", "Fixed", "Security")]
    assert order == sorted(order)
    assert "### Changed\n\n- Something changed.\n\n### Fixed" in unreleased
    assert unreleased.rstrip().endswith("### Security\n\n- A hole closed.")


def test_an_empty_unreleased_just_after_a_release():
    released = "## [1.0.0] - 2026-10-04\n\n### Added\n\n- First.\n"
    text, _ = changelog_add.added(f"# Changelog\n\n## [Unreleased]\n\n{released}", [("Fixed", "A fix.")])
    assert text == f"# Changelog\n\n## [Unreleased]\n\n### Fixed\n\n- A fix.\n\n{released}"


def test_an_entry_is_not_added_twice():
    once, _ = changelog_add.added(CHANGELOG, changelog_add.entries(BODY))
    twice, done = changelog_add.added(once, changelog_add.entries(BODY))
    assert twice == once
    assert done == []


def test_the_file_written_and_said(tmp_path, monkeypatch, capsys):
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(CHANGELOG, encoding="utf-8")
    monkeypatch.setattr(changelog_add, "CHANGELOG", changelog)
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO(BODY))
    changelog_add.main([])
    assert "A key refused is not kept." in changelog.read_text(encoding="utf-8")
    assert "Added under Fixed: A key refused is not kept." in capsys.readouterr().out


def test_check_refuses_a_description_without_entries(monkeypatch):
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO("Just words."))
    with pytest.raises(SystemExit, match="No changelog entry"):
        changelog_add.main(["--check"])
