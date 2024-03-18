import pandas as pd
import pytest
from ccc import Corpora, Corpus

from api_swedeb.core.cwb.compiler import to_cqp_exprs, _to_value_expr, _to_interval_expr
from api_swedeb.core.cwb.utility import CorpusAttribs

CWB_TEST_REGISTRY: str = "/usr/local/share/cwb/registry"
CWB_TEST_CORPUS_NAME: str = "RIKSPROT_V0100_TEST"

def test_to_value_expr():
    assert _to_value_expr(1) == '1'
    assert _to_value_expr("1") == '1'
    assert _to_value_expr([1,2,3,'a']) == '1|2|3|a'
    assert _to_value_expr([1,2,3,'a']) == '1|2|3|a'
    assert _to_value_expr((1990, 1999)) == '199[0-9]'
    assert _to_value_expr((1957, 1975)) == '195[7-9]|196[0-9]|197[0-5]'

def test_to_interval_expr():
    assert _to_interval_expr(1990, 1999) == '199[0-9]'
    assert _to_interval_expr(1990, 2000) == '199[0-9]|2000'
    assert _to_interval_expr(2000, 2000) == '2000'
    assert _to_interval_expr(1957, 1975) == '195[7-9]|196[0-9]|197[0-5]'

def test_cqp_compile_empty_query():
    query: str = to_cqp_exprs(None)
    assert query == ""

    with pytest.raises(ValueError):
        query: str = to_cqp_exprs({})


def test_cqp_compile_string_literal():
    query: str = to_cqp_exprs({"target": "apa"})
    assert query == '"apa"%c'


def test_cqp_compile_single_target_equal_value():
    query: str = to_cqp_exprs(
        {"target": "word", "value": "information", "ignore_case": False}
    )
    assert query == '[word="information"]'


def test_cqp_compile_single_target_ignore_case():
    query: str = to_cqp_exprs(
        {"target": "word", "value": "information", "ignore_case": True}
    )
    assert query == '[word="information"%c]'

    query: str = to_cqp_exprs({"target": "word", "value": "information"})
    assert query == '[word="information"%c]'


def test_cqp_compile_single_target_with_prefix():
    query: str = to_cqp_exprs({"prefix": "a", "target": "word", "value": "information"})
    assert query == 'a:[word="information"%c]'


def test_cqp_compile_single_target_multiple_values():
    query: str = to_cqp_exprs(
        {"target": "word", "value": ["information", "propaganda"]}
    )
    assert query == '[word="information|propaganda"%c]'


def test_cqp_compile_single_target_with_single_criteria():
    query: str = to_cqp_exprs(
        {
            "prefix": "a",
            "target": "word",
            "value": "propaganda",
            "criterias": {"key": "a.pos", "values": ["NN", "PM"]},
        }
    )
    assert query == 'a:[word="propaganda"%c]::(a.pos="NN|PM"%c)'


def test_to_cqp_year_interval_expr():
    assert _to_interval_expr(1990, 1999) == '199[0-9]'
    assert _to_interval_expr(1992, 1997) == '199[2-7]'
    assert _to_interval_expr(1990, 2000) == '199[0-9]|2000'
    assert (
        _to_interval_expr(1992, 2003)
        == '199[2-9]|200[0-3]'
    )
    assert (
        _to_interval_expr(1992, 2013)
        == '199[2-9]|200[0-9]|201[0-3]'
    )


def test_cqp_compile_single_target_with_multiple_criterias():
    query: str = to_cqp_exprs(
        {
            "prefix": "a",
            "target": "word",
            "value": "propaganda",
            "criterias": [
                {"key": "a.speech_who", "values": ["Q1807154", "Q4973765"]},
                {"key": "a.speech_party_id", "values": ["7"]},
                {"key": "a.pos", "values": ["NN", "PM"]},
            ],
        }
    )
    assert (
        query
        == 'a:[word="propaganda"%c]::(a.speech_who="Q1807154|Q4973765"%c)&(a.speech_party_id="7"%c)&(a.pos="NN|PM"%c)'
    )


def test_cqp_compile_multiple_targets():
    opts = [
        {"target": "word", "value": "information", "ignore_case": False},
        {"target": "och", "value": None, "ignore_case": False},
        {"target": "word", "value": "propaganda", "ignore_case": False},
    ]
    query: str = to_cqp_exprs(opts)
    assert query == '[word="information"] "och" [word="propaganda"]'


def test_cqp_compile_multiple_targets_with_criteras():
    opts = [
        {
            "prefix": "a",
            "target": "word",
            "value": "information",
            "ignore_case": False,
            "criterias": [
                {"key": "a.speech_who", "values": ["Q1807154", "Q4973765"]},
            ],
        },
        {"target": "och", "value": None, "ignore_case": False},
        {"target": "word", "value": "propaganda", "ignore_case": False},
    ]
    query: str = to_cqp_exprs(opts)
    assert (
        query
        == 'a:[word="information"]::(a.speech_who="Q1807154|Q4973765") "och" [word="propaganda"]'
    )


def test_cqp_execute_query():
    corpora: Corpora = Corpora(registry_dir=CWB_TEST_REGISTRY)
    corpus: Corpus = corpora.corpus(corpus_name=CWB_TEST_CORPUS_NAME)

    query: str = to_cqp_exprs(
        {
            "prefix": "a",
            "target": "lemma",
            "value": "information",
            "criterias": [
                {"key": "a.speech_who", "values": ["Q1807154", "Q4973765"]},
                {"key": "a.speech_party_id", "values": "7"},
            ],
        }
    )
    subcorpus = corpus.query(query, context_left=2, context_right=2)
    data: pd.DataFrame = subcorpus.concordance(
        form="kwic",
        p_show=["word"],
        s_show=[
            "speech_who",
            "speech_party_id",
        ],
        order="first",
        cut_off=2000000,
        matches=None,
        slots=None,
        cwb_ids=False,
    )

    assert data is not None

def test_compute_n_grams():

    corpus: Corpus = Corpora(registry_dir=CWB_TEST_REGISTRY).corpus(
        corpus_name=CWB_TEST_CORPUS_NAME
    )

    attribs: CorpusAttribs = CorpusAttribs(corpus)

    assert attribs is not None
