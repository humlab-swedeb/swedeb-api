from __future__ import annotations

from typing import Any, Literal

import pandas as pd
from ccc import Corpus, SubCorpus

from api_swedeb.core.codecs import PersonCodecs
from api_swedeb.core.cwb import to_cqp_exprs
from api_swedeb.core.speech_index import get_speeches_by_speech_ids

S_ATTR_RENAMES: dict[str, str] = {
    'year_year': 'year',
    'id': 'speech_id',
    'speech_who': 'person_id',
    'speech_party_id': 'party_id',
    'speech_gender_id': 'gender_id',
    'speech_date': 'date',
    'speech_title': 'document_name',
    'speech_office_type_id': 'office_type_id',
    'speech_sub_office_type_id': 'sub_office_type_id',
    "left_lemma": "left_word",
    "node_lemma": "node_word",
    "right_lemma": "right_word",
}


def empty_kwic(p_show: str) -> pd.DataFrame:
    return pd.DataFrame(
        index=pd.Index([], name="speech_id"), columns=[f"left_{p_show}", f"node_{p_show}", f"right_{p_show}"]
    )


def kwic(  # pylint: disable=too-many-arguments
    corpus: Corpus,
    opts: dict[str, Any],
    *,
    words_before: int,
    words_after: int,
    p_show: Literal["word", "lemma"] = "word",
    cut_off: int = None,
) -> pd.DataFrame:
    """Computes n-grams from a corpus segments that contains a keyword specified in opts.

    Args:
        corpus (Corpus): a `cwb-ccc` corpus object
        opts (dict[str, Any]): CQO query options (see utils/cwp.py to_cqp_exprs() for details
        words_before (int, optional): Number of words left of keyword.
        words_after (int, optional): Number of words right of keyword.
        p_show (Literal['word', 'lemma'], optional): Target type to display. Defaults to "word".
        cut_off (int, optional): Threshold of number of hits. Defaults to a big numbere.
    Returns:
        pd.DataFrame: dataframe with index speech_id and columns left_word, node_word, right_word.
    """
    query: str = to_cqp_exprs(opts, within="speech")

    subcorpus: SubCorpus | str = corpus.query(query, context_left=words_before, context_right=words_after)

    segments: pd.DataFrame = subcorpus.concordance(
        form="kwic",
        p_show=[p_show],
        s_show=['speech_id'],
        order="first",
        cut_off=cut_off,
    )

    if len(segments) == 0:
        return empty_kwic(p_show)

    segments = segments.set_index("speech_id", drop=True)

    return segments


def kwic_with_decode(
    corpus: Any,
    opts: dict[str, Any],
    *,
    speech_index: pd.DataFrame,
    codecs: PersonCodecs,
    words_before: int = 3,
    words_after: int = 3,
    p_show: str = "word",
    cut_off: int = 200000,
) -> pd.DataFrame:
    """_summary_

    Args:
        corpus (ccc.Corpus): A CWB corpus object.
        opts (dict): Query parameters.
        words_before (int, optional): Number of words before search term(s). Defaults to 3.
        words_after (int, optional): Number of words after search term(s). Defaults to 3.
        p_show (str, optional): What to display, `word` or `lemma`. Defaults to "word".
        cut_off (int, optional): Cut off. Defaults to 200000.
    Returns:
        KeywordInContextResult: _description_
    """

    kwic_data: pd.DataFrame = kwic(
        corpus, opts, words_before=words_before, words_after=words_after, p_show=p_show, cut_off=cut_off
    )

    speech_index: pd.DataFrame = get_speeches_by_speech_ids(
        speech_index, speech_ids=kwic_data, left_on="speech_id", right_index=True
    )
    speech_index = codecs.decode_speech_index(speech_index, sort_values=False)

    return speech_index
