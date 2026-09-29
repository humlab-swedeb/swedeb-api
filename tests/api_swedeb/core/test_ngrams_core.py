import io
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
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
    assert not list(ng.to_n_grams("", 2))

    # Single word, n=1
    assert list(ng.to_n_grams("word", 1)) == ["word"]

    # n larger than phrase length
    assert not list(ng.to_n_grams("a b", 3))

    # n equal to phrase length
    assert list(ng.to_n_grams("a b c", 3)) == ["a b c"]


def test_to_ngrams_dataframe_keeps_source_segments():
    """Test row expansion keeps the source DataFrame index for each n-gram."""
    windows = pd.DataFrame(
        {
            'window': ['alpha beta gamma', 'delta epsilon'],
        },
        index=[10, 20],
    )

    result = ng.to_ngrams_dataframe(windows, n=2)

    assert result.to_dict('list') == {
        'segment': [10, 10, 20],
        'ngram': ['alpha beta', 'beta gamma', 'delta epsilon'],
    }


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


@pytest.mark.parametrize(
    ("query_or_opts", "expected_error", "expected_message"),
    [
        (None, ValueError, "query_or_opts cannot be None"),
        (123, TypeError, "query_or_opts must be a string, a dictionary or a list of dictionaries"),
    ],
)
def test_query_keyword_windows_rejects_invalid_query_options(query_or_opts, expected_error, expected_message):
    corpus: MagicMock = corpus_mock(SUPER_SIMPLE_CONCORDANCE)

    with pytest.raises(expected_error, match=expected_message):
        ng.query_keyword_windows(corpus, query_or_opts=query_or_opts, context_size=1, p_show="word")


@pytest.mark.parametrize(
    ("context_size", "expected_error", "expected_message"),
    [
        ("1", TypeError, "context_size must be an integer or a tuple of two integers"),
        ((1,), ValueError, "context_size tuple must have exactly two integer elements"),
        ((1, "2"), ValueError, "context_size tuple must have exactly two integer elements"),
    ],
)
def test_query_keyword_windows_rejects_invalid_context_size(context_size, expected_error, expected_message):
    corpus: MagicMock = corpus_mock(SUPER_SIMPLE_CONCORDANCE)

    with pytest.raises(expected_error, match=expected_message):
        ng.query_keyword_windows(corpus, query_or_opts="noop", context_size=context_size, p_show="word")


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


def test_query_keyword_windows_returns_empty_grouped_frame():
    corpus: MagicMock = corpus_mock("word\tspeech_id\n")

    result: pd.DataFrame = ng.query_keyword_windows(corpus, query_or_opts="'missing'%c", context_size=3, p_show="word")

    corpus.query.assert_called_once_with(cqp_query="'missing'%c", context=2)
    assert result.to_dict('list') == {'window': [], 'count': [], 'documents': []}


def test_query_keyword_windows_uses_enough_context_for_all_sliding_positions():
    corpus: MagicMock = corpus_mock("word\tspeech_id\nbefore focus after\tA\n")

    ng.query_keyword_windows(corpus, query_or_opts="'focus'%c", context_size=3, p_show="word")

    corpus.query.assert_called_once_with(cqp_query="'focus'%c", context=2)


def test_query_keyword_windows_adjusts_context_for_multi_token_query():
    corpus: MagicMock = corpus_mock("word\tspeech_id\nfocus word after\tA\n")
    query_options = [{"target": "focus"}, {"target": "word"}]

    with patch("api_swedeb.core.n_grams.compute.to_cqp_exprs", return_value='"focus"%c "word"%c'):
        ng.query_keyword_windows(corpus, query_or_opts=query_options, context_size=3, p_show="word")

    corpus.query.assert_called_once_with(cqp_query='"focus"%c "word"%c', context=1)


def test_query_keyword_windows_compiles_options_and_uses_tuple_context():
    corpus: MagicMock = corpus_mock("lemma\tspeech_id\nalpha beta\tB\nalpha beta\tA\n")
    query_options = {"target": "alpha"}

    with patch("api_swedeb.core.n_grams.compute.to_cqp_exprs", return_value='[lemma="alpha"]') as to_cqp_exprs:
        result: pd.DataFrame = ng.query_keyword_windows(
            corpus,
            query_or_opts=query_options,
            context_size=(1, 2),
            p_show="lemma",
        )

    to_cqp_exprs.assert_called_once_with(query_options, within="speech")
    corpus.query.assert_called_once_with(cqp_query='[lemma="alpha"]', context_left=1, context_right=2)
    subcorpus = corpus.query.return_value
    subcorpus.concordance.assert_called_once_with(
        form="simple",
        p_show=["lemma"],
        s_show=['speech_id'],
        order="first",
        cut_off=None,
    )
    assert result.to_dict('records') == [{'window': 'alpha beta', 'count': 2, 'documents': 'A,B'}]


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


def test_compile_n_grams_filters_locked_windows_with_threshold():
    windows: pd.DataFrame = pd.read_csv(io.StringIO(SUPER_SIMPLE_CONCORDANCE_GROUPED), sep="\t")

    n_grams: pd.DataFrame = ng.compile_n_grams(windows, n=2, threshold=3, mode="locked")

    assert n_grams.reset_index().to_dict('list') == {
        'ngram': ['f e n', 'n e b'],
        'window_count': [4, 3],
        'documents': ['B,C', 'A,B'],
    }


@pytest.mark.parametrize(
    ("mode", "expected_context_size", "expected_compile_mode"),
    [
        ("sliding", 3, "sliding"),
        ("left-aligned", (0, 1), "locked"),
        ("right-aligned", (1, 0), "locked"),
    ],
)
def test_n_grams_translates_modes_to_context_and_compile_mode(mode, expected_context_size, expected_compile_mode):
    corpus: MagicMock = MagicMock(spec=Corpus)
    windows = pd.DataFrame(
        {
            'window': ['alpha beta gamma'],
            'count': [2],
            'documents': ['A'],
        }
    )
    expected = pd.DataFrame({'window_count': [2], 'documents': ['A']}, index=pd.Index(['alpha beta'], name='ngram'))

    with (
        patch("api_swedeb.core.n_grams.compute.query_keyword_windows", return_value=windows) as query_windows,
        patch("api_swedeb.core.n_grams.compute.compile_n_grams", return_value=expected) as compile_n_grams,
    ):
        result = ng.n_grams(corpus, [{"target": "alpha"}, {"target": "beta"}], n=3, threshold=2, mode=mode)

    query_windows.assert_called_once_with(
        corpus,
        [{"target": "alpha"}, {"target": "beta"}],
        context_size=expected_context_size,
        p_show="word",
    )
    compile_n_grams.assert_called_once_with(windows, n=3, threshold=2, mode=expected_compile_mode)
    assert result is expected


def test_n_grams_width_three_sliding_returns_focus_in_all_positions():
    corpus: MagicMock = corpus_mock("word\tspeech_id\nleft2 left1 focus right1 right2\tA\n")

    result = ng.n_grams(corpus, "'focus'%c", n=3, mode="sliding")

    corpus.query.assert_called_once_with(cqp_query="'focus'%c", context=2)
    assert set(result.index) == {
        "left2 left1 focus",
        "left1 focus right1",
        "focus right1 right2",
    }


def test_n_grams_rejects_invalid_query_options():
    corpus: MagicMock = MagicMock(spec=Corpus)

    with pytest.raises(TypeError, match="query_or_opts must be a string, a dictionary or a list of dictionaries"):
        ng.n_grams(corpus, MagicMock())
