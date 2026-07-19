from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api import router
from app.config import AppConfig
from app.service import BridgeService
from app.version import __version__


FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


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
    app.include_router(router)
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
    return app


app = create_app()


def main() -> None:
    config = AppConfig()
    uvicorn.run(create_app(config), host="127.0.0.1", port=config.port)


if __name__ == "__main__":
    main()
