"""The relay's API (notosaurus_core.relay_api): in step with core's functions, its
OpenAPI description up to date, and workable as described."""

import importlib.util
import inspect
import json
from pathlib import Path

import pytest
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.testclient import TestClient
from pydantic import ValidationError

from notosaurus_core import llm, pictures
from notosaurus_core import relay_api as api
from notosaurus_core.config import AIConfig
from notosaurus_core.models import Card, Deck

ROOT = Path(__file__).parent.parent


def openapi_tool():
    spec = importlib.util.spec_from_file_location("relay_openapi", ROOT / "tools" / "relay_openapi.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_openapi_description_up_to_date():
    """core/relay-api-v1.json is what tools/relay_openapi.py writes: run it after
    changing relay_api.py."""
    assert (ROOT / "core" / "relay-api-v1.json").read_text(encoding="utf-8") == openapi_tool().text()


def parameters(function, *but: str) -> set[str]:
    return set(inspect.signature(function).parameters) - {"s", *but}


@pytest.mark.parametrize(
    ("request_model", "function", "not_sent"),
    [
        (api.ExtractRequest, llm.extract_cards, ("images", "on_card")),  # the multipart's "images"; on_card: not sent
        (api.ReviseRequest, llm.revise_cards, ("images", "demo")),  # demo: the relay never runs the demo AI
        (api.ExplainRequest, llm.explain_card, ()),
        (api.FigureRequest, llm.draw_figure, ()),
        (api.PictureRequest, pictures.picture, ()),
    ],
)
def test_each_request_is_its_core_function(request_model, function, not_sent):
    """A parameter added to a core function is added to its route too (or said not sent)."""
    assert set(request_model.model_fields) == parameters(function, *not_sent)


def test_answers_carry_core_results():
    for answer, result in [
        (api.ExtractResponse, llm.Extracted),
        (api.ReviseResponse, llm.Revision),
        (api.ExplainResponse, llm.Explanation),
    ]:
        assert set(answer.model_fields) == {*result.model_fields, "usage"}


def test_limits():
    assert api.ExtractRequest(prompt="Vocabulary").deck == ""
    for wrong in [
        {"prompt": ""},
        {"prompt": "x" * (api.MAX_PROMPT + 1)},
        {"prompt": "p", "page_texts": [""] * (api.MAX_IMAGES + 1)},
        {"prompt": "p", "instructions": "x" * (api.MAX_INSTRUCTIONS + 1)},
    ]:
        with pytest.raises(ValidationError):
            api.ExtractRequest(**wrong)
    with pytest.raises(ValidationError):
        api.ReviseRequest(prompt="p", deck=Deck(deck="D", cards=[]), instruction="")
    with pytest.raises(ValidationError):
        api.ExplainRequest(card=Card(front="a", back="b"), kind="joke", prompt="p", deck="D")


def test_openapi_description():
    spec = json.loads((ROOT / "core" / "relay-api-v1.json").read_text(encoding="utf-8"))
    assert set(spec["paths"]) == {
        f"/v1/{route}" for route in ("extract", "revise", "explain", "figure", "picture", "account")
    }
    for route, request in (("extract", "ExtractRequest"), ("revise", "ReviseRequest")):
        body = spec["paths"][f"/v1/{route}"]["post"]["requestBody"]["content"]["multipart/form-data"]
        assert body["schema"]["properties"]["request"]["$ref"] == f"#/components/schemas/{request}"
        assert body["encoding"]["request"]["contentType"] == "application/json"
        assert request in spec["components"]["schemas"]
    picture = spec["paths"]["/v1/picture"]["post"]["responses"]["200"]
    assert set(picture["content"]) == {"image/jpeg"} and api.CREDITS_LEFT_HEADER in picture["headers"]
    described = json.dumps(spec["paths"])
    assert all(f"`{code}`" in described for code in api.ERRORS)  # every error code, with its status
    assert "HTTPValidationError" not in described  # FastAPI's own 422 replaced by relay.invalid_request


def test_photos_and_request_in_one_multipart():
    """The routes with photos work as described: the JSON request in a part of its own,
    the photos as files. A minimal relay with the demo AI, called as a client would."""
    relay = FastAPI()

    @relay.post("/v1/extract")
    async def extract(request: str = Form(), images: list[UploadFile] = File([])) -> api.ExtractResponse:
        req = api.ExtractRequest.model_validate_json(request)
        photos = [llm.Image(await i.read(), i.content_type) for i in images]
        found = await llm.extract_cards(AIConfig(llm="fake"), photos, **req.model_dump())
        return api.ExtractResponse(**found.model_dump(), usage=api.Usage(credits=1, credits_left=99))

    request = api.ExtractRequest(prompt="FR → ES", decks=["Espagnol"], page_texts=["", ""])
    files = [
        ("request", (None, request.model_dump_json(), "application/json")),
        ("images", ("page-1.jpg", b"photo 1", "image/jpeg")),
        ("images", ("page-2.jpg", b"photo 2", "image/jpeg")),
    ]
    response = TestClient(relay).post("/v1/extract", files=files, headers={api.CLIENT_HEADER: "1.1.0"})
    assert response.status_code == 200
    answer = api.ExtractResponse.model_validate_json(response.content)
    assert answer.deck.cards and answer.turns == [0, 0] and answer.usage.credits_left == 99
