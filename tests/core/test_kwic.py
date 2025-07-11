from typing import Any

import ccc
import pandas as pd
import pytest

from api_swedeb.core.codecs import PersonCodecs
from api_swedeb.core.kwic import simple

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


def encode_party_abbrev2id(person_codecs: PersonCodecs, criterias: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Helper function that encodes party abbreviations to party ids (simplifies designing test cases)"""

    if criterias:
        for criteria in criterias:
            if not criteria['key'].endswith("_party_abbrev"):
                continue

            criteria['key'] = 'a.speech_party_id'
            party_abbrev: str = criteria['values'] if isinstance(criteria['values'], list) else [criteria['values']]
            criteria['values'] = [person_codecs.party_abbrev2id.get(party, 0) for party in party_abbrev]

    return criterias


@pytest.mark.parametrize(
    "word,target,p_show,filter_opts,expected_words",
    [
        (
            ["kärnkraft|kärnvapen", "och"],
            "word",
            "word",
            {},
            ["kärnkraft och", "kärnvapen och"],
        ),
        (
            ["debatt"],
            "word",
            "word",
            [
                {'key': 'a.year_year', 'values': (1970, 1980)},
                {'key': 'a.speech_party_abbrev', 'values': 'S'},
                {'key': 'a.speech_gender_id', 'values': [2]},
            ],
            ["debatt"],
        ),
    ],
)
def test_simple_kwic_without_decode_with_multiple_terms(
    corpus: ccc.Corpus,
    person_codecs: PersonCodecs,
    word: str | list[str],
    target: str,
    p_show: str,
    filter_opts: dict[str, Any],
    expected_words: str | list[str] | None,
):
    filter_opts = encode_party_abbrev2id(person_codecs, filter_opts)

    search_opts: list[dict] = [
        {
            "prefix": None if not filter_opts else "a",
            "target": target,
            "value": word,
            "criterias": filter_opts if filter_opts and i == 0 else None,
        }
        for i, word in enumerate([word] if isinstance(word, str) else word)
    ]

    data: pd.DataFrame = simple.kwic(
        corpus, opts=search_opts, words_before=5, words_after=5, p_show=p_show, cut_off=200
    )

    assert data is not None
    assert len(data) > 0

    assert set(data[f"node_{p_show}"].unique()) == set(expected_words)
    assert data.index.name == "speech_id"
    assert set(data.columns) == {"left_word", "node_word", "right_word"}


@pytest.mark.parametrize(
    "word,target,p_show,criterias,expected_words",
    [
        (
            "att",
            "word",
            "word",
            [
                {"key": "a.year_year", "values": (1970, 1980)},
                {"key": "a.speech_party_id", "values": [1, 5, 9]},
            ],
            ["att", "Att"],
        ),
        ("information|kunskap", "word", "word", None, ["information", "kunskap"]),
        ("information", "lemma", "lemma", None, ["information"]),
        (
            "information",
            "lemma",
            "lemma",
            None,
            ["information"],
        ),
        ("landet", "word", "lemma", None, ["land"]),
        ("debatter", "word", "lemma", None, ["debatt"]),
    ],
)
def test_simple_kwic_with_decode_results_for_various_setups(
    corpus: ccc.Corpus,
    person_codecs: PersonCodecs,
    speech_index: pd.DataFrame,
    word: str | list[str],
    target: str,
    p_show: str,
    criterias: list[dict[str, Any]],
    expected_words: str | list[str] | None,
):
    search_opts: list[dict] = [
        {
            "prefix": None if not criterias else "a",
            "target": target,
            "value": word,
            "criterias": criterias if criterias and i == 0 else None,
        }
        for i, word in enumerate([word] if isinstance(word, str) else word)
    ]

    data: pd.DataFrame = simple.kwic_with_decode(
        corpus,
        opts=search_opts,
        speech_index=speech_index,
        words_before=2,
        words_after=2,
        p_show=p_show,
        cut_off=200,
        codecs=person_codecs,
    )

    assert data is not None
    assert len(data) > 0

    assert set(data[f"node_{p_show}"].unique()) == set(expected_words)


def test_kwic_with_decode(corpus: ccc.Corpus, speech_index: pd.DataFrame, person_codecs: PersonCodecs):
    party_abbrev: str = 'S'
    gender_id: int = 2

    party_id: int = person_codecs.party_abbrev2id.get(party_abbrev, 0)

    search_opts: dict[str, Any] = [
        {
            'prefix': 'a',
            'criterias': [
                {'key': 'a.year_year', 'values': (1970, 1980)},
                {'key': 'a.speech_party_id', 'values': party_id},
                {'key': 'a.speech_gender_id', 'values': [gender_id]},
            ],
            'target': 'word',
            'value': 'debatt',
        }
    ]

    data: pd.DataFrame = simple.kwic_with_decode(
        corpus,
        opts=search_opts,
        speech_index=speech_index,
        codecs=person_codecs,
        p_show="word",
        cut_off=200,
        words_after=5,
        words_before=5,
    )
    assert data is not None
    assert len(data) > 0
