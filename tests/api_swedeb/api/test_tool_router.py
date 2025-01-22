from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from api_swedeb.api.tool_router import router
from api_swedeb.api.utils.common_params import CommonQueryParams
from api_swedeb.schemas.kwic_schema import KeywordInContextResult
from api_swedeb.schemas.word_trends_schema import WordTrendsResult, SearchHits
from api_swedeb.schemas.ngrams_schema import NGramResult
from api_swedeb.schemas.speech_text_schema import SpeechesTextResultItem
from api_swedeb.schemas.speeches_schema import SpeechesResult, SpeechesResultWT

client = TestClient(router)

version = "v1"


class TestGetKwicResults:
    def test_get_kwic_results(self):
        response = client.get(f"{version}/tools/kwic/test_search")
        assert response.status_code == 200
        result = KeywordInContextResult(**response.json())
        assert isinstance(result, KeywordInContextResult)
        
    def test_get_kwic_results_with_space_in_search(self):
        response = client.get(f"{version}/tools/kwic/test search")
        assert response.status_code == 200
        result = KeywordInContextResult(**response.json())
        assert isinstance(result, KeywordInContextResult)

    def test_get_kwic_results_with_lemmatized_false(self):
        response = client.get(f"{version}/tools/kwic/test_search?lemmatized=false")
        assert response.status_code == 200
        result = KeywordInContextResult(**response.json())
        assert isinstance(result, KeywordInContextResult)


    def test_get_kwic_results_with_custom_words_before_after(self):
        response = client.get(f"{version}/tools/kwic/test_search?words_before=3&words_after=3")
        assert response.status_code == 200
        result = KeywordInContextResult(**response.json())
        assert isinstance(result, KeywordInContextResult)


    def test_get_kwic_results_with_cut_off(self):
        response = client.get(f"{version}/tools/kwic/test_search?cut_off=100000")
        assert response.status_code == 200
        result = KeywordInContextResult(**response.json())
        assert isinstance(result, KeywordInContextResult)


class TestGetWordTrendsResult:
    def test_get_word_trends_result(self):
        response = client.get(f"{version}/tools/word_trends/test_search")
        assert response.status_code == 200
        result = WordTrendsResult(**response.json())
        assert isinstance(result, WordTrendsResult)

class TestGetWordTrendsSpeeches:
    def test_get_word_trend_speeches(self):
        response = client.get(f"{version}/tools/word_trend_speeches/test_search")
        assert response.status_code == 200
        result = SpeechesResultWT(**response.json())
        assert isinstance(result, SpeechesResultWT)

class TestGetWordHits:
    def test_get_word_hits(self):
        response = client.get(f"{version}/tools/word_trend_hits/test_search")
        assert response.status_code == 200
        result = SearchHits(**response.json())
        assert isinstance(result, SearchHits)
        
class TestGetNgramResults:
    def test_get_ngram_results(self):
        response = client.get(f"{version}/tools/ngrams/test_search")
        assert response.status_code == 200
        result = NGramResult(**response.json())
        assert isinstance(result, NGramResult)

    def test_get_ngram_results_with_width(self):
        response = client.get(f"{version}/tools/ngrams/test_search?width=4")
        assert response.status_code == 200
        result = NGramResult(**response.json())
        assert isinstance(result, NGramResult)

    def test_get_ngram_results_with_target(self):
        response = client.get(f"{version}/tools/ngrams/test_search?target=lemma")
        assert response.status_code == 200
        result = NGramResult(**response.json())
        assert isinstance(result, NGramResult)

    def test_get_ngram_results_with_mode(self):
        response = client.get(f"{version}/tools/ngrams/test_search?mode=left-aligned")
        assert response.status_code == 200
        result = NGramResult(**response.json())
        assert isinstance(result, NGramResult)

    def test_get_ngram_results_with_all_params(self):
        response = client.get(f"{version}/tools/ngrams/test_search?width=4&target=lemma&mode=right-aligned")
        assert response.status_code == 200
        result = NGramResult(**response.json())
        assert isinstance(result, NGramResult)

    def test_get_ngram_results_with_search_as_string(self):
        response = client.get(f"{version}/tools/ngrams/test search")
        assert response.status_code == 200
        result = NGramResult(**response.json())
        assert isinstance(result, NGramResult)
        
    @patch("api_swedeb.api.tool_router.isinstance", return_value=False)
    def test_get_ngram_results_with_search_as_list(self, mock_isinstance):
        response = client.get(f"{version}/tools/ngrams/test_search")
        assert response.status_code == 200
        result = NGramResult(**response.json())
        assert isinstance(result, NGramResult)



class TestGetWordTrendsResult:
    def test_get_speeches_result(self):
        response = client.get(f"{version}/tools/speeches")
        assert response.status_code == 200
        result = SpeechesResult(**response.json())
        assert isinstance(result, SpeechesResult)

class TestGetSpeechByid:
    def test_get_speech_by_id_result(self):
        response = client.get(f"{version}/tools/speeches/test_speech_id")
        assert response.status_code == 200
        result = SpeechesTextResultItem(**response.json())
        assert isinstance(result, SpeechesTextResultItem)

@pytest.mark.skip(reason="Not implemented yet. speech_text.py raises ValueError")
def test_get_zip():
    response = client.post(f"{version}/tools/speech_download/", json=["test_id1", "test_id2"])
    assert response.status_code == 200
    assert response.headers['Content-Disposition'] == 'attachment; filename=speeches.zip'
    assert response.headers['Content-Type'] == 'application/zip'
    assert len(response.content) > 0


class TestGetTopics:
    def test_get_topics(self):
        response = client.get(f"{version}/tools/topics")
        assert response.status_code == 200
        assert response.json() == {"message": "Not implemented yet"}
        
        
