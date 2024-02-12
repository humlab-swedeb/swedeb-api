
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
    response = client.get(f"{version}/tools/kwic/search_term?from_year=1960&to_year=1970&office_types=riksdagsledamot&sub_office_types=riksdagsledamot&speaker_ids=1&sort_by=year_title&parties=S&genders=M&chambers=riksdagen&limit=10&offset=0&sort_order=asc")
    assert response.status_code == status.HTTP_200_OK
    json = response.json()
    assert 'kwic_list' in json

def test_kwic_without_search_term(client):
    response = client.get(f"{version}/tools/kwic")
    assert response.status_code == status.HTTP_404_NOT_FOUND # search term is missing

def test_kwic_bad_param(client):
    response = client.get(f"{version}/tools/kwic/search_term?made_up_param=1")
    json = response.json()
    print(json)

def test_word_trends(client):

    response = client.get(f"{version}/tools/word_trends/search_term")
    assert response.status_code == status.HTTP_200_OK

    json = response.json()
    first_result = json['wt_list'][0]

    assert 'year' in first_result
    assert 'count' in first_result
    assert 'search_term' in first_result['count']
    assert first_result['count']['search_term'] == 1


def test_ngrams(client):
    response = client.get(f"{version}/tools/ngrams/search_term")
    assert response.status_code == status.HTTP_200_OK
    json = response.json()

    assert 'ngram_list' in json
    first_result = json['ngram_list'][0]
    assert 'ngram' in first_result
    assert 'count' in first_result

def test_speeches(client):
    response = client.get(f"{version}/tools/speeches")
    assert response.status_code == status.HTTP_200_OK
    
    json = response.json()
    first_result = json['speech_list'][0]
    
    assert 'speech_list' in json
    assert 'speaker_column' in first_result
    assert 'year_column' in first_result
    assert 'gender_column' in first_result
    assert 'party_column' in first_result
    assert 'source_column' in first_result
    assert 'speech_id_column' in first_result


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


    

def test_parties(client):
    response = client.get(f"{version}/metadata/parties")
    assert response.status_code == status.HTTP_200_OK
    json = response.json()
    assert 'parties' in json
    assert len(json['parties']) > 0

def test_genders(client):
    response = client.get(f"{version}/metadata/genders")
    assert response.status_code == status.HTTP_200_OK

    json = response.json()
    assert 'genders' in json
    assert len(json['genders']) > 0

def test_chambers(client):
    
    response = client.get(f"{version}/metadata/chambers")
    assert response.status_code == status.HTTP_200_OK

    json = response.json()
    assert 'chambers' in json
    assert len(json['chambers']) > 0

def test_office_types(client):
    
    response = client.get(f"{version}/metadata/office_types")
    assert response.status_code == status.HTTP_200_OK

    json = response.json()

    assert 'office_types' in json
    assert len(json['office_types']) > 0

def test_sub_office_types(client):
    
    response = client.get(f"{version}/metadata/sub_office_types")
    assert response.status_code == status.HTTP_200_OK

    json = response.json()
    assert 'sub_office_types' in json
    assert len(json['sub_office_types']) > 0

def test_speakers(client):
    
    response = client.get(f"{version}/metadata/speakers")
    assert response.status_code == status.HTTP_200_OK

    json = response.json()
    assert 'speaker_list' in json
    first_result = json['speaker_list'][0]
    assert 'speaker_name' in first_result
    assert 'speaker_party' in first_result
    assert 'speaker_birth_year' in first_result
    assert 'speaker_death_year' in first_result
