import os

import ccc
from fastapi import Depends

from api_swedeb.api.utils.corpus import Corpus
from api_swedeb.api.utils.kwic_corpus import KwicCorpus

shared_corpus = Corpus(".env_1960")
shared_kwic_corpus = KwicCorpus(".env_1960")


async def get_corpus():
    return Corpus(".env_1960")


async def get_kwic_corpus():
    return KwicCorpus(".env_1960")


def get_cwb_corpus_opts():
    return {
        "registry_dir": os.environ.get("CWB_REGISTRY_DIR"),
        "corpus_name": os.environ.get("CWB_CORPUS_NAME"),
    }


async def get_cwb_corpus(opts: dict = Depends(get_cwb_corpus_opts)) -> ccc.Corpus:
    return ccc.Corpora(opts.get("registry_dir")).corpus(opts.get("corpus_name"))
