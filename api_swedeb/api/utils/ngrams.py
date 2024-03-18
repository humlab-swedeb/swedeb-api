from api_swedeb.api.utils.common_params import CommonQueryParams
from api_swedeb.api.utils.kwic_corpus import KwicCorpus
from api_swedeb.schemas.ngrams_schema import NGramResult, NGramResultItem


def get_ngrams(search_term: str, commons: CommonQueryParams, corpus: KwicCorpus):
    # DUMMY DATA
    ngram1 = NGramResultItem(ngram=f"{search_term}", count=1)
    ngram2 = NGramResultItem(ngram=f"{search_term} Dummy", count=2)
    return NGramResult(ngram_list=[ngram1, ngram2])
