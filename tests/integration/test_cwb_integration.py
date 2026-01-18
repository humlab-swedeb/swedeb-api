"""Integration tests for api_swedeb.core.cwb with real CWB corpus."""

import ccc
import pandas as pd
import pytest

from api_swedeb.core.codecs import PersonCodecs
from api_swedeb.core.cwb import compiler
from api_swedeb.core.cwb.utility import CorpusAttribs


def test_cqp_execute_query(corpus: ccc.Corpus, person_codecs: PersonCodecs):
    """Test CQP query execution with real corpus data."""
    party_id = person_codecs.get_mapping('party_abbrev', 'party_id').get("M")
    query: str = compiler.to_cqp_exprs(
        {
            "prefix": "a",
            "target": "lemma",
            "value": "information",
            "criterias": [
                {"key": "a.speech_who", "values": ['i-AUocZy5YDqXmCwrRq6eGaW', 'i-5hWJKAnAs7X9iuugADpXr7']},
                {"key": "a.speech_party_id", "values": f"{party_id}"},
            ],
        }
    )
    subcorpus = corpus.query(query, context_left=2, context_right=2)

    assert isinstance(subcorpus, ccc.SubCorpus)

    data: pd.DataFrame = subcorpus.concordance(form="kwic", p_show=["word"], s_show=["speech_who", "speech_party_id"])

    assert data is not None
    assert len(data) > 0
    assert 'speech_who' in data.columns and 'speech_party_id' in data.columns
    assert (data.speech_party_id.astype(int) == party_id).all()


def test_corpus_attribs(corpus: ccc.Corpus):
    """Test CorpusAttribs wrapper with real corpus data."""
    attribs: CorpusAttribs = CorpusAttribs(corpus)

    assert attribs is not None


def test_cqp_query_that_returns_speech_id(corpus: ccc.Corpus):
    """Test CQP query that returns speech_id with real corpus data."""
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
        .concordance(**opts)  # type: ignore
        .reset_index(drop=True)
    )

    assert segments is not None
    assert 'speech_id' in segments.columns


@pytest.mark.parametrize(
    'query, answer',
    [
        ('"information"', {'ak', 'ek'}),
        ('a:[word="information"] :: (a.year_year="1975")', {'ek'}),
        ('a:[word="information"] :: (a.protocol_chamber="ek")', {'ek'}),
        ('a:[word="information"] :: (a.protocol_chamber="ak")', {'ak'}),
    ],
)
def test_cqp_query_with_chamber_filter(corpus: ccc.Corpus, query: str, answer: set[str]):
    """Test CQP queries with chamber filter using real corpus data."""
    opts = {
        "form": "kwic",
        "p_show": ["word"],
        "s_show": ["year_year", "speech_id", "protocol_chamber"],
        "order": "first",
        "cut_off": None,
    }
    segments: pd.DataFrame = (
        corpus.query(query, context_left=2, context_right=2).concordance(**opts).reset_index(drop=True)  # type: ignore
    )
    assert segments is not None
    assert 'protocol_chamber' in segments.columns
    assert set(segments.protocol_chamber.unique()) == answer
