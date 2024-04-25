from typing import Any
from unittest.mock import Mock, MagicMock

import pandas as pd
from api_swedeb.api.utils.kwic import RiksprotKwicConfig

import pytest
from fastapi.testclient import TestClient
from fastapi import status
from api_swedeb.core import kwic
from api_swedeb.core.cwb.compiler import to_cqp_exprs
from api_swedeb.mappers.cqp_opts import query_params_to_CQP_opts
from main import app
import ccc

# pylint: disable=redefined-outer-name

version = "v1"


@pytest.fixture(scope="module")
def client():
    client = TestClient(app)
    yield client


@pytest.fixture(scope="module")
def decoder() -> MagicMock:
    mock = MagicMock()

    def mock_decode_columns(df: pd.DataFrame, **_) -> pd.DataFrame:
        return df.assign(
            **{
                "office_type": "Ledamot",
                "gender": "Man",
                "party_abbrev": "Sosse",
                "name": "Trazan",
                "sub_office_type": "Unknown",
            }
        )

    mock.decode.side_effect = mock_decode_columns
    return mock





@pytest.mark.parametrize(
    "word,target,display_target,expected_words",
    [
        ("att", "word", "word", ["att"]),
        ("information|kunskap", "word", "word", ["information", "kunskap"]),
        ("information", "lemma", "lemma", ["information"]),
        ("information", "lemma", "word", ["information", "informationer"]),
        ("landet", "word", "lemma", ["land"]),
    ],
)
def test_get_kwic_results_for_single_search_term(
    corpus: ccc.Corpus,
    decoder: MagicMock,
    word: str | list[str],
    target: str,
    display_target: str,
    expected_words: str | list[str] | None,
):

    search_opts: dict = {
        "prefix": "a",
        "target": target,
        "value": word,
        "criterias": [
            {"key": "a.year_year", "values": (1960, 1965)},
            {"key": "a.speech_who", "values": ["Q5715273", "Q5980083", "Q5980083"]},
            {"key": "a.speech_party_id", "values": [1, 5, 9]},
        ],
    }

    kwic_opts: dict[str, Any] = {
        "words_before": 2,
        "words_after": 2,
        "p_show": display_target,
        "cut_off": 200,
        "decoder": decoder,
    } | RiksprotKwicConfig.opts()

    kwic_results: pd.DataFrame = kwic.compute_kwic(corpus, opts=search_opts, **kwic_opts)

    assert kwic_results is not None
    assert len(kwic_results) > 0

    assert set(kwic_results["node_word"].unique()) == set(expected_words)


@pytest.mark.parametrize(
    "word,target,display_target,expected_words",
    [
        (
            ["kärnkraft|atomkraft", "och"],
            "word",
            "word",
            ["Atomkraft och", "atomkraft och", "kärnkraft och", "Kärnkraft och"],
        ),
    ],
)
def test_get_kwic_results_for_multiple_search_term(
    corpus: ccc.Corpus,
    decoder: MagicMock,
    word: str | list[str],
    target: str,
    display_target: str,
    expected_words: str | list[str] | None,
):
    search_opts: list[dict] = [
        {
            "prefix": None,
            "target": target,
            "value": word,
            "criterias": [
                # {"key": "a.year_year", "values": (1960, 1965)},
            ],
        }
        for word in word
    ]

    kwic_opts: dict[str, Any] = {
        "words_before": 5,
        "words_after": 5,
        "p_show": display_target,
        "cut_off": 200,
        "decoder": decoder,
    } | RiksprotKwicConfig.opts()

    query: str = to_cqp_exprs(search_opts, within="speech")
    assert query == '[word="kärnkraft|atomkraft"%c] [word="och"%c] within speech'

    kwic_results: pd.DataFrame = kwic.compute_kwic(corpus, opts=search_opts, **kwic_opts)

    assert kwic_results is not None
    assert len(kwic_results) > 0

    assert set(kwic_results[f"node_{display_target}"].unique()) == set(expected_words)


def test_get_kwic_compute_kwic(corpus: ccc.Corpus, decoder: MagicMock):

    commons = Mock(
        lemmatized=False,
        from_year=1960,
        to_year=1969,
        who=["Q5781896", "Q5584283", "Q5746460"],
        party_id=1,
        office_types=[1],
        sub_office_types=[1, 2],
        gender_id=[1],
    )
    search_opts = query_params_to_CQP_opts(commons, [("debatt", "word")])

    query: str = to_cqp_exprs(search_opts, within="speech")
    assert query == (
        'a:[word="debatt"%c]::(a.year_year="196[0-9]"%c)'
        '&(a.speech_who="Q5781896|Q5584283|Q5746460"%c)&(a.speech_party_id="1"%c)&(a.speech_office_type_id="1"%c)'
        '&(a.speech_sub_office_type_id="1|2"%c)&(a.speech_gender_id="1"%c) within speech'
    )

    kwic_opts: dict[str, Any] = {
        "words_before": 5,
        "words_after": 5,
        "p_show": "word",
        "cut_off": 200,
        "strip_s_tags": True,
        "decoder": decoder,
    } | RiksprotKwicConfig.opts()

    kwic_results: pd.DataFrame = kwic.compute_kwic(corpus, opts=search_opts, **kwic_opts)

    assert kwic_results is not None
    assert len(kwic_results) > 0


def test_kwic_api(client):
    response = client.get(
        f"{version}/tools/kwic/debatt?words_before=2&words_after=2&cut_off=200&lemmatized=false"
        "&from_year=1960&to_year=1961&who=Q5781896&who=Q5584283&who=Q5746460&party_id=1&office_types=1&sub_office_types=1&sub_office_types=2&gender_id=1"
    )
    assert response.status_code == 200
    print(response.json())
    assert len(response.json()["kwic_list"]) > 0
    assert "name" in response.json()["kwic_list"][0]
    assert "party_abbrev" in response.json()["kwic_list"][0]

def test_kwic_non_existing_search_term(client):
    # non-existing word
    search_term = 'non_existing_word_'
    response = client.get(f"{version}/tools/kwic/{search_term}")
    assert response.status_code == status.HTTP_200_OK
    assert 'kwic_list' in response.json()
    assert len(response.json()['kwic_list']) == 0

