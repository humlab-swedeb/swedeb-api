

import pytest
from fastapi.testclient import TestClient
from main import app
from fastapi import status
from api_swedeb.api.utils.corpus import load_corpus
import pandas as pd

pd.set_option('display.max_columns', None)

version = "v1"

@pytest.fixture(scope="module")
def client():
    client = TestClient(app)
    yield client

@pytest.fixture(scope="module")
def corpus():
    return load_corpus('.env_1920_2020')








    

def test_get_speakers(corpus):
    speakers = corpus.get_speakers(selections={})
    assert len(speakers) > 0



def test_get_filtered_speakers_by_party_int(corpus):
    # party_id 9 is S
    speakers = corpus.get_speakers(selections={'party_id':[9]})
    assert len(speakers) > 0
    assert 'S' in speakers['party_abbrev'].unique()
    assert all(['S' in pa for pa in speakers['party_abbrev'].unique()])




def test_get_speakers_api(client):
    
    response = client.get(f"{version}/metadata/speakers")
    assert response.status_code == status.HTTP_200_OK

    json = response.json()
    assert 'speaker_list' in json
    first_result = json['speaker_list'][0]
    assert 'name' in first_result
    assert 'party_abbrev' in first_result
    assert 'year_of_birth' in first_result
    assert 'year_of_death' in first_result


def test_get_speakers_api_with_params(client):
    
    response = client.get(f"{version}/metadata/speakers?party_id=9&gender_id=2")
    assert response.status_code == status.HTTP_200_OK

    json = response.json()
    assert 'speaker_list' in json
    for speaker in json['speaker_list']:
        assert 'S' in speaker['party_abbrev']
        
        print(speaker)
        
