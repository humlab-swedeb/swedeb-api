from unittest.mock import Mock, patch

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from api_swedeb.api.metadata_router import router
from api_swedeb.api.utils.dependencies import get_shared_corpus
from api_swedeb.schemas.metadata_schema import (
    ChamberList,
    GenderItem,
    GenderList,
    OfficeTypeList,
    PartyItem,
    PartyList,
    SpeakerItem,
    SpeakerResult,
    SubOfficeTypeList,
)


@patch("api_swedeb.api.metadata_router.get_start_year", return_value=1234)
def test_get_meta_start_year(mock_get_start_year: Mock, fastapi_client):
    response = fastapi_client.get("/v1/metadata/start_year")
    assert response.status_code == status.HTTP_200_OK
    assert isinstance(response.json(), int)
    assert response.json() == 1234


@patch("api_swedeb.api.metadata_router.get_end_year", return_value=1234)
def test_get_meta_end_year(mock_get_end_year: Mock, fastapi_client):
    response = fastapi_client.get("/v1/metadata/end_year")
    assert response.status_code == status.HTTP_200_OK
    assert isinstance(response.json(), int)
    assert response.json() == 1234


@patch(
    "api_swedeb.api.metadata_router.get_parties",
    return_value=PartyList(party_list=[PartyItem(party_id=1, party="Party A", party_abbrev="PA", party_color="red")]),
)
def test_get_meta_parties(mock_get_parties: Mock, fastapi_client):
    response = fastapi_client.get("/v1/metadata/parties")
    assert response.status_code == status.HTTP_200_OK
    assert isinstance(response.json(), dict)
    assert 'party_list' in response.json()
    assert len(response.json()['party_list']) == 1
    assert isinstance(response.json()['party_list'], list)  # NOTE: Should be a PartyList object?
    assert isinstance(response.json()['party_list'][0], dict)  # NOTE: Should be a PartyItem object?
    assert response.json() == {
        "party_list": [{"party_id": 1, "party": "Party A", "party_abbrev": "PA", "party_color": "red"}]
    }


@patch(
    "api_swedeb.api.metadata_router.get_genders",
    return_value=GenderList(gender_list=[GenderItem(gender_id=1, gender="gender", gender_abbrev="G")]),
)
def test_get_meta_genders(mock_get_genders: Mock, fastapi_client):
    response = fastapi_client.get("/v1/metadata/genders")
    assert response.status_code == status.HTTP_200_OK
    assert isinstance(response.json(), dict)
    assert 'gender_list' in response.json()
    assert len(response.json()['gender_list']) == 1
    assert isinstance(response.json()['gender_list'], list)  # NOTE: Should be a GenderList object?
    assert isinstance(response.json()['gender_list'][0], dict)  # NOTE: Should be a GenderItem object?
    assert response.json() == {"gender_list": [{"gender_id": 1, "gender": "gender", "gender_abbrev": "G"}]}


@patch(
    "api_swedeb.api.metadata_router.get_chambers",
    return_value=ChamberList(chamber_list=[{"chamber_id": 1, "chamber": "chamber", "chamber_abbrev": "C"}]),
)
def test_get_meta_chambers(mock_get_chambers: Mock, fastapi_client):
    response = fastapi_client.get("/v1/metadata/chambers")
    assert response.status_code == status.HTTP_200_OK
    assert isinstance(response.json(), dict)
    assert 'chamber_list' in response.json()
    assert len(response.json()['chamber_list']) == 1
    assert isinstance(response.json()['chamber_list'], list)  # NOTE: Should be a ChamberList object?
    assert isinstance(response.json()['chamber_list'][0], dict)  # NOTE: Should be a ChamberItem object?
    assert response.json() == {"chamber_list": [{"chamber_id": 1, "chamber": "chamber", "chamber_abbrev": "C"}]}


@patch(
    "api_swedeb.api.metadata_router.get_office_types",
    return_value=OfficeTypeList(office_type_list=[{"office_type_id": 1, "office": "office"}]),
)
def test_get_meta_office_types(mock_get_office_types: Mock, fastapi_client):
    response = fastapi_client.get("/v1/metadata/office_types")
    assert response.status_code == status.HTTP_200_OK
    assert isinstance(response.json(), dict)
    assert 'office_type_list' in response.json()
    assert len(response.json()['office_type_list']) == 1
    assert isinstance(response.json()['office_type_list'], list)  # NOTE: Should be a OfficeTypeList object?
    assert isinstance(response.json()['office_type_list'][0], dict)  # NOTE: Should be a OfficeTypeItem object?
    assert response.json() == {"office_type_list": [{"office_type_id": 1, "office": "office"}]}


@patch(
    "api_swedeb.api.metadata_router.get_sub_office_types",
    return_value=SubOfficeTypeList(
        sub_office_type_list=[{"sub_office_type_id": 1, "office_type_id": 1, "identifier": "identifier"}]
    ),
)
def test_get_meta_sub_office_types(mock_get_sub_office_types: Mock, fastapi_client):
    response = fastapi_client.get("/v1/metadata/sub_office_types")
    assert response.status_code == status.HTTP_200_OK
    assert isinstance(response.json(), dict)
    assert 'sub_office_type_list' in response.json()
    assert len(response.json()['sub_office_type_list']) == 1
    assert isinstance(response.json()['sub_office_type_list'], list)  # NOTE: Should be a SubOfficeTypeList object?
    assert isinstance(response.json()['sub_office_type_list'][0], dict)  # NOTE: Should be a SubOfficeTypeItem object?
    assert response.json() == {
        "sub_office_type_list": [{"sub_office_type_id": 1, "office_type_id": 1, "identifier": "identifier"}]
    }


@patch(
    "api_swedeb.api.metadata_router.get_speakers",
    return_value=SpeakerResult(
        speaker_list=[
            SpeakerItem(name="name", party_abbrev="PA", year_of_birth=1800, year_of_death=1940, person_id="123")
        ]
    ),
)
def test_get_meta_speakers(mock_get_speakers: Mock, fastapi_client):
    response = fastapi_client.get("/v1/metadata/speakers")
    assert response.status_code == status.HTTP_200_OK
    assert isinstance(response.json(), dict)
    assert 'speaker_list' in response.json()
    assert len(response.json()['speaker_list']) == 1
    assert isinstance(response.json()['speaker_list'], list)  # NOTE: Should be a SpeakerResult object?
    assert isinstance(response.json()['speaker_list'][0], dict)  # NOTE: Should be a SpeakerItem object?
    assert response.json() == {
        "speaker_list": [
            {"name": "name", "party_abbrev": "PA", "year_of_birth": 1800, "year_of_death": 1940, "person_id": "123"}
        ]
    }
