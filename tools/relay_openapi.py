"""Write core/relay-api-v1.json: the OpenAPI description of the relay's API, from
notosaurus_core.relay_api (a test checks it is up to date).

Usage: .venv/bin/python tools/relay_openapi.py

The routes below only describe the API (they answer nothing): the relay implements
them, with the same paths and models.
"""

import json
import sys
from pathlib import Path

from fastapi import FastAPI, Header
from fastapi.responses import Response
from pydantic.json_schema import models_json_schema

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "core"))

from notosaurus_core import relay_api as api  # noqa: E402

OUT = ROOT / "core" / "relay-api-v1.json"
REF = "#/components/schemas/{model}"


def errors(*codes: str) -> dict:
    """The error answers of a route, grouped by HTTP status."""
    by_status: dict[int, list[str]] = {}
    for code in codes:
        by_status.setdefault(api.ERRORS[code], []).append(code)
    return {
        status: {"model": api.Error, "description": "Codes: " + ", ".join(f"`{c}`" for c in found)}
        for status, found in sorted(by_status.items())
    }


COMMON = (
    "relay.invalid_request",
    "relay.invalid_key",
    "relay.no_credits",
    "relay.daily_limit",
    "relay.client_outdated",
    "relay.unavailable",
)
PHOTOS = (*COMMON, "relay.too_large", "relay.bad_image")


def multipart(request: type) -> dict:
    """The body of a route with photos: the JSON request, then the photos."""
    return {
        "requestBody": {
            "required": True,
            "content": {
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "required": ["request"],
                        "properties": {
                            "request": {"$ref": REF.format(model=request.__name__)},
                            "images": {
                                "type": "array",
                                "maxItems": api.MAX_IMAGES,
                                "items": {"type": "string", "format": "binary"},
                                "description": f"The photos, in order: {', '.join(api.IMAGE_TYPES)}, "
                                f"at most {api.MAX_IMAGE_BYTES // (1024 * 1024)} MB each.",
                            },
                        },
                    },
                    "encoding": {
                        "request": {"contentType": "application/json"},
                        "images": {"contentType": ", ".join(api.IMAGE_TYPES)},
                    },
                }
            },
        }
    }


def build() -> dict:
    app = FastAPI(
        title="Notosaurus relay",
        version="1",
        summary="notosaurus_core behind a licence key",
        description=api.__doc__,
        separate_input_output_schemas=False,
    )
    client = Header(alias=api.CLIENT_HEADER, description='The client\'s version ("1.1.0").')

    @app.post(
        f"{api.PREFIX}/extract",
        response_model=api.ExtractResponse,
        responses={
            200: {
                "description": f'The cards; asked with "Accept: {api.STREAM_TYPE}": as the AI writes them, '
                "one ExtractLine per line.",
                "content": {api.STREAM_TYPE: {"schema": {"$ref": REF.format(model="ExtractLine")}}},
            },
            **errors(*PHOTOS),
        },
        openapi_extra=multipart(api.ExtractRequest),
    )
    def extract(x_notosaurus_version: str = client):
        """Cards from the photos of a lesson (llm.extract_cards)."""

    @app.post(
        f"{api.PREFIX}/revise",
        response_model=api.ReviseResponse,
        responses=errors(*PHOTOS),
        openapi_extra=multipart(api.ReviseRequest),
    )
    def revise(x_notosaurus_version: str = client):
        """A natural-language correction of the cards (llm.revise_cards)."""

    @app.post(f"{api.PREFIX}/explain", response_model=api.ExplainResponse, responses=errors(*COMMON))
    def explain(request: api.ExplainRequest, x_notosaurus_version: str = client):
        """A card explained to the pupil (llm.explain_card)."""

    @app.post(f"{api.PREFIX}/figure", response_model=api.FigureResponse, responses=errors(*COMMON))
    def figure(request: api.FigureRequest, x_notosaurus_version: str = client):
        """An exact figure as SVG (llm.draw_figure)."""

    credit_headers = {
        api.CREDITS_HEADER: {"description": "Credits this call used.", "schema": {"type": "integer"}},
        api.CREDITS_LEFT_HEADER: {"description": "Credits left in this period.", "schema": {"type": "integer"}},
    }

    @app.post(
        f"{api.PREFIX}/picture",
        response_class=Response,
        responses={
            200: {
                "description": "The picture, card size.",
                "content": {"image/jpeg": {"schema": {"type": "string", "format": "binary"}}},
                "headers": credit_headers,
            },
            **errors(*COMMON),
        },
    )
    def picture(request: api.PictureRequest, x_notosaurus_version: str = client):
        """A picture for a card (pictures.picture)."""

    @app.post(
        f"{api.PREFIX}/speak",
        response_class=Response,
        responses={
            200: {
                "description": "The text read aloud.",
                "content": {"audio/mpeg": {"schema": {"type": "string", "format": "binary"}}},
                "headers": credit_headers,
            },
            **errors(*COMMON),
        },
    )
    def speak(request: api.SpeakRequest, x_notosaurus_version: str = client):
        """A card's back read aloud with one of /v1/voices."""

    @app.get(
        f"{api.PREFIX}/voices",
        response_model=list[api.Voice],
        responses=errors("relay.invalid_key", "relay.client_outdated", "relay.unavailable"),
    )
    def voices(x_notosaurus_version: str = client):
        """The voices /v1/speak reads with."""

    @app.get(
        f"{api.PREFIX}/account",
        response_model=api.Account,
        responses=errors("relay.invalid_key", "relay.client_outdated", "relay.unavailable"),
    )
    def account(x_notosaurus_version: str = client):
        """What the licence gives; also the connection test."""

    schema = app.openapi()
    # Requests that aren't the API's are answered like any error (relay.invalid_request)
    for path in schema["paths"].values():
        for operation in path.values():
            operation["responses"]["422"] = {
                "description": "Codes: `relay.invalid_request`",
                "content": {"application/json": {"schema": {"$ref": REF.format(model="Error")}}},
            }
    for name in ("HTTPValidationError", "ValidationError"):
        schema["components"]["schemas"].pop(name, None)
    # The multipart requests, which FastAPI doesn't see (they are in openapi_extra)
    _, found = models_json_schema(
        [(api.ExtractRequest, "validation"), (api.ReviseRequest, "validation"), (api.ExtractLine, "serialization")],
        ref_template=REF,
    )
    for name, model in found["$defs"].items():
        schema["components"]["schemas"].setdefault(name, model)
    schema["components"]["schemas"] = dict(sorted(schema["components"]["schemas"].items()))
    schema["components"]["securitySchemes"] = {"licence": {"type": "http", "scheme": "bearer"}}
    schema["security"] = [{"licence": []}]
    return schema


def text() -> str:
    return json.dumps(build(), ensure_ascii=False, indent=2) + "\n"


if __name__ == "__main__":
    OUT.write_text(text(), encoding="utf-8")
    print(OUT)
