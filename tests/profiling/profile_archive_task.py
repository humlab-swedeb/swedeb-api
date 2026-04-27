"""Standalone profiling script for the archive-generation hot path.

Exercises the exact same path that the Celery ``execute_archive_task`` runs:
  1. ``WordTrendsService.get_speeches_for_word_trends()`` → speech IDs
  2. ``TicketedDownloadService.for_format(zip).write()`` → ZIP on disk

This lets pyinstrument show where time is spent inside ``ZipArchiveWriter``
and ``SearchService.get_speeches_text_batch`` without Celery or worker-init
overhead and without the SpeechStore cold-load that inflates the first
Celery task per worker.

Usage::

    # Quick terminal flamegraph
    uv run pyinstrument tests/profiling/profile_archive_task.py

    # HTML report
    make profile-archive-pyinstrument

    # Different word or year range
    make profile-archive-pyinstrument WORD=skola START_YEAR=1900 END_YEAR=2000

    # cProfile + snakeviz
    uv run python -m cProfile -o tests/output/archive_task.prof \\
        tests/profiling/profile_archive_task.py
    uv run snakeviz tests/output/archive_task.prof
"""

from __future__ import annotations

import argparse
import tempfile
import time
from pathlib import Path

from api_swedeb.api.services.corpus_loader import CorpusLoader  # type: ignore[import]
from api_swedeb.api.services.search_service import SearchService  # type: ignore[import]
from api_swedeb.api.services.ticketed_download_service import TicketedDownloadService  # type: ignore[import]
from api_swedeb.api.services.word_trends_service import WordTrendsService  # type: ignore[import]
from api_swedeb.core.configuration import get_config_store  # type: ignore[import]
from api_swedeb.schemas.bulk_archive_schema import BulkArchiveFormat  # type: ignore[import]

get_config_store().configure_context(source="config/config.yml")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Profile archive-task ZIP generation.")
    parser.add_argument("--word", default="skola", help="Search word (default: skola)")
    parser.add_argument("--start-year", type=int, default=1867, help="Start year (default: 1867)")
    parser.add_argument("--end-year", type=int, default=2022, help="End year (default: 2022)")
    parser.add_argument(
        "--format",
        default="zip",
        choices=["zip", "csv.gz", "jsonl.gz"],
        help="Archive format (default: zip)",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    print(f"# Profile archive task: word='{args.word}' ({args.start_year}–{args.end_year})", flush=True)
    print("=" * 72)

    # --- Load corpus (mirrors Celery worker cold-start) ----------------------
    t0 = time.perf_counter()
    print("Loading CorpusLoader…", flush=True)
    loader = CorpusLoader()
    _ = loader.person_codecs
    _ = loader.document_index
    _ = loader.decoded_persons
    _ = loader.repository  # triggers SpeechStore load
    _ = loader.prebuilt_speech_index
    _ = loader.vectorized_corpus
    print(f"  corpus ready in {time.perf_counter() - t0:.2f}s", flush=True)

    # --- Phase 1: speech-ID lookup (matches execute_word_trend_speeches_ticket) ---
    print(f"\nPhase 1: get_speeches_for_word_trends('{args.word}')…", flush=True)
    word_trends_service = WordTrendsService(loader)
    filter_opts = {"year": (args.start_year, args.end_year)}

    t1 = time.perf_counter()
    df = word_trends_service.get_speeches_for_word_trends(
        selected_terms=[args.word],
        filter_opts=filter_opts,
    )
    speech_ids: list[str] = (
        list(dict.fromkeys(sid for sid in df["speech_id"].tolist() if sid)) if "speech_id" in df.columns else []
    )
    elapsed1 = time.perf_counter() - t1
    print(f"  {len(speech_ids):,} speech IDs in {elapsed1:.2f}s", flush=True)

    if not speech_ids:
        print("No speeches found — check word and year range.", flush=True)
        return

    # --- Phase 2: archive generation (matches execute_archive_task) ----------
    archive_format = BulkArchiveFormat(args.format)
    search_service = SearchService(loader)
    writer = TicketedDownloadService.for_format(archive_format)

    print(f"\nPhase 2: {archive_format.value} archive for {len(speech_ids):,} speeches…", flush=True)

    with tempfile.TemporaryDirectory() as tmp:
        dest = Path(tmp) / f"archive.{archive_format.value}"

        t2 = time.perf_counter()
        writer.write(
            speech_ids=speech_ids,
            search_service=search_service,
            dest_path=dest,
            manifest_meta={"word": args.word, "from_year": args.start_year, "to_year": args.end_year},
        )
        elapsed2 = time.perf_counter() - t2

        size_mb = dest.stat().st_size / 1_048_576
        rate = len(speech_ids) / elapsed2 if elapsed2 > 0 else 0
        print(f"  {size_mb:.1f} MB written in {elapsed2:.2f}s  ({rate:,.0f} speeches/s)", flush=True)

    print(f"\nTotal (excluding corpus load): {elapsed1 + elapsed2:.2f}s", flush=True)


if __name__ == "__main__":
    main()
