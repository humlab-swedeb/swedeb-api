"""N-gram multiprocessing worker and orchestrator.

Pattern mirrors ``api_swedeb/core/kwic/multiprocess.py``, with one key
difference: because n-gram shards for the same *ngram* string must be
*merged* (window_count summed, documents unioned) rather than simply
concatenated, this module does *not* return independent shard files.
Instead each worker returns its per-shard aggregate and the orchestrator
(and the ``on_shard_complete`` callback) maintains a *running aggregate*
that the ticket service writes atomically as ``current_aggregate.feather``.
"""

from __future__ import annotations

import multiprocessing as mp
import os
import shutil
import tempfile
from collections.abc import Callable
from datetime import datetime
from typing import Any, Literal

import ccc
import pandas as pd

from api_swedeb.core.configuration.inject import ConfigValue
from api_swedeb.core.cwb.utility import CorpusCreateOpts
from api_swedeb.core.kwic.utility import create_year_chunks, extract_year_range, inject_year_filter

from .compute import n_grams as _compute_n_grams


# ---------------------------------------------------------------------------
# Internal helper: merge two shard DataFrames into a running aggregate
# ---------------------------------------------------------------------------

def _merge_ngrams_aggregate(current: pd.DataFrame, new_shard: pd.DataFrame) -> pd.DataFrame:
    """Merge *new_shard* into *current* by summing counts and unioning document IDs.

    Both DataFrames must have columns ``[ngram, window_count, documents]`` where
    ``documents`` is a comma-separated string of unique speech-ID tokens.
    """
    if current.empty:
        return new_shard.copy()
    if new_shard.empty:
        return current.copy()

    combined = pd.concat([current, new_shard], ignore_index=True)
    merged = (
        combined.groupby("ngram")
        .agg(
            window_count=("window_count", "sum"),
            documents=("documents", lambda x: ",".join(sorted(set(",".join(x).split(","))))),
        )
        .reset_index()
    )
    return merged


# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------

def ngrams_worker(args: tuple) -> tuple[int, pd.DataFrame]:
    """Worker function for multiprocessing n-gram queries.

    Designed to be called by ``multiprocessing.Pool.imap_unordered()``.  Each
    worker creates its own isolated temporary directory to avoid GDBM
    file-locking conflicts between concurrent processes.

    Args:
        args: Tuple of
            ``(shard_index, corpus_opts, opts, year_range, n, p_show, mode)``

    Returns:
        ``(shard_index, DataFrame)`` where the DataFrame has columns
        ``[ngram, window_count, documents]`` (``ngram`` as a plain column,
        not as the index).
    """
    shard_index, corpus_opts, opts, year_range, n, p_show, mode = args

    opts_with_year: list[dict[str, Any]] = inject_year_filter(opts, year_range)

    process_id = os.getpid()
    unique_data_dir = tempfile.mkdtemp(
        prefix=f"ccc-{ccc.__version__}-swedeb-ngrams-worker-{process_id}-",
        dir=tempfile.gettempdir(),
    )

    corpus_opts_isolated = CorpusCreateOpts(
        registry_dir=corpus_opts.registry_dir,
        corpus_name=corpus_opts.corpus_name,
        data_dir=unique_data_dir,
    )

    corpus: ccc.Corpus = corpus_opts_isolated.create_corpus()

    try:
        result: pd.DataFrame = _compute_n_grams(
            corpus,
            opts_with_year,
            n=n,
            p_show=p_show,
            threshold=None,
            mode=mode,
        )
        # compile_n_grams returns ngram as the index; reset so callers always
        # receive a flat DataFrame with ngram as a plain column.
        return shard_index, result.reset_index()
    finally:
        try:
            shutil.rmtree(unique_data_dir, ignore_errors=True)
        except Exception:  # pylint: disable=broad-except
            pass


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def execute_ngrams_multiprocess(
    corpus: ccc.Corpus | CorpusCreateOpts,
    opts: dict[str, Any] | list[dict[str, Any]],
    *,
    n: int,
    p_show: Literal["word", "lemma"],
    mode: Literal["sliding", "left-aligned", "right-aligned"],
    num_processes: int | None,
    num_shards: int | None = None,
    on_shards_total: Callable[[int], None] | None = None,
    on_shard_complete: Callable[[int, pd.DataFrame], None] | None = None,
) -> pd.DataFrame:
    """Execute an n-gram query using multiprocessing with year-based partitioning.

    Each shard covers a disjoint year range.  Shard results are merged into a
    running aggregate (summed counts, unioned documents) as they arrive from
    ``imap_unordered``.

    Args:
        corpus: CWB corpus object or ``CorpusCreateOpts``.
        opts: CQP query options (dict or list of dicts).
        n: N-gram width.
        p_show: Positional attribute to display (``"word"`` or ``"lemma"``).
        mode: N-gram extraction mode (``"sliding"``, ``"left-aligned"``,
              ``"right-aligned"``).
        num_processes: Pool size.  ``None`` → CPU count.
        num_shards: Year-range partition count.  ``None`` → ``num_processes``.
        on_shards_total: Optional callback invoked once with the total shard
                         count before the pool starts (used by the ticket
                         service to initialise shard tracking).
        on_shard_complete: Optional callback invoked per completed shard with
                           ``(shard_index, shard_df)`` in arrival order
                           (``imap_unordered``).

    Returns:
        Fully merged aggregate DataFrame with columns
        ``[ngram, window_count, documents]``.
    """
    if num_processes is None:
        num_processes = mp.cpu_count()

    effective_num_shards: int = num_shards if num_shards is not None else num_processes

    corpus_opts: CorpusCreateOpts = CorpusCreateOpts.to_opts(corpus)

    default_min: int = ConfigValue("kwic.default_min_year", default=1867).resolve()
    default_max: int = ConfigValue("kwic.default_max_year", default=datetime.now().year).resolve()

    min_year, max_year = extract_year_range(opts, default_min=default_min, default_max=default_max)
    year_chunks: list[tuple[int, int]] = create_year_chunks(min_year, max_year, effective_num_shards)

    if on_shards_total is not None:
        on_shards_total(len(year_chunks))

    worker_args: list[tuple[Any, ...]] = [
        (i, corpus_opts, opts, year_range, n, p_show, mode)
        for i, year_range in enumerate(year_chunks)
    ]

    aggregate = pd.DataFrame(columns=["ngram", "window_count", "documents"])

    with mp.Pool(processes=num_processes) as pool:
        for shard_index, shard_df in pool.imap_unordered(ngrams_worker, worker_args):
            aggregate = _merge_ngrams_aggregate(aggregate, shard_df)
            if on_shard_complete is not None:
                on_shard_complete(shard_index, aggregate)

    return aggregate
