
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


def test_additional_parameters(client):
    # asserts that there are no errors with additional paramters
    # but these are not really tested yet, since not fully implemented
    response = client.get(f"{version}/tools/speeches??from_year=1960&to_year=1962&office_types=adskfjl&sub_office_types=d&speaker_ids=lkkl&sort_by=year_title&sort_order=asc")
    assert response.status_code == status.HTTP_200_OK
