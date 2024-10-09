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
    "title",
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
                {'key': 'a.speech_party_id', 'values': 9},
                {'key': 'a.speech_gender_id', 'values': [2]},
            ],
            ["debatt"],
        ),
    ],
)
def test_simple_kwic_without_decode_with_multiple_terms(
    corpus: ccc.Corpus,
    word: str | list[str],
    target: str,
    p_show: str,
    filter_opts: dict[str, Any],
    expected_words: str | list[str] | None,
):
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
        ("information|kunskap", "word", "word", None, ["information", "kunskap", "Information"]),
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
    search_opts: dict[str, Any] = [
        {
            'prefix': 'a',
            'criterias': [
                {'key': 'a.year_year', 'values': (1970, 1980)},
                {'key': 'a.speech_party_id', 'values': 9},
                {'key': 'a.speech_gender_id', 'values': [2]},
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
