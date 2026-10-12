"""The add-on's own module (anki_addon/__init__.py) without Anki: aqt and its Qt replaced by
fakes that record what is shown, enough to load it. Its pure parts are tested here (the
menu, the documentation's address, the texts, the server's answers, the steps of a start);
its dialogs are left to Anki itself. The bridge: test_addon_bridge.py; the launcher:
test_addon_launcher.py."""

import importlib.util
import io
import json
import sys
import types
import urllib.error
from pathlib import Path
from typing import ClassVar

import pytest

ADDON = Path("anki_addon")
NAME = "notosaurus_addon_unit"  # in Anki, the add-on's folder name


class Signal:
    def __init__(self):
        self.handlers = []

    def connect(self, handler):
        self.handlers.append(handler)


class QAction:
    def __init__(self, text, parent):
        self.text, self.triggered = text, Signal()


class QMenu:
    def __init__(self, title, parent):
        self.title, self.actions = title, []

    def addAction(self, action):
        self.actions.append(action)


class FakeMainWindow:
    def __init__(self, config):
        self.config, self.written, self.menus, self.background, self.later = config, [], [], [], []
        self.addonManager = types.SimpleNamespace(getConfig=lambda name: self.config, writeConfig=self.write)
        self.form = types.SimpleNamespace(menuTools=types.SimpleNamespace(addMenu=self.menus.append))
        self.taskman = types.SimpleNamespace(run_in_background=self.run_in_background)
        self.progress = types.SimpleNamespace(single_shot=lambda ms, fn: self.later.append(fn))

    def write(self, name, config):
        self.written.append(config)
        self.config = config

    def run_in_background(self, task, on_done, uses_collection):
        self.background.append((task, on_done))


class FakeServer:
    def __init__(self):
        self.up, self.started, self.stopped = False, [], 0

    def running(self):
        return self.up

    def start(self, config, url, key, lang):
        self.started.append((config, url, key, lang))

    def stop(self):
        self.stopped += 1

    def log_tail(self, lines=40):
        return "the log"


class FakeBridge:
    made: ClassVar[list] = []

    def __init__(self):
        self.url, self.key, self.running = "http://127.0.0.1:9999", "k", False
        FakeBridge.made.append(self)

    def start(self):
        self.running = True

    def stop(self):
        self.running = False


@pytest.fixture
def addon(monkeypatch):
    """The add-on loaded with Anki in French, its config the default one; `ui` lists what it
    showed ((function, text)), `answer` what the user answers to a question."""
    config = json.loads((ADDON / "config.json").read_text())
    mw = FakeMainWindow(config)
    shown = types.SimpleNamespace(ui=[], answer=True)

    def recorder(kind):
        def show(text, **kwargs):
            shown.ui.append((kind, text))
            return shown.answer if kind == "askUser" else None

        return show

    hooks = types.SimpleNamespace(main_window_did_init=[], addons_dialog_will_delete_addons=[])
    fakes = {
        "anki": types.ModuleType("anki"),
        "anki.lang": types.SimpleNamespace(current_lang="fr_FR"),
        "aqt": types.SimpleNamespace(mw=mw, gui_hooks=hooks),
        "aqt.qt": types.SimpleNamespace(
            QAction=QAction,
            QMenu=QMenu,
            QTimer=None,
            Qt=None,
            QApplication=None,
            QDialog=None,
            QDialogButtonBox=None,
            QLabel=None,
            QPixmap=None,
            QVBoxLayout=None,
        ),
        "aqt.utils": types.SimpleNamespace(
            **{k: recorder(k) for k in ("askUser", "showInfo", "showText", "showWarning", "tooltip")}
        ),
    }
    fakes["anki"].lang = fakes["anki.lang"]
    for name, module in fakes.items():
        monkeypatch.setitem(sys.modules, name, module)
    monkeypatch.setattr("atexit.register", lambda fn: fn)  # not at the tests' exit
    spec = importlib.util.spec_from_file_location(NAME, ADDON / "__init__.py", submodule_search_locations=[str(ADDON)])
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, NAME, module)
    try:
        spec.loader.exec_module(module)
        yield types.SimpleNamespace(module=module, mw=mw, hooks=hooks, shown=shown, anki_lang=fakes["anki.lang"])
    finally:
        for name in [n for n in sys.modules if n.startswith(NAME + ".")]:
            del sys.modules[name]


def test_the_menu_in_ankis_language(addon):
    m = addon.module
    (menu,) = addon.mw.menus  # Tools → Notosaurus
    assert menu.title == "Notosaurus"
    french = json.loads(Path("static/i18n/fr.json").read_text(encoding="utf-8"))["addon"]
    assert [a.text for a in menu.actions] == [
        french[k]
        for k in (
            *("menuOpen", "menuPhone", "menuSetup", "menuSettings", "menuAddress"),
            *("menuRestart", "menuLog", "menuHelp", "menuSupport"),
        )
    ]
    handlers = [h for a in menu.actions for h in a.triggered.handlers]
    assert handlers == [
        m.open_in_browser, m.show_phone, m.open_setup, m.open_settings, m.show_address, m.restart,
        m.show_log, m.open_help, m.open_support,
    ]  # fmt: skip
    assert addon.hooks.main_window_did_init == [m.on_main_window_ready]
    assert addon.hooks.addons_dialog_will_delete_addons == [m.on_addons_deleted]


@pytest.mark.parametrize(
    ("lang", "url"),
    [
        ("fr_FR", "https://cchabanois.github.io/notosaurus/fr/phone/"),
        ("pt_BR", "https://cchabanois.github.io/notosaurus/pt-br/phone/"),
        ("de-DE", "https://cchabanois.github.io/notosaurus/de/phone/"),
        ("en_US", "https://cchabanois.github.io/notosaurus/phone/"),
        ("ja_JP", "https://cchabanois.github.io/notosaurus/phone/"),  # no translation: English
        (None, "https://cchabanois.github.io/notosaurus/phone/"),
    ],
)
def test_the_documentation_in_ankis_language(addon, lang, url):
    addon.anki_lang.current_lang = lang
    assert addon.module.docs_url("phone") == url
    assert addon.module.docs_url() == url.removesuffix("phone/")


def test_texts_translated_from_the_servers_files(addon, monkeypatch):
    t = addon.module.t
    assert t("addon.ready", url="http://192.168.1.20:8000") == "Notosaurus est prêt : http://192.168.1.20:8000"
    addon.anki_lang.current_lang = "pt_BR"  # no pt-br.json: Portuguese
    assert t("addon.menuOpen") == "Abrir o Notosaurus"
    addon.anki_lang.current_lang = "ja_JP"  # no Japanese: English
    assert t("addon.menuOpen") == "Open Notosaurus"
    assert t("addon.nothing") == "addon.nothing"  # unknown: the key, not a crash
    assert t("addon") == "addon"  # not a text

    def nowhere(config):
        raise addon.module.LaunchError("errors.addon.source_not_found")

    monkeypatch.setattr(addon.module, "layout", nowhere)  # the server's code not found: the keys
    assert t("addon.menuOpen") == "addon.menuOpen"


def test_the_addresses_from_the_config(addon, monkeypatch):
    monkeypatch.setattr(addon.module, "lan_address", lambda: "192.168.1.20")
    assert addon.module.urls() == ("http://localhost:8000", "http://192.168.1.20:8000")
    addon.mw.config = {**addon.mw.config, "port": 8123}
    assert addon.module.urls() == ("http://localhost:8123", "http://192.168.1.20:8123")
    addon.mw.config = None  # Anki without a config for it: the defaults
    assert addon.module.urls()[0] == "http://localhost:8000"


def _answering(monkeypatch, addon, answers: dict):
    """urlopen answering by path: bytes, or an exception raised."""
    asked = []

    def urlopen(url, timeout):
        asked.append(url)
        answer = answers[url.split("?")[0].split(":8000")[1]]
        if isinstance(answer, Exception):
            raise answer
        return io.BytesIO(answer)

    monkeypatch.setattr(addon.module.urllib.request, "urlopen", urlopen)
    return asked


@pytest.mark.parametrize(
    ("answer", "configured", "link"),
    [
        (b'{"configured": true, "url": "http://192.168.1.20:8000/#t=abc"}', True, "http://192.168.1.20:8000/#t=abc"),
        (b'{"configured": false}', False, None),
        (b"<html>", None, None),  # not JSON
        (urllib.error.URLError("refused"), None, None),  # not started yet
        (TimeoutError(), None, None),
    ],
)
def test_what_the_server_says(addon, monkeypatch, answer, configured, link):
    _answering(monkeypatch, addon, {"/api/config": answer, "/api/admin/phone": answer})
    assert addon.module.configured() is configured
    assert addon.module.phone_link() == link


def test_the_qr_code_asked_from_the_server(addon, monkeypatch):
    asked = _answering(monkeypatch, addon, {"/api/qr": b"\x89PNG"})
    assert addon.module.qr_png("http://192.168.1.20:8000/#t=a&b") == b"\x89PNG"
    assert asked == ["http://127.0.0.1:8000/api/qr?text=http%3A%2F%2F192.168.1.20%3A8000%2F%23t%3Da%26b"]
    _answering(monkeypatch, addon, {"/api/qr": urllib.error.URLError("refused")})
    assert addon.module.qr_png("x") is None


@pytest.fixture
def starting(addon, monkeypatch):
    """The add-on with its server and bridge faked, the install already done."""
    m = addon.module
    monkeypatch.setattr(m, "server", FakeServer())
    monkeypatch.setattr(m, "Bridge", FakeBridge)
    monkeypatch.setattr(m, "install_needed", lambda config: False)
    FakeBridge.made.clear()
    return addon


def test_an_install_needs_the_users_consent(starting, monkeypatch):
    m, shown = starting.module, starting.shown
    monkeypatch.setattr(m, "install_needed", lambda config: True)
    shown.answer = False
    m.start()
    assert [k for k, _ in shown.ui] == ["askUser", "tooltip"]
    assert not FakeBridge.made and not starting.mw.background  # nothing downloaded

    shown.answer, shown.ui[:] = True, []
    m.start()
    assert [k for k, _ in shown.ui] == ["askUser"]
    assert FakeBridge.made[0].running and len(starting.mw.background) == 1


def test_a_start_in_the_background(starting):
    m = starting.module
    m.start()
    ((task, on_done),) = starting.mw.background
    task()  # the server started with the bridge's address and key, in Anki's language
    assert m.server.started == [(starting.mw.config, "http://127.0.0.1:9999", "k", "fr_FR")]
    on_done(types.SimpleNamespace(result=lambda: None))
    assert starting.mw.later == [m.check_started]  # then checked

    def failed(error):
        def result():
            raise error

        return types.SimpleNamespace(result=result)

    on_done(failed(m.LaunchError("errors.addon.install_failed")))
    kind, text = starting.shown.ui[-1]
    assert kind == "showWarning" and "Notosaurus" in text and "errors.addon" not in text  # translated
    on_done(failed(RuntimeError("boom")))
    kind, text = starting.shown.ui[-1]
    assert kind == "showText" and "boom" in text and "the log" in text

    m.server.up = True  # already running: nothing more
    m.start()
    assert len(starting.mw.background) == 1 and len(FakeBridge.made) == 1


def test_a_start_without_the_servers_code(starting, monkeypatch):
    def nowhere(config):
        raise starting.module.LaunchError("errors.addon.source_not_found")

    monkeypatch.setattr(starting.module, "install_needed", nowhere)
    starting.module.start()
    ((kind, text),) = starting.shown.ui
    assert kind == "showWarning" and "errors.addon" not in text and not starting.mw.background


def test_the_first_start_offers_the_setup_once(starting, monkeypatch):
    m, shown = starting.module, starting.shown
    opened = []
    monkeypatch.setattr(m.webbrowser, "open", opened.append)
    monkeypatch.setattr(m, "configured", lambda: False)
    m.server.up = True
    m.check_started()
    assert starting.mw.config["phone_help_shown"] is True  # once
    assert [k for k, _ in shown.ui] == ["askUser"] and opened == ["http://localhost:8000/setup.html"]

    shown.ui.clear()
    monkeypatch.setattr(m, "lan_address", lambda: "192.168.1.20")
    m.check_started()  # the next starts: only said ready
    assert shown.ui == [("tooltip", "Notosaurus est prêt : http://192.168.1.20:8000")]

    shown.ui.clear()
    m.server.up = False  # stopped at once: why, with the log
    m.check_started()
    ((kind, text),) = shown.ui
    assert kind == "showText" and text.endswith("the log")


def test_the_first_start_declined_says_where_the_setup_is(starting, monkeypatch):
    m, shown = starting.module, starting.shown
    opened = []
    monkeypatch.setattr(m.webbrowser, "open", opened.append)
    monkeypatch.setattr(m, "configured", lambda: False)
    m.server.up, shown.answer = True, False
    m.check_started()
    assert [k for k, _ in shown.ui] == ["askUser", "tooltip"] and not opened


def test_deleting_the_addon_removes_its_runtime(starting, monkeypatch):
    m = starting.module
    removed = []
    monkeypatch.setattr(m, "remove_runtime", lambda: removed.append(True))
    m.on_addons_deleted(None, ["another add-on"])
    assert m.server.stopped == 0 and not removed
    m.on_addons_deleted(None, ["another add-on", NAME])
    assert m.server.stopped == 1 and removed == [True]
