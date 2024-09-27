from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Literal

import pandas as pd
from ccc import Corpus, SubCorpus

from api_swedeb.core.cwb import to_cqp_exprs

if TYPE_CHECKING:
    from api_swedeb.api.parlaclarin.codecs import Codecs


def kwik( # pylint: disable=too-many-arguments
    corpus: Corpus,
    opts: dict[str, Any],
    *,
    words_before: int,
    words_after: int,
    p_show: Literal["word", "lemma"] = "word",
    s_show: list[str] = None,
    decoder: Codecs = None,
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
    if s_show and strip_s_tags:
        segments = segments.rename(columns={name: name.split("_", maxsplit=1)[1] for name in s_show})
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
