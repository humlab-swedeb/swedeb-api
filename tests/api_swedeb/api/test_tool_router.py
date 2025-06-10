# type: ignore
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient

from api_swedeb.api.tool_router import router
from api_swedeb.api.utils.common_params import CommonQueryParams
from api_swedeb.schemas.kwic_schema import KeywordInContextResult
from api_swedeb.schemas.ngrams_schema import NGramResult
from api_swedeb.schemas.speech_text_schema import SpeechesTextResultItem
from api_swedeb.schemas.speeches_schema import SpeechesResult, SpeechesResultWT
from api_swedeb.schemas.word_trends_schema import SearchHits, WordTrendsResult

version = "v1"


@pytest.fixture(name='speech_ids')
def mock_speech_ids():
    return ["i-Tthy1hzk6Yg4W5NfXLwJrA;i-Ua1nqYCRbnUSNc5Tw1tXiK", "i-284a2ff9c2603b5f-0;i-Ua1nqYCRbnUSNc5Tw1tXiK"]


class TestGetKwicResults:
    def test_get_kwic_results(self, fastapi_client):
        response = fastapi_client.get(f"{version}/tools/kwic/test_search")
        assert response.status_code == 200
        result = KeywordInContextResult(**response.json())
        assert isinstance(result, KeywordInContextResult)

    def test_get_kwic_results_with_space_in_search(self, fastapi_client):
        response = fastapi_client.get(f"{version}/tools/kwic/test search")
        assert response.status_code == 200
        result = KeywordInContextResult(**response.json())
        assert isinstance(result, KeywordInContextResult)

    def test_get_kwic_results_with_lemmatized_false(self, fastapi_client):
        response = fastapi_client.get(f"{version}/tools/kwic/test_search?lemmatized=false")
        assert response.status_code == 200
        result = KeywordInContextResult(**response.json())
        assert isinstance(result, KeywordInContextResult)

    def test_get_kwic_results_with_custom_words_before_after(self, fastapi_client):
        response = fastapi_client.get(f"{version}/tools/kwic/test_search?words_before=3&words_after=3")
        assert response.status_code == 200
        result = KeywordInContextResult(**response.json())
        assert isinstance(result, KeywordInContextResult)

    def test_get_kwic_results_with_cut_off(self, fastapi_client):
        response = fastapi_client.get(f"{version}/tools/kwic/test_search?cut_off=100000")
        assert response.status_code == 200
        result = KeywordInContextResult(**response.json())
        assert isinstance(result, KeywordInContextResult)


# FIXME: #151 Fix TestGetWordTrendsResult.
@pytest.mark.skip(reason="Fails on `api_swedeb/api/utils/word_trends.py#L21` because `df` is empty")
class TestGetWordTrendsResult:

    def test_get_word_trends_result(self, fastapi_client):
        response = fastapi_client.get(f"{version}/tools/word_trends/test_search")
        assert response.status_code == 200
        result = WordTrendsResult(**response.json())
        assert isinstance(result, WordTrendsResult)

    def test_get_word_trends_result_with_normalize_true(self, fastapi_client):
        response = fastapi_client.get(f"{version}/tools/word_trends/test_search?normalize=true")
        assert response.status_code == 200
        result = WordTrendsResult(**response.json())
        assert isinstance(result, WordTrendsResult)

    def test_get_word_trends_result_with_normalize_false(self, fastapi_client):
        response = fastapi_client.get(f"{version}/tools/word_trends/test_search?normalize=false")
        assert response.status_code == 200
        result = WordTrendsResult(**response.json())
        assert isinstance(result, WordTrendsResult)


class TestGetWordTrendsSpeeches:
    def test_get_word_trend_speeches(self, fastapi_client):
        response = fastapi_client.get(f"{version}/tools/word_trend_speeches/test_search")
        assert response.status_code == 200
        result = SpeechesResultWT(**response.json())
        assert isinstance(result, SpeechesResultWT)


class TestGetWordHits:
    def test_get_word_hits(self, fastapi_client):
        response = fastapi_client.get(f"{version}/tools/word_trend_hits/test_search")
        assert response.status_code == 200
        result = SearchHits(**response.json())
        assert isinstance(result, SearchHits)


class TestGetNgramResults:
    def test_get_ngram_results(self, fastapi_client):
        response = fastapi_client.get(f"{version}/tools/ngrams/test_search")
        assert response.status_code == 200
        result = NGramResult(**response.json())
        assert isinstance(result, NGramResult)

    def test_get_ngram_results_with_width(self, fastapi_client):
        response = fastapi_client.get(f"{version}/tools/ngrams/test_search?width=4")
        assert response.status_code == 200
        result = NGramResult(**response.json())
        assert isinstance(result, NGramResult)

    def test_get_ngram_results_with_target(self, fastapi_client):
        response = fastapi_client.get(f"{version}/tools/ngrams/test_search?target=lemma")
        assert response.status_code == 200
        result = NGramResult(**response.json())
        assert isinstance(result, NGramResult)

    def test_get_ngram_results_with_mode(self, fastapi_client):
        response = fastapi_client.get(f"{version}/tools/ngrams/test_search?mode=left-aligned")
        assert response.status_code == 200
        result = NGramResult(**response.json())
        assert isinstance(result, NGramResult)

    def test_get_ngram_results_with_all_params(self, fastapi_client):
        response = fastapi_client.get(f"{version}/tools/ngrams/test_search?width=4&target=lemma&mode=right-aligned")
        assert response.status_code == 200
        result = NGramResult(**response.json())
        assert isinstance(result, NGramResult)

    def test_get_ngram_results_with_search_as_string(self, fastapi_client):
        response = fastapi_client.get(f"{version}/tools/ngrams/test search")
        assert response.status_code == 200
        result = NGramResult(**response.json())
        assert isinstance(result, NGramResult)

    @patch("api_swedeb.api.tool_router.isinstance", return_value=False)
    def test_get_ngram_results_with_search_as_list(self, mock_isinstance, fastapi_client):
        response = fastapi_client.get(f"{version}/tools/ngrams/test_search")
        assert response.status_code == 200
        result = NGramResult(**response.json())
        assert isinstance(result, NGramResult)


class TestGetSpeechesResult:
    def test_get_speeches_result(self, fastapi_client):
        response = fastapi_client.get(f"{version}/tools/speeches")
        assert response.status_code == 200
        result = SpeechesResult(**response.json())
        assert isinstance(result, SpeechesResult)


class TestGetSpeechByid:
    def test_get_speech_by_id_result(self, fastapi_client):
        response = fastapi_client.get(f"{version}/tools/speeches/test_speech_id")
        assert response.status_code == 200
        result = SpeechesTextResultItem(**response.json())
        assert isinstance(result, SpeechesTextResultItem)


class TestGetZip:
    def test_get_zip_with_valid_speech_ids(self, speech_ids, fastapi_client):
        response = fastapi_client.post(f"{version}/tools/speech_download/", json=speech_ids)
        assert response.status_code == 200
        assert response.headers['Content-Disposition'] == 'attachment; filename=speeches.zip'
        assert response.headers['Content-Type'] == 'application/zip'
        assert len(response.content) > 0

    def test_get_zip_with_invalid_speech_ids_raises_ValueError(self, fastapi_client):
        with pytest.raises(ValueError, match="unknown speech key"):
            fastapi_client.post(f"{version}/tools/speech_download/", json=["invalid_id"])

    @pytest.mark.skip(reason="HTTPException not raised. fastapi raises a RequestValidationError if the list is empty.")
    def test_get_zip_with_no_speech_ids_raises_HTTPException(self, fastapi_client):
        with pytest.raises(HTTPException, match="Speech ids are required"):
            fastapi_client.post(f"{version}/tools/speech_download/", json=[])

    @pytest.mark.skip(reason="Not intended: RequestValidationError is raised instead of HTTPException")
    def test_get_zip_with_empty_speech_ids_raises_RequestValidationError(self, fastapi_client):
        with pytest.raises(RequestValidationError):
            fastapi_client.post(f"{version}/tools/speech_download/", json=[])


class TestGetTopics:
    def test_get_topics(self, fastapi_client):
        response = fastapi_client.get(f"{version}/tools/topics")
        assert response.status_code == 200
        assert response.json() == {"message": "Not implemented yet"}
