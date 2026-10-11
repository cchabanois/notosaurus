"""docs/public/relay.json: where the Android app finds the relays when it starts
(android/.../RelayDirectory.kt). A typo there would send every installed app nowhere."""

import json
import re
from pathlib import Path
from urllib.parse import urlsplit

import pytest

RELAY_JSON = Path(__file__).parent.parent / "docs" / "public" / "relay.json"
CLOUD_RUN = re.compile(r"^[a-z0-9-]+\.[a-z0-9-]+\.run\.app$")  # as RelayDirectory.CLOUD_RUN


def accepted(address: str) -> bool:
    """RelayDirectory.accepted, in Python: https, on Cloud Run, nothing but the host."""
    try:
        parts = urlsplit(address)
        port = parts.port
    except ValueError:
        return False
    return (
        parts.scheme == "https"
        and CLOUD_RUN.match(parts.hostname or "") is not None
        and parts.netloc == parts.hostname  # no user, no port, no uppercase
        and port is None
        and parts.path == ""
        and parts.query == ""
        and parts.fragment == ""
    )


@pytest.mark.parametrize(
    ("address", "ok"),
    [
        ("https://notosaurus-relay-1.europe-west1.run.app", True),
        ("http://notosaurus-relay-1.europe-west1.run.app", False),  # not https
        ("https://notosaurus-relay-1.europe-west1.run.app:8443", False),
        ("https://notosaurus-relay-1.europe-west1.run.app/v1", False),
        ("https://notosaurus-relay-1.europe-west1.run.app?x=1", False),
        ("https://me@notosaurus-relay-1.europe-west1.run.app", False),
        ("https://relay.example.com", False),  # not on Cloud Run
        ("https://run.app", False),
    ],
)
def test_the_rule_copied_from_the_app(address, ok):
    assert accepted(address) is ok


def test_every_relay_listed_is_one_the_app_takes():
    """Valid JSON, both relays listed, each address accepted as the app checks it (a
    trailing "/" dropped first, as the app does)."""
    listed = json.loads(RELAY_JSON.read_text(encoding="utf-8"))
    assert {"real", "test"} <= listed.keys()
    for role in ("real", "test"):
        assert accepted(listed[role].rstrip("/")), f"{role}: {listed[role]}"
    assert listed["real"] != listed["test"]
