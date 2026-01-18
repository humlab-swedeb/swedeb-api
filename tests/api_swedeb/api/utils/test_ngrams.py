"""Unit tests for api_swedeb.api.utils.ngrams module."""

from unittest.mock import MagicMock, Mock, patch

import pytest

from api_swedeb.api.utils.common_params import CommonQueryParams
from api_swedeb.api.utils.ngrams import get_ngrams
from api_swedeb.schemas import NGramResult


class TestGetNgrams:
    """Tests for get_ngrams function."""

    @patch('api_swedeb.api.utils.ngrams.NGramsService')
    def test_get_ngrams_with_string(self, mock_service_class):
        """Test get_ngrams with string search_term."""
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service

        mock_corpus = Mock()
        mock_commons = CommonQueryParams()

        expected_result = NGramResult(ngram_list=[])
        mock_service.get_ngrams.return_value = expected_result

        result = get_ngrams(
            corpus=mock_corpus,
            search_term="hello",
            commons=mock_commons
        )

        assert isinstance(result, NGramResult)
        assert hasattr(result, 'ngram_list')

    @patch('api_swedeb.api.utils.ngrams.NGramsService')
    def test_get_ngrams_with_list(self, mock_service_class):
        """Test get_ngrams with list of search terms."""
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service

        mock_corpus = Mock()
        mock_commons = CommonQueryParams()

        expected_result = NGramResult(ngram_list=[])
        mock_service.get_ngrams.return_value = expected_result

        result = get_ngrams(
            corpus=mock_corpus,
            search_term=["hello", "world"],
            commons=mock_commons
        )

        assert isinstance(result, NGramResult)
        assert hasattr(result, 'ngram_list')

    def test_get_ngrams_empty_list_raises(self):
        """Test empty search_term list raises ValueError."""
        mock_corpus = Mock()
        mock_commons = CommonQueryParams()

        with pytest.raises(ValueError, match="must contain at least one term"):
            get_ngrams(
                corpus=mock_corpus,
                search_term=[],
                commons=mock_commons
            )

    @patch('api_swedeb.api.utils.ngrams.NGramsService')
    def test_get_ngrams_empty_opts_returns_empty(self, mock_service_class):
        """Test empty opts returns empty NGramResult."""
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service

        mock_corpus = Mock()
        mock_commons = CommonQueryParams()

        expected_result = NGramResult(ngram_list=[])
        mock_service.get_ngrams.return_value = expected_result

        result = get_ngrams(
            corpus=mock_corpus,
            search_term="test",
            commons=mock_commons
        )

        assert isinstance(result, NGramResult)
        assert result.ngram_list == []
