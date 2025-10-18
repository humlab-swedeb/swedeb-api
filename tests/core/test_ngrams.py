import io
from collections import Counter, defaultdict
from typing import Iterable
from unittest.mock import MagicMock, patch

import pandas as pd
from ccc import Corpus, SubCorpus

from api_swedeb.core import n_grams as ng

version = "v1"


# def random_letter():
#     return random.choice(string.ascii_lowercase)

# def random_ids(n: int) -> str:
#     j: int = random.choice([1,2,3])
#     def fx(n, i) -> str:
#         return f"'i-{n}{random_letter()}{i}'"
#     return f"{j}\t[{','.join(fx(n,i) for i in range(j))}]"

# def generate_random_string_with_fixed_middle(n: int) -> str:
#     middle_letter: str = random_letter()
#     return '\n'.join(
#         f"{random_letter()} {random_letter()} {middle_letter} {random_letter()} {random_letter()}\t{random_ids(i)}"
#         for i in range(n)
#     )


SUPER_SIMPLE_CONCORDANCE = """word\tspeech_id
f e b\tA
f e b\tA
n e b\tA
n e b\tA
n e b\tB
f e n\tB
f e n\tC
f e n\tC
f e n\tC
e e e\tD
e e e\tD
"""

SUPER_SIMPLE_CONCORDANCE_GROUPED = """window\tcount\tdocuments
f e b\t2\tA
f e n\t4\tB,C
n e b\t3\tA,B
e e e\t2\tD
"""


def corpus_mock(return_data: str) -> MagicMock:
    simpleConcordance: pd.DataFrame = pd.read_csv(io.StringIO(return_data), sep="\t")
    subCorpusMock: MagicMock = MagicMock(spec=SubCorpus, concordance=MagicMock(return_value=simpleConcordance))
    corpusMock: MagicMock = MagicMock(spec=Corpus, query=MagicMock(return_value=subCorpusMock))
    return corpusMock


def test_to_n_grams():
    phrase: str = "f e b"
    assert list(ng.to_n_grams(phrase, 3)) == ["f e b"]
    assert list(ng.to_n_grams(phrase, 2)) == ["f e", "e b"]

    phrase: str = "a b c d e"

    assert list(ng.to_n_grams(phrase, 2)) == ["a b", "b c", "c d", "d e"]
    assert list(ng.to_n_grams(phrase, 3)) == ["a b c", "b c d", "c d e"]


@patch("api_swedeb.core.cwb.to_cqp_exprs", lambda *_, **__: 'apa')
def test_query_keyword_windows():
    corpus: MagicMock = corpus_mock(SUPER_SIMPLE_CONCORDANCE)

    result: pd.DataFrame = ng.query_keyword_windows(corpus, query_or_opts="noop", context_size=1, p_show="word")

    expected_result: pd.DataFrame = pd.read_csv(io.StringIO(SUPER_SIMPLE_CONCORDANCE_GROUPED), sep="\t")

    assert result is not None

    expected_result = expected_result.sort_values(by='window').reset_index(drop=True)
    result = result.sort_values(by='window').reset_index(drop=True)

    assert result.equals(expected_result)


def test_compute_n_grams_with_sliding_window():
    windows: pd.DataFrame = pd.read_csv(io.StringIO(SUPER_SIMPLE_CONCORDANCE_GROUPED), sep="\t")
    n_grams: pd.DataFrame = ng.compile_n_grams(windows, n=2, threshold=None, mode="sliding")

    assert n_grams is not None

    assert n_grams.reset_index().to_dict('list') == {
        'ngram': ['e b', 'e e', 'e n', 'f e', 'n e'],
        'window_count': [5, 4, 4, 6, 3],
        'documents': ['A,B', 'D', 'B,C', 'A,B,C', 'A,B'],
    }


def test_compute_n_grams_with_locked_window():
    windows: pd.DataFrame = pd.read_csv(io.StringIO(SUPER_SIMPLE_CONCORDANCE_GROUPED), sep="\t")
    n_grams: pd.DataFrame = ng.compile_n_grams(windows, n=2, threshold=None, mode="locked")
    assert n_grams is not None
    assert n_grams.index.name == 'ngram'
    assert n_grams.reset_index().to_dict('list') == {
        'ngram': ['f e b', 'f e n', 'n e b', 'e e e'],
        'window_count': [2, 4, 3, 2],
        'documents': ['A', 'B,C', 'A,B', 'D'],
    }


def test_compute_n_grams2(corpus: Corpus):
    n: int = 2
    keyword: str = '"sverige"%c'

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
    query_or_opts = {
        "target": "information",
    }
    n: int = 2

    # with patch("api_swedeb.core.n_grams.compute.compile_n_grams", lambda *_, **__: 'apa'):
    data: pd.DataFrame = ng.n_grams(corpus, query_or_opts, n=n, threshold=2, mode="sliding")
    assert data is not None
    assert len(data) > 0
    assert data.columns.tolist() == ['window_count', 'documents']
    assert data.index.name == 'ngram'
    assert data.index.str.lower().str.contains('information').all()
    assert (data.index.str.split().str.len() == 2).all()

    data_left_aligned: pd.DataFrame = ng.n_grams(corpus, query_or_opts, n=n, threshold=1, mode="left-aligned")
    assert data_left_aligned is not None
    assert len(data_left_aligned) > 0
    assert data_left_aligned.index.str.lower().str.startswith('information').all()
    assert (data_left_aligned.index.str.split().str.len() == 2).all()

    data_right_aligned: pd.DataFrame = ng.n_grams(corpus, query_or_opts, n=n, threshold=1, mode="right-aligned")
    assert data_right_aligned is not None
    assert len(data_right_aligned) > 0
    assert data_right_aligned.index.str.lower().str.endswith('information').all()
    assert (data_right_aligned.index.str.split().str.len() == 2).all()
