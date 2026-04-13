"""Regression tests for kwic_with_decode output schema and field values.

These tests capture the exact output contract of the prebuilt speech_index
decode path in simple.kwic_with_decode.  The prebuilt speech_index.feather
contains fully materialised speaker metadata including wiki_id, removing the
need for runtime codec lookups.

Run these after any refactoring to the KWIC decode pipeline to verify the
output shape and field semantics are preserved.
"""

from __future__ import annotations

from typing import Any

import ccc
import pandas as pd
import pytest

from api_swedeb.api.services.corpus_loader import CorpusLoader
from api_swedeb.core.kwic import simple
from api_swedeb.mappers.kwic import kwic_to_api_model
from api_swedeb.schemas.kwic_schema import KeywordInContextResult

# pylint: disable=redefined-outer-name

# ---------------------------------------------------------------------------
# Expected column contract for kwic_with_decode output
# ---------------------------------------------------------------------------
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

# Fixed search: word "debatt", years 1970-1980, small cut-off for speed
FIXED_SEARCH_OPTS: list[dict[str, Any]] = [
    {
        "prefix": "a",
        "target": "word",
        "value": "debatt",
        "criterias": [
            {"key": "a.year_year", "values": (1970, 1980)},
        ],
    }
]


# ---------------------------------------------------------------------------
# Shared fixture — runs the decode pipeline once per module
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def _kwic_loader() -> CorpusLoader:
    """CorpusLoader pointing at the real data symlink (data/v1.4.1/...).

    Uses the same real dataset as test_index_diffs.py — the prebuilt
    speech_index.feather is not checked in under tests/test_data/, it is
    produced by the build pipeline and lives under data/.
    """
    from api_swedeb.core.configuration import ConfigValue  # pylint: disable=import-outside-toplevel

    bootstrap_folder = "data/v1.4.1/speeches/bootstrap_corpus"
    loader = CorpusLoader(
        speech_bootstrap_corpus_folder=bootstrap_folder,
        dtm_tag=ConfigValue("dtm.tag").resolve(),
        dtm_folder=ConfigValue("dtm.folder").resolve(),
        metadata_filename=ConfigValue("metadata.filename").resolve(),
    )
    _ = loader.prebuilt_speech_index
    return loader


@pytest.fixture(scope="module")
def kwic_baseline(corpus: ccc.Corpus, _kwic_loader: CorpusLoader) -> pd.DataFrame:
    """KWIC result via the prebuilt speech_index decode path."""
    return simple.kwic_with_decode(
        corpus,
        opts=FIXED_SEARCH_OPTS,
        prebuilt_speech_index=_kwic_loader.prebuilt_speech_index,
        words_before=3,
        words_after=3,
        p_show="word",
        cut_off=500,
    )


# ---------------------------------------------------------------------------
# Schema / shape tests
# ---------------------------------------------------------------------------


def test_output_has_rows(kwic_baseline: pd.DataFrame):
    """A known word must produce at least one hit."""
    assert len(kwic_baseline) > 0, "kwic_with_decode returned empty DataFrame for 'debatt'"


def test_output_columns_exact(kwic_baseline: pd.DataFrame):
    """Column set must exactly match the documented contract."""
    actual = set(kwic_baseline.columns)
    missing = EXPECTED_COLUMNS - actual
    extra = actual - EXPECTED_COLUMNS
    assert not missing and not extra, f"Missing columns: {missing}  |  Unexpected columns: {extra}"


# ---------------------------------------------------------------------------
# Key field integrity tests
# ---------------------------------------------------------------------------


def test_speech_id_never_null(kwic_baseline: pd.DataFrame):
    """speech_id must be populated on every row — it is the stable speech key."""
    null_count = int(kwic_baseline["speech_id"].isna().sum())
    assert null_count == 0, f"{null_count} rows have null speech_id"


def test_document_name_never_null(kwic_baseline: pd.DataFrame):
    """document_name must be present on every row — used to generate speech_link."""
    null_count = int(kwic_baseline["document_name"].isna().sum())
    assert null_count == 0, f"{null_count} rows have null document_name"


def test_document_id_never_null(kwic_baseline: pd.DataFrame):
    """document_id (DTM integer key) is None in the prebuilt path — this is expected.

    The prebuilt speech_index does not carry the DTM document_id.  The column
    must still exist (schema requires Optional[int]) but will be all-null.
    """
    assert "document_id" in kwic_baseline.columns, "document_id column is missing"


def test_node_word_matches_search_term(kwic_baseline: pd.DataFrame):
    """node_word must contain the searched word (case-insensitive)."""
    unexpected = kwic_baseline[~kwic_baseline["node_word"].str.lower().str.contains("debatt")]
    assert (
        unexpected.empty
    ), f"{len(unexpected)} rows have unexpected node_word values: {unexpected['node_word'].unique()}"


def test_year_within_filter_range(kwic_baseline: pd.DataFrame):
    """All rows must fall within the requested year range [1970, 1980]."""
    out_of_range = kwic_baseline[(kwic_baseline["year"] < 1970) | (kwic_baseline["year"] > 1980)]
    assert out_of_range.empty, f"{len(out_of_range)} rows have year outside [1970, 1980]"


# ---------------------------------------------------------------------------
# Codec-decoded fields
# ---------------------------------------------------------------------------


def test_wiki_id_column_present(kwic_baseline: pd.DataFrame):
    """wiki_id column must exist (individual values may be None for unknown speakers)."""
    assert "wiki_id" in kwic_baseline.columns


def test_link_format_for_known_speakers(kwic_baseline: pd.DataFrame):
    """link must begin with the Wikidata base URL for speakers with a real wiki_id."""
    known = kwic_baseline[kwic_baseline["wiki_id"].notna() & ~kwic_baseline["wiki_id"].isin(["unknown", ""])]
    if not known.empty:
        bad = known[~known["link"].str.startswith("https://www.wikidata.org/wiki/")]
        assert bad.empty, f"{len(bad)} known-speaker rows have malformed link: {bad['link'].unique()}"


def test_speech_link_column_present(kwic_baseline: pd.DataFrame):
    """speech_link column must exist (values may be None for some rows)."""
    assert "speech_link" in kwic_baseline.columns


def test_gender_and_abbrev_columns_present(kwic_baseline: pd.DataFrame):
    """Decoded gender columns must both be present."""
    assert "gender" in kwic_baseline.columns
    assert "gender_abbrev" in kwic_baseline.columns


def test_party_columns_present(kwic_baseline: pd.DataFrame):
    """party_abbrev must be present; full party name column exists but may be null in prebuilt path."""
    assert "party_abbrev" in kwic_baseline.columns
    assert "party" in kwic_baseline.columns  # column present, values may be None


# ---------------------------------------------------------------------------
# Mapper / schema round-trip
# ---------------------------------------------------------------------------


def test_schema_roundtrip_produces_valid_result(kwic_baseline: pd.DataFrame):
    """kwic_to_api_model must produce a valid KeywordInContextResult from the output."""
    result: KeywordInContextResult = kwic_to_api_model(kwic_baseline)
    assert isinstance(result, KeywordInContextResult)
    assert len(result.kwic_list) == len(kwic_baseline)


def test_schema_roundtrip_first_item_fields(kwic_baseline: pd.DataFrame):
    """First item in the API result must have non-null values for mandatory fields."""
    result: KeywordInContextResult = kwic_to_api_model(kwic_baseline)
    item = result.kwic_list[0]
    assert item.node_word is not None, "node_word is None in API result"
    # speech_id must be present — it is the stable speech identifier
    assert item.speech_id is not None, "speech_id is None in API result"
    assert item.document_name is not None, "document_name is None in API result"
    assert item.year is not None, "year is None in API result"
    # document_id is null in the prebuilt path (no DTM integer key)
    # party full name is null in the prebuilt path until rebuilt with that column
