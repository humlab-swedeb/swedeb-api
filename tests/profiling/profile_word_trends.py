"""Standalone profiling script for WordTrendsService.get_word_trend_results.

Profiles word trends analysis for a single word across the entire corpus
to identify performance bottlenecks.

Usage::

    # HTML report (open in browser)
    make profile-word-trends-pyinstrument

    # Quick terminal output
    uv run pyinstrument tests/profiling/profile_word_trends.py

    # With custom word and year range
    uv run pyinstrument tests/profiling/profile_word_trends.py --word skola --start-year 1867 --end-year 2022

    # cProfile + snakeviz
    uv run python -m cProfile -o tests/output/word_trends.prof tests/profiling/profile_word_trends.py
    uv run snakeviz tests/output/word_trends.prof
"""

from __future__ import annotations

import argparse

from api_swedeb.api.services.corpus_loader import CorpusLoader  # type: ignore[import]
from api_swedeb.api.services.word_trends_service import WordTrendsService  # type: ignore[import]
from api_swedeb.core.configuration import get_config_store  # type: ignore[import]

get_config_store().configure_context(source="config/config.yml")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Profile word trends analysis.")
    parser.add_argument("--word", default="skola", help="Word to analyze (default: skola)")
    parser.add_argument("--start-year", type=int, default=1867, help="Start year (default: 1867)")
    parser.add_argument("--end-year", type=int, default=2022, help="End year (default: 2022)")
    parser.add_argument("--normalize", action="store_true", help="Normalize trends by total tokens per year")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    print(f"# Profiling word trends for '{args.word}' ({args.start_year}–{args.end_year})", flush=True)
    print("Loading corpus…", flush=True)

    # Initialize corpus loader
    loader = CorpusLoader()
    _ = loader.person_codecs
    _ = loader.document_index
    _ = loader.decoded_persons
    _ = loader.vectorized_corpus

    print("Creating WordTrendsService…", flush=True)
    word_trends_service = WordTrendsService(loader)

    # Setup filter options for the entire corpus or specified range
    filter_opts = {"year": (args.start_year, args.end_year)}
    search_terms = [args.word]

    print(f"Running get_word_trend_results('{args.word}')…", flush=True)

    # This is the hot path we're profiling
    df = word_trends_service.get_word_trend_results(
        search_terms=search_terms, filter_opts=filter_opts, normalize=args.normalize
    )

    print(
        f"Done! Result: {len(df)} rows × {len(df.columns)} columns = {df.shape[0] * df.shape[1]:,} cells", flush=True
    )
    print(f"Memory usage: {df.memory_usage(deep=True).sum() / 1024**2:.2f} MB", flush=True)

    if not df.empty:
        print(f"Columns: {list(df.columns[:5])}{'...' if len(df.columns) > 5 else ''}", flush=True)
        print(f"Word '{args.word}' found in vocabulary: {args.word in loader.vectorized_corpus.token2id}", flush=True)


if __name__ == "__main__":
    main()
