"""Jobcu's local web server: serves the Jobcu screen and its internal API.

It only ever listens on this computer (127.0.0.1). Extra checks stop other
websites open in the same browser from using Jobcu behind the user's back.
"""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from jobcu import COPYRIGHT, __version__
from jobcu.documents_api import router as documents_router
from jobcu.paths import data_dir
from jobcu.settings_api import router as settings_router

WEB_DIR = Path(__file__).resolve().parent / "web"

# Requests must be addressed to this computer by name. This blocks
# "DNS rebinding", where a website pretends to be 127.0.0.1.
LOCAL_HOSTS = ["127.0.0.1", "localhost"]

# Anything that changes data must come from Jobcu's own page. Other websites
# can't add this header without the browser asking Jobcu first (and Jobcu
# never agrees), and the Origin check catches the rest.
UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
REQUEST_HEADER = "X-Jobcu"

SECURITY_HEADERS = {
    # Only load files from Jobcu itself: no outside scripts, fonts or trackers.
    "Content-Security-Policy": (
        "default-src 'self'; img-src 'self' data:; object-src 'none'; "
        "base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
    ),
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
}


def create_app() -> FastAPI:
    app = FastAPI(
        title="Jobcu",
        version=__version__,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    @app.middleware("http")
    async def protect_local_app(request: Request, call_next):
        if request.method in UNSAFE_METHODS:
            origin = request.headers.get("origin")
            host = request.headers.get("host", "")
            if request.headers.get(REQUEST_HEADER) != "1" or (
                origin is not None and origin != f"http://{host}"
            ):
                return JSONResponse(
                    {"error": "This request didn't come from the Jobcu page."},
                    status_code=403,
                )
        response = await call_next(request)
        for name, value in SECURITY_HEADERS.items():
            response.headers.setdefault(name, value)
        return response

    # Added last so it runs first.
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=LOCAL_HOSTS)

    @app.get("/api/health")
    def health() -> dict:
        return {"app": "jobcu", "version": __version__}

    @app.get("/api/about")
    def about() -> dict:
        return {
            "version": __version__,
            "copyright": COPYRIGHT,
            "data_folder": str(data_dir()),
        }

    app.include_router(settings_router)
    app.include_router(documents_router)

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(WEB_DIR / "index.html")

    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")
    return app
