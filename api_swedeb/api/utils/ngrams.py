from typing import Any, Literal

import pandas as pd
from api_swedeb.api.utils.common_params import CommonQueryParams
from api_swedeb.api.utils.kwic_corpus import KwicCorpus

from api_swedeb import mappers
from api_swedeb.core import n_grams
from api_swedeb import schemas


def get_ngrams(
    search_term: str,
    commons: CommonQueryParams,
    corpus: Any | KwicCorpus,
    n_gram_width: int = 2,
    n_threshold: int = 2,
    search_target: Literal["word", "lemma"] = "word",
    display_target: Literal["word", "lemma"] = "word",
) -> schemas.NGramResult:

    if isinstance(corpus, KwicCorpus):
        corpus = corpus.load_kwic_corpus()

    # attribs: cwb.CorpusAttribs = n_grams.cwb(corpus)
    opts: dict[str, Any] = mappers.query_params_to_CQP_opts(commons, [(search_term, search_target)])
    ngrams: pd.DataFrame = n_grams.compute_n_grams(
        corpus, opts, n=n_gram_width, p_show=display_target, threshold=n_threshold
    )

    return mappers.ngrams_to_ngram_result(ngrams)
