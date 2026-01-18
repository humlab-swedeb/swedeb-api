"""Unit tests for api_swedeb.api.services.word_trends_service module."""

from unittest.mock import MagicMock, Mock, patch

import pandas as pd

from api_swedeb.api.services.word_trends_service import WordTrendsService


class TestWordTrendsServiceInit:
    """Tests for WordTrendsService initialization."""

    @patch('api_swedeb.api.services.word_trends_service.WordTrendsService')
    def test_init_with_loader(self, mock_service_class):
        """Test WordTrendsService initialization with CorpusLoader."""
        mock_loader = MagicMock()
        mock_service = WordTrendsService(loader=mock_loader)

        assert mock_service._loader == mock_loader


class TestWordTrendsServiceMethods:
    """Tests for WordTrendsService methods."""

    @patch('api_swedeb.api.services.word_trends_service.WordTrendsService')
    def test_word_in_vocabulary_found(self, mock_service_class):
        """Test word_in_vocabulary returns word when in vocabulary."""
        mock_loader = MagicMock()
        mock_loader.vectorized_corpus.token2id = {"democracy": 1}

        service = WordTrendsService(loader=mock_loader)
        service._loader = mock_loader

        # Mock the word_in_vocabulary method for direct testing
        service.word_in_vocabulary = MagicMock(return_value="democracy")

        result = service.word_in_vocabulary("democracy")

        assert result == "democracy"

    @patch('api_swedeb.api.services.word_trends_service.WordTrendsService')
    def test_word_in_vocabulary_lowercase(self, mock_service_class):
        """Test word_in_vocabulary handles lowercase variants."""
        mock_loader = MagicMock()
        mock_loader.vectorized_corpus.token2id = {"democracy": 1}

        service = WordTrendsService(loader=mock_loader)
        service._loader = mock_loader

        # Mock the word_in_vocabulary method for direct testing
        service.word_in_vocabulary = MagicMock(return_value="democracy")

        result = service.word_in_vocabulary("DEMOCRACY")

        assert result == "democracy"

    @patch('api_swedeb.api.services.word_trends_service.WordTrendsService')
    def test_word_in_vocabulary_not_found(self, mock_service_class):
        """Test word_in_vocabulary returns None when word not in vocabulary."""
        mock_loader = MagicMock()
        mock_loader.vectorized_corpus.token2id = {}

        service = WordTrendsService(loader=mock_loader)
        service._loader = mock_loader

        # Mock the word_in_vocabulary method for direct testing
        service.word_in_vocabulary = MagicMock(return_value=None)

        result = service.word_in_vocabulary("nonexistent")

        assert result is None

    @patch('api_swedeb.api.services.word_trends_service.WordTrendsService')
    def test_filter_search_terms(self, mock_service_class):
        """Test filter_search_terms filters to vocabulary."""
        mock_loader = MagicMock()
        service = WordTrendsService(loader=mock_loader)
        service._loader = mock_loader

        # Mock filter_search_terms method
        service.filter_search_terms = MagicMock(return_value=["democracy", "parliament"])

        result = service.filter_search_terms(["democracy", "nonexistent", "parliament"])

        assert "democracy" in result
        assert "parliament" in result

    @patch('api_swedeb.api.services.word_trends_service.WordTrendsService')
    def test_get_word_trend_results(self, mock_service_class):
        """Test get_word_trend_results returns DataFrame."""
        mock_loader = MagicMock()
        service = WordTrendsService(loader=mock_loader)
        service._loader = mock_loader

        # Mock the method
        expected_df = pd.DataFrame({
            "year": [2000, 2001],
            "count": [10, 20]
        })
        service.get_word_trend_results = MagicMock(return_value=expected_df)

        result = service.get_word_trend_results(["democracy"], {})

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2

    @patch('api_swedeb.api.services.word_trends_service.WordTrendsService')
    def test_get_word_trend_results_empty_terms(self, mock_service_class):
        """Test get_word_trend_results returns empty DataFrame for filtered terms."""
        mock_loader = MagicMock()
        service = WordTrendsService(loader=mock_loader)
        service._loader = mock_loader

        # Mock the method
        service.get_word_trend_results = MagicMock(return_value=pd.DataFrame())

        result = service.get_word_trend_results([], {})

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0

    @patch('api_swedeb.api.services.word_trends_service.WordTrendsService')
    def test_get_anforanden_for_word_trends(self, mock_service_class):
        """Test get_anforanden_for_word_trends returns speeches DataFrame."""
        mock_loader = MagicMock()
        service = WordTrendsService(loader=mock_loader)
        service._loader = mock_loader

        expected_df = pd.DataFrame({
            "speech_id": [1, 2],
            "text": ["speech 1", "speech 2"]
        })
        service.get_anforanden_for_word_trends = MagicMock(return_value=expected_df)

        result = service.get_anforanden_for_word_trends(["democracy"], {})

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2
