
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
        assert 'year' in speech, 'year is missing in response'
        assert speech['year'] >= start_year, 'year is less than start_year'
        assert speech['year'] <= end_year, 'year is greater than end_year'


def test_get_speeches_corpus(corpus):
    df_filtered = corpus.get_anforanden(
        from_year= 1900,
        to_year= 2000,
        selections = {'party_id':[4,5], 'gender_id':[1,2]},
        di_selected= None)
     
    print(df_filtered.head()[['year', 'gender', 'party_abbrev']])
    print(df_filtered.columns)
    df_unfiltered = corpus.get_anforanden(
        from_year= 1900,
        to_year= 2000,
        selections = {},
        di_selected= None)
    assert len(df_filtered) < len(df_unfiltered)
    assert df_filtered['party_abbrev'].unique() == ['L']


def test_get_speeches_corpus_party_id(corpus):
    df_filtered = corpus.get_anforanden(
        from_year= 1900,
        to_year= 2000,
        selections = {'party_id':[4,5]},
        di_selected= None)
     
     
    print(df_filtered.head())



def find_a_speech_id(corpus):
    df = corpus.get_anforanden(
        from_year= 1900,
        to_year= 2000,
        selections = {},
        di_selected= None)
    return (df.iloc[0]['document_name'])
    

def test_get_speech_by_id(corpus):
    speech_id = find_a_speech_id(corpus)
    speech_text = corpus.get_speech_text(speech_id)
    assert speech_text is not None
    assert len(speech_text) > 0

def test_get_speech_by_id_missing(corpus):
    # non-existing speech (gives empty string as response)
    speech_id = 'prot-1971--1_007_missing'
    speech_text = corpus.get_speech_text(speech_id)
    assert len(speech_text) == 0
    

def test_get_speaker_note(corpus):
    speech_id = find_a_speech_id(corpus)
    speaker_note = corpus.get_speaker_note(speech_id)
    assert speaker_note is not None
    assert len(speaker_note) > 0
    print(speaker_note)


def test_get_speech_by_api(client, corpus):
    speech_id = find_a_speech_id(corpus)
    response = client.get(f"{version}/tools/speeches/{speech_id}")
    assert response.status_code == status.HTTP_200_OK
    assert len(response.json()['speech_text']) > 0
    assert len(response.json()['speaker_note']) > 0

