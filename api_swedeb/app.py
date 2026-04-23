import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from api_swedeb.api.container import AppContainer
from api_swedeb.api.services.result_store import ResultStore
from api_swedeb.api.v1.endpoints import metadata_router, tool_router
from api_swedeb.core.configuration import ConfigValue, get_config_store

# pylint: disable=import-outside-toplevel
DEFAULT_CONFIG_SOURCE = os.environ.get("SWEDEB_CONFIG_PATH", "config/config.yml")


def create_app(*, config_source: str | None = DEFAULT_CONFIG_SOURCE, static_dir: str | None = None) -> FastAPI:
    if config_source is not None:
        get_config_store().configure_context(source=config_source)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        from loguru import logger  # type: ignore[import]

        if ConfigValue("development.celery_enabled", default=False).resolve():
            from api_swedeb.celery_app import configure_celery  # type: ignore[import]

            configure_celery()

        logger.info("Building AppContainer and pre-loading corpus resources...")
        import time

        start = time.perf_counter()
        app.state.container = AppContainer.build()

        # Eager-load expensive corpus resources at startup instead of on first request
        # This moves the ~71s cold-cache load from first request to app startup
        _ = app.state.container.corpus_loader.vectorized_corpus  # ~3.8s warm, ~71s cold
        _ = app.state.container.corpus_loader.person_codecs  # Fast
        _ = app.state.container.corpus_loader.document_index  # Fast (already loaded with corpus)

        elapsed = time.perf_counter() - start
        logger.info(f"Corpus resources loaded in {elapsed:.2f}s")

        result_store = ResultStore.from_config()
        await result_store.startup()
        app.state.result_store = result_store
        try:
            yield
        finally:
            await result_store.shutdown()

    app = FastAPI(lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=ConfigValue("fastapi.origins").resolve(),
        allow_methods=["GET", "POST"],
        allow_headers=[],
        allow_credentials=True,
    )

    app.include_router(tool_router.router)
    app.include_router(metadata_router.router)

    @app.get("/public/index.html", include_in_schema=False)
    async def redirect_legacy_entrypoint():
        """Redirect old /public/index.html bookmarks to the root URL."""
        return RedirectResponse(url="/", status_code=301)

    if static_dir is not None:
        # Mounted last so API routes take precedence.
        # html=True enables SPA fallback: unknown paths return index.html (required for history-mode routing).
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

    return app
