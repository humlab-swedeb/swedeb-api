import pytest
from fastapi import status

from .core.test_kwic import EXPECTED_COLUMNS

# pylint: disable=redefined-outer-name

version = "v1"


def test_kwic_api(fastapi_client):
    response = fastapi_client.get(
        f"{version}/tools/kwic/debatt?words_before=2&words_after=2&cut_off=200&lemmatized=false"
        "&from_year=1970&to_year=1975&gender_id=1"
    )
    data: dict = response.json()
    assert response.status_code == 200
    assert len(data["kwic_list"]) > 0

    item: dict = data["kwic_list"][0]
    assert set(item.keys()) == EXPECTED_COLUMNS


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


@pytest.mark.parametrize(
    "word, chambers, n_expected",
    [
        ("sverige", "ak", 42),
        ("sverige", "AK", 42),
        ("sverige", "ek", 264),
        ("sverige", ["ak", "ek"], 264 + 42),
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
