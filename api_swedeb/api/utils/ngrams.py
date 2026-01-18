from typing import Any, Literal

import ccc

from api_swedeb.api.services.ngrams_service import NGramsService
from api_swedeb.api.utils.common_params import CommonQueryParams
from api_swedeb import schemas


def get_ngrams(
    corpus: ccc.Corpus,
    search_term: str | list[str],
    commons: CommonQueryParams,
    n_gram_width: int = 2,
    n_threshold: int = 2,
    search_target: None | Literal["word", "lemma"] = "word",
    display_target: Literal["word", "lemma"] = "word",
    mode: Literal['sliding', 'left-aligned', 'right-aligned'] = 'sliding',
) -> schemas.NGramResult:
    """Get n-grams from a corpus"""
    service = NGramsService()
    return service.get_ngrams(
        corpus=corpus,
        search_term=search_term,
        commons=commons,
        n_gram_width=n_gram_width,
        n_threshold=n_threshold,
        search_target=search_target,
        display_target=display_target,
        mode=mode,
    )
