"""The add-on's bridge (anki_addon/bridge.py) as an HTTP endpoint, without Anki: aqt
replaced by a fake main window. Its actions on a real collection: test_real_anki.py."""

import importlib.util
import json
import sys
import types
import urllib.request
from pathlib import Path

import pytest


class FakeCol:
    def __init__(self):
        self.queries = []

    def find_cards(self, query):
        self.queries.append(query)
        if query == "bad(":
            raise ValueError("invalid search")
        return [11, 12]


class FakeMainWindow:
    def __init__(self):
        self.col = FakeCol()
        self.ran = []  # what ran "on the main thread"
        self.taskman = types.SimpleNamespace(run_on_main=self.run_on_main)
        self.pm = types.SimpleNamespace(name="Léa", profiles=lambda: ["Léa", "Paul"])
        self.stuck = False  # a modal dialog: tasks for the main thread never run

    def run_on_main(self, fn):
        if not self.stuck:
            self.ran.append(fn)
            fn()


@pytest.fixture
def bridge(monkeypatch):
    mw = FakeMainWindow()
    aqt = types.ModuleType("aqt")
    aqt.mw = mw
    qt = types.ModuleType("aqt.qt")
    qt.QTimer = types.SimpleNamespace(singleShot=lambda ms, fn: None)
    monkeypatch.setitem(sys.modules, "aqt", aqt)
    monkeypatch.setitem(sys.modules, "aqt.qt", qt)
    spec = importlib.util.spec_from_file_location("notosaurus_bridge_unit", Path("anki_addon/bridge.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    server = module.Bridge()
    server.start()
    yield types.SimpleNamespace(module=module, server=server, mw=mw)
    server.stop()


def post(bridge, body) -> dict:
    data = body if isinstance(body, bytes) else json.dumps(body).encode()
    request = urllib.request.Request(bridge.server.url, data=data, method="POST")
    with urllib.request.urlopen(request, timeout=10) as response:
        assert response.status == 200 and response.headers["Content-Type"] == "application/json"
        return json.loads(response.read())


def test_actions_with_the_key(bridge):
    key = bridge.server.key
    assert bridge.server._server.server_address[0] == "127.0.0.1"  # this computer only, not the Wi-Fi
    assert post(bridge, {"action": "version", "key": key}) == {"result": 6, "error": None}
    found = post(bridge, {"action": "findCards", "key": key, "params": {"query": "deck:D"}})
    assert found == {"result": [11, 12], "error": None}
    assert bridge.mw.col.queries == ["deck:D"] and len(bridge.mw.ran) == 1  # on the main thread
    assert post(bridge, {"action": "getActiveProfile", "key": key}) == {"result": "Léa", "error": None}


def test_a_wrong_key_is_refused(bridge):
    for key in [None, "", "wrong", 42, bridge.server.key[:-1]]:
        body = {"action": "findCards", "params": {"query": "deck:D"}}
        if key is not None:
            body["key"] = key
        assert post(bridge, body) == {"result": None, "error": "invalid key"}, key
        assert post(bridge, {**body, "action": "version"})["error"] == "invalid key", key
    assert bridge.mw.ran == [] and bridge.mw.col.queries == []  # nothing ran


def test_errors_are_answers(bridge):
    """Whatever goes wrong, an AnkiConnect-style answer ({"result": null, "error": …}),
    never a dropped connection."""
    key = bridge.server.key
    unknown = post(bridge, {"action": "deleteEverything", "key": key})
    assert unknown == {"result": None, "error": "unsupported action: deleteEverything"}
    assert post(bridge, b"{not json")["error"] and post(bridge, b"")["error"]
    failed = post(bridge, {"action": "findCards", "key": key, "params": {"query": "bad("}})
    assert failed == {"result": None, "error": "invalid search"}
    missing = post(bridge, {"action": "findCards", "key": key})  # no params
    assert missing["result"] is None and missing["error"]

    bridge.mw.col = None  # the profile screen: no collection
    closed = post(bridge, {"action": "findCards", "key": key, "params": {"query": "deck:D"}})
    assert closed == {"result": None, "error": "no profile open"}
    assert post(bridge, {"action": "getActiveProfile", "key": key}) == {"result": None, "error": None}


def test_anki_not_responding(bridge, monkeypatch):
    monkeypatch.setattr(bridge.module, "MAIN_THREAD_TIMEOUT", 0.1)
    bridge.mw.stuck = True
    answer = post(bridge, {"action": "findCards", "key": bridge.server.key, "params": {"query": "deck:D"}})
    assert answer["result"] is None and "not responding" in answer["error"]
