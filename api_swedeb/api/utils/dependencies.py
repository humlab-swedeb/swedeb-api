from api_swedeb.api.utils.corpus import Corpus
from api_swedeb.api.utils.kwic_corpus import KwicCorpus


async def get_corpus():
    return Corpus(".env_1960")


async def get_kwic_corpus():
    return KwicCorpus(".env_1960")
