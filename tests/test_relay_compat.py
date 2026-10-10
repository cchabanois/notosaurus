"""The relay's API only grows within /v1: an app already released (its API frozen in
core/relay-api-releases/) keeps working with today's relay (tools/relay_compat.py)."""

import copy
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CURRENT = json.loads((ROOT / "core" / "relay-api-v1.json").read_text(encoding="utf-8"))


def tool():
    spec = importlib.util.spec_from_file_location("relay_compat", ROOT / "tools" / "relay_compat.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_every_released_app_still_served():
    """A failure: today's API would break an app already released. Keep /v1 growing only
    (optional fields, new routes), or make a /v2 beside it."""
    releases = sorted((ROOT / "core" / "relay-api-releases").glob("*.json"))
    assert releases, "no frozen API"
    for release in releases:
        assert tool().problems(json.loads(release.read_text(encoding="utf-8")), CURRENT) == [], release.name


def changed(change) -> list[str]:
    new = copy.deepcopy(CURRENT)
    change(new["components"]["schemas"], new["paths"])
    return tool().problems(CURRENT, new)


def test_what_breaks_an_old_app():
    def route_gone(schemas, paths):
        del paths["/v1/explain"]

    def field_required(schemas, paths):
        schemas["ExplainRequest"]["required"].append("language")

    def field_gone(schemas, paths):
        del schemas["ExtractRequest"]["properties"]["helps"]

    def limit_tightened(schemas, paths):
        schemas["ExtractRequest"]["properties"]["prompt"]["maxLength"] = 100

    def value_gone(schemas, paths):
        schemas["ExplainRequest"]["properties"]["kind"]["anyOf"][1]["enum"].remove("why")

    def answer_field_gone(schemas, paths):
        schemas["ExplainResponse"]["required"].remove("text")

    def answer_type_changed(schemas, paths):
        schemas["Usage"]["properties"]["credits"]["type"] = "string"

    for change, expected in [
        (route_gone, "POST /v1/explain: gone"),
        (field_required, "POST /v1/explain request.language: now required"),
        (field_gone, "helps: gone (an old app still sends it)"),
        (limit_tightened, "prompt: maxLength tightened"),
        (value_gone, "kind: values no longer taken ['why']"),
        (answer_field_gone, "POST /v1/explain 200.text: no longer always there"),
        (answer_type_changed, "usage.credits: type integer → string"),
    ]:
        found = changed(change)
        assert any(expected in problem for problem in found), (change.__name__, found)


def test_what_an_old_app_doesnt_mind():
    def grown(schemas, paths):
        schemas["ExplainRequest"]["properties"]["tone"] = {"type": "string", "default": ""}  # optional
        schemas["ExplainResponse"]["properties"]["source"] = {"type": "string"}  # an answer field more
        schemas["ExplainResponse"]["required"].append("source")
        schemas["ExplainRequest"]["properties"]["kind"]["anyOf"][1]["enum"].append("story")  # a value more
        schemas["ExtractRequest"]["properties"]["prompt"]["maxLength"] *= 2  # a limit loosened
        paths["/v1/new"] = copy.deepcopy(paths["/v1/account"])  # a route more

    assert changed(grown) == []
