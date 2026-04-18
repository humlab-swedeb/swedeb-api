import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api_swedeb.api.container import AppContainer
from api_swedeb.api.services.result_store import ResultStore
from api_swedeb.api.v1.endpoints import metadata_router, tool_router
from api_swedeb.core.configuration import ConfigValue, get_config_store

DEFAULT_CONFIG_SOURCE = os.environ.get("SWEDEB_CONFIG_PATH", "config/config.yml")


def create_app(*, config_source: str | None = DEFAULT_CONFIG_SOURCE, static_dir: str | None = None) -> FastAPI:
    if config_source is not None:
        get_config_store().configure_context(source=config_source)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.container = AppContainer.build()
        result_store = ResultStore.from_config()
        await result_store.startup()
        app.state.result_store = result_store
        try:
            yield
        finally:
            await result_store.shutdown()

    app = FastAPI(lifespan=lifespan)

    if static_dir is not None:
        app.mount("/public", StaticFiles(directory=static_dir), name="public")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=ConfigValue("fastapi.origins").resolve(),
        allow_methods=["GET", "POST"],
        allow_headers=[],
        allow_credentials=True,
    )

    app.include_router(tool_router.router)
    app.include_router(metadata_router.router)

    return app
