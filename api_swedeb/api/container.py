"""Application-scoped service container.

Example usage with FastAPI dependency injection:

```python
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request

from api_swedeb.api.container import AppContainer
from api_swedeb.api.services.search_service import SearchService


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.container = AppContainer.build()
    yield


def get_container(request: Request) -> AppContainer:
    return request.app.state.container


def get_search_service(
    container: AppContainer = Depends(get_container),
) -> SearchService:
    return container.search_service
```

This keeps route-level `Depends()` usage, but moves service lifecycle and
composition into one explicit app-scoped object instead of module globals.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from fastapi import Request

from api_swedeb.api.services.corpus_loader import CorpusLoader
from api_swedeb.api.services.download_service import DownloadService
from api_swedeb.api.services.kwic_service import KWICService
from api_swedeb.api.services.kwic_ticket_service import KWICTicketService
from api_swedeb.api.services.metadata_service import MetadataService
from api_swedeb.api.services.ngrams_service import NGramsService
from api_swedeb.api.services.search_service import SearchService
from api_swedeb.api.services.word_trends_service import WordTrendsService


@dataclass(slots=True)
class AppContainer:
    """Application-scoped service container for FastAPI app.state usage."""

    corpus_loader: CorpusLoader
    metadata_service: MetadataService
    word_trends_service: WordTrendsService
    ngrams_service: NGramsService
    search_service: SearchService
    kwic_service: KWICService
    kwic_ticket_service: KWICTicketService
    download_service: DownloadService

    @classmethod
    def build(cls) -> AppContainer:
        """Construct the default app-scoped service graph."""
        corpus_loader = CorpusLoader()
        return cls(
            corpus_loader=corpus_loader,
            metadata_service=MetadataService(corpus_loader),
            word_trends_service=WordTrendsService(corpus_loader),
            ngrams_service=NGramsService(),
            search_service=SearchService(corpus_loader),
            kwic_service=KWICService(corpus_loader),
            kwic_ticket_service=KWICTicketService(),
            download_service=DownloadService(),
        )


def get_container(request: Request) -> AppContainer:
    """Return the app-scoped service container stored on app.state."""
    container = getattr(request.app.state, "container", None)
    if container is None:
        raise RuntimeError("AppContainer is not initialized")
    return cast(AppContainer, container)
