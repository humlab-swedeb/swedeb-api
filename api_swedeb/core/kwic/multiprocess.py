from __future__ import annotations

import multiprocessing as mp
import os
import tempfile
from collections.abc import Callable
from datetime import datetime
from typing import Any, Literal

import ccc
import pandas as pd

from api_swedeb.core.configuration.inject import ConfigValue
from api_swedeb.core.cwb.utility import CorpusCreateOpts

from .singleprocess import execute_kwic_singleprocess
from .utility import create_year_chunks, empty_kwic, extract_year_range, inject_year_filter


def kwic_worker(args: tuple) -> tuple[int, pd.DataFrame]:
    """Worker function for multiprocessing kwic queries.

    This function is designed to be called by multiprocessing.Pool.imap_unordered().
    Each worker creates its own isolated work directory to avoid file locking conflicts.

    Args:
        args: Tuple of (shard_index, corpus_opts, opts, year_range, words_before, words_after, p_show, cut_off)

    Returns:
        Tuple of (shard_index, DataFrame) with kwic results for the specified year range
    """

    shard_index, corpus_opts, opts, year_range, words_before, words_after, p_show, cut_off = args

    opts_with_year_range: list[dict[str, Any]] = inject_year_filter(opts, year_range)

    # Create a unique work_dir for this worker process to avoid GDBM file locking conflicts
    # Each process gets its own temporary directory with the process ID in the name
    process_id = os.getpid()
    unique_data_dir = tempfile.mkdtemp(
        prefix=f"ccc-{ccc.__version__}-swedeb-worker-{process_id}-", dir=tempfile.gettempdir()
    )

    # Create a new CorpusCreateOpts with the unique data_dir
    corpus_opts_isolated = CorpusCreateOpts(
        registry_dir=corpus_opts.registry_dir,
        corpus_name=corpus_opts.corpus_name,
        data_dir=unique_data_dir,
    )

    corpus: ccc.Corpus = corpus_opts_isolated.create_corpus()

    try:
        result = execute_kwic_singleprocess(
            corpus=corpus,
            opts=opts_with_year_range,
            words_before=words_before,
            words_after=words_after,
            p_show=p_show,
            cut_off=cut_off,
        )
        return shard_index, result
    finally:
        # Clean up the temporary directory after processing
        # Note: We leave cleanup to the OS in case of crashes, but try to clean up on success
        try:
            import shutil  # pylint: disable=import-outside-toplevel

            shutil.rmtree(unique_data_dir, ignore_errors=True)
        except Exception:  # pylint: disable=broad-except
            pass  # Best effort cleanup


def execute_kwic_multiprocess(
    corpus: ccc.Corpus | CorpusCreateOpts,
    opts: dict[str, Any] | list[dict[str, Any]],
    *,
    words_before: int,
    words_after: int,
    p_show: Literal["word", "lemma"],
    cut_off: int | None,
    num_processes: int | None,
    num_shards: int | None = None,
    on_shards_total: Callable[[int], None] | None = None,
    on_shard_complete: Callable[[int, pd.DataFrame], None] | None = None,
) -> pd.DataFrame:
    """Execute KWIC query using multiprocessing with year-based partitioning.

    Args:
        corpus: CWB corpus object
        opts: Query options
        words_before: Number of words before match
        words_after: Number of words after match
        p_show: What to display ('word' or 'lemma')
        cut_off: Maximum number of results
        num_processes: Number of parallel worker processes (pool size).  None = CPU count.
        num_shards: Number of year-range partitions to divide the corpus into.
                    When None, defaults to ``num_processes`` (previous behaviour).
                    Setting this higher than ``num_processes`` enables finer-grained
                    partitioning with load balancing across workers.
        on_shards_total: Optional callback invoked once with the total shard count
                         before the pool starts.  Used by the ticket service to
                         pre-register shard metadata.
        on_shard_complete: Optional callback invoked per completed shard with
                           (shard_index, raw_DataFrame).  Fired in completion
                           order (imap_unordered), not submission order.

    Returns:
        Combined DataFrame from all worker processes
    """
    if num_processes is None:
        num_processes = mp.cpu_count()

    # num_shards controls partitioning granularity; defaults to num_processes
    # when not set so that existing behaviour is preserved.
    effective_num_shards: int = num_shards if num_shards is not None else num_processes

    corpus_opts: CorpusCreateOpts = CorpusCreateOpts.to_opts(corpus)

    default_min: int = ConfigValue("kwic.default_min_year", default=1867).resolve()
    default_max: int = ConfigValue("kwic.default_max_year", default=datetime.now().year).resolve()

    # Extract year range from opts or use defaults
    min_year, max_year = extract_year_range(opts, default_min=default_min, default_max=default_max)

    # Create year chunks — partitioning driven by num_shards, parallelism by num_processes
    year_chunks: list[tuple[int, int]] = create_year_chunks(min_year, max_year, effective_num_shards)

    # Notify caller of total shard count before pool starts (for capacity reservation)
    if on_shards_total is not None:
        on_shards_total(len(year_chunks))

    # Each shard uses the full global cut_off so that no year period is silently
    # truncated before the merge.
    shard_cut_off: int | None = cut_off

    # Prepare worker arguments (shard_index is first element)
    worker_args: list[tuple[Any, ...]] = [
        (i, corpus_opts, opts, year_range, words_before, words_after, p_show, shard_cut_off)
        for i, year_range in enumerate(year_chunks)
    ]

    # Run queries in parallel, collecting results as they complete
    results: dict[int, pd.DataFrame] = {}
    with mp.Pool(processes=num_processes) as pool:
        for shard_index, df in pool.imap_unordered(kwic_worker, worker_args):
            results[shard_index] = df
            if on_shard_complete is not None:
                on_shard_complete(shard_index, df)

    # Reconstruct in submission order for the combined return value
    ordered_results = [results[i] for i in sorted(results.keys())]

    # Combine results
    if not ordered_results or all(len(df) == 0 for df in ordered_results):
        return empty_kwic(p_show)

    non_empty_results: list[pd.DataFrame] = [df for df in ordered_results if len(df) > 0]
    if not non_empty_results:
        return empty_kwic(p_show)

    combined = pd.concat(non_empty_results, axis=0)

    # Apply cut_off if specified
    if cut_off is not None and len(combined) > cut_off:
        combined = combined.iloc[:cut_off]

    return combined
