import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.api import router
from app.config import AppConfig
from app.service import BridgeService
from app.version import __version__


FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
_FRONTEND_ASSET_SUFFIXES = {".css", ".js", ".html", ".svg", ".png"}


def _frontend_index_html() -> str:
    """Liefert das Frontend mit versionsgebundenen Asset-URLs.

    Ohne Cache-Busting kann der Browser nach einem Update weiterhin eine alte
    noema-ui.js laden. Dann zeigt die API zwar die neue Versionsnummer, aber die
    Oberfläche bleibt technisch auf dem alten Stand. Genau das soll hier
    dauerhaft ausgeschlossen werden.
    """
    html = (FRONTEND_DIR / "index.html").read_text(encoding="utf-8")
    version_query = f"?v={__version__}"

    for asset in ("style.css", "noema-theme.css", "app.js", "noema-ui.js"):
        html = html.replace(f'/{asset}"', f'/{asset}{version_query}"')

    if "kitt-header.css" not in html:
        marker = f'<link rel="stylesheet" href="/noema-theme.css{version_query}">'
        kitt_link = (
            f'{marker}\n'
            f'    <link rel="stylesheet" href="/kitt-header.css{version_query}" '
            'data-kitt-header>'
        )
        html = html.replace(marker, kitt_link)

    html = re.sub(
        r"<title>NOEMA Live Bridge v[^<]+</title>",
        f"<title>NOEMA Live Bridge v{__version__}</title>",
        html,
    )
    html = re.sub(
        r'(<span class="version-chip" id="app-version">)v[^<]+',
        rf"\1v{__version__}",
        html,
    )
    return html


def create_app(config: AppConfig | None = None) -> FastAPI:
    resolved_config = config or AppConfig()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        service = BridgeService(resolved_config)
        app.state.bridge = service
        await service.start()
        try:
            yield
        finally:
            await service.stop()

    app = FastAPI(
        title="NOEMA TikTok Live Chat Bridge",
        version=__version__,
        lifespan=lifespan,
    )

    @app.middleware("http")
    async def disable_frontend_cache(request: Request, call_next):
        response = await call_next(request)
        path = request.url.path
        if path == "/" or Path(path).suffix.lower() in _FRONTEND_ASSET_SUFFIXES:
            response.headers["Cache-Control"] = (
                "no-store, no-cache, must-revalidate, max-age=0"
            )
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

    app.include_router(router)

    @app.get("/", include_in_schema=False, response_class=HTMLResponse)
    async def frontend_index() -> HTMLResponse:
        return HTMLResponse(_frontend_index_html())

    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
    return app


app = create_app()


def main() -> None:
    config = AppConfig()
    uvicorn.run(create_app(config), host="127.0.0.1", port=config.port)


if __name__ == "__main__":
    main()
