"""The AI configuration: the service writing the cards, its model and key, and the
service drawing the pictures. The app keeps it with its other settings and passes
it to every call."""

from pydantic import BaseModel

from . import recommended

PROVIDERS = ("gemini", "anthropic", "openai", "openrouter", "compatible", "fake")

# The three providers speaking OpenAI's API: OpenAI itself, OpenRouter (every
# provider's models with one key), and any other compatible service at its address
# (Ollama, LM Studio, Mistral…).
OPENAI_URL = "https://api.openai.com/v1"
OPENROUTER_URL = "https://openrouter.ai/api/v1"
OPENAI_LIKE = ("openai", "openrouter", "compatible")

# The providers that hear a recording (a dictation): Gemini, and the demo (canned)
HEARS_AUDIO = ("gemini", "fake")

# Each service's first recommended model (recommended.py); a compatible service's
# depends on it: chosen in the admin page
DEFAULT_MODELS = {provider: recommended.default(recommended.CARDS, provider) for provider in PROVIDERS}


class GeminiRouting(BaseModel):
    """How Gemini's answer is waited for, and where else it is asked when a route stalls.
    A route: a Vertex AI location ("eu", "global"…) or "key" (the Gemini API, with
    gemini_api_key). The main one is `first`, else the config's own; `routes` are tried after it, the same
    model, before the fallback models (a busy region is often busy for every model).
    A route stalling `stalls` times within `window_s` rests `rest_s` seconds (every call
    goes to the next one), then one call tries it again. No `routes`: as before, the
    fallback models on the config's own route."""

    first: str = ""  # the route tried first ("": the config's own): the relay's switch to "key", Vertex AI kept behind
    routes: str = ""  # comma-separated, in order: e.g. "key" or "global,key"
    # The answer's first part (a lesson's first card): it comes once the model has thought,
    # whatever the number of pages (2026-11-11: 4-6 s quick, 9-14 s careful, 1 to 10
    # pages); then the stream silent this long: given up on. None: the provider's own
    # (providers/gemini.py's FIRST_PART_S, NEXT_PART_S)
    first_part_s: float | None = None
    first_part_quick_s: float | None = None
    next_part_s: float | None = None
    stalls: int = 3
    window_s: float = 300
    rest_s: float = 900
    # Another route is tried only this long after the call began: past it, the fallback
    # models answer (the wait never longer than with one route)
    budget_s: float = 90

    def route_names(self) -> list[str]:
        return [r.strip() for r in self.routes.split(",") if r.strip()]


class AIConfig(BaseModel):
    llm: str = "gemini"
    model: str = ""  # empty = the provider's default model
    # Gemini only, comma-separated: when the model is overloaded or has no quota left (a
    # free key has none for the latest models). Not flash-lite: it reads lessons badly.
    fallback_models: str = "gemini-3.5-flash"
    gemini_api_key: str = ""
    # Gemini through Google Cloud's Vertex AI instead of a key: the project, its region
    # ("global": any), the credentials from the environment (a service account on
    # Google Cloud, `gcloud auth application-default login` elsewhere)
    gemini_vertex_project: str = ""
    gemini_vertex_location: str = "global"
    gemini_routing: GeminiRouting = GeminiRouting()
    anthropic_api_key: str = ""
    openai_api_key: str = ""  # OpenAI itself
    openrouter_api_key: str = ""
    compatible_base_url: str = ""  # e.g. http://localhost:11434/v1 (Ollama)
    compatible_api_key: str = ""  # often none (local servers)
    # Card pictures: the service drawing them ("" = the cards' own when it draws, see
    # pictures.service; "none" = no pictures) and its model ("" = that service's default)
    picture_service: str = ""
    picture_model: str = ""
    # A card's picture showing a real thing (Card.picture_search): a free one found first
    # (stock.find, chosen by the cards' AI), drawn when none fits. False: always drawn
    picture_find: bool = True
    # Figures drawn with Typst when it is installed (figures_typst). False: as SVG by the AI
    # (the relay's figures.typst switch)
    typst: bool = True
    # Figures drawn at all (llm.made_figure). False: refused, relay.feature_off (the relay's
    # figures.draw switch)
    figures: bool = True

    def model_for_provider(self) -> str:
        return self.model.strip() or DEFAULT_MODELS.get(self.llm, "")

    def base_url(self) -> str:
        """Address of the OpenAI-like provider in use."""
        return {"openai": OPENAI_URL, "openrouter": OPENROUTER_URL}.get(self.llm, self.compatible_base_url.strip())

    def gemini_ready(self) -> bool:
        """Whether Gemini can be called: a key, or a Vertex AI project."""
        return bool(self.gemini_api_key.strip() or self.gemini_vertex_project.strip())

    def gemini_options(self) -> dict:
        """google-genai's Client options: Vertex AI when a project is set, else the key."""
        if self.gemini_vertex_project.strip():
            project, location = self.gemini_vertex_project.strip(), self.gemini_vertex_location.strip() or "global"
            return {"vertexai": True, "project": project, "location": location}
        return {"api_key": self.gemini_api_key}

    def gemini_route(self) -> str:
        """The config's own Gemini route: its Vertex AI location, or "key"."""
        if self.gemini_vertex_project.strip():
            return self.gemini_vertex_location.strip() or "global"
        return "key"

    def on_gemini_route(self, route: str) -> "AIConfig | None":
        """The config sent through another route (GeminiRouting); None when it can't be:
        "key" without a key, a location without a Vertex AI project."""
        if route == "key":
            if not self.gemini_api_key.strip():
                return None
            return self.model_copy(update={"gemini_vertex_project": ""})
        if not self.gemini_vertex_project.strip():
            return None
        return self.model_copy(update={"gemini_vertex_location": route})

    def api_key(self) -> str:
        """Key of the OpenAI-like provider in use."""
        return {
            "openai": self.openai_api_key,
            "openrouter": self.openrouter_api_key,
            "compatible": self.compatible_api_key,
        }.get(self.llm, "")


def configured(s: AIConfig) -> bool:
    """Whether the cards' AI service can be called: its key (or, for a compatible
    service, its address; for Gemini, a Vertex AI project) is set."""
    if s.llm == "fake":
        return True
    if s.llm == "compatible":
        return bool(s.compatible_base_url.strip())
    if s.llm == "gemini":
        return s.gemini_ready()
    return bool(getattr(s, f"{s.llm}_api_key", "").strip())
