"""Unit tests for api_swedeb.api.services.ngrams_service module."""

from unittest.mock import MagicMock, Mock, patch

import pandas as pd

from api_swedeb import schemas
from api_swedeb.api.params import CommonQueryParams
from api_swedeb.api.services.ngrams_service import NGramsService
from api_swedeb.schemas import NGramResult


class TestNGramsServiceInit:
    """Tests for NGramsService initialization."""

    def test_init(self):
        """Test NGramsService initialization."""
        service = NGramsService()
        assert service is not None


class TestNGramsServiceMethods:
    """Tests for NGramsService methods."""

    @patch('api_swedeb.api.services.ngrams_service.n_grams.n_grams')
    @patch('api_swedeb.api.services.ngrams_service.mappers.query_params_to_CQP_opts')
    @patch('api_swedeb.api.services.ngrams_service.mappers.ngrams_to_ngram_result')
    def test_get_ngrams_success(self, mock_to_result, mock_to_opts, mock_n_grams):
        """Test get_ngrams returns NGramResult."""
        mock_corpus = MagicMock()
        mock_to_opts.return_value = [{"cqp": "test"}]

        ngrams_df = pd.DataFrame({"ngram": ["test ngram"], "count": [5]})
        mock_n_grams.return_value = ngrams_df

        expected_result = schemas.NGramResult(ngram_list=[])
        mock_to_result.return_value = expected_result

        service = NGramsService()
        commons = CommonQueryParams(from_year=2000, to_year=2010)

        result = service.get_ngrams(
            corpus=mock_corpus,
            search_term="test",
            commons=commons,
            n_gram_width=3,
        )

        assert result == expected_result
        mock_to_opts.assert_called_once()
        mock_n_grams.assert_called_once()

    @patch('api_swedeb.api.services.ngrams_service.n_grams.n_grams')
    @patch('api_swedeb.api.services.ngrams_service.mappers.query_params_to_CQP_opts')
    def test_get_ngrams_empty_opts(self, mock_to_opts, mock_n_grams):
        """Test get_ngrams returns empty result when no options."""
        mock_corpus = MagicMock()
        mock_to_opts.return_value = []

        service = NGramsService()
        commons = CommonQueryParams(from_year=2000, to_year=2010)

        result = service.get_ngrams(
            corpus=mock_corpus,
            search_term="test",
            commons=commons,
        )

        assert isinstance(result, schemas.NGramResult)
        assert len(result.ngram_list) == 0

    @patch('api_swedeb.api.services.ngrams_service.mappers.query_params_to_CQP_opts')
    def test_get_ngrams_empty_search_term_raises(self, mock_to_opts):
        """Test get_ngrams raises ValueError for empty search terms."""
        mock_corpus = MagicMock()

        service = NGramsService()
        commons = CommonQueryParams(from_year=2000, to_year=2010)

        try:
            service.get_ngrams(
                corpus=mock_corpus,
                search_term=[],
                commons=commons,
            )
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "search_term must contain at least one term" in str(e)

    @patch('api_swedeb.api.services.ngrams_service.n_grams.n_grams')
    @patch('api_swedeb.api.services.ngrams_service.mappers.query_params_to_CQP_opts')
    @patch('api_swedeb.api.services.ngrams_service.mappers.ngrams_to_ngram_result')
    def test_get_ngrams_with_list_terms(self, mock_to_result, mock_to_opts, mock_n_grams):
        """Test get_ngrams with list of search terms."""
        mock_corpus = MagicMock()
        mock_to_opts.return_value = [{"cqp": "test"}]

        ngrams_df = pd.DataFrame({"ngram": ["test ngram"], "count": [5]})
        mock_n_grams.return_value = ngrams_df

        expected_result = schemas.NGramResult(ngram_list=[])
        mock_to_result.return_value = expected_result

        service = NGramsService()
        commons = CommonQueryParams(from_year=2000, to_year=2010)

        result = service.get_ngrams(
            corpus=mock_corpus,
            search_term=["test", "word"],
            commons=commons,
            n_gram_width=2,
        )

        assert result == expected_result
        mock_to_opts.assert_called_once()


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
        result = service.get_ngrams(corpus=mock_corpus, search_term="hello", commons=mock_commons)

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
        result = service.get_ngrams(corpus=mock_corpus, search_term=["hello", "world"], commons=mock_commons)

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
        result = service.get_ngrams(corpus=mock_corpus, search_term="test", commons=mock_commons)

        assert isinstance(result, NGramResult)
        assert result.ngram_list == []
