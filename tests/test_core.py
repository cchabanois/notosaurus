"""notosaurus_core stands on its own: other programs use it without the app."""

import json
import os
import subprocess
import sys
from pathlib import Path

CORE = Path(__file__).parent.parent / "core"

# Imports every module of the package, then lists what got imported
PROBE = """
import json, pkgutil, sys
import notosaurus_core
for m in pkgutil.iter_modules(notosaurus_core.__path__):
    __import__(f"notosaurus_core.{m.name}")
print(json.dumps(sorted(sys.modules)))
"""


def test_core_never_uses_the_app(tmp_path):
    """Nothing of the web app, Anki or the data folder: with only core on the path
    (run elsewhere than in the repository), every module imports."""
    env = {**os.environ, "PYTHONPATH": str(CORE)}
    out = subprocess.run(
        [sys.executable, "-c", PROBE], cwd=tmp_path, env=env, capture_output=True, text=True, check=True
    ).stdout
    loaded = {name.split(".")[0] for name in json.loads(out)}
    assert not loaded & {"app", "fastapi", "starlette", "uvicorn", "genanki", "segno", "dotenv"}
