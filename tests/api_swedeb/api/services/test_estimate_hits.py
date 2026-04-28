"""Unit tests for WordTrendsService.estimate_hits."""

from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import scipy.sparse as sp

from api_swedeb.api.services.word_trends_service import WordTrendsService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TOKEN2ID = {"klimat": 0, "demokrati": 1, "budget": 2}

# 3 documents × 3 tokens: each document has a different count per token
# doc 0 (year=1990, party_id=1, gender_id=1): klimat=2, demokrati=0, budget=1
# doc 1 (year=2000, party_id=1, gender_id=2): klimat=0, demokrati=3, budget=0
# doc 2 (year=2010, party_id=2, gender_id=1): klimat=1, demokrati=1, budget=0
MATRIX = sp.csr_matrix(
    np.array(
        [
            [2, 0, 1],
            [0, 3, 0],
            [1, 1, 0],
        ],
        dtype=np.int32,
    )
)

DOCUMENT_INDEX = pd.DataFrame(
    {
        "year": [1990, 2000, 2010],
        "party_id": [1, 1, 2],
        "gender_id": [1, 2, 1],
    }
)


def _make_corpus(matrix=MATRIX, doc_index=DOCUMENT_INDEX) -> MagicMock:
    corpus = MagicMock()
    corpus.token2id = dict(TOKEN2ID)
    corpus.bag_term_matrix = matrix
    corpus.document_index = doc_index.copy().reset_index(drop=True)
    return corpus


def _make_loader(corpus=None) -> MagicMock:
    loader = MagicMock()
    loader.vectorized_corpus = corpus or _make_corpus()
    return loader


def _make_filtered_corpus(rows: list[int]) -> MagicMock:
    """Return a mock corpus that looks like the result of corpus.filter(...) with only the given rows."""
    sub_matrix = MATRIX[rows, :]
    sub_doc_index = DOCUMENT_INDEX.iloc[rows].copy().reset_index(drop=True)
    return _make_corpus(matrix=sub_matrix, doc_index=sub_doc_index)


# ---------------------------------------------------------------------------
# Tests — no filters
# ---------------------------------------------------------------------------


class TestEstimateHitsNoFilters:
    def test_returns_none_for_unknown_word(self):
        service = WordTrendsService(loader=_make_loader())
        assert service.estimate_hits("nonexistent") is None

    def test_returns_none_for_empty_string(self):
        service = WordTrendsService(loader=_make_loader())
        assert service.estimate_hits("") is None

    def test_returns_total_column_sum_for_known_word(self):
        service = WordTrendsService(loader=_make_loader())
        # klimat: col 0 — docs 0,1,2 → 2+0+1 = 3
        assert service.estimate_hits("klimat") == 3

    def test_returns_correct_sum_for_second_token(self):
        service = WordTrendsService(loader=_make_loader())
        # demokrati: col 1 — docs 0,1,2 → 0+3+1 = 4
        assert service.estimate_hits("demokrati") == 4

    def test_lowercase_fallback_matches_vocabulary_word(self):
        # Put an upper-case key in token2id but the service does lowercase fallback
        corpus = _make_corpus()
        corpus.token2id = {"Klimat": 0, "demokrati": 1, "budget": 2}
        loader = MagicMock()
        loader.vectorized_corpus = corpus
        service = WordTrendsService(loader=loader)
        # "klimat" not in token2id directly; "Klimat" also not; no match
        assert service.estimate_hits("klimat") is None

    def test_exact_match_preferred_over_lowercase(self):
        # If exact match exists, it is used without lowercasing
        corpus = _make_corpus()
        service = WordTrendsService(loader=MagicMock(vectorized_corpus=corpus))
        assert service.estimate_hits("klimat") == 3  # exact match, col 0

    def test_returns_zero_when_token_has_no_occurrences(self):
        # Replace row values so budget (col 2) sums to 0 across all docs
        matrix = sp.csr_matrix(np.array([[0, 0, 0], [0, 3, 0], [1, 1, 0]], dtype=np.int32))
        service = WordTrendsService(loader=_make_loader(_make_corpus(matrix=matrix)))
        assert service.estimate_hits("budget") == 0


# ---------------------------------------------------------------------------
# Tests — year filter
# ---------------------------------------------------------------------------


class TestEstimateHitsYearFilter:
    def test_single_year_selects_one_document(self):
        service = WordTrendsService(loader=_make_loader())
        # year=1990 only → row 0 → klimat count = 2
        opts = {"year": {"low": 1990, "high": 1990}}
        assert service.estimate_hits("klimat", opts) == 2

    def test_year_range_selects_multiple_documents(self):
        service = WordTrendsService(loader=_make_loader())
        # years 1990–2000 → rows 0,1 → demokrati = 0+3 = 3
        opts = {"year": {"low": 1990, "high": 2000}}
        assert service.estimate_hits("demokrati", opts) == 3

    def test_year_range_outside_corpus_returns_zero(self):
        service = WordTrendsService(loader=_make_loader())
        opts = {"year": {"low": 1800, "high": 1850}}
        assert service.estimate_hits("klimat", opts) == 0

    def test_missing_low_defaults_to_zero(self):
        service = WordTrendsService(loader=_make_loader())
        # low defaults to 0 → all years with year <= 2000 → rows 0,1 → klimat = 2+0 = 2
        opts = {"year": {"high": 2000}}
        assert service.estimate_hits("klimat", opts) == 2

    def test_missing_high_defaults_to_large_value(self):
        service = WordTrendsService(loader=_make_loader())
        # high defaults to 9999 → all years with year >= 2000 → rows 1,2 → klimat = 0+1 = 1
        opts = {"year": {"low": 2000}}
        assert service.estimate_hits("klimat", opts) == 1

    def test_none_filter_opts_behaves_like_no_filter(self):
        service = WordTrendsService(loader=_make_loader())
        assert service.estimate_hits("klimat", None) == 3


# ---------------------------------------------------------------------------
# Tests — column filters (party_id, gender_id) via corpus.filter()
# ---------------------------------------------------------------------------


class TestEstimateHitsColumnFilters:
    def _service_with_filter_side_effect(self):
        """Return a service whose corpus.filter returns only party_id=1 rows (0,1)."""
        base_corpus = _make_corpus()
        filtered_corpus = _make_filtered_corpus([0, 1])

        base_corpus.filter = MagicMock(return_value=filtered_corpus)

        loader = MagicMock()
        loader.vectorized_corpus = base_corpus
        return WordTrendsService(loader=loader)

    def test_column_filter_delegates_to_corpus_filter(self):
        service = self._service_with_filter_side_effect()
        opts = {"party_id": [1]}
        # After filter → rows 0,1 → klimat = 2+0 = 2
        result = service.estimate_hits("klimat", opts)
        assert result == 2
        service._loader.vectorized_corpus.filter.assert_called_once()

    def test_year_and_column_filter_combined(self):
        """Year filter applied after corpus.filter reduces rows further."""
        service = self._service_with_filter_side_effect()
        # party_id filter → rows 0,1 (years 1990, 2000)
        # then year 1990–1990 → row 0 only → klimat = 2
        opts = {"party_id": [1], "year": {"low": 1990, "high": 1990}}
        result = service.estimate_hits("klimat", opts)
        assert result == 2

    def test_no_column_filter_does_not_call_corpus_filter(self):
        corpus = _make_corpus()
        corpus.filter = MagicMock()
        loader = MagicMock(vectorized_corpus=corpus)
        service = WordTrendsService(loader=loader)
        service.estimate_hits("klimat")
        corpus.filter.assert_not_called()
