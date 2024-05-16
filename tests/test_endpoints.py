
import pytest
from fastapi.testclient import TestClient
from main import app
from fastapi import status

# these tests mainly check that the endpoints are reachable and returns something
# the actual content of the response is not checked

version = "v1"

@pytest.fixture(scope="module")
def client():
    client = TestClient(app)
    yield client

def test_read_nonexisting(client):
    response = client.get(f"{version}/kwic/ost/")
    assert response.status_code == status.HTTP_404_NOT_FOUND

############## TOOLS #####################

def test_kwic(client):
    response = client.get(f"{version}/tools/kwic/debatt")
    assert response.status_code == status.HTTP_200_OK

    json = response.json()
    first_result = json['kwic_list'][0]
    print(first_result)
    
    assert 'kwic_list' in json
    assert 'left_word' in first_result
    assert 'node_word' in first_result
    assert 'right_word' in first_result
    assert 'year' in first_result
    assert 'name' in first_result
    assert 'party_abbrev' in first_result
    assert 'speech_title' in first_result
    assert 'gender' in first_result

def test_kwic_with_with_parameters(client):
    search_term = 'debatt'
    response = client.get(
        f"{version}/tools/kwic/{search_term}?words_before=2&words_after=2&cut_off=200&lemmatized=false"
        "&from_year=1960&to_year=1961&who=Q5781896&who=Q5584283&who=Q5746460&party_id=1&office_types=1&sub_office_types=1&sub_office_types=2&gender_id=1"
    )
    assert response.status_code == status.HTTP_200_OK
    json = response.json()
    assert 'kwic_list' in json

def test_kwic_without_search_term(client):
    response = client.get(f"{version}/tools/kwic")
    assert response.status_code == status.HTTP_404_NOT_FOUND # search term is missing

def test_kwic_bad_param(client):
    search_term = 'debatt'
    response = client.get(f"{version}/tools/kwic/{search_term}?made_up_param=1")
    assert response.status_code == status.HTTP_200_OK



def test_word_trends(client):

    response = client.get(f"{version}/tools/word_trends/debatt")
    assert response.status_code == status.HTTP_200_OK

    json = response.json()
    assert len(json) > 0

def test_ngrams(client):
    search_term = 'debatt'

    response = client.get(f"{version}/tools/ngrams/{search_term}")
    assert response.status_code == status.HTTP_200_OK
    json = response.json()

    assert 'ngram_list' in json
    first_result = json['ngram_list'][0]
    assert 'ngram' in first_result
    assert 'count' in first_result

def test_ngrams_non_existing_word(client):
    # ngram should handle unknown words
    search_term = 'xyzåölkråka'

    response = client.get(f"{version}/tools/ngrams/{search_term}")
    assert response.status_code == status.HTTP_200_OK
    json = response.json()

    assert 'ngram_list' in json
    first_result = json['ngram_list'][0]
    assert 'ngram' in first_result
    assert 'count' in first_result




def test_speech_by_id(client):
    response = client.get(f"{version}/tools/speeches/1")
    assert response.status_code == status.HTTP_200_OK
    
    json = response.json()
    assert 'speaker_note' in json
    assert 'speech_text' in json

def test_topics(client):
    response = client.get(f"{version}/tools/topics")
    assert response.status_code == status.HTTP_200_OK
    
    json = response.json()
    assert 'message' in json
    assert json['message'] == 'Not implemented yet'


############## METADATA #####################

def test_start_year(client):
    response = client.get(f"{version}/metadata/start_year")
    assert response.status_code == status.HTTP_200_OK

    

def test_end_year(client):
    response = client.get(f"{version}/metadata/end_year")
    assert response.status_code == status.HTTP_200_OK


    

def test_speakers(client):
    
    response = client.get(f"{version}/metadata/speakers")
    assert response.status_code == status.HTTP_200_OK

