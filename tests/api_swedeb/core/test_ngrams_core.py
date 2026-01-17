import io
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


def test_to_n_grams_edge_cases():
    """Test to_n_grams with edge cases."""
    # Empty phrase
    assert list(ng.to_n_grams("", 2)) == []
    
    # Single word, n=1
    assert list(ng.to_n_grams("word", 1)) == ["word"]
    
    # n larger than phrase length
    assert list(ng.to_n_grams("a b", 3)) == []
    
    # n equal to phrase length
    assert list(ng.to_n_grams("a b c", 3)) == ["a b c"]


def test_compile_n_grams_empty_input():
    """Test compile_n_grams with empty DataFrame."""
    empty_df = pd.DataFrame(columns=['window', 'count', 'documents'])
    result = ng.compile_n_grams(empty_df, n=2, mode="sliding")
    
    assert isinstance(result, pd.DataFrame)
    assert result.index.name == 'ngram'
    assert list(result.columns) == ['window_count', 'documents']
    assert len(result) == 0


def test_compile_n_grams_with_threshold():
    """Test compile_n_grams applies threshold correctly."""
    windows = pd.read_csv(io.StringIO(SUPER_SIMPLE_CONCORDANCE_GROUPED), sep="\t")
    
    # Threshold filters out low-count ngrams
    n_grams = ng.compile_n_grams(windows, n=2, threshold=5, mode="sliding")
    
    assert isinstance(n_grams, pd.DataFrame)
    assert len(n_grams) == 2  # 'e b' (count=5) and 'f e' (count=6) have count >= 5
    assert 'f e' in n_grams.index
    assert 'e b' in n_grams.index
    assert n_grams.loc['f e', 'window_count'] == 6
    assert n_grams.loc['e b', 'window_count'] == 5


@patch("api_swedeb.core.cwb.to_cqp_exprs", lambda *_, **__: 'apa')
def test_query_keyword_windows():
    corpus: MagicMock = corpus_mock(SUPER_SIMPLE_CONCORDANCE)

    result: pd.DataFrame = ng.query_keyword_windows(corpus, query_or_opts="noop", context_size=1, p_show="word")

    expected_result: pd.DataFrame = pd.read_csv(io.StringIO(SUPER_SIMPLE_CONCORDANCE_GROUPED), sep="\t")

    # Verify result is a DataFrame with correct structure
    assert isinstance(result, pd.DataFrame)
    assert list(result.columns) == ['window', 'count', 'documents']
    assert len(result) == 4  # Four unique windows in test data

    expected_result = expected_result.sort_values(by='window').reset_index(drop=True)
    result = result.sort_values(by='window').reset_index(drop=True)

    assert result.equals(expected_result)


def test_compute_n_grams_with_sliding_window():
    windows: pd.DataFrame = pd.read_csv(io.StringIO(SUPER_SIMPLE_CONCORDANCE_GROUPED), sep="\t")
    n_grams: pd.DataFrame = ng.compile_n_grams(windows, n=2, threshold=None, mode="sliding")

    # Verify DataFrame structure and content
    assert isinstance(n_grams, pd.DataFrame)
    assert n_grams.index.name == 'ngram'
    assert list(n_grams.columns) == ['window_count', 'documents']
    assert len(n_grams) == 5  # Five unique 2-grams

    assert n_grams.reset_index().to_dict('list') == {
        'ngram': ['e b', 'e e', 'e n', 'f e', 'n e'],
        'window_count': [5, 4, 4, 6, 3],
        'documents': ['A,B', 'D', 'B,C', 'A,B,C', 'A,B'],
    }


def test_compute_n_grams_with_locked_window():
    windows: pd.DataFrame = pd.read_csv(io.StringIO(SUPER_SIMPLE_CONCORDANCE_GROUPED), sep="\t")
    n_grams: pd.DataFrame = ng.compile_n_grams(windows, n=2, threshold=None, mode="locked")
    
    # Verify DataFrame structure and content
    assert isinstance(n_grams, pd.DataFrame)
    assert n_grams.index.name == 'ngram'
    assert list(n_grams.columns) == ['window_count', 'documents']
    assert len(n_grams) == 4  # Four locked windows
    
    assert n_grams.reset_index().to_dict('list') == {
        'ngram': ['f e b', 'f e n', 'n e b', 'e e e'],
        'window_count': [2, 4, 3, 2],
        'documents': ['A', 'B,C', 'A,B', 'D'],
    }
