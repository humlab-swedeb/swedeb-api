from typing import Any
from unittest.mock import MagicMock, patch

import ccc
import pandas as pd
import pytest

from api_swedeb.core.codecs import PersonCodecs
from api_swedeb.core.cwb import CorpusCreateOpts
from api_swedeb.core.kwic import simple
from api_swedeb.core.kwic.multiprocess import execute_kwic_multiprocess, kwic_worker
from api_swedeb.core.kwic.singleprocess import execute_kwic_singleprocess
from api_swedeb.core.kwic.utility import (
    create_year_chunks,
    empty_kwic,
    extract_year_range,
    inject_year_filter,
)

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


@pytest.fixture(scope="module")
def corpus_opts(corpus: ccc.Corpus) -> CorpusCreateOpts:
    """Create CorpusCreateOpts from corpus for multiprocessing tests."""
    return CorpusCreateOpts.to_opts(corpus)


def encode_party_abbrev2id(person_codecs: PersonCodecs, criterias: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Helper function that encodes party abbreviations to party ids (simplifies designing test cases)"""

    if criterias:
        for criteria in criterias:
            if not criteria['key'].endswith("_party_abbrev"):
                continue

            criteria['key'] = 'a.speech_party_id'
            party_abbrev: str = criteria['values'] if isinstance(criteria['values'], list) else [criteria['values']]
            criteria['values'] = [
                person_codecs.get_mapping('party_abbrev', 'party_id').get(party, 0) for party in party_abbrev
            ]

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
    search_opts: list[dict[str, Any]] = [
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

    party_id: int = person_codecs.get_mapping('party_abbrev', 'party_id').get(party_abbrev, 0)

    search_opts: list[dict[str, Any]] = [
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


# ==============================================================================
# Tests for utility.py
# ==============================================================================


def test_empty_kwic():
    """Test empty_kwic creates proper empty DataFrame."""
    result = empty_kwic("word")
    assert isinstance(result, pd.DataFrame)
    assert result.index.name == "speech_id"
    assert len(result) == 0
    assert list(result.columns) == ["left_word", "node_word", "right_word"]

    result_lemma = empty_kwic("lemma")
    assert list(result_lemma.columns) == ["left_lemma", "node_lemma", "right_lemma"]


@pytest.mark.parametrize(
    "opts,default_min,default_max,expected",
    [
        # Dict with year range tuple
        (
            {"criterias": [{"key": "a.year_year", "values": (1970, 1980)}]},
            1867,
            2025,
            (1970, 1980),
        ),
        # List of dicts with year range
        (
            [{"criterias": [{"key": "year_year", "values": (1990, 2000)}]}],
            1867,
            2025,
            (1990, 2000),
        ),
        # Year as list
        (
            {"criterias": [{"key": "a.year_year", "values": [1950, 1960, 1970]}]},
            1867,
            2025,
            (1950, 1970),
        ),
        # Single year value
        (
            {"criterias": [{"key": "year_year", "values": 1985}]},
            1867,
            2025,
            (1985, 1985),
        ),
        # No year criteria - use defaults
        (
            {"criterias": [{"key": "party_id", "values": 1}]},
            1867,
            2025,
            (1867, 2025),
        ),
        # Empty criterias
        ({}, 1900, 2020, (1900, 2020)),
        # Criterias as dict (not list)
        (
            {"criterias": {"key": "a.year_year", "values": (1945, 1955)}},
            1867,
            2025,
            (1945, 1955),
        ),
    ],
)
def test_extract_year_range(opts, default_min, default_max, expected):
    """Test extract_year_range handles various input formats."""
    result = extract_year_range(opts, default_min, default_max)
    assert result == expected


@pytest.mark.parametrize(
    "min_year,max_year,num_chunks,expected_count",
    [
        (1867, 2024, 4, 4),
        (1900, 1910, 5, 5),
        (2000, 2005, 10, 6),  # More chunks than years
        (1950, 1950, 3, 1),  # Single year
        (1867, 2024, 1, 1),  # Single chunk
    ],
)
def test_create_year_chunks(min_year, max_year, num_chunks, expected_count):
    """Test create_year_chunks divides year ranges correctly."""
    chunks = create_year_chunks(min_year, max_year, num_chunks)
    assert len(chunks) == expected_count

    # Verify chunks cover the entire range
    assert chunks[0][0] == min_year
    assert chunks[-1][1] == max_year

    # Verify no gaps between chunks
    for i in range(len(chunks) - 1):
        assert chunks[i][1] + 1 == chunks[i + 1][0]


def test_create_year_chunks_detailed():
    """Test create_year_chunks produces correct ranges."""
    chunks = create_year_chunks(1900, 1919, 4)
    assert len(chunks) == 4

    # Each chunk should have roughly equal size (5 years)
    for chunk in chunks:
        assert chunk[0] <= chunk[1]


@pytest.mark.parametrize(
    "opts,year_range,expected_year_filter",
    [
        # Replace existing year filter
        (
            {"prefix": "a", "criterias": [{"key": "a.year_year", "values": (1900, 1950)}]},
            (1970, 1980),
            (1970, 1980),
        ),
        # Add year filter when none exists
        (
            {"prefix": "a", "criterias": [{"key": "a.party_id", "values": 1}]},
            (1990, 2000),
            (1990, 2000),
        ),
        # Dict criterias (not list)
        (
            {"prefix": "b", "criterias": {"key": "b.party_id", "values": 1}},
            (1985, 1995),
            (1985, 1995),
        ),
    ],
)
def test_inject_year_filter(opts, year_range, expected_year_filter):
    """Test inject_year_filter correctly adds/replaces year filters."""
    result = inject_year_filter(opts, year_range)

    assert isinstance(result, list)
    assert len(result) > 0

    # Check that year filter was injected
    found_year = False
    for opt in result:
        criterias = opt.get("criterias", [])
        if isinstance(criterias, dict):
            criterias = [criterias]

        for criteria in criterias:
            if "year" in criteria.get("key", "").lower():
                assert criteria["values"] == expected_year_filter
                found_year = True
                break

    assert found_year, "Year filter was not injected"


def test_inject_year_filter_list_of_opts():
    """Test inject_year_filter works with list of options."""
    opts = [
        {"prefix": "a", "criterias": [{"key": "a.party_id", "values": 1}]},
        {"prefix": "b", "criterias": [{"key": "b.gender_id", "values": 2}]},
    ]
    year_range = (1975, 1985)

    result = inject_year_filter(opts, year_range)

    assert len(result) == 2
    # Only first opt should have year filter injected
    first_criterias = result[0]["criterias"]
    assert any("year" in c.get("key", "").lower() for c in first_criterias)


# ==============================================================================
# Tests for singleprocess.py
# ==============================================================================


def test_execute_kwic_singleprocess_basic(corpus: ccc.Corpus):
    """Test basic singleprocess KWIC execution."""
    opts = {
        "prefix": "a",
        "target": "word",
        "value": "debatt",
        "criterias": [{"key": "a.year_year", "values": (1970, 1975)}],
    }

    result = execute_kwic_singleprocess(
        corpus=corpus,
        opts=opts,
        words_before=3,
        words_after=3,
        p_show="word",
        cut_off=50,
    )

    assert isinstance(result, pd.DataFrame)
    assert result.index.name == "speech_id"
    assert "node_word" in result.columns
    assert "left_word" in result.columns
    assert "right_word" in result.columns


def test_execute_kwic_singleprocess_no_results(corpus: ccc.Corpus):
    """Test singleprocess KWIC with no matching results."""
    opts = {
        "prefix": "a",
        "target": "word",
        "value": "nonexistentword123456",
        "criterias": [],
    }

    result = execute_kwic_singleprocess(
        corpus=corpus,
        opts=opts,
        words_before=3,
        words_after=3,
        p_show="word",
        cut_off=None,
    )

    assert isinstance(result, pd.DataFrame)
    assert len(result) == 0


def test_execute_kwic_singleprocess_lemma(corpus: ccc.Corpus):
    """Test singleprocess KWIC with lemma display."""
    opts = {
        "target": "lemma",
        "value": "information",
        "criterias": [],
    }

    result = execute_kwic_singleprocess(
        corpus=corpus,
        opts=opts,
        words_before=2,
        words_after=2,
        p_show="lemma",
        cut_off=100,
    )

    assert isinstance(result, pd.DataFrame)
    if len(result) > 0:
        assert "node_lemma" in result.columns
        assert "left_lemma" in result.columns
        assert "right_lemma" in result.columns


# ==============================================================================
# Tests for multiprocess.py
# ==============================================================================


def test_corpus_create_opts_serialization(corpus: ccc.Corpus):
    """Test that CorpusCreateOpts can be created from corpus and reconstructed."""
    # Create opts from corpus
    corpus_opts = CorpusCreateOpts.to_opts(corpus)

    assert isinstance(corpus_opts, CorpusCreateOpts)
    assert corpus_opts.registry_dir == corpus.registry_dir
    assert corpus_opts.corpus_name == corpus.corpus_name
    assert corpus_opts.data_dir == corpus.data_dir

    # Test that it can be used to create a new corpus
    new_corpus = corpus_opts.create_corpus()
    assert isinstance(new_corpus, ccc.Corpus)
    assert new_corpus.registry_dir == corpus.registry_dir
    assert new_corpus.corpus_name == corpus.corpus_name


def test_corpus_create_opts_resolve(corpus: ccc.Corpus):
    """Test CorpusCreateOpts.resolve() method."""
    corpus_opts = CorpusCreateOpts.to_opts(corpus)

    # Test resolve with CorpusCreateOpts
    resolved = CorpusCreateOpts.resolve(corpus_opts)
    assert isinstance(resolved, ccc.Corpus)

    # Test resolve with already a Corpus
    resolved2 = CorpusCreateOpts.resolve(corpus)
    assert resolved2 is corpus


def test_kwic_worker(corpus_opts: CorpusCreateOpts):
    """Test kwic_worker function."""
    opts = {
        "prefix": "a",
        "target": "word",
        "value": "debatt",
    }
    year_range = (1970, 1975)
    args = (corpus_opts, opts, year_range, 3, 3, "word", 50)

    result = kwic_worker(args)

    assert isinstance(result, pd.DataFrame)
    assert result.index.name == "speech_id"


def test_execute_kwic_multiprocess_basic(corpus_opts: CorpusCreateOpts):
    """Test basic multiprocess KWIC execution."""
    opts = {
        "prefix": "a",
        "target": "word",
        "value": "debatt",
        "criterias": [{"key": "a.year_year", "values": (1970, 1980)}],
    }

    result = execute_kwic_multiprocess(
        corpus=corpus_opts,
        opts=opts,
        words_before=3,
        words_after=3,
        p_show="word",
        cut_off=100,
        num_processes=2,
    )

    assert isinstance(result, pd.DataFrame)
    assert result.index.name == "speech_id"
    if len(result) > 0:
        assert "node_word" in result.columns


def test_execute_kwic_multiprocess_with_cutoff(corpus_opts: CorpusCreateOpts):
    """Test multiprocess KWIC respects cutoff."""
    opts = {
        "target": "word",
        "value": "att",
        "criterias": [{"key": "a.year_year", "values": (1970, 1985)}],
    }

    cut_off = 20
    result = execute_kwic_multiprocess(
        corpus=corpus_opts,
        opts=opts,
        words_before=2,
        words_after=2,
        p_show="word",
        cut_off=cut_off,
        num_processes=2,
    )

    assert len(result) <= cut_off


def test_execute_kwic_multiprocess_no_results(corpus_opts: CorpusCreateOpts):
    """Test multiprocess KWIC with no results."""
    opts = {
        "target": "word",
        "value": "nonexistentword999999",
        "criterias": [{"key": "a.year_year", "values": (1970, 1975)}],
    }

    result = execute_kwic_multiprocess(
        corpus=corpus_opts,
        opts=opts,
        words_before=2,
        words_after=2,
        p_show="word",
        cut_off=None,
        num_processes=2,
    )

    assert isinstance(result, pd.DataFrame)
    assert len(result) == 0


@patch("api_swedeb.core.kwic.multiprocess.mp.cpu_count", return_value=4)
def test_execute_kwic_multiprocess_default_num_processes(mock_cpu_count, corpus_opts: CorpusCreateOpts):
    """Test multiprocess KWIC uses CPU count when num_processes is None."""
    opts = {
        "target": "word",
        "value": "debatt",
        "criterias": [{"key": "a.year_year", "values": (1970, 1975)}],
    }

    result = execute_kwic_multiprocess(
        corpus=corpus_opts,
        opts=opts,
        words_before=2,
        words_after=2,
        p_show="word",
        cut_off=50,
        num_processes=None,
    )

    assert isinstance(result, pd.DataFrame)
    mock_cpu_count.assert_called_once()


# ==============================================================================
# Tests for simple.py
# ==============================================================================


def test_kwic_singleprocess_mode(corpus: ccc.Corpus):
    """Test kwic function in singleprocess mode."""
    opts = {
        "target": "word",
        "value": "debatt",
        "criterias": [{"key": "a.year_year", "values": (1970, 1975)}],
    }

    result = simple.kwic(
        corpus=corpus,
        opts=opts,
        words_before=3,
        words_after=3,
        p_show="word",
        cut_off=50,
        use_multiprocessing=False,
    )

    assert isinstance(result, pd.DataFrame)
    assert result.index.name == "speech_id"


def test_kwic_multiprocess_mode(corpus_opts: CorpusCreateOpts):
    """Test kwic function in multiprocess mode."""
    opts = {
        "target": "word",
        "value": "debatt",
        "criterias": [{"key": "a.year_year", "values": (1970, 1980)}],
    }

    result = simple.kwic(
        corpus=corpus_opts,
        opts=opts,
        words_before=3,
        words_after=3,
        p_show="word",
        cut_off=50,
        use_multiprocessing=True,
        num_processes=2,
    )

    assert isinstance(result, pd.DataFrame)
    assert result.index.name == "speech_id"


def test_kwic_with_list_of_words(corpus: ccc.Corpus):
    """Test kwic with multiple search terms."""
    opts = [
        {"target": "word", "value": "kärnkraft"},
        {"target": "word", "value": "kärnvapen"},
    ]

    result = simple.kwic(
        corpus=corpus,
        opts=opts,
        words_before=2,
        words_after=2,
        p_show="word",
        cut_off=100,
        use_multiprocessing=False,
    )

    assert isinstance(result, pd.DataFrame)


def test_kwic_with_decode_returns_enriched_data(
    corpus: ccc.Corpus,
    speech_index: pd.DataFrame,
    person_codecs: PersonCodecs,
):
    """Test kwic_with_decode adds metadata columns."""
    opts = {
        "target": "word",
        "value": "debatt",
        "criterias": [{"key": "a.year_year", "values": (1970, 1975)}],
    }

    result = simple.kwic_with_decode(
        corpus=corpus,
        opts=opts,
        speech_index=speech_index,
        codecs=person_codecs,
        words_before=2,
        words_after=2,
        p_show="word",
        cut_off=50,
        use_multiprocessing=False,
    )

    assert isinstance(result, pd.DataFrame)
    if len(result) > 0:
        # Check for decoded columns
        assert "name" in result.columns
        assert "party_abbrev" in result.columns
        assert "gender" in result.columns
        assert "node_word" in result.columns


def test_kwic_with_decode_multiprocess(
    corpus_opts: CorpusCreateOpts,
    speech_index: pd.DataFrame,
    person_codecs: PersonCodecs,
):
    """Test kwic_with_decode in multiprocess mode."""
    opts = {
        "target": "word",
        "value": "debatt",
        "criterias": [{"key": "a.year_year", "values": (1970, 1980)}],
    }

    result = simple.kwic_with_decode(
        corpus=corpus_opts,
        opts=opts,
        speech_index=speech_index,
        codecs=person_codecs,
        words_before=2,
        words_after=2,
        p_show="word",
        cut_off=50,
        use_multiprocessing=True,
        num_processes=2,
    )

    assert isinstance(result, pd.DataFrame)
    if len(result) > 0:
        assert "name" in result.columns
        assert "node_word" in result.columns


def test_kwic_lemma_vs_word_comparison(corpus: ccc.Corpus):
    """Test kwic returns different results for word vs lemma."""
    opts_word = {"target": "word", "value": "landet"}
    opts_lemma = {"target": "lemma", "value": "land"}

    result_word = simple.kwic(
        corpus=corpus,
        opts=opts_word,
        words_before=2,
        words_after=2,
        p_show="word",
        cut_off=50,
    )

    result_lemma = simple.kwic(
        corpus=corpus,
        opts=opts_lemma,
        words_before=2,
        words_after=2,
        p_show="lemma",
        cut_off=50,
    )

    assert isinstance(result_word, pd.DataFrame)
    assert isinstance(result_lemma, pd.DataFrame)


@pytest.mark.parametrize(
    "use_multiprocessing,num_processes",
    [
        (False, None),
        (True, 2),
        (True, 3),
    ],
)
def test_kwic_processing_modes(
    corpus: ccc.Corpus,
    corpus_opts: CorpusCreateOpts,
    use_multiprocessing: bool,
    num_processes: int | None,
):
    """Test different processing modes produce valid results."""
    opts = {
        "target": "word",
        "value": "debatt",
        "criterias": [{"key": "a.year_year", "values": (1970, 1975)}],
    }

    # Use corpus_opts for multiprocessing, corpus for singleprocessing
    corpus_param = corpus_opts if use_multiprocessing else corpus

    result = simple.kwic(
        corpus=corpus_param,
        opts=opts,
        words_before=2,
        words_after=2,
        p_show="word",
        cut_off=50,
        use_multiprocessing=use_multiprocessing,
        num_processes=num_processes,
    )

    assert isinstance(result, pd.DataFrame)
    assert result.index.name == "speech_id"
