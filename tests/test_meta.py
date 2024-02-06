
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



def test_parties_test_test(corpus):
    parties = corpus.get_available_parties()
    assert len(parties) > 0
    assert 'S' in parties


def test_parties_api(client):
    response = client.get(f"{version}/metadata/parties")
    assert response.status_code == status.HTTP_200_OK
    json = response.json()
    assert 'parties' in json
    assert len(json['parties']) > 0
    assert 'S' in json['parties']


def test_start_year(client):
    response = client.get(f"{version}/metadata/start_year")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == 1960
    

def test_end_year(client):
    response = client.get(f"{version}/metadata/end_year")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == 1980




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