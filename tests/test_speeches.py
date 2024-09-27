import pytest
from fastapi.testclient import TestClient
from main import app
from fastapi import status
from api_swedeb.api.utils.corpus import load_corpus
from api_swedeb.api.utils.protocol_id_format import format_protocol_id

# these tests mainly check that the endpoints are reachable and returns something
# the actual content of the response is not checked

version = "v1"


@pytest.fixture(scope="module")
def client():
    client = TestClient(app)
    yield client


@pytest.fixture(scope="module")
def corpus():
    return load_corpus('test.env')


def test_speeches_get(client):
    # assert that the speeches endpoint is reachable
    response = client.get(f"{version}/tools/speeches/prot-1971--1_007")
    assert response.status_code == status.HTTP_200_OK
    print(response.json())


def test_get_all_protocol_ids(corpus):
    df = corpus.get_anforanden(from_year=1900, to_year=2000, selections={}, di_selected=None)
    all_ids = df['document_name']
    for id in all_ids:
        try:
            format_protocol_id(id)
        except IndexError:
            print(id)
            assert False


def test_get_speaker_name(corpus):
    #
    speech_id = find_a_speech_id(corpus)
    speaker = corpus.get_speaker(speech_id)
    assert speaker is not None
    assert len(speaker) > 0
    # speech with unknown speaker prot-1963-höst-ak--35_090.txt


def test_get_speaker_name_for_unknown_speaker(corpus):
    speech_id = "prot-1963-höst-ak--35_090"
    speaker = corpus.get_speaker(speech_id)
    assert speaker == "Okänd"


def test_get_speaker_name_for_non_existing_speech(corpus):
    speech_id = "prot-made_up_and_missing"
    speaker = corpus.get_speaker(speech_id)
    assert speaker == "Okänd"


def test_format_speech_id(corpus):
    prot = 'prot-1966-höst-fk--38_044'
    assert format_protocol_id(prot) == 'Första kammaren 1966:38 044'
    prot = 'prot-200405--113_075'
    assert format_protocol_id(prot) == '2004/05:113 075'
    prot = 'prot-1958-a-ak--17-01_001'
    assert format_protocol_id(prot) == 'Andra kammaren 1958:17 01 001'


def test_get_formatted_speech_id(corpus):
    df_filtered = corpus.get_anforanden(
        from_year=1900, to_year=2000, selections={'party_id': [4, 5], 'gender_id': [1, 2]}, di_selected=None
    )
    assert 'formatted_speech_id' in df_filtered.columns


def test_get_speech_by_id_client(client, corpus):
    speech_id = find_a_speech_id(corpus)
    start_year = corpus.get_years_start()
    print(start_year)

    response = client.get(f"v1/tools/speeches/{speech_id}")
    assert response.status_code == status.HTTP_200_OK
    assert 'speech_text' in response.json()
    assert len(response.json()['speech_text']) > 1
    assert len(response.json()['speaker_note']) > 1
    print(response.json()['speaker_note'])


def test_speeches_get_years(client):
    # assert that the returned speeches comes from the correct years
    start_year = 1960
    end_year = 1961
    response = client.get(f"{version}/tools/speeches?from_year={start_year}&to_year={end_year}")
    assert response.status_code == status.HTTP_200_OK
    speeches = response.json()['speech_list']
    for speech in speeches:
        assert 'year' in speech, 'year is missing in response'
        assert speech['year'] >= start_year, 'year is less than start_year'
        assert speech['year'] <= end_year, 'year is greater than end_year'


def test_speeches_zip(client):
    payload = ['prot-1966-höst-fk--38_044', 'prot-1966-höst-fk--38_043']
    response = client.post(f"{version}/tools/speech_download/", json=payload)
    assert response.status_code == status.HTTP_200_OK
    assert response.headers['Content-Disposition'] == 'attachment; filename=speeches.zip'
    assert response.headers['Content-Type'] == 'application/zip'
    assert len(response.content) > 0


def test_get_speeches_corpus(corpus):
    df_filtered = corpus.get_anforanden(
        from_year=1900, to_year=2000, selections={'party_id': [4, 5], 'gender_id': [1, 2]}, di_selected=None
    )
    df_unfiltered = corpus.get_anforanden(from_year=1900, to_year=2000, selections={}, di_selected=None)
    assert len(df_filtered) < len(df_unfiltered)
    assert 'L' in df_filtered['party_abbrev'].unique()


def find_a_speech_id(corpus):
    df = corpus.get_anforanden(from_year=1900, to_year=2000, selections={}, di_selected=None)
    return df.iloc[0]['document_name']


def test_get_speech_by_id(corpus):
    speech_id = find_a_speech_id(corpus)
    speech_text = corpus.get_speech_text(speech_id)
    assert speech_text is not None
    assert len(speech_text) > 1


def test_get_speech_by_id_missing(corpus):
    # non-existing speech (gives empty string as response)
    speech_id = 'prot-1971--1_007_missing'
    speech_text = corpus.get_speech_text(speech_id)
    assert len(speech_text) == 0


def test_get_speaker_note(corpus):
    speech_id = find_a_speech_id(corpus)
    speaker_note = corpus.get_speaker_note(speech_id)
    assert speaker_note is not None
    assert len(speaker_note) > 0


def test_get_speech_by_api(client, corpus):
    speech_id = find_a_speech_id(corpus)
    response = client.get(f"{version}/tools/speeches/{speech_id}")
    assert response.status_code == status.HTTP_200_OK
    assert len(response.json()['speech_text']) > 0
    assert len(response.json()['speaker_note']) > 0
