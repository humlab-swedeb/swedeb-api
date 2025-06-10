import os

import ccc
from fastapi import Depends
from loguru import logger

from api_swedeb.api import parlaclarin as md
from api_swedeb.api.utils.corpus import Corpus
from api_swedeb.core.configuration import ConfigValue

__shared_corpus: Corpus = None


def get_shared_corpus() -> Corpus:
    global __shared_corpus
    if __shared_corpus is None:
        __shared_corpus = Corpus()
    return __shared_corpus


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


def get_cwb_corpus(opts: dict = None) -> ccc.Corpus:
    opts: dict = opts or get_cwb_corpus_opts()
    registry_dir = opts.get("registry_dir")
    logger.info(f"Registry dir is {registry_dir}")
    logger.info(f"Exists on disk? {os.path.isdir(registry_dir)}")
    return ccc.Corpora(registry_dir=registry_dir).corpus(
        corpus_name=opts.get("corpus_name"), data_dir=opts.get("data_dir")
    )


def get_decoder_opts() -> dict[str, str | None]:
    return {
        "metadata_filename": ConfigValue("metadata.filename").resolve(),
    }


_corpus_codecs: md.Codecs = None


async def get_corpus_decoder(opts: dict = Depends(get_decoder_opts)) -> ccc.Corpus:
    global _corpus_codecs
    if _corpus_codecs is None:
        _corpus_codecs = md.PersonCodecs().load(source=opts.get("metadata_filename"))
    return _corpus_codecs
