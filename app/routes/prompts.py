from fastapi import APIRouter, Depends

from notosaurus_core import llm

from .. import i18n, prompts, settings, usage
from ..errors import AppError
from ..models import Prompt, PromptIn, RephraseRequest
from .common import page_lang

router = APIRouter()


# --- Prompts ---------------------------------------------------------------


@router.get("/api/prompts")
def list_prompts(lang: str = Depends(page_lang)) -> list[Prompt]:
    return prompts.list_all(lang)  # Notosaurus's prompts in this language, then the user's


@router.post("/api/prompts", status_code=201)
def add_prompt(c: PromptIn) -> Prompt:
    return prompts.add(c)


@router.put("/api/prompts/{id}")
def update_prompt(id: str, c: PromptIn) -> Prompt:
    if updated := prompts.update(id, c):
        return updated
    raise AppError("prompt.not_found", 404)


@router.delete("/api/prompts/{id}", status_code=204)
def delete_prompt(id: str) -> None:
    if not prompts.delete(id):
        raise AppError("prompt.not_found", 404)


@router.post("/api/prompts/{id}/duplicate", status_code=201)
def duplicate_prompt(id: str, lang: str = Depends(page_lang)) -> Prompt:
    """A copy of any prompt (Notosaurus's included), to adapt."""
    if copy := prompts.duplicate(id, lang):
        return copy
    raise AppError("prompt.not_found", 404)


@router.post("/api/prompt/rephrase")
async def rephrase_prompt(req: RephraseRequest, lang: str = Depends(page_lang)) -> dict:
    """The instructions being written, tidied up ("✨ Tidy up"): every intention kept, none added."""
    with llm.recording("rephrase") as calls:
        try:
            text = await llm.rephrase(settings.current(), req.text, i18n.language_name(lang))
        finally:
            usage.add(calls, None)  # in the costs, with no lesson
    return {"text": text}
