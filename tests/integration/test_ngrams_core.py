"""Integration tests for api_swedeb.core.n_grams with real CWB corpus."""

from collections import Counter, defaultdict
from typing import Iterable

import pandas as pd
from ccc import Corpus

from api_swedeb.core import n_grams as ng


def test_compute_n_grams2(corpus: Corpus):
    """Test compute_n_grams with real corpus data."""
    n: int = 2
    keyword: str = "'sverige'%c"

    windows: pd.DataFrame = ng.query_keyword_windows(corpus, query_or_opts=keyword, context_size=n, p_show="word")

    ngram_counter: Counter = defaultdict(int)
    ngram_documents: Counter = defaultdict(set)

    cx: dict[int, int] = windows['count'].to_dict().get

    n_grams: Iterable[tuple[int, str, str]] = (
        (index, ngram, row['documents'])
        for index, row in windows.iterrows()
        for ngram in ng.to_n_grams(row['window'], n)
    )

    for index, ngram, documents in n_grams:
        ngram_counter[ngram] += cx(index)
        ngram_documents['documents'] |= set(documents.split(','))

    assert ngram_counter is not None


def test_n_grams(corpus: Corpus):
    """Test n_grams function with real corpus in different modes."""
    query_or_opts = {
        "target": "information",
    }
    n: int = 2

    # Test sliding window mode
    data: pd.DataFrame = ng.n_grams(corpus, query_or_opts, n=n, threshold=2, mode="sliding")
    assert data is not None
    assert len(data) > 0
    assert data.columns.tolist() == ['window_count', 'documents']
    assert data.index.name == 'ngram'
    assert data.index.str.lower().str.contains('information').all()
    assert (data.index.str.split().str.len() == 2).all()

    # Test left-aligned mode
    data_left_aligned: pd.DataFrame = ng.n_grams(corpus, query_or_opts, n=n, threshold=1, mode="left-aligned")
    assert data_left_aligned is not None
    assert len(data_left_aligned) > 0
    assert data_left_aligned.index.str.lower().str.startswith('information').all()
    assert (data_left_aligned.index.str.split().str.len() == 2).all()

    # Test right-aligned mode
    data_right_aligned: pd.DataFrame = ng.n_grams(corpus, query_or_opts, n=n, threshold=1, mode="right-aligned")
    assert data_right_aligned is not None
    assert len(data_right_aligned) > 0
    assert data_right_aligned.index.str.lower().str.endswith('information').all()
    assert (data_right_aligned.index.str.split().str.len() == 2).all()
