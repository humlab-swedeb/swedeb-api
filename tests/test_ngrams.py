import io
import uuid
from collections import Counter, defaultdict
from typing import Iterable
from unittest.mock import MagicMock, patch

import pandas as pd
from ccc import Corpora, Corpus, SubCorpus

from api_swedeb.api.utils import common_params as cp
from api_swedeb.api.utils import ngrams as ngram_service
from api_swedeb.core.configuration import ConfigValue
from api_swedeb.core.n_grams.compute import compute_n_grams, query_keyword_windows, to_n_grams
from api_swedeb.schemas.ngrams_schema import NGramResult

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


# SAMPLE_CONCORDANCE_PHRASES = """window\tcount\tdocuments
# alltför högljudda propagandan mot England\t1\t['i-19bbfe5b4652a214-2']
# att denna propaganda skulle få\t1\t['i-d9090ad17b861735-10']
# för en propaganda och som\t3\t['i-8f7d43d10fec79c5-5', 'i-20935836147b9bcb-0', 'i-93cd7ea6d9946b3f-64']
# gjorde god propaganda samt hade\t1\t['i-41e168abca4a1b3e-0']
# till den propaganda som drevs\t1\t['i-32d5069321c33bfa-3']
# och den propaganda som bedrevs\t2\t['i-82cca5660ca828a2-4', 'i-d793a784ee2b2106-50']
# är den propaganda som från\t1\t['i-d7d8d05f717925a4-0']
# den allmänna propagandan i fråga\t1\t['i-4d39ff1df7c927ac-0']
# att driva propaganda för den\t2\t['i-483ddbb423aac2cb-0', 'i-7953c3e3450f6838-0']
# den ovederhäftiga propaganda som knutits\t1\t['i-b7e9c54aef61b352-8']
# åtminstone i propagandan övertyga om\t1\t['i-85f2e168f5a8d308-13']
# """


def corpus_mock(return_data: str) -> MagicMock:
    simpleConcordance: pd.DataFrame = pd.read_csv(io.StringIO(return_data), sep="\t")
    subCorpusMock: MagicMock = MagicMock(spec=SubCorpus, concordance=MagicMock(return_value=simpleConcordance))
    corpusMock: MagicMock = MagicMock(spec=Corpus, query=MagicMock(return_value=subCorpusMock))
    return corpusMock


def test_to_n_grams():
    phrase: str = "f e b"
    assert list(to_n_grams(phrase, 3)) == ["f e b"]
    assert list(to_n_grams(phrase, 2)) == ["f e", "e b"]

    phrase: str = "a b c d e"

    assert list(to_n_grams(phrase, 2)) == ["a b", "b c", "c d", "d e"]
    assert list(to_n_grams(phrase, 3)) == ["a b c", "b c d", "c d e"]


@patch("api_swedeb.core.cwb.to_cqp_exprs", lambda *_, **__: 'apa')
def test_query_keyword_windows():
    corpus: MagicMock = corpus_mock(SUPER_SIMPLE_CONCORDANCE)

    result: pd.DataFrame = query_keyword_windows(corpus, query_or_opts="noop", n=1, p_show="word")

    expected_result: pd.DataFrame = pd.read_csv(io.StringIO(SUPER_SIMPLE_CONCORDANCE_GROUPED), sep="\t")

    assert result is not None

    expected_result = expected_result.sort_values(by='window').reset_index(drop=True)
    result = result.sort_values(by='window').reset_index(drop=True)

    assert result.equals(expected_result)


def test_compute_n_grams():
    windows: pd.DataFrame = pd.read_csv(io.StringIO(SUPER_SIMPLE_CONCORDANCE_GROUPED), sep="\t")
    n_grams: pd.DataFrame = compute_n_grams(windows, n=2, threshold=None)

    assert n_grams is not None

    assert n_grams.reset_index().to_dict('list') == {
        'ngram': ['e b', 'e e', 'e n', 'f e', 'n e'],
        'window_count': [5, 4, 4, 6, 3],
        'documents': ['A,B', 'D', 'B,C', 'A,B,C', 'A,B'],
    }


def test_compute_n_grams2():
    n: int = 2
    keyword: str = '"sverige"%c'

    corpus: Corpus = Corpora(registry_dir=ConfigValue("cwb.registry_dir").resolve()).corpus(
        corpus_name=ConfigValue("cwb.corpus_name").resolve(), data_dir=f"/tmp/ccc-{str(uuid.uuid4())[:6]}"
    )

    windows: pd.DataFrame = query_keyword_windows(corpus, query_or_opts=keyword, n=n, p_show="word")

    ngram_counter: Counter = defaultdict(int)
    ngram_documents: Counter = defaultdict(set)

    cx: dict[int, int] = windows['count'].to_dict().get

    n_grams: Iterable[tuple[int, str, str]] = (
        (index, ngram, row['documents']) for index, row in windows.iterrows() for ngram in to_n_grams(row['window'], n)
    )

    for index, ngram, documents in n_grams:
        ngram_counter[ngram] += cx(index)
        ngram_documents['documents'] |= set(documents.split(','))

    assert ngram_counter is not None


def test_n_gram_service(corpus: Corpus):
    common_opts: cp.CommonQueryParams = cp.CommonQueryParams(
        from_year=1970, to_year=1975, who=None, party_id=None, office_types=None, sub_office_types=None, gender_id=None
    )
    result: NGramResult = ngram_service.get_ngrams(
        corpus=corpus,
        search_term=['sverige', 'vara'],
        commons=common_opts,
        search_target="lemma",
        display_target="word",
        n_gram_width=5,
    )
    assert result is not None
    assert len(result.ngram_list) > 0


def test_cqp_query_that_returns_speech_id():
    corpus: Corpus = Corpora(registry_dir=ConfigValue("cwb.registry_dir").resolve()).corpus(
        corpus_name=ConfigValue("cwb.corpus_name").resolve(), data_dir=f"/tmp/ccc-{str(uuid.uuid4())[:6]}"
    )
    opts = {
        "form": "kwic",
        "p_show": ["word"],
        "s_show": ["year_year", "speech_id"],
        "order": "first",
        "cut_off": None,
    }
    segments: pd.DataFrame = (
        corpus.query(
            'a:[word="information"] :: (a.year_year="1975")',
            context_left=2,
            context_right=2,
        )
        .concordance(**opts)
        .reset_index(drop=True)
    )

    assert segments is not None
    assert 'speech_id' in segments.columns
