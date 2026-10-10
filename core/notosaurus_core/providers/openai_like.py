"""OpenAI itself, OpenRouter, and any OpenAI-compatible service at its address (Ollama,
LM Studio, Mistral…): the chat completions API with a JSON schema; the models a
service offers (list_models)."""

import base64
import json

from pydantic import BaseModel

from ..calls import ExtractionError, Image, record
from ..config import AIConfig
from ..prompts import SYSTEM_PROMPT


def _openai_service(s: AIConfig) -> str:
    """Short name of the OpenAI-like service for messages and costs: its host."""
    from urllib.parse import urlparse

    return urlparse(s.base_url()).netloc or s.base_url()


def _openai_base(s: AIConfig):
    import openai

    if not s.base_url():
        raise ExtractionError("llm.missing_url")
    # Local servers (Ollama, LM Studio) ignore the key but the SDK requires one.
    return openai.AsyncOpenAI(base_url=s.base_url(), api_key=s.api_key() or "none")


def _openai_client(s: AIConfig):
    if not s.model_for_provider():
        raise ExtractionError("llm.missing_model")
    if s.llm in ("openai", "openrouter") and not s.api_key():  # a compatible local server needs none
        raise ExtractionError("llm.missing_key", provider={"openai": "OpenAI", "openrouter": "OpenRouter"}[s.llm])
    return _openai_base(s)


def _error_message(body) -> str | None:
    """The human message in an error body, unwrapping {"error": {...}} and JSON
    nested in strings (Ollama: {"message": "{\"error\": {\"message\": …}}"})."""
    for _ in range(5):
        if isinstance(body, str):
            try:
                body = json.loads(body)
            except ValueError:
                return body
        if isinstance(body, dict):
            body = body.get("error") or body.get("message")
        else:
            return None
    return None


def _openai_error(e: Exception, s: AIConfig) -> ExtractionError:
    """Readable error for an OpenAI-compatible service failure."""
    import openai

    service = _openai_service(s)
    if isinstance(e, openai.APIConnectionError):
        return ExtractionError("llm.unreachable", provider=service)
    if isinstance(e, openai.AuthenticationError):
        return ExtractionError("llm.invalid_key", provider=service)
    if isinstance(e, openai.RateLimitError):
        return ExtractionError("llm.quota", provider=service)
    if isinstance(e, openai.APIStatusError):
        return ExtractionError(
            "llm.api_error", provider=service, status=e.status_code, detail=_error_message(e.body) or e.message
        )
    return ExtractionError("llm.api_error", provider=service, status="", detail=str(e))


def _usable(m) -> bool | None:
    """Whether an OpenAI-compatible /models entry fits Notosaurus (image input, and
    structured output when the service lists parameters); None if it says nothing."""
    extra = m.model_extra or {}
    parameters = extra.get("supported_parameters")  # OpenRouter
    if parameters is not None and "structured_outputs" not in parameters:
        return False  # can't be forced to answer in our JSON schema
    modalities = (extra.get("architecture") or {}).get("input_modalities")  # OpenRouter
    if modalities is not None:
        return "image" in modalities
    vision = (extra.get("capabilities") or {}).get("vision")  # Mistral
    return None if vision is None else bool(vision)


async def _local_vision_models(s: AIConfig) -> list[str] | None:
    """LM Studio and Ollama only describe their models in their own API, next to
    the OpenAI-compatible one: the vision models there, or None if not such a server."""
    from urllib.parse import urlparse

    import httpx

    root = s.base_url().rstrip("/").removesuffix("/v1")
    if urlparse(root).scheme != "http":  # local servers; cloud services answer in /models
        return None
    async with httpx.AsyncClient(timeout=10) as client:
        try:  # LM Studio: GET /api/v1/models → models[].capabilities.vision
            data = (await client.get(f"{root}/api/v1/models")).json()
            if isinstance(data.get("models"), list):
                return [m["key"] for m in data["models"] if (m.get("capabilities") or {}).get("vision")]
        except (httpx.HTTPError, ValueError, AttributeError, KeyError):
            pass
        try:  # Ollama: GET /api/tags, then POST /api/show per model → capabilities
            tags = (await client.get(f"{root}/api/tags")).json()["models"]
            vision = []
            for tag in tags:
                show = (await client.post(f"{root}/api/show", json={"model": tag["name"]})).json()
                if "vision" in show.get("capabilities", []):
                    vision.append(tag["name"])
            return vision
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            return None


async def list_models(s: AIConfig) -> dict:
    """Models of the OpenAI-compatible service, keeping those accepting images
    when the service tells (OpenRouter, Mistral, LM Studio, Ollama) — and
    structured output when it tells that too (OpenRouter).

    Returns {"models": [...], "vision_only": bool, "names": {id: name}}; vision_only is
    False when the service doesn't say (OpenAI): the admin test then tells for sure.
    The recommended ones are Notosaurus's own (recommended.py)."""
    import openai

    client = _openai_base(s)
    try:
        models = [m async for m in client.models.list()]
    except openai.OpenAIError as e:
        raise _openai_error(e, s) from e
    # OpenRouter's ":batch" variants: half price, answered up to hours later (the
    # providers' batch APIs). A lesson is waited for: never offered.
    models = [m for m in models if not m.id.endswith(":batch")]

    known = [_usable(m) for m in models]
    if any(k is not None for k in known):
        usable = [m for m, k in zip(models, known, strict=True) if k]
        return {
            "models": sorted(m.id for m in usable),
            "vision_only": True,
            "names": {m.id: name for m in usable if (name := (m.model_extra or {}).get("name"))},
        }
    local = await _local_vision_models(s) if s.llm == "compatible" else None
    if local is not None:
        return {"models": sorted(local), "vision_only": True, "names": {}}
    return {"models": sorted(m.id for m in models), "vision_only": False, "names": {}}


def _strict(schema: dict) -> dict:
    """The response schema as OpenAI's models require it ("strict"): every object closed
    (additionalProperties false) and every property required, the optional ones filled
    with their empty value by the model. Without it, GPT refuses the request: "Invalid
    schema for response_format… 'additionalProperties' is required to be supplied and to
    be false"."""

    def walk(node):
        if isinstance(node, dict):
            if "properties" in node:
                node["additionalProperties"] = False
                node["required"] = list(node["properties"])
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)
        return node

    return walk(json.loads(json.dumps(schema)))


def _openai_model(s: AIConfig) -> bool:
    """A model by OpenAI: with an OpenAI key, or through OpenRouter ("openai/…",
    "~openai/…-latest")."""
    return s.llm == "openai" or s.model_for_provider().lstrip("~").startswith("openai/")


async def _openai[T: BaseModel](
    s: AIConfig,
    images: list[Image],
    text: str,
    schema: type[T],
    system: str = SYSTEM_PROMPT,
    light: bool = False,
    quick: bool = False,
) -> T:
    """OpenAI-compatible providers: Ollama (qwen2.5vl, gemma3…), etc."""
    import openai

    client = _openai_client(s)
    content = [
        {
            "type": "image_url",
            "image_url": {"url": f"data:{img.media_type};base64,{base64.standard_b64encode(img.data).decode()}"},
        }
        for img in images
    ]
    content.append({"type": "text", "text": text})

    try:
        service = _openai_service(s)
        response = await client.chat.completions.create(
            model=s.model_for_provider(),
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": content},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {"name": schema.__name__.lower(), "schema": schema.model_json_schema()}
                if not _openai_model(s)
                else {"name": schema.__name__.lower(), "schema": _strict(schema.model_json_schema()), "strict": True},
            },
            # OpenRouter tells the exact cost of the call when asked
            # OpenRouter: the exact cost of the call; and, for a light task, as little
            # thinking as the model allows (a model that doesn't think ignores it)
            extra_body=(
                {"usage": {"include": True}, **({"reasoning": {"effort": EFFORT[light]}} if light or quick else {})}
                if s.llm == "openrouter"
                else None
            ),
        )
        usage = response.usage
        if usage:
            cost = (usage.model_extra or {}).get("cost")
            model = response.model or s.model_for_provider()
            await record(s, service, model, usage.prompt_tokens, usage.completion_tokens, cost)
        choice = response.choices[0]
        message = choice.message
        if getattr(message, "refusal", None) or getattr(choice, "finish_reason", "") == "content_filter":
            raise ExtractionError("llm.refused")
        return schema.model_validate(json.loads(message.content or ""))
    except openai.OpenAIError as e:
        raise _openai_error(e, s) from e
    except ValueError as e:  # invalid JSON, or JSON not matching the schema
        raise ExtractionError("llm.invalid_answer") from e


# OpenRouter's reasoning effort: a light task (True) as little as possible; a quick lesson, low
EFFORT = {True: "minimal", False: "low"}
