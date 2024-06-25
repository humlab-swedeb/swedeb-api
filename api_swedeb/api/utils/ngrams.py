from typing import Any, Literal

import pandas as pd

from api_swedeb import mappers, schemas
from api_swedeb.api.utils.common_params import CommonQueryParams
from api_swedeb.core import n_grams


def get_ngrams(
    search_term: str,
    commons: CommonQueryParams,
    corpus: Any,
    n_gram_width: int = 2,
    n_threshold: int = 2,
    search_target: Literal["word", "lemma"] = "word",
    display_target: Literal["word", "lemma"] = "word",
    mode: Literal["dataframe", "counter"] = "dataframe",
) -> schemas.NGramResult:

    opts: dict[str, Any] = mappers.query_params_to_CQP_opts(commons, [(search_term, search_target)])
    ngrams: pd.DataFrame = n_grams.compute_n_grams(
        corpus, opts, n=n_gram_width, p_show=display_target, threshold=n_threshold, mode=mode
    )

    return mappers.ngrams_to_ngram_result(ngrams)
