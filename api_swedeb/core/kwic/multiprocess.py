from __future__ import annotations

import multiprocessing as mp
import os
import tempfile
from datetime import datetime
from typing import Any, Literal

import ccc
import pandas as pd

from api_swedeb.core.configuration.inject import ConfigValue
from api_swedeb.core.cwb.utility import CorpusCreateOpts

from .singleprocess import execute_kwic_singleprocess
from .utility import create_year_chunks, empty_kwic, extract_year_range, inject_year_filter


def kwic_worker(args: tuple) -> pd.DataFrame:
    """Worker function for multiprocessing kwic queries.

    This function is designed to be called by multiprocessing.Pool.map().
    Each worker creates its own isolated work directory to avoid file locking conflicts.

    Args:
        args: Tuple of (corpus_opts, opts, year_range, words_before, words_after, p_show, cut_off)

    Returns:
        DataFrame with kwic results for the specified year range
    """

    corpus_opts, opts, year_range, words_before, words_after, p_show, cut_off = args

    opts_with_year_range: list[dict[str, Any]] = inject_year_filter(opts, year_range)

    # Create a unique work_dir for this worker process to avoid GDBM file locking conflicts
    # Each process gets its own temporary directory with the process ID in the name
    process_id = os.getpid()
    unique_data_dir = tempfile.mkdtemp(
        prefix=f"ccc-{ccc.__version__}-swedeb-worker-{process_id}-",
        dir=tempfile.gettempdir()
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
        return result
    finally:
        # Clean up the temporary directory after processing
        # Note: We leave cleanup to the OS in case of crashes, but try to clean up on success
        try:
            import shutil
            shutil.rmtree(unique_data_dir, ignore_errors=True)
        except Exception:
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
) -> pd.DataFrame:
    """Execute KWIC query using multiprocessing with year-based partitioning.

    Args:
        corpus: CWB corpus object
        opts: Query options
        words_before: Number of words before match
        words_after: Number of words after match
        p_show: What to display ('word' or 'lemma')
        cut_off: Maximum number of results
        num_processes: Number of processes to use (None = CPU count)
        empty_result_fn: Function to call for empty results

    Returns:
        Combined DataFrame from all worker processes
    """
    if num_processes is None:
        num_processes = mp.cpu_count()

    corpus_opts: CorpusCreateOpts = CorpusCreateOpts.to_opts(corpus)

    default_min: int = ConfigValue("kwic.default_min_year", default=1867).resolve()
    default_max: int = ConfigValue("kwic.default_max_year", default=datetime.now().year).resolve()

    # Extract year range from opts or use defaults
    min_year, max_year = extract_year_range(opts, default_min=default_min, default_max=default_max)

    # Create year chunks
    year_chunks: list[tuple[int, int]] = create_year_chunks(min_year, max_year, num_processes)

    # Prepare worker arguments
    worker_args: list[tuple[Any, ...]] = [
        (corpus_opts, opts, year_range, words_before, words_after, p_show, cut_off) for year_range in year_chunks
    ]

    # Run queries in parallel
    with mp.Pool(processes=num_processes) as pool:
        results: list[pd.DataFrame] = pool.map(kwic_worker, worker_args)

    # Combine results
    if not results or all(len(df) == 0 for df in results):
        return empty_kwic(p_show)

    # Concatenate all non-empty results
    non_empty_results: list[pd.DataFrame] = [df for df in results if len(df) > 0]
    if not non_empty_results:
        return empty_kwic(p_show)

    combined = pd.concat(non_empty_results, axis=0)

    # Apply cut_off if specified
    if cut_off is not None and len(combined) > cut_off:
        combined: pd.DataFrame = combined.iloc[:cut_off]

    return combined
