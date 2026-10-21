"""What an AI call costs, estimated from public prices.

The providers' APIs say how many tokens a call used, not its price (OpenRouter
excepted: it gives the exact cost). The estimate uses OpenRouter's public model
list, which has the prices of Google, Anthropic and OpenAI models: no table to
keep up to date by hand. Fetched at most once a day, kept in the cache (files.py).
"""

import logging
import re
import time

import httpx

from . import files, recommended

log = logging.getLogger("notosaurus")

MODELS_URL = "https://openrouter.ai/api/v1/models"
MAX_AGE = 24 * 3600
_transport: httpx.AsyncBaseTransport | None = None  # tests plug a fake list here

# Provider in the settings → prefix of its models in OpenRouter's list
PREFIXES = {"gemini": "google/", "anthropic": "anthropic/", "openai": "openai/"}


def _cache_path():
    return files.cache_dir("model-prices.json")


async def _prices() -> dict[str, tuple[float, ...]]:
    """Model id → (price of an input token, of an output token[, of an output image's
    token]), in US dollars: an image model draws at its own, far higher price."""
    path = _cache_path()
    cached = files.read_json(path)
    if cached and time.time() - cached.get("at", 0) < MAX_AGE:
        return {k: tuple(v) for k, v in cached["prices"].items()}
    try:
        async with httpx.AsyncClient(timeout=5, transport=_transport) as client:
            response = await client.get(MODELS_URL)
            response.raise_for_status()
            models = response.json()["data"]
        prices = {m["id"]: _price(m["pricing"]) for m in models if m.get("pricing", {}).get("prompt") is not None}
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as e:
        log.warning("Model prices unavailable: %s", e)
        return {k: tuple(v) for k, v in (cached or {}).get("prices", {}).items()}  # older prices, or none
    files.write_json(path, {"at": time.time(), "prices": prices})
    return prices


def _price(pricing: dict) -> tuple[float, ...]:
    """A model's prices in OpenRouter's list: its image output's when it draws."""
    price = (float(pricing["prompt"]), float(pricing["completion"]))
    return (*price, float(pricing["image_output"])) if pricing.get("image_output") else price


def _candidates(provider: str, model: str) -> list[str]:
    """Ids the model may have in OpenRouter's list ("claude-sonnet-4-6" is listed as
    "anthropic/claude-sonnet-4.6"; an OpenRouter model is already an id)."""
    model = model.strip().removeprefix("models/")
    ids = [model] if "/" in model else []
    prefix = PREFIXES.get(provider, "")
    ids += [prefix + model, prefix + re.sub(r"(\d)-(\d)", r"\1.\2", model)]
    return ids


async def estimate(
    provider: str, model: str, input_tokens: int, output_tokens: int, image_tokens: int = 0
) -> float | None:
    """Estimated cost of a call in US dollars; None if the model's price is unknown.
    `image_tokens`: those of the output that are a picture drawn."""
    prices = await _prices()
    known = [prices.get(model_id) for model_id in _candidates(provider, model)]
    # Not in OpenRouter's list (OpenAI's image models): the prices written in Notosaurus
    known.append(recommended.PRICES.get(re.sub(r"-\d{4}-\d{2}-\d{2}$", "", model.strip())))
    for price in known:
        if price:
            price_in, price_out, price_image = (*price, price[1])[:3]  # no image price: the output's
            text = output_tokens - image_tokens
            return round(input_tokens * price_in + text * price_out + image_tokens * price_image, 6)
    return None
