import logging
import re
from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv()  # before the app imports, some of which read variables at import time

from fastapi import FastAPI
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from . import settings, sounds
from .errors import AppError
from .hosts import KnownHostsOnly
from .routes import admin, anki, children, devices, exams, generation, lessons, pages, pictures, prompts, voices
from .routes.common import STATIC_DIR
from .version import VERSION

log = logging.getLogger("notosaurus")

# The pairing token, in the QR code's address (…/?k=<token>), would otherwise be written
# in clear in the server's log by each request: the log is shown from Anki's menu and
# pasted in bug reports. Masked in uvicorn's access lines.
TOKEN_IN_URL = re.compile(r"([?&]k=)[^&\s#]*")


class HideDeviceToken(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, tuple):
            record.args = tuple(TOKEN_IN_URL.sub(r"\1•••", a) if isinstance(a, str) else a for a in record.args)
        if isinstance(record.msg, str):
            record.msg = TOKEN_IN_URL.sub(r"\1•••", record.msg)
        return True


logging.getLogger("uvicorn.access").addFilter(HideDeviceToken())


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.warning("Notosaurus %s, LLM provider: %s", VERSION, settings.current().llm)
    yield
    await sounds.stop()  # the sounds being made ahead


app = FastAPI(title="Notosaurus", version=VERSION, lifespan=lifespan)
app.middleware("http")(devices.paired_devices_only)
app.add_middleware(KnownHostsOnly)  # added last: runs first, for every route and file


@app.exception_handler(AppError)
async def app_error(request, e: AppError) -> JSONResponse:
    # The page translates {"code", "params"} (static/i18n/<lang>.json, "errors").
    return JSONResponse(status_code=e.status, content={"detail": e.detail()})


class PageFiles(StaticFiles):
    """The page's files, revalidated on every load (ETag: a cheap 304 when unchanged).
    Without it, browsers keep old copies after an update: new HTML with old
    translations or styles."""

    def file_response(self, *args, **kwargs) -> Response:
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "no-cache"
        return response


for module in (pages, prompts, generation, anki, lessons, pictures, voices, admin, children, exams):
    app.include_router(module.router)
app.mount("/", PageFiles(directory=STATIC_DIR, html=True), name="static")
