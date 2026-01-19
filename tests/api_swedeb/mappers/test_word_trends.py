"""Unit tests for word trend mappers and WordTrendsService helpers."""

from unittest.mock import MagicMock

import pandas as pd

from api_swedeb.api.services.word_trends_service import WordTrendsService
from api_swedeb.mappers.word_trends import (
    search_hits_to_api_model,
    word_trend_speeches_to_api_model,
    word_trends_to_api_model,
)
from api_swedeb.schemas.speeches_schema import SpeechesResultWT
from api_swedeb.schemas.word_trends_schema import SearchHits, WordTrendsResult


class TestSearchHitsMapper:
    def test_search_hits_to_api_model_reverses_order(self):
        result = search_hits_to_api_model(["b", "a"])

        assert isinstance(result, SearchHits)
        assert result.hit_list == ["a", "b"]


class TestWordTrendsMapper:
    def test_word_trends_to_api_model_filters_columns(self):
        df = pd.DataFrame(
            {
                "word1": [10, 20],
                "gender_abbrev": ["M", "F"],
                "chamber_abbrev": ["AK", "FK"],
            },
            index=[2000, 2010],
        )

        result = word_trends_to_api_model(df)

        assert isinstance(result, WordTrendsResult)
        assert len(result.wt_list) == 2
        assert all("gender_abbrev" not in item.count for item in result.wt_list)
        assert all("chamber_abbrev" not in item.count for item in result.wt_list)


class TestWordTrendSpeechesMapper:
    def test_word_trend_speeches_to_api_model(self):
        df = pd.DataFrame(
            {
                "speech_id": ["s1"],
                "year": [2000],
                "node_word": ["word1"],
            }
        )

        result = word_trend_speeches_to_api_model(df)

        assert isinstance(result, SpeechesResultWT)
        assert len(result.speech_list) == 1
        assert result.speech_list[0].speech_id == "s1"


class TestWordTrendsServiceSearchHits:
    def test_get_search_hits_uses_lowercase_fallback(self):
        vectorized = MagicMock()
        vectorized.vocabulary = {"democracy"}
        vectorized.find_matching_words.return_value = ["democracy"]

        loader = MagicMock()
        loader.vectorized_corpus = vectorized

        service = WordTrendsService(loader=loader)

        hits = service.get_search_hits("DEMOCRACY", n_hits=5)

        vectorized.find_matching_words.assert_called_once()
        assert hits == ["democracy"]

    def test_get_search_hits_returns_empty_when_no_match(self):
        vectorized = MagicMock()
        vectorized.vocabulary = set()
        vectorized.find_matching_words.return_value = []

        loader = MagicMock()
        loader.vectorized_corpus = vectorized

        service = WordTrendsService(loader=loader)

        hits = service.get_search_hits("missing", n_hits=3)

        assert hits == []
