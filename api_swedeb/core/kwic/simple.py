from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal

import ccc
import pandas as pd
from fastapi.logger import logger

from api_swedeb.core.cwb import CorpusCreateOpts
from api_swedeb.core.kwic.singleprocess import execute_kwic_singleprocess
from api_swedeb.core.kwic.utility import normalize_kwic_df

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
    num_shards: int | None = None,
    on_shards_total: Callable[[int], None] | None = None,
    on_shard_complete: Callable[[int, pd.DataFrame], None] | None = None,
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
        num_processes (int, optional): Number of parallel workers (pool size). Defaults to CPU count.
        num_shards (int, optional): Year-range partitions. Defaults to num_processes when None.
        on_shards_total: Optional callback fired once with the total shard count.
        on_shard_complete: Optional callback fired per shard with (shard_index, normalized_df).
    Returns:
        pd.DataFrame: dataframe with index speech_id and columns left_word, node_word, right_word.
    """
    kwic_key: str = "multiprocess" if use_multiprocessing else "singleprocess"
    logger.info(f"Using KWIC {kwic_key}ing method.")

    # Wrap the shard callback to apply normalize_kwic_df before forwarding
    wrapped_shard_callback: Callable[[int, pd.DataFrame], None] | None = None
    if on_shard_complete is not None and use_multiprocessing:
        _p_show = p_show

        def _normalize_and_forward(shard_index: int, raw_df: pd.DataFrame) -> None:
            normalized = normalize_kwic_df(raw_df, lexical_form=_p_show)
            on_shard_complete(shard_index, normalized)

        wrapped_shard_callback = _normalize_and_forward

    if use_multiprocessing:
        kwic_data = execute_kwic_multiprocess(
            corpus=corpus,
            opts=opts,
            words_before=words_before,
            words_after=words_after,
            p_show=p_show,
            cut_off=cut_off,
            num_processes=num_processes,
            num_shards=num_shards,
            on_shards_total=on_shards_total,
            on_shard_complete=wrapped_shard_callback,
        )
    else:
        kwic_data = execute_kwic_singleprocess(
            corpus=corpus,
            opts=opts,
            words_before=words_before,
            words_after=words_after,
            p_show=p_show,
            cut_off=cut_off,
        )

    # FIXME: Temporary fix to ensure consistent column naming, but why not use S_ATTR_RENAMES?
    kwic_data = normalize_kwic_df(kwic_data, lexical_form=p_show)
    return kwic_data


def kwic_with_decode(  # pylint: disable=too-many-arguments
    corpus: ccc.Corpus | CorpusCreateOpts,
    opts: dict[str, Any] | list[dict[str, Any]],
    *,
    prebuilt_speech_index: pd.DataFrame,
    words_before: int = 3,
    words_after: int = 3,
    p_show: str = "word",
    cut_off: int | None = 200000,
    use_multiprocessing: bool = False,
    num_processes: int | None = None,
    num_shards: int | None = None,
    on_shards_total: Callable[[int], None] | None = None,
    on_shard_complete: Callable[[int, pd.DataFrame], None] | None = None,
) -> pd.DataFrame:
    """Compute KWIC with decoded speech metadata from the prebuilt speech_index.

    The prebuilt speech_index.feather already contains fully decoded speaker
    metadata (name, gender, party, office, wiki_id) materialised at build time.
    This function joins on speech_id — no codec lookups at query time.

    Args:
        corpus: A CWB corpus object or CorpusCreateOpts.
        opts: Query parameters.
        prebuilt_speech_index: DataFrame loaded from speech_index.feather,
            indexed by speech_id.
        words_before: Number of words before search term(s). Defaults to 3.
        words_after: Number of words after search term(s). Defaults to 3.
        p_show: What to display, ``word`` or ``lemma``. Defaults to "word".
        cut_off: Maximum hits to return. Defaults to 200000.
        use_multiprocessing: Whether to use multiprocessing. Defaults to False.
        num_processes: Number of parallel workers (pool size). Defaults to CPU count.
        num_shards: Year-range partitions. Defaults to num_processes when None.
        on_shards_total: Optional callback fired once with the total shard count.
        on_shard_complete: Optional callback fired per completed shard with
            (shard_index, decoded_df) where decoded_df has had the speech index
            joined and ``speech_id`` column added.
    Returns:
        pd.DataFrame: KWIC results with decoded metadata.
    """
    # Wrap the shard callback to apply the speech-index join before forwarding
    wrapped_shard_callback: Callable[[int, pd.DataFrame], None] | None = None
    if on_shard_complete is not None and use_multiprocessing:
        _prebuilt = prebuilt_speech_index

        def _join_and_forward(shard_index: int, normalized_df: pd.DataFrame) -> None:
            if normalized_df.empty:
                on_shard_complete(shard_index, normalized_df)
                return
            joined = normalized_df.join(_prebuilt, how="left")
            joined.index.name = "speech_id"
            joined["speech_id"] = joined.index
            on_shard_complete(shard_index, joined)

        wrapped_shard_callback = _join_and_forward

    kwic_data: pd.DataFrame = kwic(
        corpus,
        opts,
        words_before=words_before,
        words_after=words_after,
        p_show=p_show,  # type: ignore
        cut_off=cut_off,
        use_multiprocessing=use_multiprocessing,
        num_processes=num_processes,
        num_shards=num_shards,
        on_shards_total=on_shards_total,
        on_shard_complete=wrapped_shard_callback,
    )
    if kwic_data.empty:
        return kwic_data

    result: pd.DataFrame = kwic_data.join(prebuilt_speech_index, how="left")
    result.index.name = "speech_id"
    result["speech_id"] = result.index

    return result
