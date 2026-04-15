"""Standalone profiling script for DownloadService.create_zip_stream.

Mirrors the setup of TestCreateZipStream::test_zip_large_batch so that
pyinstrument (or cProfile) sees the real hot path without pytest overhead.

Usage::

    # HTML report (open in browser)
    make profile-zip-pyinstrument

    # Quick terminal output
    uv run pyinstrument tests/profiling/profile_zip_stream.py

    # cProfile + snakeviz
    uv run python -m cProfile -o tests/output/zip_stream.prof tests/profiling/profile_zip_stream.py
    uv run snakeviz tests/output/zip_stream.prof
"""

from __future__ import annotations

import argparse
from unittest.mock import MagicMock

from api_swedeb.api.services.corpus_loader import CorpusLoader  # type: ignore[import]
from api_swedeb.api.services.download_service import DownloadService, create_download_service  # type: ignore[import]
from api_swedeb.api.services.search_service import SearchService  # type: ignore[import]
from api_swedeb.core.configuration import get_config_store  # type: ignore[import]

get_config_store().configure_context(source="config/config.yml")


def _make_commons(selections: dict) -> MagicMock:
    mock = MagicMock()
    mock.get_filter_opts.return_value = selections
    return mock


def _collect_zip(generator) -> bytes:
    return b"".join(generator())


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark compressed stream creation.")
    parser.add_argument("--format", required=True, help="Compression format to test (zip, tar.gz, jsonl.gz)")
    parser.add_argument("--start-year", required=True, help="Start year for the benchmark range")
    parser.add_argument("--end-year", required=True, help="End year for the benchmark range")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    print("Loading corpus…", flush=True)

    loader = CorpusLoader()
    _ = loader.person_codecs
    _ = loader.document_index
    _ = loader.decoded_persons
    _ = loader.repository

    print(f"# Benchmarking using '{args.format}' ({args.start_year}–{args.end_year})", flush=True)

    search_service = SearchService(loader)
    download_service: DownloadService = create_download_service(args.format)

    commons = _make_commons({"year": (int(args.start_year), int(args.end_year))})

    print(f"Running create_{args.format}_stream({args.start_year}–{args.end_year})…", flush=True)
    zip_bytes = _collect_zip(download_service.create_stream(search_service, commons))

    # with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
    #     n = len(zf.namelist())

    print(f"Done benchmarking using '{args.format}': {len(zip_bytes):,} bytes", flush=True)


if __name__ == "__main__":
    main()
