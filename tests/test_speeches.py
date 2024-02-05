
import pytest
from fastapi.testclient import TestClient
from main import app
from fastapi import status
from api_swedeb.api.utils.corpus import load_corpus

# these tests mainly check that the endpoints are reachable and returns something
# the actual content of the response is not checked

version = "v1"

@pytest.fixture(scope="module")
def client():
    client = TestClient(app)
    yield client

@pytest.fixture(scope="module")
def corpus():
    return load_corpus('.env_1960')

def test_speeches_get(client):
    # assert that the speeches endpoint is reachable
    response = client.get(f"{version}/tools/speeches/")
    assert response.status_code == status.HTTP_200_OK
    print(response.json())


def test_speeches_get_years(client):
    # assert that the returned speeches comes from the correct years
    start_year = 1960
    end_year = 1961
    response = client.get(f"{version}/tools/speeches?from_year={start_year}&to_year={end_year}")
    assert response.status_code == status.HTTP_200_OK
    speeches = response.json()['speech_list']
    for speech in speeches:
        assert 'year_column' in speech, 'year_column is missing in response'
        assert speech['year_column'] >= start_year, 'year_column is less than start_year'
        assert speech['year_column'] <= end_year, 'year_column is greater than end_year'


def test_speaker_id(client):
    # retrieve speeches from a specific speaker
    response = client.get(f"{version}/tools/speeches?speaker_ids=Q1606431")
    speeches = response.json()['speech_list']
    print(speeches)
    for speech in speeches:
        assert 'speaker_column' in speech, 'speaker_column is missing in response'
        assert speech['speaker_column'] == 'Henry Allard', 'Q1606431 should be Henry Allard'


def test_get_speech_by_id(corpus):
    speech_id = 'prot-1971--1_007'
    speech_text = corpus.get_speech_text(speech_id)
    assert speech_text is not None
    assert len(speech_text) > 0

def test_get_speech_by_id_missing(corpus):
    # non-existing speech (gives empty string as response)
    speech_id = 'prot-1971--1_007_missing'
    speech_text = corpus.get_speech_text(speech_id)
    assert len(speech_text) == 0
    

def test_get_speaker_note(corpus):
    speech_id = 'prot-1971--1_007'
    speaker_note = corpus.get_speaker_note(speech_id)
    assert speaker_note is not None
    assert len(speaker_note) > 0
    print(speaker_note)


def test_get_speech_by_api(client):
    speech_id = 'prot-1971--1_007'
    response = client.get(f"{version}/tools/speeches/{speech_id}")
    assert response.status_code == status.HTTP_200_OK
    assert len(response.json()['speech_text']) > 0
    assert len(response.json()['speaker_note']) > 0
