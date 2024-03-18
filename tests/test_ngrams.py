from ccc import Corpora, Corpus
import pandas as pd
from api_swedeb.api.utils import ngrams as ngram_service
from api_swedeb.api.utils import common_params as cp

from api_swedeb.core.n_grams import compute_n_grams, to_n_grams

version = "v1"

CWB_TEST_REGISTRY: str = "/usr/local/share/cwb/registry"
CWB_TEST_CORPUS_NAME: str = "RIKSPROT_V0100_TEST"


# ==Context Descriptor=======================================
# Positional Attributes:  * word lemma pos xpos
# Structural Attributes:
#   year:     year_year/title
#   protocol: protocol_title/date
#   speech:   speech_id/title/who/date/party_id/gender_id/office_type_id/sub_office_type_id/name/page_number


def test_to_n_grams():
    words = ["a", "b", "c", "d", "e"]
    n = 2
    n_grams = to_n_grams(words, n)
    assert n_grams == [["a", "b"], ["b", "c"], ["c", "d"], ["d", "e"]]
    n = 3
    n_grams = to_n_grams(words, n)
    assert n_grams == [["a", "b", "c"], ["b", "c", "d"], ["c", "d", "e"]]


def test_compute_n_grams():
    corpus: Corpus = Corpora(registry_dir=CWB_TEST_REGISTRY).corpus(corpus_name=CWB_TEST_CORPUS_NAME)
    # attribs: CorpusAttribs = CorpusAttribs(corpus)

    opts: dict = {
        "prefix": "a",
        "target": "lemma",
        "value": "information",
        "criterias": [
            {"key": "a.speech_who", "values": ["Q1807154", "Q4973765"]},
            {"key": "a.speech_party_id", "values": "7"},
        ],
    }
    n: int = 4

    data: pd.DataFrame = compute_n_grams(corpus, opts, n=n, p_show="word", mode="dataframe")
    assert data is not None


def test_n_gram_service():
    corpus: Corpus = Corpora(registry_dir=CWB_TEST_REGISTRY).corpus(corpus_name=CWB_TEST_CORPUS_NAME)
    result = ngram_service.get_ngrams(
        corpus=corpus,
        search_term="propaganda",
        commons=cp.CommonQueryParams(
            from_year=1952,
            to_year=1968,
            who=None,
            party_id=None,
            office_types=None,
            sub_office_types=None,
            gender_id=None,
        ),
        search_target="lemma",
        display_target="word",
        n_gram_width=3,
    )
    assert result is not None
    assert result.ngram_list > 0


def test_bench():
    corpus: Corpus = Corpora(registry_dir=CWB_TEST_REGISTRY).corpus(corpus_name=CWB_TEST_CORPUS_NAME)
    opts = {
        "form": "kwic",
        "p_show": ["word"],
        "s_show": ["year_year"],
        "order": "first",
        "cut_off": None,
    }
    segments: pd.DataFrame = (
        corpus.query(
            'a:[word="information"]::(a.year_year="1939")',
            context_left=2,
            context_right=2,
        )
        .concordance(**opts)
        .reset_index(drop=True)
    )

    assert segments is not None
