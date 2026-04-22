import os
from typing import cast

import ccc
from fastapi import Depends, Request
from loguru import logger

from api_swedeb.api.container import AppContainer, get_container
from api_swedeb.api.services.corpus_loader import CorpusLoader
from api_swedeb.api.services.download_service import DownloadService
from api_swedeb.api.services.kwic_service import KWICService
from api_swedeb.api.services.kwic_ticket_service import KWICTicketService
from api_swedeb.api.services.metadata_service import MetadataService
from api_swedeb.api.services.ngrams_service import NGramsService
from api_swedeb.api.services.result_store import ResultStore
from api_swedeb.api.services.search_service import SearchService
from api_swedeb.api.services.word_trend_speeches_ticket_service import WordTrendSpeechesTicketService
from api_swedeb.api.services.word_trends_service import WordTrendsService
from api_swedeb.core.configuration import ConfigValue
from api_swedeb.core.person_codecs import Codecs, PersonCodecs


def get_corpus_loader(container: AppContainer = Depends(get_container)) -> CorpusLoader:
    """Get the app-scoped CorpusLoader instance."""
    return container.corpus_loader


def get_metadata_service(container: AppContainer = Depends(get_container)) -> MetadataService:
    """Get the app-scoped MetadataService instance."""
    return container.metadata_service


def get_word_trends_service(container: AppContainer = Depends(get_container)) -> WordTrendsService:
    """Get the app-scoped WordTrendsService instance."""
    return container.word_trends_service


def get_ngrams_service(container: AppContainer = Depends(get_container)) -> NGramsService:
    """Get the app-scoped NGramsService instance."""
    return container.ngrams_service


def get_search_service(container: AppContainer = Depends(get_container)) -> SearchService:
    """Get the app-scoped SearchService instance."""
    return container.search_service


def get_kwic_ticket_service(container: AppContainer = Depends(get_container)) -> KWICTicketService:
    return container.kwic_ticket_service


def get_word_trend_speeches_ticket_service(
    container: AppContainer = Depends(get_container),
) -> WordTrendSpeechesTicketService:
    return container.word_trend_speeches_ticket_service


def get_download_service(container: AppContainer = Depends(get_container)) -> DownloadService:
    """Get the app-scoped DownloadService instance."""
    return container.download_service


def get_cwb_corpus_opts() -> dict[str, str | None]:
    if ConfigValue("cwb.registry_dir").resolve() is None:
        raise ValueError("CWB registry directory not set")
    return {
        "registry_dir": ConfigValue("cwb.registry_dir").resolve(),
        "corpus_name": ConfigValue("cwb.corpus_name").resolve(),
        "data_dir": (
            ConfigValue("cwb.data_dir").resolve()
            or f"/tmp/ccc-{str(ccc.__version__)}-{os.environ.get('USER', 'swedeb')}"
        ),
    }


def get_cwb_corpus(opts: dict | None = None) -> ccc.Corpus:
    opts = opts or get_cwb_corpus_opts()
    registry_dir: str = opts.get("registry_dir") or ""
    logger.info(f"Registry dir is {registry_dir}")
    logger.info(f"Exists on disk? {os.path.isdir(registry_dir)}")
    return ccc.Corpora(registry_dir=registry_dir).corpus(
        corpus_name=opts.get("corpus_name"), data_dir=opts.get("data_dir")
    )


def get_corpus_decoder(container: AppContainer = Depends(get_container)) -> PersonCodecs | Codecs:
    return container.corpus_loader.person_codecs


def get_kwic_service(container: AppContainer = Depends(get_container)) -> KWICService:
    """Get the app-scoped KWICService instance."""
    return container.kwic_service


def get_result_store(request: Request) -> ResultStore:
    result_store = getattr(request.app.state, "result_store", None)
    if result_store is None:
        raise RuntimeError("ResultStore is not initialized")
    return cast(ResultStore, result_store)
