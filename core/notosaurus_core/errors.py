"""Errors shown to the user, as a code + parameters: the page translates them.

The server never builds user-facing sentences; `code` is looked up under
"errors" in the app's translations (static/i18n/<lang>.json, e.g.
"gemini.overloaded"), with `params` filling the {placeholders}.
"""


class AppError(Exception):
    status = 400  # HTTP status of the response

    # `http_status`, not `status`: messages use {status} for the provider's own
    # error code, passed in **params.
    def __init__(self, code: str, http_status: int | None = None, **params):
        super().__init__(code)
        self.code = code
        self.params = params
        if http_status is not None:
            self.status = http_status

    def detail(self) -> dict:
        return {"code": self.code, "params": self.params}

    def __str__(self) -> str:  # tests
        return f"{self.code} {self.params}" if self.params else self.code


def loggable(e: BaseException) -> str:
    """What a log line may say of an error: its code (and a provider's numeric status), or
    its type, never its message nor its text params. The relay's logs hold nothing of a
    lesson, and a message can carry one (a subject, a card's text, a provider's detail
    quoting the prompt)."""
    if isinstance(e, AppError):
        status = e.params.get("status")
        return f"{e.code} ({status})" if isinstance(status, int) else e.code
    return type(e).__name__
