import pandas as pd
import pytest
from fastapi import status
from fastapi.testclient import TestClient
from httpx import Response
from loguru import logger

from api_swedeb.api.utils.common_params import CommonQueryParams
from api_swedeb.api.utils.corpus import Corpus
from api_swedeb.api.utils.speech import get_speeches
from api_swedeb.core.configuration.inject import ConfigValue
from api_swedeb.core.utility import format_protocol_id
from api_swedeb.schemas.speeches_schema import SpeechesResult

# these tests mainly check that the endpoints are reachable and returns something
# the actual content of the response is not checked

# pylint: disable=redefined-outer-name

version = "v1"


def test_speeches_get(fastapi_client: TestClient):
    # assert that the speeches endpoint is reachable
    speech_name: str = "prot-1971--117_007"
    response = fastapi_client.get(f"{version}/tools/speeches/{speech_name}")
    assert response.status_code == status.HTTP_200_OK
    data: dict[str, str] = response.json()
    assert 'speech_text' in data
    assert 'speaker_note' in data
    assert len(data['speech_text']) > 0


def test_get_all_protocol_ids(api_corpus: Corpus):
    df: pd.DataFrame = api_corpus.get_anforanden(selections={'year': (1900, 2000)})
    all_ids: pd.Series = df['document_name']
    for protocol_id in all_ids:
        try:
            format_protocol_id(protocol_id)
        except IndexError:
            logger.info(f"index error {protocol_id}")
            assert False


def test_get_speaker_name(api_corpus: Corpus):
    dockument_name, speech_id = find_a_speech_id(api_corpus)
    speaker_by_speech_id = api_corpus.get_speaker(speech_id)
    assert speaker_by_speech_id is not None
    assert len(speaker_by_speech_id) > 0
    speaker_by_document_name = api_corpus.get_speaker(dockument_name)
    assert speaker_by_document_name == speaker_by_speech_id


def test_get_speaker_name_for_unknown_speaker(api_corpus: Corpus):
    unknown: str = ConfigValue("display.labels.speaker.unknown").resolve()
    speech_id = "prot-1974--136_032"
    speaker = api_corpus.get_speaker(speech_id)
    assert speaker == unknown


def test_get_speaker_name_for_non_existing_speech(api_corpus: Corpus):
    unknown: str = ConfigValue("display.labels.speaker.unknown").resolve()
    speech_id = "prot-made_up_and_missing"
    speaker = api_corpus.get_speaker(speech_id)
    assert speaker == unknown


def test_format_speech_id():
    prot = 'prot-1966-höst-fk--38_044'
    assert format_protocol_id(prot) == 'Första kammaren 1966:38 044'
    prot = 'prot-200405--113_075'
    assert format_protocol_id(prot) == '2004/05:113 075'
    prot = 'prot-1958-a-ak--17-01_001'
    assert format_protocol_id(prot) == 'Andra kammaren 1958:17 01 001'


def test_get_formatted_speech_id(api_corpus: Corpus):
    df_filtered: pd.DataFrame = api_corpus.get_anforanden(
        selections={'party_id': [4, 5], 'gender_id': [1, 2], 'year': (1900, 2000)}
    )
    assert 'speech_name' in df_filtered.columns


def test_get_speech_by_id_client(fastapi_client: TestClient, api_corpus: Corpus):
    document_name, speech_id = find_a_speech_id(api_corpus)

    response: Response = fastapi_client.get(f"v1/tools/speeches/{document_name}")
    assert response.status_code == status.HTTP_200_OK

    data_by_name: dict = response.json()
    assert 'speech_text' in data_by_name
    assert len(data_by_name['speech_text']) > 1
    assert len(data_by_name['speaker_note']) > 1

    response = fastapi_client.get(f"v1/tools/speeches/{speech_id}")
    assert response.status_code == status.HTTP_200_OK
    data_by_id: dict = response.json()

    assert data_by_id == data_by_name


def test_speeches_get_years(fastapi_client: TestClient):
    # assert that the returned speeches comes from the correct years
    start_year = 1970
    end_year = 1971
    response: Response = fastapi_client.get(f"{version}/tools/speeches?from_year={start_year}&to_year={end_year}")
    assert response.status_code == status.HTTP_200_OK
    speeches = response.json()['speech_list']
    for speech in speeches:
        assert 'year' in speech, 'year is missing in response'
        assert speech['year'] >= start_year, 'year is less than start_year'
        assert speech['year'] <= end_year, 'year is greater than end_year'


def test_speeches_zip(fastapi_client: TestClient, api_corpus: Corpus):
    payload: list[str] = api_corpus.document_index.sample(2).document_name.to_list()
    response: Response = fastapi_client.post(f"{version}/tools/speech_download/", json=payload)
    assert response.status_code == status.HTTP_200_OK
    assert response.headers['Content-Disposition'] == 'attachment; filename=speeches.zip'
    assert response.headers['Content-Type'] == 'application/zip'
    assert len(response.content) > 0


def test_get_speeches_corpus(api_corpus: Corpus):
    fx = api_corpus.person_codecs.party_abbrev2id.get
    df_filtered: pd.DataFrame = api_corpus.get_anforanden(
        selections={'party_id': [fx(x) for x in ('L', 'S')], 'gender_id': [1, 2], 'year': (1970, 1980)}
    )
    df_unfiltered: pd.DataFrame = api_corpus.get_anforanden(selections={'year': (1970, 1980)})
    assert len(df_filtered) < len(df_unfiltered)
    assert 'L' in df_filtered['party_abbrev'].unique()
    assert 'S' in df_filtered['party_abbrev'].unique()


def test_get_speeches_by_ids(api_corpus: Corpus):
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
    return df.iloc[0]['document_name'], df.iloc[0]['speech_id']


def test_get_speech_by_id(api_corpus: Corpus):
    document_name, speech_id = find_a_speech_id(api_corpus)
    speech_text: str = api_corpus.get_speech_text(speech_id)
    assert speech_text is not None
    assert len(speech_text) > 1
    assert speech_text == api_corpus.get_speech_text(document_name)


def test_get_speech_by_id_missing(api_corpus: Corpus):
    # non-existing speech (gives empty string as response)
    speech_id: str = 'prot-1971--1_007_missing'
    speech_text: str = api_corpus.get_speech_text(speech_id)
    assert len(speech_text) == 0


def test_get_speaker_note(api_corpus: Corpus):
    document_name, speech_id = find_a_speech_id(api_corpus)

    speaker_note_by_name: str = api_corpus.get_speaker_note(document_name)
    assert speaker_note_by_name is not None
    assert len(speaker_note_by_name) > 0

    speaker_note_by_id: str = api_corpus.get_speaker_note(speech_id)
    assert speaker_note_by_id == speaker_note_by_name


@pytest.mark.skip(reason="FIXME: This test fails when run in parallel with other tests")
def test_get_speech_by_api(fastapi_client: TestClient, api_corpus: Corpus):
    _, speech_id = find_a_speech_id(api_corpus)
    response: Response = fastapi_client.get(f"{version}/tools/speeches/{speech_id}", timeout=10)
    assert response.status_code == status.HTTP_200_OK
    assert len(response.json()['speech_text']) > 0
    assert len(response.json()['speaker_note']) > 0


@pytest.mark.skip(reason="FIXME: This test is only used for debugging")
def test_get_speech_party_bug():
    dtm_folder: str = "/data/swedeb/v1.1.0/dtm/text"
    dtm_tag: str = "text"
    metadata_filename: str = "/data/swedeb/v1.1.0/riksprot_metadata.db"
    tagged_corpus_folder: str = "/data/swedeb/v1.1.0/tagged_frames"

    corpus = Corpus(
        dtm_tag=dtm_tag,
        dtm_folder=dtm_folder,
        metadata_filename=metadata_filename,
        tagged_corpus_folder=tagged_corpus_folder,
    )

    df: pd.DataFrame = corpus.get_anforanden(selections={'year': (1867, 1900)})

    assert df is not None

    di: pd.DataFrame = corpus.vectorized_corpus.document_index
    assert len(di[di.year.between(1867, 1900)]) == len(df)

    args: CommonQueryParams = CommonQueryParams(from_year=1867, to_year=1900).resolve()

    result: SpeechesResult = get_speeches(commons=args, corpus=corpus)

    assert len(df) == len(result.speech_list)

    assert df.year.between(1867, 1900).all()
