from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Literal

import pandas as pd
from ccc import Corpus, SubCorpus

from api_swedeb.core.cwb import to_cqp_exprs

if TYPE_CHECKING:
    from api_swedeb.core.codecs import PersonCodecs

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


def kwic(  # pylint: disable=too-many-arguments
    corpus: Corpus,
    opts: dict[str, Any],
    *,
    words_before: int,
    words_after: int,
    p_show: Literal["word", "lemma"] = "word",
    s_show: list[str] = None,
    decoder: PersonCodecs = None,
    speech_index: pd.DataFrame = None,
    strip_s_tags: bool = True,
    cut_off: int = None,
    rename_columns: dict[str, str] = None,
    compute_columns: dict[str, Callable[[pd.DataFrame], pd.Series]] = None,
    display_columns: list[str] = None,
    dtype: dict[str, Any] = None,
) -> pd.DataFrame:
    """Computes n-grams from a corpus segments that contains a keyword specified in opts.

    Args:
        corpus (Corpus): a `cwb-ccc` corpus object
        opts (dict[str, Any]): CQO query options (see utils/cwp.py to_cqp_exprs() for details
        words_before (int, optional): Number of words left of keyword.
        words_after (int, optional): Number of words right of keyword.
        p_show (Literal['word', 'lemma'], optional): Target type to display. Defaults to "word".
        s_show (list[str], optional): Structural attributes to show. Defaults to "None".
        decoder (Codecs, optional): Decoder to use. Defaults to None.
        dtype (dict[str, Any], optional): Data columns to cast. Defaults to None.
        strip_s_tags (bool, optional): Strip structural tags from column name. Defaults to True.
        cut_off (int, optional): Threshold of number of hits. Defaults to a big numbere.
        rename_columns (dict[str, str], optional): Columns to rename. Defaults to None.
        compute_columns (dict[str, Callable], optional): Columns to compute. Defaults to None.
        display_columns (list[str], optional): Columns to keep. Defaults to None.
    Returns:
        pd.DataFrame: dataframe in "kwic" format with provided structural attributes.
    """
    query: str = to_cqp_exprs(opts, within="speech")

    subcorpus: SubCorpus | str = corpus.query(query, context_left=words_before, context_right=words_after)

    segments: pd.DataFrame = subcorpus.concordance(
        form="kwic",
        p_show=[p_show],
        s_show=s_show or [],
        order="first",
        cut_off=cut_off,
    ).reset_index(drop=True)

    if segments.empty:
        return segments

    if strip_s_tags:
        segments = segments.rename(columns=S_ATTR_RENAMES | (rename_columns or {}))

    if speech_index is not None:
        """Return join of speech_index and segments"""

        segments = segments.set_index("speech_id")[['left_word', 'node_word', 'right_word']]
        segments = segments.merge(speech_index, left_index=True, right_on='speech_id', how="inner")

        decoder.decode_speech_index(segments, drop=False)

    else:
        if s_show and strip_s_tags:
            segments = segments.rename(columns=S_ATTR_RENAMES)
            display_columns = [name.split("_", maxsplit=1)[1] if name in s_show else name for name in display_columns]

        if rename_columns:
            segments = segments.rename(columns=rename_columns)

        if dtype:
            segments = segments.astype(dtype)

        if decoder:
            segments = decoder.decode(segments, drop=False)
        else:
            display_columns = [name for name in display_columns if name not in segments.columns]

        for name, fx in compute_columns or {}:
            segments[name] = fx(segments)

        if display_columns:
            segments = segments[display_columns]

    return segments
