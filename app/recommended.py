"""The models Notosaurus recommends, per service: the only list written by hand.

From the model benchmark (photos of real notebooks, two juries; card pictures
compared by eye), in order: the best value first, then better or safer at a higher
price. The first of each list is the service's default. Pinned versions, never the
"~…-latest" aliases: what was tested is what runs, at the price it was tested at.
A new version is tested before it replaces one here.

`cents`: what a lesson (cards) or a picture costs with it, in US cents, as measured.
`note`: a translation key (admin.recommended.notes.*) when the price alone says too little.
"""

from typing import NamedTuple


class Model(NamedTuple):
    id: str
    name: str
    cents: float
    note: str = ""


CARDS: dict[str, list[Model]] = {
    "gemini": [
        Model("gemini-3.8-flash", "Gemini 3.8 Flash", 1.3),  # 8.5/10, 8.7 on photos
        Model("gemini-3.5-flash", "Gemini 3.5 Flash", 3.8, "freeKey"),  # 8.2: a free key's model
    ],
    "anthropic": [
        Model("claude-sonnet-5-5", "Claude Sonnet 5.5", 3.2, "photos"),  # 8.35, 8.8 on photos, the fastest
        Model("claude-opus-5-5", "Claude Opus 5.5", 6.4),  # 8.5
    ],
    "openai": [
        Model("gpt-6.1-sol", "GPT-6.1 Sol", 2.1),  # 8.45
        Model("gpt-6-astra", "GPT-6 Astra", 10.3, "best"),  # 8.7, the best average
    ],
    "openrouter": [
        Model("google/gemini-3.8-flash", "Gemini 3.8 Flash", 1.3),
        Model("openai/gpt-6.1-sol", "GPT-6.1 Sol", 2.1),
        Model("anthropic/claude-sonnet-5.5", "Claude Sonnet 5.5", 3.2, "photos"),
        Model("anthropic/claude-opus-5.5", "Claude Opus 5.5", 6.4),
        Model("openai/gpt-6-astra", "GPT-6 Astra", 10.3, "best"),
    ],
}

PICTURES: dict[str, list[Model]] = {
    "openai": [  # its "low" quality: the cheapest pictures by far
        Model("gpt-image-2", "GPT Image 2", 0.6),
        Model("gpt-image-1-mini", "GPT Image 1 Mini", 0.2),
        Model("gpt-image-2.5-sunburst", "GPT Image 2.5 Sunburst", 0.6, "slower"),
    ],
    "openrouter": [
        Model("google/gemini-3.1-flash-lite-image", "Gemini 3.1 Flash-Lite Image", 3.4),
        Model("openai/gpt-5-image-mini", "GPT-5 Image Mini", 4.3, "slower"),
        Model("google/gemini-3.1-flash-image", "Gemini 3.1 Flash Image", 6.7),
    ],
    "gemini": [
        Model("gemini-3.1-flash-lite-image", "Gemini 3.1 Flash-Lite Image", 3.4),
        Model("gemini-3.1-flash-image", "Gemini 3.1 Flash Image", 6.7),
    ],
}

# Prices OpenRouter's list doesn't have (the costs are estimated from it): OpenAI's
# image models, US dollars per input and per output token (economize.cloud, 2026-10).
PRICES: dict[str, tuple[float, float]] = {
    "gpt-image-1-mini": (2.5e-6, 8e-6),
    "gpt-image-2": (8e-6, 30e-6),
    "gpt-image-2.5-flare": (8e-6, 30e-6),
    "gpt-image-2.5-sunburst": (8e-6, 30e-6),
}


def default(table: dict[str, list[Model]], service: str) -> str:
    """The service's default model: its first recommended one ("" when it has none)."""
    models = table.get(service)
    return models[0].id if models else ""


def view() -> dict:
    """For the settings page: the recommended models of each service, in order."""
    return {
        kind: {service: [m._asdict() for m in models] for service, models in table.items()}
        for kind, table in (("cards", CARDS), ("pictures", PICTURES))
    }
