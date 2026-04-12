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

import io
import sys
import zipfile
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Bootstrap configuration (mirrors the module-scoped fixture in the benchmark)
# ---------------------------------------------------------------------------
from api_swedeb.core.configuration import Config, ConfigStore
from api_swedeb.core.configuration.inject import get_config_store as _orig_get_config_store

config: Config = Config.load(source="config/config.yml")
store: ConfigStore = ConfigStore()
store.configure_context(source=config)

_patcher = patch("api_swedeb.core.configuration.inject.get_config_store", return_value=store)
_patcher.start()

# ---------------------------------------------------------------------------
# Import services *after* config is patched
# ---------------------------------------------------------------------------
from api_swedeb.api.services.corpus_loader import CorpusLoader  # noqa: E402
from api_swedeb.api.services.download_service import DownloadService  # noqa: E402
from api_swedeb.api.services.search_service import SearchService  # noqa: E402


def _make_commons(selections: dict) -> MagicMock:
    mock = MagicMock()
    mock.get_filter_opts.return_value = selections
    return mock


def _collect_zip(generator) -> bytes:
    return b"".join(generator())


def main() -> None:
    print("Loading corpus…", flush=True)
    loader = CorpusLoader()
    _ = loader.person_codecs
    _ = loader.document_index
    _ = loader.decoded_persons
    _ = loader.repository

    search_service = SearchService(loader)
    download_service = DownloadService()

    commons = _make_commons({"year": (1970, 1980)})

    print("Running create_zip_stream(1970–1980)…", flush=True)
    zip_bytes = _collect_zip(download_service.create_zip_stream(search_service, commons))

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        n = len(zf.namelist())

    print(f"Done — {n:,} entries, {len(zip_bytes):,} bytes", flush=True)


if __name__ == "__main__":
    main()
    _patcher.stop()
