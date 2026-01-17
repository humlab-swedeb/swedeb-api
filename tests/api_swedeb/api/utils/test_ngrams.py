"""Unit tests for api_swedeb.api.utils.ngrams module."""

import pandas as pd
import pytest
from unittest.mock import Mock, patch

from api_swedeb.api.utils.ngrams import get_ngrams
from api_swedeb.api.utils.common_params import CommonQueryParams
from api_swedeb.schemas import NGramResult


class TestGetNgrams:
    """Tests for get_ngrams function."""

    @patch('api_swedeb.api.utils.ngrams.n_grams.n_grams')
    @patch('api_swedeb.api.utils.ngrams.mappers.query_params_to_CQP_opts')
    @patch('api_swedeb.api.utils.ngrams.mappers.ngrams_to_ngram_result')
    def test_get_ngrams_with_string(self, mock_to_result, mock_to_opts, mock_n_grams):
        """Test get_ngrams with string search_term."""
        mock_corpus = Mock()
        mock_commons = CommonQueryParams()
        
        mock_to_opts.return_value = {"target": "word"}
        mock_n_grams.return_value = pd.DataFrame({"ngram": ["test"]})
        mock_to_result.return_value = NGramResult(ngram_list=[])
        
        result = get_ngrams(
            corpus=mock_corpus,
            search_term="hello",
            commons=mock_commons
        )
        
        assert isinstance(result, NGramResult)
        mock_n_grams.assert_called_once()

    @patch('api_swedeb.api.utils.ngrams.n_grams.n_grams')
    @patch('api_swedeb.api.utils.ngrams.mappers.query_params_to_CQP_opts')
    @patch('api_swedeb.api.utils.ngrams.mappers.ngrams_to_ngram_result')
    def test_get_ngrams_with_list(self, mock_to_result, mock_to_opts, mock_n_grams):
        """Test get_ngrams with list of search terms."""
        mock_corpus = Mock()
        mock_commons = CommonQueryParams()
        
        mock_to_opts.return_value = {"target": "word"}
        mock_n_grams.return_value = pd.DataFrame()
        mock_to_result.return_value = NGramResult(ngram_list=[])
        
        result = get_ngrams(
            corpus=mock_corpus,
            search_term=["hello", "world"],
            commons=mock_commons
        )
        
        assert isinstance(result, NGramResult)

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

    @patch('api_swedeb.api.utils.ngrams.n_grams.n_grams')
    @patch('api_swedeb.api.utils.ngrams.mappers.query_params_to_CQP_opts')
    def test_get_ngrams_empty_opts_returns_empty(self, mock_to_opts, mock_n_grams):
        """Test empty opts returns empty NGramResult."""
        mock_corpus = Mock()
        mock_commons = CommonQueryParams()
        
        mock_to_opts.return_value = []
        mock_n_grams.return_value = pd.DataFrame()
        
        result = get_ngrams(
            corpus=mock_corpus,
            search_term="test",
            commons=mock_commons
        )
        
        assert result.ngram_list == []
