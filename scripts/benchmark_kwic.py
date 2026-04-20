"""KWIC performance benchmark — singleprocess vs. multiprocess.

Runs a configurable KWIC query N times against the full corpus, alternating
between singleprocess and multiprocess execution modes, and prints a summary
table to stdout.  Optionally writes a JSON result file for later analysis.

Usage examples
--------------
# Quickest check — 1 run each, word "och", full year range
uv run python scripts/benchmark_kwic.py --word och --runs 1

# Thorough benchmark — 3 runs, three process counts, common heavy word
uv run python scripts/benchmark_kwic.py \\
    --word att --from-year 1867 --to-year 2022 \\
    --cut-off 500000 --runs 3 --processes 1 4 8 \\
    --output tests/output/benchmark_kwic.json

# Different config (staging)
uv run python scripts/benchmark_kwic.py \\
    --config config/config.yml --word information --runs 2
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import uuid
from time import perf_counter
from typing import Any

from loguru import logger
from api_swedeb.core.configuration.inject import get_config_store, ConfigValue
from api_swedeb.api.params import build_common_query_params
from api_swedeb.api.services.corpus_loader import CorpusLoader
from api_swedeb.api.services.kwic_service import KWICService

# ---------------------------------------------------------------------------
# Minimal startup: configure loguru to only show INFO+
# ---------------------------------------------------------------------------
logger.remove()
logger.add(sys.stderr, level="INFO", format="<level>{level}</level>: {message}")


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Benchmark KWIC queries: singleprocess vs. multiprocess.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument(
        "--config",
        default="config/config.yml",
        metavar="PATH",
        help="Path to config YAML (default: config/config.yml).",
    )
    p.add_argument(
        "--word",
        dest="words",
        action="append",
        default=[],
        metavar="TERM",
        help="Search term(s); repeat for multiple words, e.g. --word att --word och.",
    )
    p.add_argument(
        "--lemmatized",
        action="store_true",
        default=True,
        help="Search lemmatized form (default: True).",
    )
    p.add_argument("--from-year", type=int, default=None, metavar="YEAR", help="Start year filter.")
    p.add_argument("--to-year", type=int, default=None, metavar="YEAR", help="End year filter.")
    p.add_argument(
        "--words-before",
        type=int,
        default=2,
        metavar="N",
        help="Context tokens before keyword (default: 2).",
    )
    p.add_argument(
        "--words-after",
        type=int,
        default=2,
        metavar="N",
        help="Context tokens after keyword (default: 2).",
    )
    p.add_argument(
        "--cut-off",
        type=int,
        default=500_000,
        metavar="N",
        help="Maximum concordance hits to retrieve (default: 500000).",
    )
    p.add_argument(
        "--runs",
        type=int,
        default=3,
        metavar="N",
        help="Number of timed repetitions per variant (default: 3).",
    )
    p.add_argument(
        "--processes",
        type=int,
        nargs="+",
        default=[4, 8],
        metavar="N",
        help=(
            "Process counts to test in multiprocess mode (default: 4 8). "
            "Set to 0 to skip multiprocess runs entirely."
        ),
    )
    p.add_argument(
        "--output",
        default=None,
        metavar="PATH",
        help="Write full results as JSON to this path (optional).",
    )
    return p.parse_args()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_corpus(registry_dir: str, corpus_name: str) -> Any:
    """Create a CWB corpus object, using an isolated tmp data_dir."""
    import ccc

    data_dir = f"/tmp/ccc-benchmark-{uuid.uuid4().hex[:8]}"
    return ccc.Corpora(registry_dir=registry_dir).corpus(corpus_name=corpus_name, data_dir=data_dir)


def _time_query(
    kwic_service: Any,
    corpus: Any,
    commons: Any,
    *,
    keywords: str | list[str],
    lemmatized: bool,
    words_before: int,
    words_after: int,
    cut_off: int,
    use_multiprocessing: bool,
    num_processes: int,
) -> tuple[float, int]:
    """Run one timed KWIC query, return (elapsed_seconds, row_count)."""
    import pandas as pd

    t0 = perf_counter()
    data: pd.DataFrame = kwic_service.get_kwic(
        corpus=corpus,
        commons=commons,
        keywords=keywords,
        lemmatized=lemmatized,
        words_before=words_before,
        words_after=words_after,
        cut_off=cut_off,
        use_multiprocessing=use_multiprocessing,
        n_processes=num_processes,
    )
    elapsed = perf_counter() - t0
    return elapsed, len(data)


def _run_variant(
    *,
    label: str,
    kwic_service: Any,
    registry_dir: str,
    corpus_name: str,
    commons: Any,
    keywords: str | list[str],
    lemmatized: bool,
    words_before: int,
    words_after: int,
    cut_off: int,
    use_multiprocessing: bool,
    num_processes: int,
    runs: int,
) -> dict:
    """Run a benchmark variant (single mode), returning a result dict."""
    times: list[float] = []
    row_count: int = 0

    logger.info(f"  Running variant [{label}]  ({runs} run(s))...")

    for run_index in range(runs):
        # Fresh corpus connection per run — avoids any internal CWB caching
        corpus = _make_corpus(registry_dir, corpus_name)
        elapsed, row_count = _time_query(
            kwic_service,
            corpus,
            commons,
            keywords=keywords,
            lemmatized=lemmatized,
            words_before=words_before,
            words_after=words_after,
            cut_off=cut_off,
            use_multiprocessing=use_multiprocessing,
            num_processes=num_processes,
        )
        times.append(elapsed)
        logger.info(f"    run {run_index + 1}/{runs}: {elapsed:.2f}s  ({row_count} rows)")

    return {
        "label": label,
        "use_multiprocessing": use_multiprocessing,
        "num_processes": num_processes if use_multiprocessing else 1,
        "runs": runs,
        "row_count": row_count,
        "times": times,
        "min_s": round(min(times), 3),
        "mean_s": round(statistics.mean(times), 3),
        "max_s": round(max(times), 3),
        "stdev_s": round(statistics.stdev(times), 3) if len(times) > 1 else 0.0,
    }


def _print_table(results: list[dict], baseline_mean: float) -> None:
    """Print a formatted comparison table to stdout."""
    col_label = max(len(r["label"]) for r in results)
    col_label = max(col_label, 20)

    header = (
        f"{'Variant':<{col_label}}  "
        f"{'Procs':>5}  "
        f"{'Runs':>4}  "
        f"{'Rows':>8}  "
        f"{'Min (s)':>8}  "
        f"{'Mean (s)':>8}  "
        f"{'Max (s)':>8}  "
        f"{'Stdev':>6}  "
        f"{'Speedup':>7}"
    )
    sep = "-" * len(header)

    print()
    print(sep)
    print(header)
    print(sep)

    for r in results:
        speedup = baseline_mean / r["mean_s"] if r["mean_s"] > 0 else 0.0
        print(
            f"{r['label']:<{col_label}}  "
            f"{r['num_processes']:>5}  "
            f"{r['runs']:>4}  "
            f"{r['row_count']:>8}  "
            f"{r['min_s']:>8.2f}  "
            f"{r['mean_s']:>8.2f}  "
            f"{r['max_s']:>8.2f}  "
            f"{r['stdev_s']:>6.3f}  "
            f"{speedup:>7.2f}x"
        )

    print(sep)
    print()


# ---------------------------------------------------------------------------
# Entry-point
# ---------------------------------------------------------------------------


def main() -> None:
    args = _parse_args()

    words = args.words or ["att"]
    keywords = words[0] if len(words) == 1 else words

    # ------------------------------------------------------------------
    # Bootstrap configuration
    # ------------------------------------------------------------------

    get_config_store().configure_context(source=args.config)

    registry_dir: str = ConfigValue("cwb.registry_dir").resolve()
    corpus_name: str = ConfigValue("cwb.corpus_name").resolve()

    logger.info(f"Config       : {args.config}")
    logger.info(f"Corpus       : {corpus_name}  (registry: {registry_dir})")
    logger.info(f"Keywords     : {keywords!r}  (lemmatized={args.lemmatized})")
    logger.info(f"Filters      : from_year={args.from_year}  to_year={args.to_year}")
    logger.info(f"cut_off      : {args.cut_off:,}")
    logger.info(f"Runs/variant : {args.runs}")
    logger.info(f"Multiproc N  : {args.processes}")

    # ------------------------------------------------------------------
    # Load services (this is the expensive part; done once)
    # ------------------------------------------------------------------
    logger.info("Loading CorpusLoader (this may take a while)…")

    loader = CorpusLoader()
    kwic_service = KWICService(loader=loader)

    commons = build_common_query_params(
        from_year=args.from_year,
        to_year=args.to_year,
    )

    shared_kwargs = dict(
        kwic_service=kwic_service,
        registry_dir=registry_dir,
        corpus_name=corpus_name,
        commons=commons,
        keywords=keywords,
        lemmatized=args.lemmatized,
        words_before=args.words_before,
        words_after=args.words_after,
        cut_off=args.cut_off,
        runs=args.runs,
    )

    results: list[dict] = []

    # ------------------------------------------------------------------
    # Variant 1: singleprocess baseline
    # ------------------------------------------------------------------
    logger.info("Starting singleprocess baseline…")
    baseline = _run_variant(
        label="singleprocess (baseline)",
        use_multiprocessing=False,
        num_processes=1,
        **shared_kwargs,  # type: ignore
    )
    results.append(baseline)
    baseline_mean = baseline["mean_s"]

    # ------------------------------------------------------------------
    # Variants 2+: multiprocess with varying process counts
    # ------------------------------------------------------------------
    for n in args.processes:
        if n <= 0:
            continue
        logger.info(f"Starting multiprocess variant: {n} processes…")
        result = _run_variant(
            label=f"multiprocess ({n} procs)",
            use_multiprocessing=True,
            num_processes=n,
            **shared_kwargs,  # type: ignore
        )
        results.append(result)

    # ------------------------------------------------------------------
    # Report
    # ------------------------------------------------------------------
    _print_table(results, baseline_mean)

    best = min(results[1:], key=lambda r: r["mean_s"]) if len(results) > 1 else None
    if best:
        speedup = baseline_mean / best["mean_s"]
        logger.info(f"Best multiprocess: {best['label']}  " f"mean={best['mean_s']:.2f}s  speedup={speedup:.2f}x")

    # ------------------------------------------------------------------
    # Optional JSON output
    # ------------------------------------------------------------------
    if args.output:
        os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
        payload = {
            "config": args.config,
            "keywords": keywords,
            "lemmatized": args.lemmatized,
            "from_year": args.from_year,
            "to_year": args.to_year,
            "cut_off": args.cut_off,
            "corpus_name": corpus_name,
            "results": results,
        }
        with open(args.output, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
        logger.info(f"Results written to {args.output}")


if __name__ == "__main__":
    main()
