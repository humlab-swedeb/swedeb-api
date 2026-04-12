import os

import ccc
from fastapi import Depends
from loguru import logger

from api_swedeb.api.services.corpus_loader import CorpusLoader
from api_swedeb.api.services.download_service import DownloadService
from api_swedeb.api.services.kwic_service import KWICService
from api_swedeb.api.services.metadata_service import MetadataService
from api_swedeb.api.services.ngrams_service import NGramsService
from api_swedeb.api.services.search_service import SearchService
from api_swedeb.api.services.word_trends_service import WordTrendsService
from api_swedeb.core.configuration import ConfigValue
from api_swedeb.core.person_codecs import Codecs, PersonCodecs

__loader: CorpusLoader | None = None
__metadata_service: MetadataService | None = None
__word_trends_service: WordTrendsService | None = None
__ngrams_service: NGramsService | None = None
__search_service: SearchService | None = None
__kwic_service: KWICService | None = None
__download_service: DownloadService | None = None

# pylint: disable=global-statement


def get_corpus_loader() -> CorpusLoader:
    """Get the singleton CorpusLoader instance."""
    global __loader
    if __loader is None:
        __loader = CorpusLoader()
    return __loader


def get_metadata_service() -> MetadataService:
    """Get the singleton MetadataService instance."""
    global __metadata_service
    if __metadata_service is None:
        __metadata_service = MetadataService(get_corpus_loader())
    return __metadata_service


def get_word_trends_service() -> WordTrendsService:
    """Get the singleton WordTrendsService instance."""
    global __word_trends_service
    if __word_trends_service is None:
        __word_trends_service = WordTrendsService(get_corpus_loader())
    return __word_trends_service


def get_ngrams_service() -> NGramsService:
    """Get the singleton NGramsService instance."""
    global __ngrams_service
    if __ngrams_service is None:
        __ngrams_service = NGramsService()
    return __ngrams_service


def get_search_service() -> SearchService:
    """Get the singleton SearchService instance."""
    global __search_service
    if __search_service is None:
        __search_service = SearchService(get_corpus_loader())
    return __search_service


def get_download_service() -> DownloadService:
    """Get the singleton DownloadService instance."""
    global __download_service
    if __download_service is None:
        __download_service = DownloadService()
    return __download_service


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


def get_decoder_opts() -> dict[str, str | None]:
    return {
        "metadata_filename": ConfigValue("metadata.filename").resolve(),
    }


_corpus_codecs: PersonCodecs | Codecs | None = None


async def get_corpus_decoder(opts: dict = Depends(get_decoder_opts)) -> PersonCodecs | Codecs:
    global _corpus_codecs
    if _corpus_codecs is None:
        _corpus_codecs = PersonCodecs().load(source=opts.get("metadata_filename", ""))
    return _corpus_codecs


async def get_kwic_service() -> KWICService:
    """Get the KWICService instance with loader."""
    global __kwic_service
    if __kwic_service is None:
        __kwic_service = KWICService(get_corpus_loader())
    return __kwic_service
