"""Claude, through the official Anthropic SDK (structured output)."""

import base64

from pydantic import BaseModel

from ..calls import ExtractionError, Image, record
from ..config import AIConfig
from ..prompts import SYSTEM_PROMPT


def _anthropic_client(s: AIConfig):
    import anthropic

    if not s.anthropic_api_key:
        raise ExtractionError("llm.missing_key", provider="Anthropic")
    return anthropic.AsyncAnthropic(api_key=s.anthropic_api_key)


async def _anthropic[T: BaseModel](
    s: AIConfig, images: list[Image], text: str, schema: type[T], system: str = SYSTEM_PROMPT
) -> T:
    import anthropic

    client = _anthropic_client(s)
    content = [
        {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": img.media_type,
                "data": base64.standard_b64encode(img.data).decode(),
            },
        }
        for img in images
    ]
    content.append({"type": "text", "text": text})

    try:
        response = await client.messages.parse(
            model=s.model_for_provider(),
            max_tokens=16000,
            system=system,
            messages=[{"role": "user", "content": content}],
            output_format=schema,
            # If the model refuses, the API reruns the request on a fallback model.
            extra_headers={"anthropic-beta": "server-side-fallback-2026-07-01"},
            extra_body={"fallbacks": "default"},
        )
    except anthropic.AuthenticationError as e:
        raise ExtractionError("llm.invalid_key", provider="Anthropic") from e
    except anthropic.RateLimitError as e:
        raise ExtractionError("llm.quota", provider="Anthropic") from e
    except anthropic.APIStatusError as e:
        raise ExtractionError("llm.api_error", provider="Anthropic", status=e.status_code, detail=e.message) from e
    except anthropic.APIConnectionError as e:
        raise ExtractionError("llm.unreachable", provider="Anthropic") from e

    if response.usage:
        await record(s, "anthropic", response.model, response.usage.input_tokens, response.usage.output_tokens)
    if response.stop_reason == "refusal":
        raise ExtractionError("llm.refused")
    if response.stop_reason == "max_tokens":
        raise ExtractionError("llm.truncated")
    if response.parsed_output is None:
        raise ExtractionError("llm.invalid_answer")
    return response.parsed_output
