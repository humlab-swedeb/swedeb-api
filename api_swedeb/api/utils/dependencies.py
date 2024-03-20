import os

import ccc
from fastapi import Depends

from api_swedeb.api import parlaclarin as md
from api_swedeb.api.utils.corpus import Corpus

shared_corpus = Corpus(".env_1960")


async def get_corpus():
    return Corpus(".env_1960")


def get_cwb_corpus_opts() -> dict[str, str | None]:
    return {
        "registry_dir": os.environ.get("KWIC_DIR"),
        "corpus_name": os.environ.get("KWIC_CORPUS_NAME"),
        "data_dir": (
            os.getenv("KWIC_TEMP_DIR") or f"/tmp/ccc-{str(ccc.__version__)}-{os.environ.get('USER', 'swedeb')}"
        ),
    }


async def get_cwb_corpus(opts: dict = Depends(get_cwb_corpus_opts)) -> ccc.Corpus:
    return ccc.Corpora(registry_dir=opts.get("registry_dir")).corpus(
        corpus_name=opts.get("corpus_name"), data_dir=opts.get("data_dir")
    )


def get_decoder_opts() -> dict[str, str | None]:
    return {
        "metadata_filename": os.getenv("METADATA_FILENAME"),
    }


_corpus_codecs: md.Codecs = None


async def get_corpus_decoder(opts: dict = Depends(get_decoder_opts)) -> ccc.Corpus:
    global _corpus_codecs
    if _corpus_codecs is None:
        _corpus_codecs = md.PersonCodecs().load(source=opts.get("metadata_filename"))
    return _corpus_codecs
