import pandas as pd
import pytest
from fastapi import status

from api_swedeb.api.utils.corpus import Corpus, load_corpus
from api_swedeb.schemas.metadata_schema import (
    ChamberItem,
    ChamberList,
    GenderItem,
    GenderList,
    OfficeTypeItem,
    OfficeTypeList,
    SubOfficeTypeItem,
)

# pylint: disable=redefined-outer-name

pd.set_option('display.max_columns', None)

version = "v1"


@pytest.fixture(scope="module")
def corpus() -> Corpus:
    return load_corpus()


def test_multiple_parties(corpus):
    person_data = corpus.person_codecs.persons_of_interest

    multi_party_people = person_data[person_data["has_multiple_parties"] == 1]

    assert all(',' in abbrev for abbrev in multi_party_people['party_abbrev'].to_list())
    assert all(',' in abbrev for abbrev in multi_party_people['multi_party_id'].to_list())


@pytest.mark.skip("must be adjusted to new data v1.1.0")
def test_get_speaker_with_multiple_parties(corpus):
    _ = corpus.person_codecs["Q6178909"]
    # Raoul Hamilton should be returned for L, FRIS and X, party_id: 5, 12, 1
    speakers_5 = corpus.get_speakers(selections={'party_id': [5]})
    speakers_12 = corpus.get_speakers(selections={'party_id': [12]})
    speakers_1 = corpus.get_speakers(selections={'party_id': [1]})

    assert 'Raoul Hamilton' in speakers_5['name'].to_list()
    assert 'Raoul Hamilton' in speakers_12['name'].to_list()
    assert 'Raoul Hamilton' in speakers_1['name'].to_list()


def test_meta_genders(corpus):
    df = corpus.get_gender_meta()
    genders = df.to_dict(orient="records")

    assert len(genders) == 3
    assert genders[1].get("gender_id") == 1
    assert genders[1].get("gender_abbrev") == 'M'

    rows: list[GenderItem] = [GenderItem(**row) for row in genders]
    gender_list = GenderList(gender_list=rows)

    assert len(gender_list.gender_list) == 3


def test_meta_office_types(corpus):
    df = corpus.get_office_type_meta()
    data = df.to_dict(orient="records")
    rows = [OfficeTypeItem(**row) for row in data]
    gender_list = OfficeTypeList(office_type_list=rows)
    assert gender_list is not None


def test_meta_chamber(corpus):
    df = corpus.get_chamber_meta()
    data = df.to_dict(orient="records")
    rows = [ChamberItem(**row) for row in data]
    chamber_list = ChamberList(chamber_list=rows)
    assert chamber_list is not None
    assert 'FK' in df.chamber_abbrev.to_list()


def test_meta_sub_office_type(corpus):
    df = corpus.get_sub_office_type_meta()
    data = df.to_dict(orient="records")
    rows = [SubOfficeTypeItem(**row) for row in data]

    assert len(rows) > 0

    # return SubOfficeTypeList(sub_office_type_list=rows)


def test_meta_parties(corpus):
    df = corpus.get_party_meta()
    assert 'party_abbrev' in df.columns
    assert 'party_id' in df.columns
    assert 'party' in df.columns
    assert 'C' in df.party_abbrev.to_list()
    assert '?' not in df.party_abbrev.to_list()

    assert len(df) > 0


def test_parties_api(fastapi_client):
    response = fastapi_client.get(f"{version}/metadata/parties")
    assert response.status_code == status.HTTP_200_OK
    json = response.json()
    assert 'party_list' in json
    assert len(json['party_list']) > 0


def test_start_year(fastapi_client):
    response = fastapi_client.get(f"{version}/metadata/start_year")
    assert response.status_code == status.HTTP_200_OK
    assert isinstance(response.json(), int)


def test_end_year(fastapi_client):
    response = fastapi_client.get(f"{version}/metadata/end_year")
    assert response.status_code == status.HTTP_200_OK
    assert isinstance(response.json(), int)


def test_genders(fastapi_client):
    response = fastapi_client.get(f"{version}/metadata/genders")
    assert response.status_code == status.HTTP_200_OK

    json = response.json()
    assert 'gender_list' in json
    assert len(json['gender_list']) > 0


def test_chambers(fastapi_client):
    response = fastapi_client.get(f"{version}/metadata/chambers")
    assert response.status_code == status.HTTP_200_OK

    json = response.json()
    assert 'chamber_list' in json
    assert len(json['chamber_list']) > 0


def test_office_types(fastapi_client):
    response = fastapi_client.get(f"{version}/metadata/office_types")
    assert response.status_code == status.HTTP_200_OK

    json = response.json()

    assert 'office_type_list' in json
    assert len(json['office_type_list']) > 0


def test_sub_office_types(fastapi_client):
    response = fastapi_client.get(f"{version}/metadata/sub_office_types")
    assert response.status_code == status.HTTP_200_OK

    json = response.json()
    assert 'sub_office_type_list' in json
    assert len(json['sub_office_type_list']) > 0
