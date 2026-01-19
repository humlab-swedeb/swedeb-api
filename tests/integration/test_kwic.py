import pytest
from fastapi import status

from api_swedeb.api.dependencies import get_corpus_decoder, get_corpus_loader, get_cwb_corpus, get_decoder_opts
from api_swedeb.api.services.kwic_service import KWICService
from api_swedeb.api.utils.common_params import CommonQueryParams
from api_swedeb.core.codecs import PersonCodecs
from api_swedeb.mappers.kwic import kwic_to_api_model

# pylint: disable=redefined-outer-name

version = "v1"

EXPECTED_COLUMNS: set[str] = {
    "year",
    "name",
    "party_abbrev",
    "party",
    "gender",
    "person_id",
    "link",
    "speech_name",
    "speech_link",
    "gender_abbrev",
    "document_name",
    "chamber_abbrev",
    "speech_id",
    "wiki_id",
    "document_id",
    "left_word",
    "node_word",
    "right_word",
}


def test_kwic_api(fastapi_client):
    response = fastapi_client.get(
        f"{version}/tools/kwic/debatt?words_before=2&words_after=2&cut_off=200&lemmatized=false"
        "&from_year=1970&to_year=1975&gender_id=1"
    )
    data: dict = response.json()
    assert response.status_code == 200
    assert len(data["kwic_list"]) > 0

    item: dict = data["kwic_list"][0]
    assert set(item.keys()) == EXPECTED_COLUMNS | {'party'}


def test_kwic_non_existing_search_term(fastapi_client):
    # non-existing word
    search_term = 'non_existing_word_'
    response = fastapi_client.get(f"{version}/tools/kwic/{search_term}")
    assert response.status_code == status.HTTP_200_OK
    assert 'kwic_list' in response.json()
    assert len(response.json()['kwic_list']) == 0


def test_kwic_speech_id_in_search_results(fastapi_client):
    response = fastapi_client.get(f"{version}/tools/kwic/kärnkraft?words_before=2&words_after=2&cut_off=10")
    assert response.status_code == 200
    data: dict = response.json()
    assert 'kwic_list' in data
    assert len(data['kwic_list']) > 0

    first_result = data["kwic_list"][0]

    assert set(first_result.keys()) == EXPECTED_COLUMNS
    # FIXME: `title` is None in this response (add as decode if needed)
    # assert all(x is not None for x in first_result.values())


@pytest.mark.asyncio
async def test_debug():

    corpus = get_cwb_corpus()
    decoder_opts = get_decoder_opts()
    person_codecs: PersonCodecs = await get_corpus_decoder(decoder_opts)  # type: ignore
    loader = get_corpus_loader()

    kwic_service = KWICService(loader, person_codecs)

    common_opts = {
        'office_types': None,
        'sub_office_types': None,
        'party_id': None,
        'gender_id': None,
        'chamber_abbrev': None,
        'from_year': 1867,
        'to_year': 2020,
        'speech_id': None,
        'who': None,
        'sort_by': 'year_title',
        'limit': None,
        'offset': None,
        'sort_order': 'asc',
    }

    data = kwic_service.get_kwic(
        corpus=corpus,
        commons=CommonQueryParams(**common_opts),
        keywords="kärnkraft",
        lemmatized=True,
        words_before=2,
        words_after=2,
        p_show="lemma",
        cut_off=10,
    )
    result = kwic_to_api_model(data)
    assert len(result.kwic_list) > 0


@pytest.mark.parametrize(
    "word, chambers, n_expected",
    [
        ("sverige", "ak", 42),
        ("sverige", "AK", 42),
        ("sverige", "ek", 225),
        ("sverige", ["ak", "ek"], 225 + 42),
    ],
)
def test_kwic_filter_by_chamber(fastapi_client, word: str, chambers: str | list[str], n_expected: int):
    chambers = [chambers] if isinstance(chambers, str) else chambers
    chamber_criteria: str = '&'.join([f"chamber_abbrev={chamber}" for chamber in chambers])
    response = fastapi_client.get(f"{version}/tools/kwic/{word}?words_before=2&words_after=2&{chamber_criteria}")
    assert response.status_code == 200
    data: dict = response.json()
    assert 'kwic_list' in data
    assert len(data['kwic_list']) == n_expected
