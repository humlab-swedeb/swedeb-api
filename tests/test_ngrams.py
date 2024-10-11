from typing import Any

import pytest
from ccc import Corpus

from api_swedeb.api.utils import common_params as cp
from api_swedeb.api.utils import ngrams as ngram_service
from api_swedeb.schemas.ngrams_schema import NGramResult

version = "v1"


def test_n_gram_service_with_single_word(corpus: Corpus):
    common_opts: cp.CommonQueryParams = cp.CommonQueryParams(
        from_year=1970, to_year=1975, who=None, party_id=None, office_types=None, sub_office_types=None, gender_id=None
    )
    opts: dict[str, Any] = {
        'search_term': ['sverige'],
        'search_target': "lemma",
        'display_target': "word",
        'n_gram_width': 5,
    }

    sliding_result: NGramResult = ngram_service.get_ngrams(corpus=corpus, commons=common_opts, **opts, mode="sliding")
    assert sliding_result is not None
    assert len(sliding_result.ngram_list) > 0
    assert all('sverige' in ngram.ngram.lower() for ngram in sliding_result.ngram_list)
    assert not all(ngram.ngram.lower().startswith('sverige') for ngram in sliding_result.ngram_list)

    left_aligned: NGramResult = ngram_service.get_ngrams(
        corpus=corpus, commons=common_opts, **opts, mode="left-aligned"
    )
    assert left_aligned is not None
    assert len(left_aligned.ngram_list) > 0
    assert all(ngram.ngram.lower().startswith('sverige') for ngram in left_aligned.ngram_list)

    right_aligned: NGramResult = ngram_service.get_ngrams(
        corpus=corpus, commons=common_opts, **opts, mode="right-aligned"
    )
    assert right_aligned is not None
    assert len(right_aligned.ngram_list) > 0
    assert all(ngram.ngram.lower().endswith('sverige') for ngram in right_aligned.ngram_list)


@pytest.mark.skip("FIXME: When phrase is used, to many sliding windows are created ")
def test_n_gram_service_with_phrase(corpus: Corpus):
    common_opts: cp.CommonQueryParams = cp.CommonQueryParams(from_year=1970, to_year=1975)
    opts: dict[str, Any] = {
        'search_term': ['sverige', 'vara'],
        'search_target': "lemma",
        'display_target': "word",
        'n_gram_width': 5,
    }

    sliding_result: NGramResult = ngram_service.get_ngrams(corpus=corpus, commons=common_opts, **opts, mode="sliding")
    assert sliding_result is not None
    assert len(sliding_result.ngram_list) > 0
    assert all('sverige vara' in ngram.ngram.lower() for ngram in sliding_result.ngram_list)
    left_aligned: NGramResult = ngram_service.get_ngrams(
        corpus=corpus, commons=common_opts, **opts, mode="left-aligned"
    )

    assert left_aligned is not None
    assert len(left_aligned.ngram_list) > 0
    assert all('sverige vara' in ngram.ngram.lower() for ngram in sliding_result.ngram_list)
