"""What in the relay's API would break an app already released: core/relay-api-v1.json
(today's) against core/relay-api-releases/<version>.json (the API each released app
speaks, frozen at its release). A test runs it on every frozen version.

Usage: .venv/bin/python tools/relay_compat.py [old.json [new.json]]

Within /v1 the API only grows: new routes, new optional request fields, new answer
fields. Breaking:
- a route, a content type, an answer gone;
- in a request (what an old app sends): a field gone, a field made required, a type
  changed, a limit tightened, an allowed value gone;
- in an answer (what an old app reads): a field it relies on gone or optional, a type
  changed, a value it doesn't know.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CURRENT = ROOT / "core" / "relay-api-v1.json"
RELEASES = ROOT / "core" / "relay-api-releases"
# Request limits an old app may reach: they may grow, not shrink (and the minimums the other way)
LIMITS_UP = ("maxLength", "maxItems", "maximum", "exclusiveMaximum")
LIMITS_DOWN = ("minLength", "minItems", "minimum", "exclusiveMinimum")


def problems(old: dict, new: dict) -> list[str]:
    found: list[str] = []
    for path, operations in old["paths"].items():
        for method, operation in operations.items():
            where = f"{method.upper()} {path}"
            now = new["paths"].get(path, {}).get(method)
            if now is None:
                found.append(f"{where}: gone")
                continue
            for name in _required_parameters(now) - _required_parameters(operation):
                found.append(f"{where}: parameter {name} now required")
            for ctype, body in operation.get("requestBody", {}).get("content", {}).items():
                body_now = now.get("requestBody", {}).get("content", {}).get(ctype)
                if body_now is None:
                    found.append(f"{where}: request {ctype} no longer taken")
                else:
                    _compare(old, new, body["schema"], body_now["schema"], f"{where} request", reads=False, found=found)
            for status, answer in operation["responses"].items():
                answer_now = now["responses"].get(status)
                if answer_now is None:
                    found.append(f"{where}: answer {status} gone")
                    continue
                for header in answer.get("headers", {}):
                    if header not in answer_now.get("headers", {}):
                        found.append(f"{where}: answer {status} header {header} gone")
                for ctype, content in answer.get("content", {}).items():
                    content_now = answer_now.get("content", {}).get(ctype)
                    if content_now is None:
                        found.append(f"{where}: answer {status} {ctype} gone")
                    else:
                        _compare(
                            old,
                            new,
                            content["schema"],
                            content_now["schema"],
                            f"{where} {status}",
                            reads=True,
                            found=found,
                        )
    return found


def _required_parameters(operation: dict) -> set[str]:
    return {p["name"] for p in operation.get("parameters", []) if p.get("required")}


def _resolve(doc: dict, schema: dict) -> dict:
    while "$ref" in schema:
        schema = doc["components"]["schemas"][schema["$ref"].rsplit("/", 1)[-1]]
    return schema


def _values(schema: dict) -> dict:
    """A choice of fixed values as pydantic writes a Literal union (anyOf: [{const}, {enum}]):
    one {"type", "enum"}, so that a value added is told from a value gone."""
    options = schema.get("anyOf") or []
    if options and all("const" in o or "enum" in o for o in options) and len({o.get("type") for o in options}) == 1:
        values = [v for o in options for v in ([o["const"]] if "const" in o else o["enum"])]
        return {"type": options[0].get("type"), "enum": values}
    return schema


def _nullable(schema: dict) -> tuple[dict, bool]:
    """An optional value as pydantic writes it (anyOf: [x, {"type": "null"}]): x, True."""
    options = schema.get("anyOf")
    if options and len(options) == 2 and {"type": "null"} in options:
        return next(o for o in options if o != {"type": "null"}), True
    return schema, False


def _compare(old_doc, new_doc, old, new, where, reads, found, seen=None):
    """`reads`: an answer (the old app reads what the relay writes); else a request (the
    old app writes what the relay reads)."""
    seen = seen if seen is not None else set()
    key = (where, json.dumps(old, sort_keys=True), json.dumps(new, sort_keys=True))
    if key in seen:  # recursive schemas
        return
    seen.add(key)
    old, new = _resolve(old_doc, old), _resolve(new_doc, new)
    old, old_null = _nullable(old)
    new, new_null = _nullable(new)
    old, new = _values(_resolve(old_doc, old)), _values(_resolve(new_doc, new))
    if reads and new_null and not old_null:
        found.append(f"{where}: may now be null")
    if not reads and old_null and not new_null:
        found.append(f"{where}: null no longer taken")
    if "anyOf" in old or "anyOf" in new:
        if json.dumps(old.get("anyOf"), sort_keys=True) != json.dumps(new.get("anyOf"), sort_keys=True):
            found.append(f"{where}: choice of types changed")
        return
    if old.get("type") and new.get("type") and old["type"] != new["type"]:
        found.append(f"{where}: type {old['type']} → {new['type']}")
        return
    if "enum" in old or "enum" in new:
        before, after = set(old.get("enum", [])), set(new.get("enum", []))
        if not reads and "enum" in new and before - after:
            found.append(f"{where}: values no longer taken {sorted(before - after)}")
        if reads and after - before and "enum" in old:
            found.append(f"{where}: new values an old app doesn't know {sorted(after - before)}")
    if not reads:
        for limit in LIMITS_UP:
            if limit in new and (limit not in old or new[limit] < old[limit]):
                found.append(f"{where}: {limit} tightened")
        for limit in LIMITS_DOWN:
            if limit in new and (limit not in old or new[limit] > old[limit]):
                found.append(f"{where}: {limit} tightened")
    if "items" in old and "items" in new:
        _compare(old_doc, new_doc, old["items"], new["items"], f"{where}[]", reads, found, seen)
    old_props, new_props = old.get("properties", {}), new.get("properties", {})
    old_required, new_required = set(old.get("required", [])), set(new.get("required", []))
    if reads:
        for name in old_required:
            if name not in new_props or name not in new_required:
                found.append(f"{where}.{name}: no longer always there")
    else:
        for name in new_required - old_required:
            found.append(f"{where}.{name}: now required")
        for name in old_props:
            if name not in new_props and not new.get("additionalProperties"):
                found.append(f"{where}.{name}: gone (an old app still sends it)")
    for name in old_props.keys() & new_props.keys():
        _compare(old_doc, new_doc, old_props[name], new_props[name], f"{where}.{name}", reads, found, seen)


def main(args: list[str]) -> int:
    pairs = (
        [(Path(args[0]), Path(args[1]) if len(args) > 1 else CURRENT)]
        if args
        else [(release, CURRENT) for release in sorted(RELEASES.glob("*.json"))]
    )
    failed = False
    for old_path, new_path in pairs:
        found = problems(json.loads(old_path.read_text()), json.loads(new_path.read_text()))
        print(f"{old_path.name}: {'compatible' if not found else ''}")
        for problem in found:
            print(f"  - {problem}")
        failed |= bool(found)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
