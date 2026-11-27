"""The changelog written after the merge (tools/changelog_add.py): a pull request's entries,
read from its description, put under Unreleased without any pull request touching the file."""

import shutil
import subprocess
import sys
from pathlib import Path

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


def test_an_entry_ends_at_a_blank_line():
    """The squash commit's message wraps a bullet over unindented lines, then ends with the
    description's footer and GitHub's trailers: those, after a blank line, are no entry's."""
    message = (
        "## Changelog\n### Fixed\n- Without a photo, an unchanged prompt no longer makes cards on a\n"
        "made-up subject\n\n🤖 Generated with [Claude Code](https://claude.com/claude-code)\n\n"
        "---------\n\nCo-authored-by: Someone <someone@example.org>\n"
    )
    assert changelog_add.entries(message) == [
        ("Fixed", "Without a photo, an unchanged prompt no longer makes cards on a made-up subject")
    ]
    # Bullets a blank line apart are each read, and an indented line goes on its bullet
    assert changelog_add.entries("## Changelog\n### Added\n- a\n\n- b\n\n  more of b\n") == [
        ("Added", "a"),
        ("Added", "b more of b"),
    ]


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


def test_unreleased_compared_with_the_base(tmp_path, monkeypatch, capsys):
    base = tmp_path / "base.md"
    base.write_text(CHANGELOG, encoding="utf-8")
    ours = tmp_path / "CHANGELOG.md"
    monkeypatch.setattr(changelog_add, "CHANGELOG", ours)
    # The intro reworded, a released version touched: not the entries
    ours.write_text(CHANGELOG.replace("Intro.", "Another intro.").replace("- First.", "- First!"), encoding="utf-8")
    changelog_add.main(["--unreleased-unchanged", str(base)])
    assert "Unreleased unchanged." in capsys.readouterr().out
    ours.write_text(CHANGELOG.replace("- Older fix.", "- Older fix.\n- A line by hand."), encoding="utf-8")
    with pytest.raises(SystemExit, match="Unreleased section"):
        changelog_add.main(["--unreleased-unchanged", str(base)])


def test_check_refuses_a_description_without_entries(monkeypatch):
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO("Just words."))
    with pytest.raises(SystemExit, match="No changelog entry"):
        changelog_add.main(["--check"])


ROOT = Path(__file__).resolve().parent.parent


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


@pytest.mark.skipif(sys.platform == "win32" or not shutil.which("bash"), reason="the workflow's script: bash, on Linux")
def test_pushed_on_main_as_it_is_now(tmp_path):
    """The Changelog workflow's push (tools/changelog_push.sh) from a checkout behind main: a
    merge landed after the one it adds (actions/checkout's origin/main is the commit that ran
    it). Its entries added on main as it is now and pushed, the other merge kept: #821's entry
    was refused so, twice, 2026-11-27."""
    remote = tmp_path / "remote.git"
    _git(tmp_path, "init", "-q", "--bare", "-b", "main", str(remote))
    author = ["-c", "user.name=t", "-c", "user.email=t@t"]

    def clone(name: str) -> Path:
        _git(tmp_path, "clone", "-q", str(remote), name)
        return tmp_path / name

    first = tmp_path / "first"
    first.mkdir()
    _git(first, "init", "-q", "-b", "main")
    (first / "tools").mkdir()
    for script in ("changelog_add.py", "changelog_push.sh"):
        shutil.copy2(ROOT / "tools" / script, first / "tools" / script)
    (first / "CHANGELOG.md").write_text("# Changelog\n\n## [Unreleased]\n\n## [1.0.0] - 2026-10-01\n", encoding="utf-8")
    _git(first, "add", ".")
    _git(first, *author, "commit", "-q", "-m", "Start")
    _git(first, "remote", "add", "origin", str(remote))
    _git(first, "push", "-q", "origin", "main")
    merged = "🔊 Sounds kept (#821)\n\n## Changelog\n\n### Fixed\n- 🔊 A lesson's sounds no longer go missing."
    _git(first, *author, "commit", "-q", "--allow-empty", "-m", merged)
    _git(first, "push", "-q", "origin", "main")
    sha = _git(first, "rev-parse", "HEAD")

    other = clone("other")  # another merge, after it
    (other / "x.txt").write_text("x", encoding="utf-8")
    _git(other, "add", "x.txt")
    _git(other, *author, "commit", "-q", "-m", "🧪 Another merge (#822)")
    _git(other, "push", "-q", "origin", "main")

    bot = {
        "GIT_AUTHOR_NAME": "bot",
        "GIT_AUTHOR_EMAIL": "b@b",
        "GIT_COMMITTER_NAME": "bot",
        "GIT_COMMITTER_EMAIL": "b@b",
    }
    env = {"PATH": "/usr/bin:/bin", "PYTHON": sys.executable, "HOME": str(tmp_path), **bot}
    subprocess.run(["bash", "tools/changelog_push.sh", sha], cwd=first, env=env, check=True, capture_output=True)

    after = clone("after")
    assert _git(after, "log", "-2", "--format=%s") == "📝 Changelog: 🔊 Sounds kept (#821)\n🧪 Another merge (#822)"
    changelog = (after / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "### Fixed\n\n- 🔊 A lesson's sounds no longer go missing." in changelog
    assert (after / "x.txt").exists()  # the other merge kept
