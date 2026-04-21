"""Test suite for word trends optimization."""

from unittest.mock import patch

import pytest

from api_swedeb.api.services.corpus_loader import CorpusLoader
from api_swedeb.api.services.word_trends_service import WordTrendsService
from api_swedeb.core.common.keyness import KeynessMetric
from api_swedeb.core.common.word_trends import TrendsComputeOpts, TrendsService
from api_swedeb.core.configuration import get_config_store

# pylint: disable=unused-argument, redefined-outer-name


@pytest.fixture(scope="module")
def word_trends_service():
    """Fixture providing WordTrendsService instance."""
    get_config_store().configure_context(source="config/config.yml")
    loader = CorpusLoader()
    return WordTrendsService(loader)


def test_single_word_optimization(word_trends_service):
    """Test that single word queries use the optimization path."""
    filter_opts = {"year": (1867, 2022)}
    search_terms = ["demokrati"]

    df = word_trends_service.get_word_trend_results(search_terms=search_terms, filter_opts=filter_opts, normalize=False)

    assert not df.empty
    assert "demokrati" in df.columns
    assert len(df) > 0  # Should have data for multiple years


def test_multiple_words_optimization(word_trends_service):
    """Test that small multi-word queries use the optimization path."""
    filter_opts = {"year": (1867, 2022)}
    search_terms = ["demokrati", "frihet", "jämlikhet"]

    df = word_trends_service.get_word_trend_results(search_terms=search_terms, filter_opts=filter_opts, normalize=False)

    assert not df.empty
    assert all(term in df.columns for term in search_terms)


def test_very_common_word(word_trends_service):
    """Test with very common word 'att' that should benefit most from optimization."""
    filter_opts = {"year": (1867, 2022)}
    search_terms = ["att"]

    df = word_trends_service.get_word_trend_results(search_terms=search_terms, filter_opts=filter_opts, normalize=False)

    assert not df.empty
    assert "att" in df.columns
    assert len(df) == 156  # Years 1867-2022


def test_optimization_threshold(word_trends_service):
    """Test that optimization is only applied for < 100 words."""
    corpus = word_trends_service.loader.vectorized_corpus
    search_terms = list(corpus.token2id)[:101]
    words_99 = search_terms[:99]
    words_101 = search_terms[:101]

    assert word_trends_service.filter_search_terms(words_99) == words_99
    assert word_trends_service.filter_search_terms(words_101) == words_101

    no_op_group_by = lambda self, *args, **kwargs: self

    with (
        patch.object(type(corpus), "group_by_pivot_keys", autospec=True, side_effect=no_op_group_by),
        patch.object(corpus, "slice_by_indices", wraps=corpus.slice_by_indices) as slice_by_indices_99,
    ):
        TrendsService(corpus=corpus)._transform_corpus(
            TrendsComputeOpts(
                normalize=False,
                keyness=KeynessMetric.TF,
                temporal_key="year",
                words=words_99,
            )
        )

    assert slice_by_indices_99.call_count == 1

    with (
        patch.object(type(corpus), "group_by_pivot_keys", autospec=True, side_effect=no_op_group_by),
        patch.object(corpus, "slice_by_indices", wraps=corpus.slice_by_indices) as slice_by_indices_101,
    ):
        TrendsService(corpus=corpus)._transform_corpus(
            TrendsComputeOpts(
                normalize=False,
                keyness=KeynessMetric.TF,
                temporal_key="year",
                words=words_101,
            )
        )

    assert slice_by_indices_101.call_count == 0


def test_nonexistent_word(word_trends_service):
    """Test that nonexistent words are handled gracefully."""
    filter_opts = {"year": (1867, 2022)}
    search_terms = ["thisworddoesnotexist123456"]

    df = word_trends_service.get_word_trend_results(search_terms=search_terms, filter_opts=filter_opts, normalize=False)

    assert df.empty  # Should return empty DataFrame for nonexistent words


def test_mixed_existing_nonexisting(word_trends_service):
    """Test mix of existing and non-existing words."""
    filter_opts = {"year": (1867, 2022)}
    search_terms = ["demokrati", "thisworddoesnotexist123", "frihet"]

    df = word_trends_service.get_word_trend_results(search_terms=search_terms, filter_opts=filter_opts, normalize=False)

    assert not df.empty
    assert "demokrati" in df.columns
    assert "frihet" in df.columns
    assert "thisworddoesnotexist123" not in df.columns


def test_year_range_filtering(word_trends_service):
    """Test that year range filtering works with optimization."""
    filter_opts = {"year": (2000, 2020)}
    search_terms = ["demokrati"]

    df = word_trends_service.get_word_trend_results(search_terms=search_terms, filter_opts=filter_opts, normalize=False)

    assert not df.empty
    assert len(df) == 21  # 2000-2020 inclusive


def test_normalization_with_optimization(word_trends_service):
    """Test that normalization still works with optimization."""
    filter_opts = {"year": (1867, 2022)}
    search_terms = ["demokrati"]

    df_normalized = word_trends_service.get_word_trend_results(
        search_terms=search_terms, filter_opts=filter_opts, normalize=True
    )

    df_raw = word_trends_service.get_word_trend_results(
        search_terms=search_terms, filter_opts=filter_opts, normalize=False
    )

    assert not df_normalized.empty
    assert not df_raw.empty
    # Normalized values should be different from raw counts
    assert not df_normalized.equals(df_raw)
