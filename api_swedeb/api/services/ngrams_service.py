"""N-grams analysis service for parliamentary speech data."""

from typing import Any, Literal

import ccc
import pandas as pd

from api_swedeb import mappers, schemas
from api_swedeb.api.utils.common_params import CommonQueryParams
from api_swedeb.core import n_grams


class NGramsService:
    """Service for n-grams analysis.

    Handles extraction and computation of n-grams from a CWB corpus
    with various modes and filters.
    """

    def __init__(self):
        """Initialize NGramsService."""
        pass

    def get_ngrams(
        self,
        corpus: ccc.Corpus,
        search_term: str | list[str],
        commons: CommonQueryParams,
        n_gram_width: int = 2,
        n_threshold: int = 2,
        search_target: None | Literal["word", "lemma"] = "word",
        display_target: Literal["word", "lemma"] = "word",
        mode: Literal['sliding', 'left-aligned', 'right-aligned'] = 'sliding',
    ) -> schemas.NGramResult:
        """Get n-grams from a corpus.

        Args:
            corpus: CWB corpus to query
            search_term: Single term or list of terms to search for
            commons: Common query parameters (year ranges, filters, etc.)
            n_gram_width: Width of n-grams (default: 2)
            n_threshold: Threshold for n-gram frequency (default: 2)
            search_target: Target for search - "word", "lemma", or None
            display_target: Target for display in results (default: "word")
            mode: N-gram mode - 'sliding', 'left-aligned', or 'right-aligned'

        Returns:
            NGramResult with list of n-grams and their frequencies
        """
        if isinstance(search_term, str):
            search_term = [search_term]
        if len(search_term) == 0:
            raise ValueError("search_term must contain at least one term")

        opts: dict[str, Any] | list[dict[str, Any]] = mappers.query_params_to_CQP_opts(
            commons, word_targets=search_term, search_target=search_target
        )

        ngrams: pd.DataFrame = n_grams.n_grams(
            corpus, opts, n=n_gram_width, p_show=display_target, threshold=n_threshold, mode=mode
        )

        if len(opts) == 0:
            return schemas.NGramResult(ngram_list=[])

        return mappers.ngrams_to_ngram_result(ngrams)
