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

# Each service's first recommended model (recommended.py); a compatible service's
# depends on it: chosen in the admin page
DEFAULT_MODELS = {provider: recommended.default(recommended.CARDS, provider) for provider in PROVIDERS}


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
