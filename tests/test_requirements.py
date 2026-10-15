"""requirements.txt is compiled for every system (`uv pip compile … --universal`, see
requirements.in): a package that can't install everywhere keeps its platform marker.
Recompiled without it (as Dependabot does), the add-on no longer installs on Windows."""

from pathlib import Path

REQUIREMENTS = Path(__file__).resolve().parent.parent / "requirements.txt"


def test_compiled_for_every_system():
    pins = {
        line.split("==")[0].split("[")[0]: line
        for line in REQUIREMENTS.read_text(encoding="utf-8").splitlines()
        if line and not line.startswith((" ", "#"))
    }
    assert "sys_platform != 'win32'" in pins["uvloop"], "recompile with uv pip compile --universal"
