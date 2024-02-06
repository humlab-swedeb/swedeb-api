from api_swedeb.schemas.ngrams_schema import NGramResult, NGramResultItem
from api_swedeb.api.utils.common_params import CommonQueryParams


def get_ngrams(search_term: str, commons: CommonQueryParams):
    ngram1 = NGramResultItem(ngram=f"{search_term}", count=1)
    ngram2 = NGramResultItem(ngram=f"{search_term} så", count=2)
    return NGramResult(ngram_list=[ngram1, ngram2])
