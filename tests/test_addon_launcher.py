"""The add-on's launcher (plain Python, loaded without Anki)."""

import hashlib
import importlib.util
import io
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("launcher", Path("anki_addon/launcher.py"))
launcher = importlib.util.module_from_spec(spec)
sys.modules["launcher"] = launcher  # needed by @dataclass
spec.loader.exec_module(launcher)


@pytest.mark.parametrize(
    ("system", "machine", "archive"),
    [
        ("Windows", "AMD64", "x86_64-pc-windows-msvc.zip"),
        ("Windows", "ARM64", "aarch64-pc-windows-msvc.zip"),
        ("Darwin", "arm64", "aarch64-apple-darwin.tar.gz"),
        ("Darwin", "x86_64", "x86_64-apple-darwin.tar.gz"),
        ("Linux", "x86_64", "x86_64-unknown-linux-musl.tar.gz"),
        ("Linux", "aarch64", "aarch64-unknown-linux-musl.tar.gz"),
        ("Linux", "armv7l", None),
        ("FreeBSD", "amd64", None),
    ],
)
def test_uv_archive(system, machine, archive):
    assert launcher.uv_archive(system, machine) == archive
    assert archive is None or archive in launcher.UV_SHA256


def _tar_gz(name: str, content: bytes) -> bytes:
    out = io.BytesIO()
    with tarfile.open(fileobj=out, mode="w:gz") as t:
        info = tarfile.TarInfo(f"uv-x86_64-unknown-linux-musl/{name}")
        info.size = len(content)
        t.addfile(info, io.BytesIO(content))
    return out.getvalue()


def _serve(monkeypatch, data: bytes, archive: str, sha: str | None = None):
    monkeypatch.setitem(launcher.UV_SHA256, archive, sha or hashlib.sha256(data).hexdigest())
    monkeypatch.setattr(launcher.urllib.request, "urlopen", lambda url, timeout: io.BytesIO(data))


def test_download_uv_checks_the_sha256(monkeypatch, tmp_path):
    archive = "x86_64-unknown-linux-musl.tar.gz"
    monkeypatch.setattr(launcher, "EXE", "")
    data = _tar_gz("uv", b"#!/bin/sh\necho uv\n")
    _serve(monkeypatch, data, archive)
    path = launcher.download_uv(io.StringIO(), archive, tmp_path)
    assert path == tmp_path / "uv" and path.read_bytes() == b"#!/bin/sh\necho uv\n"
    if sys.platform != "win32":  # no executable bit on Windows
        assert path.stat().st_mode & 0o111

    # A download that doesn't match the pinned checksum is refused
    (tmp_path / "uv").unlink()
    _serve(monkeypatch, data, archive, sha="0" * 64)
    with pytest.raises(launcher.LaunchError, match="uv_download_failed"):
        launcher.download_uv(io.StringIO(), archive, tmp_path)
    assert not (tmp_path / "uv").exists()


def test_download_uv_windows_zip(monkeypatch, tmp_path):
    archive = "x86_64-pc-windows-msvc.zip"
    monkeypatch.setattr(launcher, "EXE", ".exe")
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        z.writestr("uvx.exe", b"not me")
        z.writestr("uv.exe", b"MZ uv")
    _serve(monkeypatch, out.getvalue(), archive)
    assert launcher.download_uv(io.StringIO(), archive, tmp_path).read_bytes() == b"MZ uv"


def test_download_uv_unsupported_or_offline(monkeypatch, tmp_path):
    monkeypatch.setattr(launcher, "uv_archive", lambda: None)
    with pytest.raises(launcher.LaunchError, match="uv_unsupported"):
        launcher.download_uv(io.StringIO(), destination=tmp_path)

    def offline(url, timeout):
        raise OSError("no network")

    monkeypatch.setattr(launcher.urllib.request, "urlopen", offline)
    with pytest.raises(launcher.LaunchError, match="uv_download_failed"):
        launcher.download_uv(io.StringIO(), "x86_64-unknown-linux-musl.tar.gz", tmp_path)


def test_install_needed(monkeypatch, tmp_path):
    source = tmp_path / "server"
    (source / "app").mkdir(parents=True)
    (source / "app" / "main.py").write_text("")
    (source / "requirements.txt").write_text("fastapi\n")
    monkeypatch.setattr(launcher, "USER_FILES", tmp_path / "user_files")
    monkeypatch.setattr(launcher, "RUNTIME", tmp_path / "notosaurus-runtime")
    config = {"source": str(source), "python": ""}
    assert launcher.install_needed(config)  # first start

    venv = tmp_path / "notosaurus-runtime" / "venv"
    python = launcher._venv_python(venv)
    python.parent.mkdir(parents=True)
    python.write_text("")
    (venv / ".notosaurus-requirements").write_text(launcher._requirements_hash(source))
    assert not launcher.install_needed(config)  # installed

    (source / "requirements.txt").write_text("fastapi\nnew-package\n")
    assert launcher.install_needed(config)  # an update changed the dependencies

    assert not launcher.install_needed({**config, "python": "/usr/bin/python3"})  # own Python: nothing to install


# --- Starting the server: subprocess faked ----------------------------------------


@pytest.fixture
def addon(monkeypatch, tmp_path):
    """A packaged add-on in addons21/, its runtime next to addons21 (as in Anki2/)."""
    folder = tmp_path / "Anki2" / "addons21" / "notosaurus"
    (folder / "server" / "app").mkdir(parents=True)
    (folder / "server" / "app" / "main.py").write_text("")
    (folder / "server" / "requirements.txt").write_text("fastapi\n")
    monkeypatch.setattr(launcher, "ADDON_DIR", folder)
    monkeypatch.setattr(launcher, "USER_FILES", folder / "user_files")
    monkeypatch.setattr(launcher, "RUNTIME", tmp_path / "Anki2" / "notosaurus-runtime")
    return folder


class FakeUv:
    """subprocess.run for uv: records each call; `venv` makes the venv's python, a call
    whose subcommand is in `failing` fails as uv would."""

    def __init__(self, failing=()):
        self.calls, self.failing = [], failing

    def __call__(self, args, check, stdout, stderr, env, **kwargs):
        assert check and args[0] == "/fake/uv"
        self.calls.append((args[1:], env))
        if args[1] in self.failing:
            raise launcher.subprocess.CalledProcessError(1, args)
        if args[1] == "venv":
            python = launcher._venv_python(Path(args[-1]))
            python.parent.mkdir(parents=True)
            python.write_text("")


@pytest.fixture
def uv(monkeypatch):
    fake = FakeUv()
    monkeypatch.setattr(launcher, "find_uv", lambda log: "/fake/uv")
    monkeypatch.setattr(launcher.subprocess, "run", fake)
    return fake


def test_ensure_venv_made_then_reused(addon, uv):
    source, runtime = addon / "server", launcher.RUNTIME
    venv = runtime / "venv"
    python = launcher.ensure_venv(source, io.StringIO())
    assert python == launcher._venv_python(venv) and python.exists()
    (made, env), (installed, _) = uv.calls
    assert made == ["venv", "--clear", "--managed-python", "--python", "3.13", str(venv)]
    assert installed == [
        "pip",
        "install",
        "--no-cache",
        "--python",
        str(python),
        "-r",
        str(source / "requirements.txt"),
    ]
    # Python itself in the runtime (removed with the add-on), the user's uv settings ignored
    assert env["UV_PYTHON_INSTALL_DIR"] == str(runtime / "python") and env["UV_NO_CONFIG"] == "1"
    assert (venv / ".notosaurus-requirements").read_text() == launcher._requirements_hash(source)

    # Next start: nothing to do, not even finding uv
    uv.calls.clear()
    assert launcher.ensure_venv(source, io.StringIO()) == python and uv.calls == []

    # An update with new dependencies: installed into the same venv, not made again
    (source / "requirements.txt").write_text("fastapi\nnew-package\n")
    assert launcher.ensure_venv(source, io.StringIO()) == python
    assert [args[0] for args, _ in uv.calls] == ["pip"]


def test_ensure_venv_install_failed(addon, uv, monkeypatch):
    source, venv = addon / "server", launcher.RUNTIME / "venv"
    uv.failing = ("pip",)
    with pytest.raises(launcher.LaunchError, match="install_failed"):
        launcher.ensure_venv(source, io.StringIO())
    # Not marked ready: the next start tries the installation again
    assert not (venv / ".notosaurus-requirements").exists()
    assert launcher.install_needed({})
    uv.failing, uv.calls[:] = (), []
    launcher.ensure_venv(source, io.StringIO())
    assert [args[0] for args, _ in uv.calls] == ["pip"]  # the venv made already is kept

    # uv itself missing (find_uv's download refused, a deleted file…): the same error
    def missing(*args, **kwargs):
        raise FileNotFoundError("uv")

    (venv / ".notosaurus-requirements").unlink()
    monkeypatch.setattr(launcher.subprocess, "run", missing)
    with pytest.raises(launcher.LaunchError, match="install_failed"):
        launcher.ensure_venv(source, io.StringIO())


class FakeProcess:
    def __init__(self, command, cwd, env, stdout, stderr, **kwargs):
        self.command, self.cwd, self.env, self.stdout = command, Path(cwd), env, stdout

    def poll(self):
        return None


@pytest.fixture
def popen(monkeypatch):
    """subprocess.Popen faked: the processes started, in a list."""
    started = []

    def start(*args, **kwargs):
        started.append(FakeProcess(*args, **kwargs))
        return started[-1]

    monkeypatch.setattr(launcher.subprocess, "Popen", start)
    return started


def test_server_started_from_the_runtime(addon, uv, popen, monkeypatch):
    """The packaged add-on: its server runs with the runtime's Python, the code from the
    add-on's server/ (--app-dir), and its working folder in the runtime — never in the
    add-on's folder, which Anki deletes to update it (Windows refuses while a process
    works in it)."""
    monkeypatch.setenv("PYTHONHOME", "/anki/python")
    monkeypatch.setenv("PYTHONPATH", "/anki/lib")
    monkeypatch.setenv("NOTOSAURUS_SOMETHING_ELSE", "kept")
    (addon / "user_files" / "venv").mkdir(parents=True)  # left by an older version
    server = launcher.Server()
    server.start({"port": 8123}, "http://127.0.0.1:4567", "secret-key", "es")

    (process,) = popen
    runtime, source = launcher.RUNTIME, addon / "server"
    assert process.command == [
        str(launcher._venv_python(runtime / "venv")),
        "-m",
        "uvicorn",
        "--app-dir",
        str(source),
        "app.main:app",
        "--host",
        "0.0.0.0",
        "--port",
        "8123",
    ]
    assert process.cwd == runtime and not process.cwd.is_relative_to(addon)
    assert server.log_path.is_relative_to(runtime) and process.stdout.name == str(server.log_path)
    env = process.env
    assert env["NOTOSAURUS_DATA"] == str(addon / "user_files" / "data")  # kept across updates
    assert (addon / "user_files" / "data").is_dir()
    assert env["NOTOSAURUS_EMBEDDED"] == "1" and env["NOTOSAURUS_LANG"] == "es"
    assert env["NOTOSAURUS_ANKICONNECT_URL"] == "http://127.0.0.1:4567"
    assert env["NOTOSAURUS_ANKICONNECT_KEY"] == "secret-key"
    assert env["PYTHONUNBUFFERED"] == "1" and env["PYTHONDONTWRITEBYTECODE"] == "1"
    # Anki's own Python settings don't reach the server's interpreter; the rest does
    assert "PYTHONHOME" not in env and "PYTHONPATH" not in env
    assert env["NOTOSAURUS_SOMETHING_ELSE"] == "kept"
    assert not (addon / "user_files" / "venv").exists()  # the old runtime cleaned up
    assert server.running()
    process.stdout.close()


def test_server_with_its_own_python(addon, popen, monkeypatch, tmp_path):
    """Development (or the config's python): that interpreter, no venv made; host, port
    and data from the config."""

    def no_uv(*args, **kwargs):
        raise AssertionError("no venv to make")

    monkeypatch.setattr(launcher.subprocess, "run", no_uv)
    config = {"python": "/usr/bin/python3", "data": str(tmp_path / "my-data"), "host": "127.0.0.1", "port": 9000}
    server = launcher.Server()
    server.start(config, "http://127.0.0.1:1", "k", "fr")
    (process,) = popen
    assert process.command[:3] == ["/usr/bin/python3", "-m", "uvicorn"]
    assert process.command[-4:] == ["--host", "127.0.0.1", "--port", "9000"]
    assert process.env["NOTOSAURUS_DATA"] == str(tmp_path / "my-data")
    assert process.cwd == launcher.RUNTIME
    process.stdout.close()


def test_server_not_started_when_the_install_fails(addon, uv, popen):
    uv.failing = ("venv",)
    server = launcher.Server()
    with pytest.raises(launcher.LaunchError, match="install_failed"):
        server.start({}, "http://127.0.0.1:1", "k", "en")
    assert popen == [] and not server.running()
    assert "--- starting" not in server.log_tail()
