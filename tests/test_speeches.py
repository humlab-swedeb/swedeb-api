import pandas as pd
from fastapi import status
from fastapi.testclient import TestClient
from httpx import Response

from api_swedeb.api.utils.corpus import Corpus
from api_swedeb.api.utils.protocol_id_format import format_protocol_id

# these tests mainly check that the endpoints are reachable and returns something
# the actual content of the response is not checked

# pylint: disable=redefined-outer-name

version = "v1"


def test_speeches_get(fastapi_client):
    # assert that the speeches endpoint is reachable
    response = fastapi_client.get(f"{version}/tools/speeches/prot-1971--1_007")
    assert response.status_code == status.HTTP_200_OK
    print(response.json())


def test_get_all_protocol_ids(api_corpus):
    df = api_corpus.get_anforanden(selections={'year': (1900, 2000)})
    all_ids = df['document_name']
    for protocol_id in all_ids:
        try:
            format_protocol_id(protocol_id)
        except IndexError:
            print(protocol_id)
            assert False


def test_get_speaker_name(api_corpus):
    speech_id = find_a_speech_id(api_corpus)
    speaker = api_corpus.get_speaker(speech_id)
    assert speaker is not None
    assert len(speaker) > 0
    # speech with unknown speaker prot-1963-höst-ak--35_090.txt


def test_get_speaker_name_for_unknown_speaker(api_corpus: Corpus):
    speech_id = "prot-1974--136_032"
    speaker = api_corpus.get_speaker(speech_id)
    assert speaker == "Okänd"


def test_get_speaker_name_for_non_existing_speech(api_corpus):
    speech_id = "prot-made_up_and_missing"
    speaker = api_corpus.get_speaker(speech_id)
    assert speaker == "Okänd"


def test_format_speech_id():
    prot = 'prot-1966-höst-fk--38_044'
    assert format_protocol_id(prot) == 'Första kammaren 1966:38 044'
    prot = 'prot-200405--113_075'
    assert format_protocol_id(prot) == '2004/05:113 075'
    prot = 'prot-1958-a-ak--17-01_001'
    assert format_protocol_id(prot) == 'Andra kammaren 1958:17 01 001'


def test_get_formatted_speech_id(api_corpus):
    df_filtered = api_corpus.get_anforanden(selections={'party_id': [4, 5], 'gender_id': [1, 2], 'year': (1900, 2000)})
    assert 'speech_name' in df_filtered.columns


def test_get_speech_by_id_client(fastapi_client, api_corpus):
    speech_id = find_a_speech_id(api_corpus)

    response = fastapi_client.get(f"v1/tools/speeches/{speech_id}")
    assert response.status_code == status.HTTP_200_OK
    assert 'speech_text' in response.json()
    assert len(response.json()['speech_text']) > 1
    assert len(response.json()['speaker_note']) > 1
    print(response.json()['speaker_note'])


def test_speeches_get_years(fastapi_client):
    # assert that the returned speeches comes from the correct years
    start_year = 1970
    end_year = 1971
    response = fastapi_client.get(f"{version}/tools/speeches?from_year={start_year}&to_year={end_year}")
    assert response.status_code == status.HTTP_200_OK
    speeches = response.json()['speech_list']
    for speech in speeches:
        assert 'year' in speech, 'year is missing in response'
        assert speech['year'] >= start_year, 'year is less than start_year'
        assert speech['year'] <= end_year, 'year is greater than end_year'


def test_speeches_zip(fastapi_client):
    payload = ['prot-1966-höst-fk--38_044', 'prot-1966-höst-fk--38_043']
    response = fastapi_client.post(f"{version}/tools/speech_download/", json=payload)
    assert response.status_code == status.HTTP_200_OK
    assert response.headers['Content-Disposition'] == 'attachment; filename=speeches.zip'
    assert response.headers['Content-Type'] == 'application/zip'
    assert len(response.content) > 0


def test_get_speeches_corpus(api_corpus):
    df_filtered: pd.DataFrame = api_corpus.get_anforanden(
        selections={'party_id': [4, 5], 'gender_id': [1, 2], 'year': (1900, 2000)}
    )
    df_unfiltered = api_corpus.get_anforanden(selections={'year': (1970, 1980)})
    assert len(df_filtered) < len(df_unfiltered)
    assert 'L' in df_filtered['party_abbrev'].unique()


def test_get_speeches_by_ids(api_corpus):
    speech_ids: list[str] = api_corpus.document_index.speech_id.sample(3).to_list()
    speeches: pd.DataFrame = api_corpus.get_anforanden(selections={'speech_id': speech_ids})
    assert len(speeches) == len(speech_ids)
    assert set(speeches.speech_id) == set(speech_ids)


def test_get_speeches_by_ids_by_api(fastapi_client: TestClient, api_corpus: Corpus):
    speech_ids: list[str] = api_corpus.document_index.speech_id.sample(3).to_list()
    args: str = '&'.join([f"speech_id={speech_id}" for speech_id in speech_ids])
    url: str = f"{version}/tools/speeches/?{args}"
    response: Response = fastapi_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    assert 'speech_list' in response.json()
    speeches: list[dict] = response.json()['speech_list']

    assert len(speeches) == len(speech_ids)

    url: str = f"{version}/tools/speeches"
    json: dict = {'speech_id': speech_ids}
    response: Response = fastapi_client.post(url, json=json)
    assert response.status_code == status.HTTP_200_OK


def find_a_speech_id(api_corpus):
    df = api_corpus.document_index.sample(1)
    return df.iloc[0]['document_name']


def test_get_speech_by_id(api_corpus):
    speech_id = find_a_speech_id(api_corpus)
    speech_text = api_corpus.get_speech_text(speech_id)
    assert speech_text is not None
    assert len(speech_text) > 1


def test_get_speech_by_id_missing(api_corpus):
    # non-existing speech (gives empty string as response)
    speech_id = 'prot-1971--1_007_missing'
    speech_text = api_corpus.get_speech_text(speech_id)
    assert len(speech_text) == 0


def test_get_speaker_note(api_corpus):
    speech_id = find_a_speech_id(api_corpus)
    speaker_note = api_corpus.get_speaker_note(speech_id)
    assert speaker_note is not None
    assert len(speaker_note) > 0


def test_get_speech_by_api(fastapi_client, api_corpus):
    speech_id = find_a_speech_id(api_corpus)
    response = fastapi_client.get(f"{version}/tools/speeches/{speech_id}")
    assert response.status_code == status.HTTP_200_OK
    assert len(response.json()['speech_text']) > 0
    assert len(response.json()['speaker_note']) > 0
