
import pytest
from fastapi.testclient import TestClient
from main import app
from fastapi import status
from api_swedeb.api.utils.corpus import load_corpus
from api_swedeb.schemas.metadata_schema import PartyItem, PartyList, GenderItem, GenderList, ChamberItem, ChamberList, OfficeTypeItem, OfficeTypeList, SubOfficeTypeItem, SubOfficeTypeList 

version = "v1"

@pytest.fixture(scope="module")
def client():
    client = TestClient(app)
    yield client

@pytest.fixture(scope="module")
def corpus():
    return load_corpus('.env_1960')


def test_property_value_specs(corpus):
    metadata = corpus.metadata
    assert metadata is not None

    person_codecs = corpus.person_codecs
    assert person_codecs is not None

    property_value_specs = metadata.property_values_specs
    for thingy in property_value_specs:
        if thingy['text_name'] == 'gender':
            print('GENDER:   ', thingy['values'])
        elif thingy['text_name'] == 'office_type':
            print('OFFICE_TYPE:   ',thingy['values'])
        elif thingy['text_name'] == 'sub_office_type':
            print('SUB_OFFICE_TYPE', thingy['values'])
        elif thingy['text_name'] == 'party_abbrev':
            print('PARTY_ABBREV', thingy['values'])
        else:
            print('>>>>',thingy['text_name'])


    party_df = corpus.get_party_meta()
    data = party_df.to_dict(orient="records")
    rows = [PartyItem(**row) for row in data]
    party_list =  PartyList(party_list=rows)
    print(party_list)

    df2 = metadata.party
    print(df2)

def test_meta_genders(corpus):
    print()
    df = corpus.get_gender_meta()
    data = df.to_dict(orient="records")
    rows = [GenderItem(**row) for row in data]
    gender_list = GenderList(gender_list=rows)
    print(gender_list)

def test_meta_office_types(corpus):
    df = corpus.get_office_type_meta()
    data = df.to_dict(orient="records")
    rows = [OfficeTypeItem(**row) for row in data]
    gender_list = OfficeTypeList(office_type_list=rows)
    print(gender_list)

def test_meta_chamber(corpus):
    df = corpus.get_chamber_meta()
    data = df.to_dict(orient="records")
    rows = [ChamberItem(**row) for row in data]
    chamber_list = ChamberList(chamber_list=rows)
    assert chamber_list is not None

def test_meta_sub_office_type(corpus):
    df = corpus.get_sub_office_type_meta()
    data = df.to_dict(orient="records")
    rows = [SubOfficeTypeItem(**row) for row in data]
    return SubOfficeTypeList(sub_office_type_list=rows)



def test_parties_api(client):
    response = client.get(f"{version}/metadata/parties")
    assert response.status_code == status.HTTP_200_OK
    json = response.json()
    assert 'party_list' in json
    assert len(json['party_list']) > 0



def test_start_year(client):
    response = client.get(f"{version}/metadata/start_year")
    assert response.status_code == status.HTTP_200_OK
    assert isinstance(response.json(), int)

    

def test_end_year(client):
    response = client.get(f"{version}/metadata/end_year")
    assert response.status_code == status.HTTP_200_OK
    assert isinstance(response.json(), int)




def test_genders(client):
    response = client.get(f"{version}/metadata/genders")
    assert response.status_code == status.HTTP_200_OK

    json = response.json()
    assert 'gender_list' in json
    assert len(json['gender_list']) > 0

def test_chambers(client):
    
    response = client.get(f"{version}/metadata/chambers")
    assert response.status_code == status.HTTP_200_OK

    json = response.json()
    assert 'chamber_list' in json
    assert len(json['chamber_list']) > 0

def test_office_types(client):
    
    response = client.get(f"{version}/metadata/office_types")
    assert response.status_code == status.HTTP_200_OK

    json = response.json()

    assert 'office_type_list' in json
    assert len(json['office_type_list']) > 0

def test_sub_office_types(client):
    
    response = client.get(f"{version}/metadata/sub_office_types")
    assert response.status_code == status.HTTP_200_OK

    json = response.json()
    assert 'sub_office_type_list' in json
    assert len(json['sub_office_type_list']) > 0