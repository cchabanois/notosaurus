"""The atlas's steps kept (tools/atlas.py): each step's result stored under a key made of what
it reads (the sources' bytes, the results of the steps before it, its parameters) and of its
code (its function's code, the code of every function and the value of every constant of its
module it reaches, however deep), so that a build redoes only the steps whose code or data
changed, and gives what a whole build gives: a result kept is the very object the step made
(pickled), and every step is given its own copy of what it reads (a step that changes its
input changes nobody else's).

  cache = Cache(folder, salt="the libraries' versions")
  borders = cache.source("ohm-1914.json", lambda: load(...), cache.file_key(path))
  states = cache.step(past_states, borders, named, year=1914)
  states.get()  # kept: read back; else made (its inputs made or read back first), then kept
"""

import hashlib
import inspect
import json
import os
import pickle
import types
from collections.abc import Callable
from pathlib import Path
from typing import Any

_PICKLE = 5  # one protocol, whatever Python's default becomes: the same bytes, the same key


def _digest(*parts: str | bytes) -> str:
    h = hashlib.sha256()
    for part in parts:
        data = part.encode() if isinstance(part, str) else part
        h.update(len(data).to_bytes(8, "little"))
        h.update(data)
    return h.hexdigest()


def _codes(code: types.CodeType):
    """A code object and those inside it (its functions, lambdas, comprehensions)."""
    yield code
    for const in code.co_consts:
        if isinstance(const, types.CodeType):
            yield from _codes(const)


def _constant(value: Any, root: Path | None) -> str:
    """A constant as its key reads it, the same in every run and every checkout: a set's items
    in order (its repr's follows the strings' hashes, other each run), a path within `root`
    relative to it, a dict's, a list's, a tuple's items so, anything else by its repr."""
    if isinstance(value, (set, frozenset)):
        return f"{type(value).__name__}({sorted(_constant(v, root) for v in value)!r})"
    if isinstance(value, dict):
        return "{" + ", ".join(f"{_constant(k, root)}: {_constant(v, root)}" for k, v in value.items()) + "}"
    if isinstance(value, (list, tuple)):
        return f"{type(value).__name__}[" + ", ".join(_constant(v, root) for v in value) + "]"
    if isinstance(value, Path) and root is not None and value.is_relative_to(root):
        return f"Path({value.relative_to(root).as_posix()!r})"
    return repr(value)


def _code(code: types.CodeType) -> str:
    """A code object as its key reads it: its bytecode, the names and constants it uses, the
    functions inside it; not its file nor its lines (a function moved keys the same), and
    read from what Python runs, not from the file (edited meanwhile, perhaps)."""
    consts = [_code(c) if isinstance(c, types.CodeType) else _constant(c, None) for c in code.co_consts]
    return repr((code.co_name, code.co_code.hex(), code.co_names, code.co_varnames, code.co_freevars, consts))


def code_key(function: Callable, root: Path | None = None) -> str:
    """What a step's code is: its function's code, and that of every function of its module it
    names and the value of every constant of its module it names, then of those they name, and
    so on (a helper's change, a list of names', a threshold's: a new key). What other modules
    give (shapely, json) is the caller's salt: their versions."""
    module = getattr(function, "__module__", None)
    seen: dict[str, str] = {}
    pending: list[Callable] = [function]
    done: set[int] = set()
    while pending:
        current = pending.pop()
        if id(current) in done:
            continue
        done.add(id(current))
        code = getattr(current, "__code__", None)
        if code is None:  # (a class)
            try:
                seen[f"{current.__qualname__}()"] = inspect.getsource(current)
            except (OSError, TypeError):
                seen[f"{current.__qualname__}()"] = repr(current)
            continue
        defaults = (getattr(current, "__defaults__", None), getattr(current, "__kwdefaults__", None))
        seen[f"{current.__qualname__}()"] = _code(code) + repr(defaults)
        found = getattr(current, "__globals__", {})
        for name in sorted({n for c in _codes(code) for n in c.co_names}):
            if name not in found or name in seen:
                continue
            value = found[name]
            if isinstance(value, types.ModuleType):
                continue
            if isinstance(value, (types.FunctionType, type)):
                if getattr(value, "__module__", None) == module:
                    pending.append(value)
                continue
            if callable(value) and not isinstance(value, (dict, list, tuple, set, frozenset)):
                continue  # (another module's function: shapely's `shape`)
            seen[name] = _constant(value, root)
    return _digest(*(f"{name}\n{text}" for name, text in sorted(seen.items())))


class Node:
    """A source or a step's result: its key known before its value, its value made only when
    asked (a step whose key is kept never reads what it was made from)."""

    key: str
    name: str

    def get(self) -> Any:
        raise NotImplementedError


class Source(Node):
    """A file read (or downloaded) by `load`, its key what it holds."""

    def __init__(self, name: str, load: Callable[[], Any], key: str):
        self.name, self._load, self.key = name, load, key

    def get(self) -> Any:
        return self._load()  # read again for each step: its own copy


class Value(Node):
    """A value made outside the cache (a list kept in git, a parameter), its key its pickle."""

    def __init__(self, name: str, value: Any):
        self.name, self._bytes = name, pickle.dumps(value, protocol=_PICKLE)
        self.key = _digest("value", self._bytes)

    def get(self) -> Any:
        return pickle.loads(self._bytes)


class Step(Node):
    def __init__(self, cache: "Cache", function: Callable, inputs: tuple[Node, ...], params: dict, name: str):
        self._cache, self._function, self._inputs, self._params, self.name = cache, function, inputs, params, name
        self._bytes: bytes | None = None
        self.key = _digest(
            "step",
            function.__qualname__,
            cache.salt,
            cache.code(function),
            *(i.key for i in inputs),
            repr(sorted(params.items())),
        )

    def get(self) -> Any:
        if self._bytes is None:
            self._bytes = self._cache.load(self)
        return pickle.loads(self._bytes)

    def make(self) -> bytes:
        return pickle.dumps(self._function(*(i.get() for i in self._inputs), **self._params), protocol=_PICKLE)


class Cache:
    """The steps' results kept in `folder` (none: every step made, nothing kept), one file
    each, by its key; `salt` what else a result depends on (the libraries' versions)."""

    def __init__(self, folder: Path | None, salt: str = "", root: Path | None = None):
        self.folder, self.salt, self.root = folder, salt, root
        self.made: list[str] = []  # the steps made this time, by their names
        self.kept: list[str] = []  # and those read back
        self._codes: dict[int, str] = {}
        self._hashes: dict[str, list] = {}
        if folder:
            folder.mkdir(parents=True, exist_ok=True)
            try:
                self._hashes = json.loads((folder / "hashes.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                self._hashes = {}

    def code(self, function: Callable) -> str:
        if id(function) not in self._codes:
            self._codes[id(function)] = code_key(function, self.root)
        return self._codes[id(function)]

    def file_key(self, path: Path) -> str:
        """What a file holds (its bytes' hash), hashed again only when its size or date changed."""
        stat = path.stat()
        known = self._hashes.get(str(path.resolve()))
        if known and known[:2] == [stat.st_size, stat.st_mtime_ns]:
            return known[2]
        key = hashlib.sha256(path.read_bytes()).hexdigest()
        self._hashes[str(path.resolve())] = [stat.st_size, stat.st_mtime_ns, key]
        if self.folder:
            self._write(self.folder / "hashes.json", json.dumps(self._hashes, indent=0).encode())
        return key

    def source(self, name: str, load: Callable[[], Any], key: str) -> Source:
        return Source(name, load, _digest("source", key))

    def value(self, name: str, value: Any) -> Value:
        return Value(name, value)

    def step(self, function: Callable, *inputs: Node, name: str | None = None, **params: Any) -> Step:
        return Step(self, function, inputs, params, name or function.__name__)

    def load(self, step: Step) -> bytes:
        file = self.folder / f"{step.key}.pickle" if self.folder else None
        if file and file.is_file():
            self.kept.append(step.name)
            return file.read_bytes()
        made = step.make()
        self.made.append(step.name)
        if file:
            self._write(file, made)
        return made

    @staticmethod
    def _write(file: Path, data: bytes) -> None:
        """Written whole or not at all (a build stopped halfway leaves no half a result)."""
        part = file.with_name(f"{file.name}.{os.getpid()}.part")
        part.write_bytes(data)
        part.replace(file)
