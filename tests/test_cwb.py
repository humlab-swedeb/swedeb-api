import pandas as pd
import pytest
from ccc import Corpus

from api_swedeb.core.cwb import compiler
from api_swedeb.core.cwb.utility import CorpusAttribs


def test_to_value_expr():
    assert compiler._to_value_expr("") == ""
    assert compiler._to_value_expr([""]) == ""
    assert compiler._to_value_expr([None]) == ""
    assert compiler._to_value_expr(1) == "1"
    assert compiler._to_value_expr("1") == "1"
    assert compiler._to_value_expr([1, 2, 3, "a"]) == "1|2|3|a"
    assert compiler._to_value_expr([1, 2, 3, "a"]) == "1|2|3|a"
    assert compiler._to_value_expr((1990, 1999)) == "199[0-9]"
    assert compiler._to_value_expr((1957, 1975)) == "195[7-9]|196[0-9]|197[0-5]"


def test_to_interval_expr():
    assert compiler._to_interval_expr(1990, 1999) == "199[0-9]"
    assert compiler._to_interval_expr(1990, 2000) == "199[0-9]|2000"
    assert compiler._to_interval_expr(2000, 2000) == "2000"
    assert compiler._to_interval_expr(1957, 1975) == "195[7-9]|196[0-9]|197[0-5]"
    assert compiler._to_interval_expr(1990, 1999) == "199[0-9]"
    assert compiler._to_interval_expr(1992, 1997) == "199[2-7]"


def test_to_cqp_pattern_with_faulty_opts():
    with pytest.raises(ValueError):
        assert compiler.to_cqp_pattern({"value": "bepa"}) == ""
    with pytest.raises(ValueError):
        assert compiler.to_cqp_pattern({}) == ""


@pytest.mark.parametrize(
    "opts, expected",
    [
        ({"target": "word", "value": "bepa"}, '[word="bepa"%c]'),
        ({"target": "apa"}, '"apa"%c'),
        ({"target": "word", "value": "information"}, '[word="information"%c]'),
        ({"target": "word", "value": "information", "ignore_case": True}, '[word="information"%c]'),
        ({"target": "word", "value": "information", "ignore_case": False}, '[word="information"]'),
        ({"target": "word", "value": ["information", "propaganda"]}, '[word="information|propaganda"%c]'),
        (
            {"prefix": "a", "target": "word", "value": ["information", "propaganda"]},
            'a:[word="information|propaganda"%c]',
        ),
        ("apa", '"apa"%c'),
        ({"target": "word", "value": "apa%c"}, '[word="apa"%c]'),
        ({"prefix": "a", "target": "word", "value": "bepa"}, 'a:[word="bepa"%c]'),
    ],
)
def test_to_cqp_pattern_with_correct_opts(opts, expected):
    assert compiler.to_cqp_pattern(opts) == expected


@pytest.mark.parametrize(
    "opts, expected",
    [
        (None, ''),
        ("apa", '"apa"%c'),
        ({"target": "apa"}, '"apa"%c'),
        ([{"target": "apa"}], '"apa"%c'),
        (
            [
                {"target": "word", "value": "information", "ignore_case": False},
            ],
            '[word="information"]',
        ),
        (
            [
                {"target": "word", "value": "information", "ignore_case": False},
                {"target": "och", "value": None, "ignore_case": False},
                {"target": "word", "value": "propaganda", "ignore_case": True},
            ],
            '[word="information"] "och" [word="propaganda"%c]',
        ),
        (
            [
                None,
            ],
            '',
        ),
        (
            [
                None,
                None,
            ],
            '',
        ),
    ],
)
def test_to_cqp_patterns_with_correct_opts(opts, expected):
    assert compiler.to_cqp_patterns(opts) == expected


@pytest.mark.parametrize(
    "criterias,expected",
    [
        (
            [
                {"key": "a.pos", "values": ["NN", "PM"], "ignore_case": False},
            ],
            '(a.pos="NN|PM")',
        ),
        (
            [
                {"key": "a.pos", "values": ["NN", "PM"], "ignore_case": True},
            ],
            '(a.pos="NN|PM"%c)',
        ),
        (
            [
                {"key": "a.speech_who", "values": ["Q1807154", "Q4973765"], "ignore_case": True},
            ],
            '(a.speech_who="Q1807154|Q4973765"%c)',
        ),
    ],
)
def test_to_cqp_criteria_expr(criterias, expected):
    assert compiler.to_cqp_criteria_expr(criterias) == expected


@pytest.mark.parametrize(
    "opts,expected",
    [
        (None, ""),
        ({}, ""),
        ({"target": "apa"}, '"apa"%c'),
        ({"target": "word", "value": "information", "ignore_case": False}, '[word="information"]'),
        ({"target": "word", "value": "information", "ignore_case": True}, '[word="information"%c]'),
        ({"target": "word", "value": "information"}, '[word="information"%c]'),
        ({"prefix": "a", "target": "word", "value": "information"}, 'a:[word="information"%c]'),
        ({"target": "word", "value": ["information", "propaganda"]}, '[word="information|propaganda"%c]'),
        (
            {
                "prefix": "a",
                "target": "word",
                "value": "propaganda",
                "criterias": {"key": "a.pos", "values": ["NN", "PM"], "ignore_case": True},
            },
            'a:[word="propaganda"%c] :: (a.pos="NN|PM"%c)',
        ),
        (
            {
                "prefix": "a",
                "target": "word",
                "value": "propaganda",
                "criterias": [
                    {"key": "a.speech_who", "values": ["Q1807154", "Q4973765"], "ignore_case": True},
                    {"key": "a.speech_party_id", "values": ["7"], "ignore_case": True},
                    {"key": "a.pos", "values": ["NN", "PM"], "ignore_case": True},
                ],
            },
            'a:[word="propaganda"%c] :: (a.speech_who="Q1807154|Q4973765"%c)&(a.speech_party_id="7"%c)&(a.pos="NN|PM"%c)',
        ),
        (
            [
                {"target": "word", "value": "information", "ignore_case": False},
                {"target": "och", "value": None, "ignore_case": False},
                {"target": "word", "value": "propaganda", "ignore_case": False},
            ],
            '[word="information"] "och" [word="propaganda"]',
        ),
        (
            [
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
            ],
            'a:[word="information"] "och" [word="propaganda"] :: (a.speech_who="Q1807154|Q4973765")',
        ),
    ],
)
def test_to_cqp_exprs(opts, expected):
    assert compiler.to_cqp_exprs(opts) == expected


def test_cqp_execute_query(corpus: Corpus):
    query: str = compiler.to_cqp_exprs(
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


def test_corpus_attribs(corpus: Corpus):
    attribs: CorpusAttribs = CorpusAttribs(corpus)

    assert attribs is not None
