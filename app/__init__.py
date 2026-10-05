"""Notosaurus's web server.

In the repository, notosaurus_core is in core/: put on the path for the server run
from there (the add-on and the Docker image put notosaurus_core next to app/).
"""

import sys
from pathlib import Path

_core = Path(__file__).resolve().parent.parent / "core"
if (_core / "notosaurus_core").is_dir() and str(_core) not in sys.path:
    sys.path.insert(0, str(_core))
