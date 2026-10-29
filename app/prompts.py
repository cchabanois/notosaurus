"""Prompts: Notosaurus's own, and the user's.

- Notosaurus's prompts (their names and options: "builtinPrompts" in
  static/i18n/<lang>.json; their texts: static/prompts/<lang>/<key>.md): in the page's
  language, read-only, never deleted, improved with the app. Their ids are
  "notosaurus:<key>".
- The user's prompts, in data/prompts.json: added, changed, deleted, or copied from
  any prompt ("Duplicate") to be adapted.

data/prompts.json: {"user": [prompts], "builtin_used": {key: date}}. Before, it was
a list seeded once with the default prompts: read as the user's prompts, without the
old defaults left unchanged that a Notosaurus prompt now replaces.
"""

from . import i18n, storage
from .errors import AppError
from .models import Prompt, PromptIn

PREFIX = "notosaurus:"
# Their texts, one file per prompt and language; their names and options in the i18n files
PROMPTS_DIR = i18n.I18N_DIR.parent / "prompts"
BUILTIN = (
    "auto",
    "vocabulary",
    "sentences",
    "conjugation",
    "table",
    "questions",
    "dates",
    "definitions",
    "examples",
    "cloze",
    "quiz",
    "true_false",
    "methods",
    "formulas",
    "geometry",
    "diagram",
    "pictures",
    "blanks",
    "dictation",
    "dictation_gaps",
    "recitation",
)

# Old default prompts that a Notosaurus prompt covers: dropped when left unchanged.
# (The old "FR → ES" ones carry a Spanish voice and deck name: kept as the user's.)
REPLACED = {
    "Crée des cartes question → réponse pour réviser le contenu de la leçon (dates, définitions, notions clés). "
    "Questions courtes et précises, réponses brèves, en français.",
    # the same, before the interface had languages
    "Crée des cartes question → réponse pour réviser le contenu de la leçon (dates, définitions, notions clés). "
    "Questions courtes et précises, réponses brèves.",
    "Create question → answer cards to review the content of the lesson (dates, definitions, key ideas). "
    "Short, precise questions and brief answers, in English.",
}


class BuiltinPrompt(AppError):
    status = 403


def _path():
    return storage.data_dir() / "prompts.json"


# prompts.json's format; storage.migrate brings older files up to it
FORMAT = 1


def _format_1(data: dict) -> dict:
    """Format 0 → 1: before Notosaurus's prompts, the file was a list, seeded once with the
    default prompts: read as the user's prompts, without the old defaults left unchanged."""
    if "list" not in data:  # already {"user", "builtin_used"}, before formats
        return data
    return {"user": [p for p in data["list"] if p.get("text") not in REPLACED], "builtin_used": {}}


def _read() -> tuple[list[Prompt], dict[str, str]]:
    data = storage.read_json(_path())
    if data is None:
        return [], {}
    data = storage.migrate({"list": data} if isinstance(data, list) else data, "prompts", FORMAT, {0: _format_1})
    return [Prompt(**p) for p in data.get("user", [])], dict(data.get("builtin_used", {}))


def _write(user: list[Prompt], used: dict[str, str]) -> None:
    storage.write_json(_path(), {"format": FORMAT, "user": [p.model_dump() for p in user], "builtin_used": used})


def _builtins(lang: str, used: dict[str, str]) -> list[Prompt]:
    texts = i18n.get(lang, "builtinPrompts", {})
    return [
        Prompt(
            id=PREFIX + key,
            builtin=True,
            used_at=used.get(key),
            **PromptIn(**texts[key], text=text(lang, key)).model_dump(),
        )
        for key in BUILTIN
        if key in texts
    ]


def text(lang: str, key: str) -> str:
    """A Notosaurus prompt's text (static/prompts/<lang>/<key>.md), in English when that
    language has none."""
    for code in (lang, i18n.DEFAULT):
        path = PROMPTS_DIR / code / f"{key}.md"
        if path.is_file():
            return path.read_text(encoding="utf-8")
    return ""


def list_all(lang: str = i18n.DEFAULT) -> list[Prompt]:
    with storage.lock:
        user, used = _read()
    return [*_builtins(lang, used), *user]


def get(id: int | str, lang: str = i18n.DEFAULT) -> Prompt | None:
    return next((p for p in list_all(lang) if str(p.id) == str(id)), None)


def _user_id(id: int | str) -> int:
    """The id of a user prompt; Notosaurus's prompts can't be changed or deleted."""
    if str(id).startswith(PREFIX):
        raise BuiltinPrompt("prompt.builtin")
    try:
        return int(id)
    except ValueError as e:
        raise AppError("prompt.not_found", 404) from e


def add(p: PromptIn) -> Prompt:
    with storage.lock:
        user, used = _read()
        prompt = Prompt(id=max((int(x.id) for x in user), default=0) + 1, **p.model_dump())
        _write([*user, prompt], used)
    return prompt


def update(id: int | str, p: PromptIn) -> Prompt | None:
    user_id = _user_id(id)
    with storage.lock:
        user, used = _read()
        for i, old in enumerate(user):
            if old.id == user_id:
                user[i] = old.model_copy(update=p.model_dump())
                _write(user, used)
                return user[i]
    return None


def duplicate(id: int | str, lang: str = i18n.DEFAULT) -> Prompt | None:
    """A copy of any prompt (Notosaurus's or the user's), as a new user prompt to adapt."""
    source = get(id, lang)
    if source is None:
        return None
    name = i18n.get(lang, "app.editor.copyName", "{name} (copy)").format(name=source.name)
    return add(PromptIn(**{**source.model_dump(include=set(PromptIn.model_fields)), "name": name}))


def mark_used(id: int | str) -> None:
    """Remember when a prompt was last used, to list recent prompts first."""
    with storage.lock:
        user, used = _read()
        if str(id).startswith(PREFIX):
            used[str(id).removeprefix(PREFIX)] = storage.now()
        else:
            for p in user:
                if str(p.id) == str(id):
                    p.used_at = storage.now()
        _write(user, used)


def delete(id: int | str) -> bool:
    user_id = _user_id(id)
    with storage.lock:
        user, used = _read()
        kept = [p for p in user if p.id != user_id]
        if len(kept) == len(user):
            return False
        _write(kept, used)
    return True
