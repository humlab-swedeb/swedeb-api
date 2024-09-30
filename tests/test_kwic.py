from typing import Any
from unittest.mock import MagicMock, Mock

import ccc
import pandas as pd
import pytest
from fastapi import status

from api_swedeb.api.utils.kwic import RiksprotKwicConfig
from api_swedeb.core import kwic
from api_swedeb.core.cwb.compiler import to_cqp_exprs
from api_swedeb.mappers.cqp_opts import query_params_to_CQP_opts

# pylint: disable=redefined-outer-name

version = "v1"


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
        ("att", "word", "word", ["att", "Att"]),
        ("information|kunskap", "word", "word", ["information", "kunskap"]),
        ("information", "lemma", "lemma", ["information"]),
        (
            "information",
            "lemma",
            "word",
            ["information", "informationen", "Informationen", "informationer", 'informations-'],
        ),
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
            {"key": "a.year_year", "values": (1970, 1980)},
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
            ["kärnkraft|kärnvapen", "och"],
            "word",
            "word",
            ["kärnkraft och", "kärnvapen och"],
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
            "criterias": [],
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
    assert query == '[word="kärnkraft|kärnvapen"%c] [word="och"%c] within speech'

    kwic_results: pd.DataFrame = kwic.compute_kwic(corpus, opts=search_opts, **kwic_opts)

    assert kwic_results is not None
    assert len(kwic_results) > 0

    assert set(kwic_results[f"node_{display_target}"].unique()) == set(expected_words)


def test_get_kwic_compute_kwic(decoder: MagicMock):
    commons = Mock(
        lemmatized=False,
        from_year=1970,
        to_year=1980,
        who=["Q5781896", "Q5584283", "Q5746460"],
        party_id=1,
        office_types=[1],
        sub_office_types=[1, 2],
        gender_id=[1],
    )
    search_opts = query_params_to_CQP_opts(commons, [("debatt", "word")])
    fake_data: pd.DataFrame = pd.DataFrame(
        {
            'left_word': [
                'jag påpekade i en tidigare',
                'inte dra upp någon stor',
                'en så lång och ingående',
                'mig att dra upp en',
                'skatteexperter var uppe i denna',
            ],
            'node_word': ['debatt', 'debatt', 'debatt', 'debatt', 'debatt'],
            'right_word': [
                'här i kammaren — att',
                'i detta ämne , jag',
                'som det nu föreliggande .',
                'ytterligare en gång . Vi',
                ', och vederbörande hann inte',
            ],
            'year_year': ['1970', '1970', '1970', '1970', '1970'],
            'speech_id': ['i-xyz-3', 'i-xyz-9', 'i-xyz-3', 'i-xyz-0', 'i-xyz-21'],
            'speech_who': ['u-AX', 'u-ox', 'u-GJ', 'u-jH', 'u-QL'],
            'speech_party_id': ['9', '9', '2', '9', '9'],
            'speech_gender_id': ['1', '1', '1', '1', '1'],
            'speech_date': ['1970-05-27', '1970-05-27', '1970-05-27', '1970-05-27', '1970-05-27'],
            'speech_title': [
                'prot-1970--ak--029_013',
                'prot-1970--ak--029_029',
                'prot-1970--ak--029_043',
                'prot-1970--ak--029_064',
                'prot-1970--ak--029_066',
            ],
            'speech_office_type_id': ['1', '2', '1', '1', '1'],
            'speech_sub_office_type_id': ['1', '27', '2', '2', '2'],
        }
    )

    kwic_opts: dict[str, Any] = {
        "words_before": 5,
        "words_after": 5,
        "p_show": "word",
        "cut_off": 200,
        "strip_s_tags": True,
        "decoder": decoder,
    } | RiksprotKwicConfig.opts()

    corpus_mock = Mock(
        spec=ccc.Corpus, query=lambda *_, **__: Mock(ccc.SubCorpus, concordance=lambda *_, **__: fake_data)
    )

    kwic_results: pd.DataFrame = kwic.compute_kwic(corpus_mock, opts=search_opts, **kwic_opts)

    assert kwic_results is not None
    assert len(kwic_results) == len(fake_data)


def test_kwic_api(fastapi_client):
    response = fastapi_client.get(
        f"{version}/tools/kwic/debatt?words_before=2&words_after=2&cut_off=200&lemmatized=false"
        "&from_year=1970&to_year=1975&gender_id=1"
    )
    data: dict = response.json()
    assert response.status_code == 200
    assert len(data["kwic_list"]) > 0
    assert "name" in data["kwic_list"][0]
    assert "party_abbrev" in data["kwic_list"][0]


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
    print(response.json())
    data: dict = response.json()
    assert 'kwic_list' in data
    assert len(data['kwic_list']) > 0

    first_result = data["kwic_list"][0]

    assert set(first_result.keys()) == {
        'link',
        'speech_link',
        'name',
        'left_word',
        'person_id',
        'title',
        'formatted_speech_id',
        'gender',
        'node_word',
        'right_word',
        'year',
        'party_abbrev',
    }
    assert all(x is not None for x in first_result.values())
