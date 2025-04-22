from unittest.mock import patch

import pytest

from api_swedeb.schemas.kwic_schema import KeywordInContextResult
from api_swedeb.schemas.ngrams_schema import NGramResult
from api_swedeb.schemas.speech_text_schema import SpeechesTextResultItem
from api_swedeb.schemas.speeches_schema import SpeechesResult, SpeechesResultWT
from api_swedeb.schemas.word_trends_schema import SearchHits, WordTrendsResult

VERSION = "v1"
EXISTING_SEARCH_TERM = "vad"
NON_EXISTING_SEARCH_TERM = "non_existing_word"


@pytest.fixture(name='speech_ids')
def mock_speech_ids():
    return ["i-Tthy1hzk6Yg4W5NfXLwJrA;i-Ua1nqYCRbnUSNc5Tw1tXiK", "i-284a2ff9c2603b5f-0;i-Ua1nqYCRbnUSNc5Tw1tXiK"]


# NOTE: search other than "test_search". Search with some other string that is in test data.
class TestGetKwicResults:

    @pytest.mark.parametrize("search_term", [EXISTING_SEARCH_TERM, NON_EXISTING_SEARCH_TERM])
    def test_get_kwic_results(self, fastapi_client, search_term):
        response = fastapi_client.get(f"{VERSION}/tools/kwic/{search_term}")
        assert response.status_code == 200
        result = KeywordInContextResult(**response.json())
        assert isinstance(result, KeywordInContextResult)

    @pytest.mark.parametrize("search_term", ["test search", "vad är"])
    def test_get_kwic_results_with_space_in_search(self, fastapi_client, search_term):
        response = fastapi_client.get(f"{VERSION}/tools/kwic/{search_term}")
        assert response.status_code == 200
        result = KeywordInContextResult(**response.json())
        assert isinstance(result, KeywordInContextResult)

    @pytest.mark.parametrize("search_term", [EXISTING_SEARCH_TERM, NON_EXISTING_SEARCH_TERM])
    def test_get_kwic_results_with_lemmatized_false(self, fastapi_client, search_term):
        response = fastapi_client.get(f"{VERSION}/tools/kwic/{search_term}?lemmatized=false")
        assert response.status_code == 200
        result = KeywordInContextResult(**response.json())
        assert isinstance(result, KeywordInContextResult)

    @pytest.mark.parametrize("search_term", [EXISTING_SEARCH_TERM, NON_EXISTING_SEARCH_TERM])
    def test_get_kwic_results_with_custom_words_before_after(self, fastapi_client, search_term):
        response = fastapi_client.get(f"{VERSION}/tools/kwic/{search_term}?words_before=3&words_after=3")
        assert response.status_code == 200
        result = KeywordInContextResult(**response.json())
        assert isinstance(result, KeywordInContextResult)

    @pytest.mark.parametrize("search_term", [EXISTING_SEARCH_TERM, NON_EXISTING_SEARCH_TERM])
    def test_get_kwic_results_with_cut_off(self, fastapi_client, search_term):
        response = fastapi_client.get(f"{VERSION}/tools/kwic/{search_term}?cut_off=100000")
        assert response.status_code == 200
        result = KeywordInContextResult(**response.json())
        assert isinstance(result, KeywordInContextResult)


class TestGetWordTrendsResult:

    def test_get_word_trends_result(self, fastapi_client):
        response = fastapi_client.get(f"{VERSION}/tools/word_trends/{EXISTING_SEARCH_TERM}")
        assert response.status_code == 200
        result = WordTrendsResult(**response.json())
        assert isinstance(result, WordTrendsResult)

    # FIXME: #151 get_word_trends uses .str accessor on columns that may contain non-string data
    def test_get_word_trends_result_with_non_existing_word(self, fastapi_client):
        with pytest.raises(AttributeError, match="Can only use .str accessor with string values!"):
            fastapi_client.get(f"{VERSION}/tools/word_trends/{NON_EXISTING_SEARCH_TERM}")

    def test_get_word_trends_result_with_normalize_true(self, fastapi_client):
        response = fastapi_client.get(f"{VERSION}/tools/word_trends/{EXISTING_SEARCH_TERM}?normalize=true")
        assert response.status_code == 200
        result = WordTrendsResult(**response.json())
        assert isinstance(result, WordTrendsResult)

    def test_get_word_trends_result_with_normalize_false(self, fastapi_client):
        response = fastapi_client.get(f"{VERSION}/tools/word_trends/{EXISTING_SEARCH_TERM}?normalize=false")
        assert response.status_code == 200
        result = WordTrendsResult(**response.json())
        assert isinstance(result, WordTrendsResult)


class TestGetWordTrendsSpeeches:
    @pytest.mark.parametrize("search_term", [EXISTING_SEARCH_TERM, NON_EXISTING_SEARCH_TERM])
    def test_get_word_trend_speeches(self, fastapi_client, search_term):
        response = fastapi_client.get(f"{VERSION}/tools/word_trend_speeches/{search_term}")
        assert response.status_code == 200
        result = SpeechesResultWT(**response.json())
        assert isinstance(result, SpeechesResultWT)


class TestGetWordHits:
    @pytest.mark.parametrize("search_term", [EXISTING_SEARCH_TERM, NON_EXISTING_SEARCH_TERM])
    def test_get_word_hits(self, fastapi_client, search_term):
        response = fastapi_client.get(f"{VERSION}/tools/word_trend_hits/{search_term}")
        assert response.status_code == 200
        result = SearchHits(**response.json())
        assert isinstance(result, SearchHits)


class TestGetNgramResults:
    @pytest.mark.parametrize("search_term", [EXISTING_SEARCH_TERM, NON_EXISTING_SEARCH_TERM])
    def test_get_ngram_results(self, fastapi_client, search_term):
        response = fastapi_client.get(f"{VERSION}/tools/ngrams/{search_term}")
        assert response.status_code == 200
        result = NGramResult(**response.json())
        assert isinstance(result, NGramResult)

    @pytest.mark.parametrize("search_term", [EXISTING_SEARCH_TERM, NON_EXISTING_SEARCH_TERM])
    def test_get_ngram_results_with_width(self, fastapi_client, search_term):
        response = fastapi_client.get(f"{VERSION}/tools/ngrams/{search_term}?width=4")
        assert response.status_code == 200
        result = NGramResult(**response.json())
        assert isinstance(result, NGramResult)

    def test_get_ngram_results_with_invalid_width(self, fastapi_client):
        response = fastapi_client.get(f"{VERSION}/tools/ngrams/{EXISTING_SEARCH_TERM}?width=invalid")
        assert response.status_code == 422
        assert response.is_error

    @pytest.mark.parametrize("search_term", [EXISTING_SEARCH_TERM, NON_EXISTING_SEARCH_TERM])
    def test_get_ngram_results_with_target(self, fastapi_client, search_term):
        response = fastapi_client.get(f"{VERSION}/tools/ngrams/{search_term}?target=lemma")
        assert response.status_code == 200
        result = NGramResult(**response.json())
        assert isinstance(result, NGramResult)

    @pytest.mark.parametrize("search_term", [EXISTING_SEARCH_TERM, NON_EXISTING_SEARCH_TERM])
    def test_get_ngram_results_with_mode(self, fastapi_client, search_term):
        response = fastapi_client.get(f"{VERSION}/tools/ngrams/{search_term}?mode=left-aligned")
        assert response.status_code == 200
        result = NGramResult(**response.json())
        assert isinstance(result, NGramResult)

    @pytest.mark.parametrize("search_term", [EXISTING_SEARCH_TERM, NON_EXISTING_SEARCH_TERM])
    def test_get_ngram_results_with_all_params(self, fastapi_client, search_term):
        response = fastapi_client.get(f"{VERSION}/tools/ngrams/{search_term}?width=4&target=lemma&mode=right-aligned")
        assert response.status_code == 200
        result = NGramResult(**response.json())
        assert isinstance(result, NGramResult)

    @pytest.mark.parametrize("search_term", [EXISTING_SEARCH_TERM, NON_EXISTING_SEARCH_TERM])
    def test_get_ngram_results_with_search_as_string(self, fastapi_client, search_term):
        response = fastapi_client.get(f"{VERSION}/tools/ngrams/{search_term}?search=test_search")
        assert response.status_code == 200
        result = NGramResult(**response.json())
        assert isinstance(result, NGramResult)

    @pytest.mark.parametrize("search_term", [EXISTING_SEARCH_TERM, NON_EXISTING_SEARCH_TERM])
    @patch("api_swedeb.api.tool_router.isinstance", return_value=False)
    def test_get_ngram_results_with_search_as_list(self, mock_isinstance, fastapi_client, search_term):
        response = fastapi_client.get(f"{VERSION}/tools/ngrams/{search_term}?search=test_search")
        assert response.status_code == 200
        result = NGramResult(**response.json())
        assert isinstance(result, NGramResult)


class TestGetSpeechesResult:
    def test_get_speeches_result(self, fastapi_client):
        response = fastapi_client.get(f"{VERSION}/tools/speeches")
        assert response.status_code == 200
        result = SpeechesResult(**response.json())
        assert isinstance(result, SpeechesResult)


class TestGetSpeechByid:
    def test_get_speech_by_id_result(self, fastapi_client):
        response = fastapi_client.get(f"{VERSION}/tools/speeches/test_speech_id")
        assert response.status_code == 200
        result = SpeechesTextResultItem(**response.json())
        assert isinstance(result, SpeechesTextResultItem)


class TestGetZip:
    def test_get_zip_with_valid_speech_ids(self, speech_ids, fastapi_client):
        response = fastapi_client.post(f"{VERSION}/tools/speech_download/", json=speech_ids)
        assert response.status_code == 200
        assert response.headers['Content-Disposition'] == 'attachment; filename=speeches.zip'
        assert response.headers['Content-Type'] == 'application/zip'
        assert len(response.content) > 0

    def test_get_zip_with_invalid_speech_ids_raises_ValueError(self, fastapi_client):
        with pytest.raises(ValueError, match="unknown speech key"):
            fastapi_client.post(f"{VERSION}/tools/speech_download/", json=["invalid_id"])


class TestGetTopics:
    def test_get_topics(self, fastapi_client):
        response = fastapi_client.get(f"{VERSION}/tools/topics")
        assert response.status_code == 200
        assert response.json() == {"message": "Not implemented yet"}
