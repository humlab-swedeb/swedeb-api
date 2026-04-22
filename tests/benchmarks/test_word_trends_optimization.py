"""Test suite for word trends optimization."""

from typing import Generator
from unittest.mock import patch

import pytest

from api_swedeb.api.services.corpus_loader import CorpusLoader
from api_swedeb.api.services.word_trends_service import WordTrendsService
from api_swedeb.core.configuration import Config, ConfigStore


@pytest.fixture(scope="module", autouse=True)
def config_store() -> Generator[ConfigStore, None, None]:
    """Fixture to provide a clean ConfigStore instance for tests.
    Automatically patches get_config_store() to return this store for the duration of the test.
    """
    config: Config = Config.load(source="config/config.yml")
    store: ConfigStore = ConfigStore()
    store.configure_context(source=config)

    with patch("api_swedeb.core.configuration.inject.get_config_store", return_value=store):
        yield store


@pytest.fixture(scope="module")
def word_trends_service(config_store):
    """Fixture providing WordTrendsService instance."""
    config_store.configure_context(source="config/config.yml")
    loader = CorpusLoader()
    return WordTrendsService(loader)


@pytest.mark.skip(reason="Optimization logic is currently disabled, needs refactor to be testable")
def test_single_word_optimization(word_trends_service):
    """Test that single word queries use the optimization path."""
    filter_opts = {"year": (1867, 2022)}
    search_terms = ["demokrati"]

    df = word_trends_service.get_word_trend_results(search_terms=search_terms, filter_opts=filter_opts, normalize=False)

    assert not df.empty
    assert "demokrati" in df.columns
    assert len(df) > 0  # Should have data for multiple years


@pytest.mark.skip(reason="Optimization logic is currently disabled, needs refactor to be testable")
def test_multiple_words_optimization(word_trends_service):
    """Test that small multi-word queries use the optimization path."""
    filter_opts = {"year": (1867, 2022)}
    search_terms = ["demokrati", "frihet", "jämlikhet"]

    df = word_trends_service.get_word_trend_results(search_terms=search_terms, filter_opts=filter_opts, normalize=False)

    assert not df.empty
    assert all(term in df.columns for term in search_terms)


@pytest.mark.skip(reason="Optimization logic is currently disabled, needs refactor to be testable")
def test_very_common_word(word_trends_service):
    """Test with very common word 'att' that should benefit most from optimization."""
    filter_opts = {"year": (1867, 2022)}
    search_terms = ["att"]

    df = word_trends_service.get_word_trend_results(search_terms=search_terms, filter_opts=filter_opts, normalize=False)

    assert not df.empty
    assert "att" in df.columns
    assert len(df) == 156  # Years 1867-2022


@pytest.mark.skip(reason="Optimization logic is currently disabled, needs refactor to be testable")
def test_nonexistent_word(word_trends_service):
    """Test that nonexistent words are handled gracefully."""
    filter_opts = {"year": (1867, 2022)}
    search_terms = ["thisworddoesnotexist123456"]

    df = word_trends_service.get_word_trend_results(search_terms=search_terms, filter_opts=filter_opts, normalize=False)

    assert df.empty  # Should return empty DataFrame for nonexistent words


@pytest.mark.skip(reason="Optimization logic is currently disabled, needs refactor to be testable")
def test_mixed_existing_nonexisting(word_trends_service):
    """Test mix of existing and non-existing words."""
    filter_opts = {"year": (1867, 2022)}
    search_terms = ["demokrati", "thisworddoesnotexist123", "frihet"]

    df = word_trends_service.get_word_trend_results(search_terms=search_terms, filter_opts=filter_opts, normalize=False)

    assert not df.empty
    assert "demokrati" in df.columns
    assert "frihet" in df.columns
    assert "thisworddoesnotexist123" not in df.columns


@pytest.mark.skip(reason="Optimization logic is currently disabled, needs refactor to be testable")
def test_year_range_filtering(word_trends_service):
    """Test that year range filtering works with optimization."""
    filter_opts = {"year": (2000, 2020)}
    search_terms = ["demokrati"]

    df = word_trends_service.get_word_trend_results(search_terms=search_terms, filter_opts=filter_opts, normalize=False)

    assert not df.empty
    assert len(df) == 21  # 2000-2020 inclusive


@pytest.mark.skip(reason="Optimization logic is currently disabled, needs refactor to be testable")
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
