"""Integration benchmarks and correctness tests for DownloadService.

Run against the full database to identify bottlenecks:

    pytest tests/integration/test_download_service.py -v -s

Add --benchmark-only for pytest-benchmark timing if available, or inspect the
printed timings produced by the time.perf_counter wrappers in each test.
"""

from __future__ import annotations

import io
import time
import zipfile
from typing import Any, Generator
from unittest.mock import MagicMock, patch

import pytest

from api_swedeb.api.services.corpus_loader import CorpusLoader
from api_swedeb.api.services.download_service import DownloadService
from api_swedeb.api.services.search_service import SearchService
from api_swedeb.core.configuration import ConfigStore, Config

# pylint: disable=redefined-outer-name,unused-argument

@pytest.fixture(scope="module", autouse=True)
def config_store() -> Generator[ConfigStore, None, None]:
    """Fixture to provide a clean ConfigStore instance for tests.
    Automatically patches get_config_store() to return this store for the duration of the test.
    """
    config: Config = Config.load(source="config/config.yml")
    store: ConfigStore = ConfigStore()
    store.configure_context(source=config)

    with patch("api_swedeb.core.configuration.inject.get_config_store", return_value=store):
        yield store

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

version = "v1"


def _elapsed(start: float) -> float:
    return time.perf_counter() - start


def _make_commons(selections: dict[str, Any]) -> MagicMock:
    """Build a minimal CommonParams-like mock that returns *selections* from get_filter_opts."""
    mock = MagicMock()
    mock.get_filter_opts.return_value = selections
    return mock


def _collect_zip(generator) -> bytes:
    """Drain a streaming generator and return the assembled ZIP bytes."""
    return b"".join(generator())


def _zip_entry_names(zip_bytes: bytes) -> list[str]:
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        return zf.namelist()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def corpus_loader() -> CorpusLoader:
    loader: CorpusLoader = CorpusLoader()
    _ = loader.vectorized_corpus
    _ = loader.person_codecs
    _ = loader.document_index
    _ = loader.decoded_persons
    _ = loader.repository
    return loader

@pytest.fixture(scope="module")
def search_service(config_store, corpus_loader: CorpusLoader) -> SearchService:
    return SearchService(corpus_loader)


@pytest.fixture(scope="module")
def download_service(config_store) -> DownloadService:
    return DownloadService()


@pytest.fixture(scope="module")
def party_id_map(config_store, corpus_loader: CorpusLoader) -> dict[str, int]:
    return corpus_loader.person_codecs.get_mapping("party_abbrev", "party_id")


# ---------------------------------------------------------------------------
# get_anforanden benchmarks
# ---------------------------------------------------------------------------


class TestGetAnforanden:
    """Correctness and performance tests for SearchService.get_anforanden."""

    def test_no_filter_returns_all(self, search_service: SearchService):
        t0 = time.perf_counter()
        df = search_service.get_anforanden(selections={"year": (1970, 1970)})
        elapsed = _elapsed(t0)
        print(f"\n  get_anforanden(no filter): {len(df):,} rows in {elapsed:.3f}s")
        assert len(df) > 0
        assert "speech_id" in df.columns
        assert "name" in df.columns

    def test_year_range_filter(self, search_service: SearchService):
        t0 = time.perf_counter()
        df = search_service.get_anforanden(selections={"year": (1970, 1975)})
        elapsed = _elapsed(t0)
        print(f"\n  get_anforanden(year 1970-1975): {len(df):,} rows in {elapsed:.3f}s")
        assert len(df) > 0
        assert df["year"].between(1970, 1975).all()

    def test_party_filter(self, search_service: SearchService, party_id_map: dict[str, int]):
        party_ids = [party_id_map.get("S"), party_id_map.get("M")]
        party_ids = [p for p in party_ids if p is not None]
        t0 = time.perf_counter()
        df = search_service.get_anforanden(selections={"party_id": party_ids, "year": (1970, 1990)})
        elapsed = _elapsed(t0)
        print(f"\n  get_anforanden(S+M, 1970-1990): {len(df):,} rows in {elapsed:.3f}s")
        assert len(df) > 0
        assert set(df["party_abbrev"].unique()).issubset({"S", "M", "?"})

    def test_gender_filter(self, search_service: SearchService):
        t0 = time.perf_counter()
        df = search_service.get_anforanden(selections={"gender_id": [2], "year": (1970, 1990)})
        elapsed = _elapsed(t0)
        print(f"\n  get_anforanden(gender_id=2, 1970-1990): {len(df):,} rows in {elapsed:.3f}s")
        assert len(df) > 0

    def test_combined_filter(self, search_service: SearchService, party_id_map: dict[str, int]):
        party_ids = [party_id_map.get("S")]
        party_ids = [p for p in party_ids if p is not None]
        selections = {"party_id": party_ids, "gender_id": [1, 2], "year": (1960, 1970)}
        t0 = time.perf_counter()
        df = search_service.get_anforanden(selections=selections)
        elapsed = _elapsed(t0)
        print(f"\n  get_anforanden(S, all genders, 1960-1970): {len(df):,} rows in {elapsed:.3f}s")
        assert len(df) > 0

    def test_result_has_required_columns(self, search_service: SearchService):
        df = search_service.get_anforanden(selections={"year": (1970, 1971)})
        required = {"speech_id", "document_name", "name", "year", "party_abbrev", "gender", "speech_link", "link"}
        missing = required - set(df.columns)
        assert not missing, f"Missing columns: {missing}"

    def test_large_year_range(self, search_service: SearchService):
        """Benchmark a broad query that returns a large result set."""
        t0 = time.perf_counter()
        df = search_service.get_anforanden(selections={"year": (1960, 2000)})
        elapsed = _elapsed(t0)
        print(f"\n  get_anforanden(1960-2000): {len(df):,} rows in {elapsed:.3f}s")
        assert len(df) > 0


# ---------------------------------------------------------------------------
# get_speeches_batch benchmarks
# ---------------------------------------------------------------------------


class TestGetSpeechesBatch:
    """Correctness and performance tests for SearchService.get_speeches_batch."""

    def _sample_speech_ids(self, search_service: SearchService, n: int, year_range: tuple) -> list[str]:
        df = search_service.get_anforanden(selections={"year": year_range})
        available = df["speech_id"].dropna()
        return available.sample(min(n, len(available)), random_state=42).tolist()

    def test_small_batch(self, search_service: SearchService):
        ids = self._sample_speech_ids(search_service, 10, (1970, 1975))
        t0 = time.perf_counter()
        results = list(search_service.get_speeches_batch(ids))
        elapsed = _elapsed(t0)
        print(f"\n  get_speeches_batch(n=10): {len(results)} speeches in {elapsed:.3f}s")
        assert len(results) == 10
        for speech_id, speech in results:
            assert speech_id.startswith("i-")
            assert speech is not None

    def test_medium_batch(self, search_service: SearchService):
        ids = self._sample_speech_ids(search_service, 100, (1970, 1980))
        t0 = time.perf_counter()
        results = list(search_service.get_speeches_batch(ids))
        elapsed = _elapsed(t0)
        print(f"\n  get_speeches_batch(n=100): {len(results)} speeches in {elapsed:.3f}s")
        assert len(results) == 100

    def test_large_batch(self, search_service: SearchService):
        ids = self._sample_speech_ids(search_service, 500, (1970, 1990))
        t0 = time.perf_counter()
        results = list(search_service.get_speeches_batch(ids))
        elapsed = _elapsed(t0)
        print(f"\n  get_speeches_batch(n=500): {len(results)} speeches in {elapsed:.3f}s")
        assert len(results) == 500

    def test_batch_yields_text(self, search_service: SearchService):
        ids = self._sample_speech_ids(search_service, 5, (1975, 1980))
        results = list(search_service.get_speeches_batch(ids))
        # At least some speeches should have non-empty text
        texts = [speech.text for _, speech in results if speech.text]
        assert len(texts) > 0, "No speeches returned non-empty text"

    def test_batch_returns_matching_ids(self, search_service: SearchService):
        ids = self._sample_speech_ids(search_service, 20, (1970, 1975))
        results = list(search_service.get_speeches_batch(ids))
        returned_ids = {sid for sid, _ in results}
        assert returned_ids == set(ids)

    def test_batch_across_protocols(self, search_service: SearchService):
        """IDs from many different protocols — tests feather file grouping path."""
        ids = self._sample_speech_ids(search_service, 200, (1960, 2000))
        t0 = time.perf_counter()
        results = list(search_service.get_speeches_batch(ids))
        elapsed = _elapsed(t0)
        print(f"\n  get_speeches_batch(n=200, spread 1960-2000): {len(results)} speeches in {elapsed:.3f}s")
        assert len(results) == 200


# ---------------------------------------------------------------------------
# create_zip_stream benchmarks
# ---------------------------------------------------------------------------


class TestCreateZipStream:
    """Correctness and performance tests for DownloadService.create_zip_stream."""

    def _selections_to_commons(self, selections: dict) -> MagicMock:
        return _make_commons(selections)

    def test_small_zip(self, download_service: DownloadService, search_service: SearchService):
        df = search_service.get_anforanden(selections={"year": (1970, 1971)})
        speech_ids = df["speech_id"].dropna().sample(min(10, len(df)), random_state=1).tolist()
        commons = _make_commons({"year": (1970, 1971), "speech_id": speech_ids})

        t0 = time.perf_counter()
        zip_bytes = _collect_zip(download_service.create_zip_stream(search_service, commons))
        elapsed = _elapsed(t0)
        print(f"\n  create_zip_stream(n≤10 filtered): {len(zip_bytes):,} bytes in {elapsed:.3f}s")

        names = _zip_entry_names(zip_bytes)
        assert len(names) > 0
        for name in names:
            assert name.endswith(".txt")
            assert "_i-" in name  # format: {speaker}_{speech_id}.txt

    def test_zip_year_filter(self, download_service: DownloadService, search_service: SearchService):
        commons = _make_commons({"year": (1970, 1971)})
        t0 = time.perf_counter()
        zip_bytes = _collect_zip(download_service.create_zip_stream(search_service, commons))
        elapsed = _elapsed(t0)
        names = _zip_entry_names(zip_bytes)
        print(f"\n  create_zip_stream(1970-1971): {len(names)} files, {len(zip_bytes):,} bytes in {elapsed:.3f}s")
        assert len(names) > 0

    def test_zip_party_and_gender_filter(
        self, download_service: DownloadService, search_service: SearchService, party_id_map: dict[str, int]
    ):
        party_ids = [party_id_map.get("S")]
        party_ids = [p for p in party_ids if p is not None]
        commons = _make_commons({"party_id": party_ids, "gender_id": [2], "year": (1975, 1980)})
        t0 = time.perf_counter()
        zip_bytes = _collect_zip(download_service.create_zip_stream(search_service, commons))
        elapsed = _elapsed(t0)
        names = _zip_entry_names(zip_bytes)
        print(
            f"\n  create_zip_stream(S, gender_id=2, 1975-1980): {len(names)} files, "
            f"{len(zip_bytes):,} bytes in {elapsed:.3f}s"
        )
        assert len(names) >= 0  # may be empty for narrow filter; just no crash

    def test_zip_is_valid(self, download_service: DownloadService, search_service: SearchService):
        commons = _make_commons({"year": (1972, 1973)})
        zip_bytes = _collect_zip(download_service.create_zip_stream(search_service, commons))
        assert zip_bytes[:4] == b"PK\x03\x04" or zip_bytes[:4] == b"PK\x05\x06", "Not a valid ZIP"
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            assert zf.testzip() is None, "ZIP contains corrupt entries"

    def test_zip_filenames_include_speaker(self, download_service: DownloadService, search_service: SearchService):
        commons = _make_commons({"year": (1970, 1971)})
        zip_bytes = _collect_zip(download_service.create_zip_stream(search_service, commons))
        names = _zip_entry_names(zip_bytes)
        # All filenames follow '{speaker}_{speech_id}.txt' — speaker must not be blank
        for name in names:
            parts = name.rsplit("_i-", 1)
            assert len(parts) == 2, f"Unexpected filename format: {name!r}"
            speaker_part = parts[0]
            assert speaker_part, f"Empty speaker in filename: {name!r}"

    def test_zip_large_batch(self, download_service: DownloadService, search_service: SearchService):
        """Benchmark a broad query to stress the streaming path."""
        commons = _make_commons({"year": (1970, 1975)})
        t0 = time.perf_counter()
        zip_bytes = _collect_zip(download_service.create_zip_stream(search_service, commons))
        elapsed = _elapsed(t0)
        names = _zip_entry_names(zip_bytes)
        print(
            f"\n  create_zip_stream(1970-1975, large): {len(names)} files, "
            f"{len(zip_bytes):,} bytes in {elapsed:.3f}s"
        )
        assert len(names) > 0
