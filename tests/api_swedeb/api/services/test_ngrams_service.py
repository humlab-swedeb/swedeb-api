"""Unit tests for api_swedeb.api.services.ngrams_service."""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from api_swedeb.api.params import CommonQueryParams
from api_swedeb.api.services.ngrams_service import NGramsService
from api_swedeb.schemas import NGramResult, NGramResultItem


def test_get_ngrams_converts_string_term_and_maps_result():
    service = NGramsService()
    corpus = MagicMock()
    commons = CommonQueryParams(from_year=2000, to_year=2010)
    ngrams_df = pd.DataFrame({"ngram": ["test ngram"], "count": [5]})
    expected = NGramResult(ngram_list=[NGramResultItem(ngram="test ngram", count=5, documents=["i-1"])])

    with (
        patch(
            "api_swedeb.api.services.ngrams_service.mappers.query_params_to_CQP_opts",
            return_value=[{"cqp": "test"}],
        ) as to_opts,
        patch("api_swedeb.api.services.ngrams_service.n_grams.n_grams", return_value=ngrams_df) as n_grams_fn,
        patch(
            "api_swedeb.api.services.ngrams_service.mappers.ngrams_to_ngram_result", return_value=expected
        ) as to_result,
    ):
        result = service.get_ngrams(
            corpus=corpus,
            search_term="test",
            commons=commons,
            n_gram_width=3,
            n_threshold=4,
            search_target="lemma",
            display_target="word",
            mode="left-aligned",
        )

    to_opts.assert_called_once_with(commons, word_targets=["test"], search_target="lemma")
    n_grams_fn.assert_called_once_with(
        corpus,
        [{"cqp": "test"}],
        n=3,
        p_show="word",
        threshold=4,
        mode="left-aligned",
    )
    to_result.assert_called_once_with(ngrams_df)
    assert result == expected


def test_get_ngrams_accepts_list_terms():
    service = NGramsService()
    corpus = MagicMock()
    commons = CommonQueryParams()

    with (
        patch(
            "api_swedeb.api.services.ngrams_service.mappers.query_params_to_CQP_opts",
            return_value=[{"cqp": "test"}],
        ) as to_opts,
        patch("api_swedeb.api.services.ngrams_service.n_grams.n_grams", return_value=pd.DataFrame()) as n_grams_fn,
        patch(
            "api_swedeb.api.services.ngrams_service.mappers.ngrams_to_ngram_result",
            return_value=NGramResult(ngram_list=[]),
        ),
    ):
        service.get_ngrams(corpus=corpus, search_term=["hello", "world"], commons=commons)

    to_opts.assert_called_once_with(commons, word_targets=["hello", "world"], search_target="word")
    n_grams_fn.assert_called_once()


def test_get_ngrams_raises_for_empty_search_term():
    service = NGramsService()

    with pytest.raises(ValueError, match="search_term must contain at least one term"):
        service.get_ngrams(corpus=MagicMock(), search_term=[], commons=CommonQueryParams())


def test_get_ngrams_returns_empty_result_when_opts_are_empty():
    service = NGramsService()
    corpus = MagicMock()
    commons = CommonQueryParams()

    with (
        patch("api_swedeb.api.services.ngrams_service.mappers.query_params_to_CQP_opts", return_value=[]) as to_opts,
        patch("api_swedeb.api.services.ngrams_service.n_grams.n_grams", return_value=pd.DataFrame()) as n_grams_fn,
        patch("api_swedeb.api.services.ngrams_service.mappers.ngrams_to_ngram_result") as to_result,
    ):
        result = service.get_ngrams(corpus=corpus, search_term="test", commons=commons)

    to_opts.assert_called_once_with(commons, word_targets=["test"], search_target="word")
    n_grams_fn.assert_called_once_with(corpus, [], n=2, p_show="word", threshold=2, mode="sliding")
    to_result.assert_not_called()
    assert result == NGramResult(ngram_list=[])
