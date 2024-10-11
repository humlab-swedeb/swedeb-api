from typing import Any, Literal

import pandas as pd

from api_swedeb import mappers, schemas
from api_swedeb.api.utils.common_params import CommonQueryParams
from api_swedeb.core import n_grams


def get_ngrams(
    corpus: Any,
    search_term: str | list[str],
    commons: CommonQueryParams,
    n_gram_width: int | tuple[int, int] = 2,
    n_threshold: int = 2,
    search_target: None | Literal["word", "lemma"] = "word",
    display_target: Literal["word", "lemma"] = "word",
    mode: Literal['sliding', 'left-aligned', 'right-aligned'] = 'sliding',
) -> schemas.NGramResult:
    """Get n-grams from a corpus"""

    if isinstance(search_term, str):
        search_term = [search_term]
    if len(search_term) == 0:
        raise ValueError("search_term must contain at least one term")
    opts: dict[str, Any] = mappers.query_params_to_CQP_opts(
        commons, word_targets=search_term, search_target=search_target
    )
    ngrams: pd.DataFrame = n_grams.n_grams(
        corpus, opts, n=n_gram_width, p_show=display_target, threshold=n_threshold, mode=mode
    )

    if len(opts) == 0:
        return schemas.NGramResult(ngram_list=[])

    return mappers.ngrams_to_ngram_result(ngrams)
