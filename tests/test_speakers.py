

import pytest
from fastapi.testclient import TestClient
from main import app
from fastapi import status
from api_swedeb.api.utils.corpus import load_corpus



version = "v1"

@pytest.fixture(scope="module")
def client():
    client = TestClient(app)
    yield client

@pytest.fixture(scope="module")
def corpus():
    return load_corpus('.env_1960')


def test_get_speakers(corpus):
    speakers = corpus.get_speakers(selections={})
    assert len(speakers) > 0
    assert 'Tage Erlander'in speakers['speaker_name'].values
    print(speakers.head())
    print(speakers.columns)
    print(speakers['has_multiple_parties'].unique())


def test_get_filtered_speakers_by_party_int(corpus):
    speakers = corpus.get_speakers(selections={'party_id':[9]})
    assert len(speakers) > 0
    assert 'Tage Erlander'in speakers['speaker_name'].values
    assert 'S' in speakers['speaker_party'].unique()
    assert len(speakers['speaker_party'].unique()) == 1
    print(speakers.columns)

def test_get_speakers_api(client):
    
    response = client.get(f"{version}/metadata/speakers")
    assert response.status_code == status.HTTP_200_OK

    json = response.json()
    assert 'speaker_list' in json
    first_result = json['speaker_list'][0]
    assert 'speaker_name' in first_result
    assert 'speaker_party' in first_result
    assert 'speaker_birth_year' in first_result
    assert 'speaker_death_year' in first_result


def test_get_speakers_api_with_params(client):
    
    response = client.get(f"{version}/metadata/speakers?party_id=9&gender_id=2")
    assert response.status_code == status.HTTP_200_OK

    json = response.json()
    assert 'speaker_list' in json
    for speaker in json['speaker_list']:
        assert speaker['speaker_party'] == 'S'
        assert 'Tage' not in speaker['speaker_name']
        
    print(json)