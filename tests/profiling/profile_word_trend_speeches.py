"""Standalone profiling script for WordTrendsService.get_speeches_for_word_trends.

Profiles speech lookup for a word to identify why common words take so long.

Usage::

    # Quick terminal output
    uv run python tests/profiling/profile_word_trend_speeches.py

    # With custom word
    uv run python tests/profiling/profile_word_trend_speeches.py --word att
"""

from __future__ import annotations

import argparse
import time

from api_swedeb.api.services.corpus_loader import CorpusLoader  # type: ignore[import]
from api_swedeb.api.services.word_trends_service import WordTrendsService  # type: ignore[import]
from api_swedeb.core.configuration import get_config_store  # type: ignore[import]

get_config_store().configure_context(source="config/config.yml")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Profile word trend speeches lookup.")
    parser.add_argument("--word", default="skola", help="Word to analyze (default: skola)")
    parser.add_argument("--start-year", type=int, default=1867, help="Start year (default: 1867)")
    parser.add_argument("--end-year", type=int, default=2022, help="End year (default: 2022)")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    print(f"# Profiling word trend speeches for '{args.word}' ({args.start_year}–{args.end_year})", flush=True)
    print("=" * 80)
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

    print(f"\nRunning get_speeches_for_word_trends('{args.word}')…", flush=True)

    # This is the hot path we're profiling
    start_time = time.time()
    df = word_trends_service.get_speeches_for_word_trends(
        selected_terms=search_terms, filter_opts=filter_opts
    )
    elapsed = time.time() - start_time

    print("=" * 80)
    print(f"✓ Done in {elapsed:.2f} seconds")
    print()
    print(f"Number of speeches returned: {len(df):,}")
    print(f"DataFrame columns: {len(df.columns)}")
    print(f"Total cells: {len(df) * len(df.columns):,}")
    print(f"Memory usage: {df.memory_usage(deep=True).sum() / 1024**2:.2f} MB")
    print()
    
    if not df.empty:
        print("DataFrame info:")
        print(f"  Columns: {list(df.columns)}")
        print()
        print("First 3 speeches:")
        print(df.head(3).to_string())
        print()
        
        # Estimate JSON payload size
        import json
        sample_rows = min(100, len(df))
        sample_json = df.head(sample_rows).to_json(orient='records')
        estimated_full_size = len(sample_json) * len(df) / sample_rows / (1024**2)
        print(f"Estimated JSON payload size: {estimated_full_size:.2f} MB")


if __name__ == "__main__":
    main()
