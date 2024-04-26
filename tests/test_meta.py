
import pytest
from fastapi.testclient import TestClient
from main import app
from fastapi import status
from api_swedeb.api.utils.corpus import load_corpus
from api_swedeb.schemas.metadata_schema import  GenderItem, GenderList, ChamberItem, ChamberList, OfficeTypeItem, OfficeTypeList, SubOfficeTypeItem, SubOfficeTypeList 
import pandas as pd


pd.set_option('display.max_columns', None)

version = "v1"

@pytest.fixture(scope="module")
def client():
    client = TestClient(app)
    yield client

@pytest.fixture(scope="module")
def corpus():
    return load_corpus('.env_1960')




def test_multiple_parties(corpus):
    metadata = corpus.metadata
    assert metadata is not None

    person_data = corpus.person_codecs.persons_of_interest
    party_data = corpus.party_data
    assert person_data is not None

   
    print(corpus.person_codecs.person_party.head())

    print(party_data[party_data['has_multiple_parties']==1])

    
    grouped_parties = party_data.groupby('person_id')['party_id'].apply(lambda x: ', '.join(set((map(str, x))))).reset_index()
    
    print(grouped_parties.head())


    print(corpus.get_party_meta())

    
    print('-------- person data with multi party abbrevs --------')
    print(person_data.head())
    print('-------- person data with multi party abbrevs MULTI--------')

    print(person_data[person_data['has_multiple_parties']==1].head())

    party_person_dict = party_data.groupby('party_id')['person_id'].apply(list).to_dict()
    for k,v in party_person_dict.items():
        print(k,len(v))



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