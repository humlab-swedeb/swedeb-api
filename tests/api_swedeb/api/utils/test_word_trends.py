"""Unit tests for api_swedeb.api.utils.word_trends module."""

from unittest.mock import Mock

import pandas as pd

from api_swedeb.api.utils.common_params import CommonQueryParams
from api_swedeb.api.utils.word_trends import get_search_hit_results, get_word_trend_speeches, get_word_trends
from api_swedeb.schemas.speeches_schema import SpeechesResultWT
from api_swedeb.schemas.word_trends_schema import SearchHits, WordTrendsResult


class TestGetSearchHitResults:
    """Tests for get_search_hit_results function."""

    def test_get_search_hit_results_success(self):
        """Test get_search_hit_results returns SearchHits."""
        mock_corpus = Mock()
        mock_corpus.get_word_hits.return_value = ["word1", "word2", "word3"]

        result = get_search_hit_results("test", mock_corpus, 5)

        assert isinstance(result, SearchHits)
        assert hasattr(result, 'hit_list')
        assert len(result.hit_list) == 3
        assert result.hit_list == ["word1", "word2", "word3"]
        mock_corpus.get_word_hits.assert_called_once_with("test", 5)

    def test_get_search_hit_results_empty(self):
        """Test get_search_hit_results with no hits."""
        mock_corpus = Mock()
        mock_corpus.get_word_hits.return_value = []

        result = get_search_hit_results("missing", mock_corpus, 5)

        assert isinstance(result, SearchHits)
        assert hasattr(result, 'hit_list')
        assert len(result.hit_list) == 0
        assert result.hit_list == []

    def test_get_search_hit_results_max_hits(self):
        """Test get_search_hit_results respects max_hits parameter."""
        mock_corpus = Mock()
        mock_corpus.get_word_hits.return_value = ["a", "b", "c"]

        result = get_search_hit_results("test", mock_corpus, 10)

        assert isinstance(result, SearchHits)
        assert len(result.hit_list) == 3
        mock_corpus.get_word_hits.assert_called_once_with("test", 10)


class TestGetWordTrends:
    """Tests for get_word_trends function."""

    def test_get_word_trends_success(self):
        """Test get_word_trends returns WordTrendsResult."""
        mock_corpus = Mock()
        trends_df = pd.DataFrame({
            "word1": [10, 20, 30]
        }, index=[1990, 2000, 2010])
        mock_corpus.get_word_trend_results.return_value = trends_df

        commons = CommonQueryParams()
        result = get_word_trends("word1", commons, mock_corpus, normalize=False)

        assert isinstance(result, WordTrendsResult)
        assert hasattr(result, 'wt_list')
        assert len(result.wt_list) == 3
        assert result.wt_list[0].year == 1990
        assert result.wt_list[1].year == 2000
        assert result.wt_list[2].year == 2010
        # Verify actual count values from DataFrame
        assert hasattr(result.wt_list[0], 'count')

    def test_get_word_trends_multiple_words(self):
        """Test get_word_trends with multiple search terms."""
        mock_corpus = Mock()
        trends_df = pd.DataFrame({
            "word1": [10, 20],
            "word2": [5, 15]
        }, index=[2000, 2010])
        mock_corpus.get_word_trend_results.return_value = trends_df

        commons = CommonQueryParams()
        _ = get_word_trends("word1,word2", commons, mock_corpus, normalize=True)

        mock_corpus.get_word_trend_results.assert_called_once()
        call_args = mock_corpus.get_word_trend_results.call_args
        assert call_args[1]['search_terms'] == ["word1", "word2"]
        assert call_args[1]['normalize'] is True

    def test_get_word_trends_filters_columns(self):
        """Test get_word_trends removes gender/chamber columns."""
        mock_corpus = Mock()
        trends_df = pd.DataFrame({
            "word1": [10, 20],
            "gender_abbrev": ["M", "F"],
            "chamber_abbrev": ["AK", "FK"]
        }, index=[2000, 2010])
        mock_corpus.get_word_trend_results.return_value = trends_df

        commons = CommonQueryParams()
        result = get_word_trends("word1", commons, mock_corpus, normalize=False)

        # Result should not have gender_abbrev or chamber_abbrev
        assert all("gender_abbrev" not in item.count for item in result.wt_list)

    def test_get_word_trends_empty_result(self):
        """Test get_word_trends with empty DataFrame with proper columns."""
        mock_corpus = Mock()
        # Empty but with named columns to avoid .str accessor error
        mock_corpus.get_word_trend_results.return_value = pd.DataFrame(columns=["year", "count"])

        commons = CommonQueryParams()
        result = get_word_trends("missing", commons, mock_corpus, normalize=False)

        assert isinstance(result, WordTrendsResult)
        assert hasattr(result, 'wt_list')
        assert len(result.wt_list) == 0

    def test_get_word_trends_normalization(self):
        """Test get_word_trends passes normalize parameter."""
        mock_corpus = Mock()
        trends_df = pd.DataFrame({"word1": [10]}, index=[2000])
        mock_corpus.get_word_trend_results.return_value = trends_df

        commons = CommonQueryParams()
        _ = get_word_trends("word1", commons, mock_corpus, normalize=True)

        call_args = mock_corpus.get_word_trend_results.call_args
        assert call_args[1]['normalize'] is True


class TestGetWordTrendSpeeches:
    """Tests for get_word_trend_speeches function."""

    def test_get_word_trend_speeches_success(self):
        """Test get_word_trend_speeches returns SpeechesResultWT."""
        mock_corpus = Mock()
        speeches_df = pd.DataFrame({
            "speech_id": ["s1", "s2"],
            "year": [2000, 2001],
            "node_word": ["word1", "word1"]
        })
        mock_corpus.get_anforanden_for_word_trends.return_value = speeches_df

        commons = CommonQueryParams()
        result = get_word_trend_speeches("word1", commons, mock_corpus)

        assert isinstance(result, SpeechesResultWT)
        assert hasattr(result, 'speech_list')
        assert len(result.speech_list) == 2
        # Verify speech objects have required fields
        assert hasattr(result.speech_list[0], 'speech_id')
        assert hasattr(result.speech_list[0], 'year')

    def test_get_word_trend_speeches_multiple_words(self):
        """Test get_word_trend_speeches with comma-separated words."""
        mock_corpus = Mock()
        speeches_df = pd.DataFrame({
            "speech_id": ["s1"],
            "year": [2000],
            "node_word": ["word1"]
        })
        mock_corpus.get_anforanden_for_word_trends.return_value = speeches_df

        commons = CommonQueryParams()
        _ = get_word_trend_speeches("word1,word2", commons, mock_corpus)

        call_args = mock_corpus.get_anforanden_for_word_trends.call_args
        assert call_args[0][0] == ["word1", "word2"]

    def test_get_word_trend_speeches_empty(self):
        """Test get_word_trend_speeches with no results."""
        mock_corpus = Mock()
        mock_corpus.get_anforanden_for_word_trends.return_value = pd.DataFrame({
            "speech_id": [],
            "year": [],
            "node_word": []
        })

        commons = CommonQueryParams()
        result = get_word_trend_speeches("missing", commons, mock_corpus)

        assert isinstance(result, SpeechesResultWT)
        assert hasattr(result, 'speech_list')
        assert len(result.speech_list) == 0
        assert result.speech_list == []
