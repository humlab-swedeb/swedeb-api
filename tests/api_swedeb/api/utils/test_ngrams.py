"""Unit tests for NGramsService."""

from unittest.mock import MagicMock, Mock, patch

import pytest

from api_swedeb.api.services.ngrams_service import NGramsService
from api_swedeb.api.utils.common_params import CommonQueryParams
from api_swedeb.schemas import NGramResult


class TestNGramsService:
    """Tests for NGramsService.get_ngrams method."""

    @patch('api_swedeb.api.services.ngrams_service.NGramsService.get_ngrams')
    def test_get_ngrams_with_string(self, mock_get_ngrams):
        """Test get_ngrams with string search_term."""
        mock_corpus = Mock()
        mock_commons = CommonQueryParams()

        expected_result = NGramResult(ngram_list=[])
        mock_get_ngrams.return_value = expected_result

        service = NGramsService()
        result = service.get_ngrams(
            corpus=mock_corpus,
            search_term="hello",
            commons=mock_commons
        )

        assert isinstance(result, NGramResult)
        assert hasattr(result, 'ngram_list')

    @patch('api_swedeb.api.services.ngrams_service.NGramsService.get_ngrams')
    def test_get_ngrams_with_list(self, mock_get_ngrams):
        """Test get_ngrams with list of search terms."""
        mock_corpus = Mock()
        mock_commons = CommonQueryParams()

        expected_result = NGramResult(ngram_list=[])
        mock_get_ngrams.return_value = expected_result

        service = NGramsService()
        result = service.get_ngrams(
            corpus=mock_corpus,
            search_term=["hello", "world"],
            commons=mock_commons
        )

        assert isinstance(result, NGramResult)
        assert hasattr(result, 'ngram_list')

    @patch('api_swedeb.api.services.ngrams_service.NGramsService.get_ngrams')
    def test_get_ngrams_empty_opts_returns_empty(self, mock_get_ngrams):
        """Test get_ngrams returns empty NGramResult when appropriate."""
        mock_corpus = Mock()
        mock_commons = CommonQueryParams()

        expected_result = NGramResult(ngram_list=[])
        mock_get_ngrams.return_value = expected_result

        service = NGramsService()
        result = service.get_ngrams(
            corpus=mock_corpus,
            search_term="test",
            commons=mock_commons
        )

        assert isinstance(result, NGramResult)
        assert result.ngram_list == []
