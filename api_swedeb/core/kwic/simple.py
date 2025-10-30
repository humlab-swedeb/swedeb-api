from __future__ import annotations

from typing import Any, Literal

import ccc
import pandas as pd

from api_swedeb.core.codecs import PersonCodecs
from api_swedeb.core.cwb import CorpusCreateOpts
from api_swedeb.core.kwic.singleprocess import execute_kwic_singleprocess
from api_swedeb.core.speech_index import get_speeches_by_speech_ids

from .multiprocess import execute_kwic_multiprocess

S_ATTR_RENAMES: dict[str, str] = {
    'year_year': 'year',
    'id': 'speech_id',
    'protocol_chamber': 'chamber_abbrev',
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


KWIC_REGISTRY: dict[str, Any] = {
    "singleprocess": execute_kwic_singleprocess,
    "multiprocess": execute_kwic_multiprocess,
}


def kwic(  # pylint: disable=too-many-arguments
    corpus: ccc.Corpus | CorpusCreateOpts,
    opts: dict[str, Any] | list[dict[str, Any]],
    *,
    words_before: int,
    words_after: int,
    p_show: Literal["word", "lemma"] = "word",
    cut_off: int | None = None,
    use_multiprocessing: bool = False,
    num_processes: int | None = None,
) -> pd.DataFrame:
    """Computes n-grams from a corpus segments that contains a keyword specified in opts.

    Args:
        corpus (Corpus): a `cwb-ccc` corpus object
        opts (dict[str, Any]): CQP query options (see utils/cwp.py to_cqp_exprs() for details
        words_before (int, optional): Number of words left of keyword.
        words_after (int, optional): Number of words right of keyword.
        p_show (Literal['word', 'lemma'], optional): Target type to display. Defaults to "word".
        cut_off (int, optional): Threshold of number of hits. Defaults to None (unlimited).
        use_multiprocessing (bool, optional): Whether to use multiprocessing. Defaults to False.
        num_processes (int, optional): Number of processes to use. Defaults to CPU count.
    Returns:
        pd.DataFrame: dataframe with index speech_id and columns left_word, node_word, right_word.
    """
    kwic_key: str = "multiprocess" if use_multiprocessing else "singleprocess"
    return KWIC_REGISTRY[kwic_key](
        corpus=corpus,
        opts=opts,
        words_before=words_before,
        words_after=words_after,
        p_show=p_show,
        cut_off=cut_off,
        num_processes=num_processes,
    )


def kwic_with_decode(  # pylint: disable=too-many-arguments
    corpus: ccc.Corpus | CorpusCreateOpts,
    opts: dict[str, Any],
    *,
    speech_index: pd.DataFrame,
    codecs: PersonCodecs,
    words_before: int = 3,
    words_after: int = 3,
    p_show: str = "word",
    cut_off: int | None = 200000,
    use_multiprocessing: bool = False,
    num_processes: int | None = None,
) -> pd.DataFrame:
    """Compute KWIC with decoded speech metadata.

    Args:
        corpus (ccc.Corpus): A CWB corpus object.
        opts (dict): Query parameters.
        speech_index (pd.DataFrame): Speech index dataframe.
        codecs (PersonCodecs): Codecs for decoding.
        words_before (int, optional): Number of words before search term(s). Defaults to 3.
        words_after (int, optional): Number of words after search term(s). Defaults to 3.
        p_show (str, optional): What to display, `word` or `lemma`. Defaults to "word".
        cut_off (int, optional): Cut off limit. Defaults to 200000.
        use_multiprocessing (bool, optional): Whether to use multiprocessing. Defaults to False.
        num_processes (int, optional): Number of processes to use. Defaults to CPU count.
    Returns:
        pd.DataFrame: KWIC results with decoded metadata.
    """

    kwic_data: pd.DataFrame = kwic(
        corpus,
        opts,
        words_before=words_before,
        words_after=words_after,
        p_show=p_show,  # type: ignore
        cut_off=cut_off,
        use_multiprocessing=use_multiprocessing,
        num_processes=num_processes,
    )

    speeches: pd.DataFrame = get_speeches_by_speech_ids(
        speech_index, speech_ids=kwic_data, left_on="speech_id", right_index=True
    )
    speeches = codecs.decode_speech_index(speeches, sort_values=False)

    return speeches
