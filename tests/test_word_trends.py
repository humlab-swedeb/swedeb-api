from api_swedeb.api.utils.corpus import Corpus

import pytest
from fastapi.testclient import TestClient
from main import app
from fastapi import status

version = 'v1'
@pytest.fixture(scope="module")
def corpus():
    env_file = '.env_1960'
    corpus = Corpus(env_file=env_file)
    return corpus

@pytest.fixture(scope="module")
def client():
    client = TestClient(app)
    yield client


def test_word_trends(client):
    search_term = '*debatt'
    response = client.get(f"{version}/tools/word_trends/{search_term}")
    assert response.status_code == status.HTTP_200_OK

    json = response.json()
    first_result = json['wt_list'][0]

    assert 'year' in first_result
    assert 'count' in first_result
    assert search_term in first_result['count']
    assert first_result['count'][search_term] == 1


def test_word_trends_speeches(client):
    search_term = '*debatt'

    response = client.get(f"{version}/tools/word_trend_speeches/{search_term}")
    assert response.status_code == status.HTTP_200_OK

    json = response.json()
    first_result = json['speech_list'][0]

    assert 'year_column' in first_result
    assert 'speaker_column' in first_result
    assert 'gender_column' in first_result
    assert 'party_column' in first_result
    assert 'source_column' in first_result
    assert 'speech_id_column' in first_result
    assert 'hit' in first_result

def test_word_trend_corpus(corpus):
    corpus.get_word_trends()