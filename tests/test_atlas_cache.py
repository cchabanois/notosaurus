"""tools/atlas_cache.py: an atlas step is made again when what it reads or its code changes,
read back otherwise; small synthetic steps, no atlas built."""

import importlib.util
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # (inspect finds a function's source by its module)
    spec.loader.exec_module(module)
    return module


atlas_cache = _load("atlas_cache", ROOT / "tools" / "atlas_cache.py")

STEPS = """
from pathlib import Path

LIMIT = 2
NAMES = ["Saône", "Somme"]
UNUSED = 1
HERE = Path({root!r}) / "data.json"

def helper(x):
    return x * LIMIT

def double(data):
    return [helper(x) for x in data]

def named(data):
    return [n for n in NAMES if n] + [len(data), HERE.name]

def other(data):
    return UNUSED
"""


def steps(tmp_path: Path, name: str = "steps", root: Path | None = None, **changes: str):
    """A module of steps written in `tmp_path`, `changes` replacing a line of it."""
    text = STEPS.format(root=str(root or tmp_path))
    for old, new in changes.items():
        text = text.replace(old, new)
    path = tmp_path / f"{name}.py"
    path.write_text(textwrap.dedent(text), encoding="utf-8")
    return _load(name, path)


def build(cache_dir: Path, module, data: list, step: str = "double", root: Path | None = None, **params):
    cache = atlas_cache.Cache(cache_dir, salt="test", root=root)
    function = getattr(module, step)
    source = cache.value("data", data)
    made = cache.step(function, source, **params)
    return made.get(), cache.made, made.key


def test_a_step_is_read_back_when_nothing_changed(tmp_path):
    module = steps(tmp_path)
    first, made, key = build(tmp_path / "cache", module, [1, 2])
    again, made_again, key_again = build(tmp_path / "cache", module, [1, 2])
    assert first == again == [2, 4]
    assert made == ["double"] and made_again == [] and key == key_again


def test_a_step_is_made_again_when_its_input_changes(tmp_path):
    module = steps(tmp_path)
    build(tmp_path / "cache", module, [1, 2])
    value, made, _ = build(tmp_path / "cache", module, [1, 3])
    assert value == [2, 6] and made == ["double"]


def test_a_step_is_made_again_when_its_parameters_change(tmp_path):
    module = steps(tmp_path)
    cache = atlas_cache.Cache(tmp_path / "cache")
    data = cache.value("data", [1])
    assert cache.step(module.double, data).key == cache.step(module.double, data).key
    assert cache.step(min, data, default=1).key != cache.step(min, data, default=2).key


@pytest.mark.parametrize(
    "change",
    [
        {"    return [helper(x) for x in data]": "    return [helper(x) + 0 for x in data]"},  # its own code
        {"    return x * LIMIT": "    return LIMIT * x"},  # a helper's it calls
        {"LIMIT = 2": "LIMIT = 3"},  # a constant its helper reads
    ],
)
def test_a_step_is_made_again_when_its_code_changes(tmp_path, change):
    build(tmp_path / "cache", steps(tmp_path, "before"), [1, 2])
    changed = steps(tmp_path, "after", **change)
    value, made, _ = build(tmp_path / "cache", changed, [1, 2])
    assert made == ["double"]
    assert value == changed.double([1, 2])


def test_a_list_of_names_changed_makes_again_only_the_steps_reading_it(tmp_path):
    before = steps(tmp_path, "names")
    build(tmp_path / "cache", before, [1], step="named")
    build(tmp_path / "cache", before, [1], step="double")
    after = steps(tmp_path, "names_after", **{'NAMES = ["Saône", "Somme"]': 'NAMES = ["Saône", "Somme", "Loire"]'})
    value, made, _ = build(tmp_path / "cache", after, [1], step="named")
    assert value == ["Saône", "Somme", "Loire", 1, "data.json"] and made == ["named"]
    assert build(tmp_path / "cache", after, [1], step="double")[1] == []  # (it reads no names)


def test_what_a_step_never_reads_changes_nothing(tmp_path):
    build(tmp_path / "cache", steps(tmp_path, "unused"), [1])
    changed = steps(tmp_path, "unused_after", **{"UNUSED = 1": "UNUSED = 2"})
    assert build(tmp_path / "cache", changed, [1])[1] == []


def test_a_path_within_the_root_keys_the_same_in_every_checkout(tmp_path):
    one, two = tmp_path / "one", tmp_path / "two"
    one.mkdir(), two.mkdir()
    keys = [
        build(tmp_path / "cache", steps(folder, f"checkout_{folder.name}", root=folder), [1], step="named", root=folder)
        for folder in (one, two)
    ]
    assert keys[0][2] == keys[1][2] and keys[1][1] == []


def test_a_step_made_after_another_keys_by_the_one_before(tmp_path):
    module = steps(tmp_path)

    def run(data: list) -> tuple[list, list]:
        cache = atlas_cache.Cache(tmp_path / "cache", salt="test")
        first = cache.step(module.double, cache.value("data", data))
        second = cache.step(module.double, first, name="again")
        return second.get(), cache.made

    assert run([1]) == ([4], ["double", "again"])
    assert run([1]) == ([4], [])  # (the first step never read: the second is kept)
    assert run([2]) == ([8], ["double", "again"])


def test_every_step_reads_its_own_copy(tmp_path):
    cache = atlas_cache.Cache(None)
    shared = cache.step(list, cache.value("data", [1, 2]))
    shared.get().append(3)
    assert shared.get() == [1, 2]  # (a step changing what it reads changes nobody else's)


def test_a_source_keys_by_its_bytes(tmp_path):
    """A source changed (its date with it): keyed again by its bytes. Its date set apart as a
    download's would be: written twice in the same instant, the same size, a coarse clock
    (Windows) gave it the same date, and its hash was taken as known."""
    cache = atlas_cache.Cache(tmp_path / "cache")
    file = tmp_path / "source.json"
    file.write_text("[1]")
    os.utime(file, ns=(1_000_000_000, 1_000_000_000))
    before = cache.source("source", lambda: None, cache.file_key(file)).key
    file.write_text("[2]")
    os.utime(file, ns=(2_000_000_000, 2_000_000_000))
    assert cache.source("source", lambda: None, cache.file_key(file)).key != before


def test_the_salt_keys_the_steps(tmp_path):
    module = steps(tmp_path)
    keys = []
    for salt in ("shapely 2.1", "shapely 2.2"):
        cache = atlas_cache.Cache(tmp_path / "cache", salt=salt)
        keys.append(cache.step(module.double, cache.value("data", [1])).key)
    assert keys[0] != keys[1]


def test_a_comment_or_a_function_moved_keys_the_same(tmp_path):
    before = steps(tmp_path, "moved")
    after = steps(tmp_path, "moved_after", **{"def helper(x):": "# a comment\n\n\ndef helper(x):"})
    assert atlas_cache.code_key(before.double) == atlas_cache.code_key(after.double)


def test_a_set_keys_the_same_in_every_run(tmp_path):
    """A set's repr follows its strings' hashes (PYTHONHASHSEED): other in each process."""
    script = (
        f"import sys; sys.path.insert(0, {str(ROOT / 'tools')!r}); import atlas_cache\n"
        "KINDS = {'Island', 'Island group', 'Peninsula', 'Desert', 'Plain', 'Range/mtn'}\n"
        "def kind(x):\n    return x in KINDS or x in {'Gulf', 'Bay', 'Strait', 'Sound'}\n"
        "print(atlas_cache.code_key(kind))\n"
    )
    module = tmp_path / "kinds.py"
    module.write_text(script, encoding="utf-8")
    keys = {
        subprocess.run(
            [sys.executable, str(module)], env={"PYTHONHASHSEED": str(seed)}, capture_output=True, text=True, check=True
        ).stdout
        for seed in range(6)
    }
    assert len(keys) == 1


def test_the_same_step_written_by_two_threads_at_once(tmp_path, monkeypatch):
    """Steps run side by side: two threads making the same one each write it whole, neither
    losing its file to the other (they once shared one, the second replace then failing)."""
    import threading

    both = threading.Barrier(2, timeout=5)
    replace = Path.replace

    def together(self, target):
        both.wait()  # each has written its part: then both replace
        return replace(self, target)

    monkeypatch.setattr(Path, "replace", together)
    file = tmp_path / "step.pickle"
    failed = []

    def write(data):
        try:
            atlas_cache.Cache._write(file, data)
        except OSError as e:
            failed.append(e)

    threads = [threading.Thread(target=write, args=(b"made",)) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert failed == []
    assert file.read_bytes() == b"made"
    assert [p.name for p in tmp_path.iterdir()] == ["step.pickle"]
