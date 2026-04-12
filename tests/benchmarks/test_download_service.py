"""Integration benchmarks and correctness tests for DownloadService.

Run benchmarks with::

    pytest tests/benchmarks/ -m benchmark --benchmark-only -v
"""

from __future__ import annotations

import gzip
import io
import json
import tarfile
import zipfile
from typing import Any, Generator
from unittest.mock import MagicMock, patch

import pytest

from api_swedeb.api.services.corpus_loader import CorpusLoader
from api_swedeb.api.services.download_service import (
    DownloadService,
    JsonlGzCompressionStrategy,
    TarGzCompressionStrategy,
    ZipCompressionStrategy,
)
from api_swedeb.api.services.search_service import SearchService
from api_swedeb.core.configuration import Config, ConfigStore

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


def _make_commons(selections: dict[str, Any]) -> MagicMock:
    """Build a minimal CommonParams-like mock that returns *selections* from get_filter_opts."""
    mock = MagicMock()
    mock.get_filter_opts.return_value = selections
    return mock


def _collect(generator) -> bytes:
    """Drain a streaming generator and return the raw bytes."""
    return b"".join(generator())


def _collect_zip(generator) -> bytes:
    """Drain a streaming generator and return the assembled ZIP bytes."""
    return _collect(generator)


def _collect_tar_gz(generator) -> dict[str, str]:
    """Drain a tar.gz generator and return {filename: text} entries."""
    raw = _collect(generator)
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as tf:
        return {
            m.name: tf.extractfile(m).read().decode("utf-8")  # type: ignore[union-attr]
            for m in tf.getmembers()
            if m.isfile()
        }


def _collect_jsonl_gz(generator) -> list[dict]:
    """Drain a jsonl.gz generator and return a list of parsed records."""
    raw = _collect(generator)
    with gzip.open(io.BytesIO(raw), "rt", encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _zip_entry_names(zip_bytes: bytes) -> list[str]:
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        return zf.namelist()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def corpus_loader() -> CorpusLoader:
    loader: CorpusLoader = CorpusLoader()
    # _ = loader.vectorized_corpus
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
    return DownloadService(ZipCompressionStrategy())


@pytest.fixture(scope="module")
def tar_gz_download_service(config_store) -> DownloadService:
    return DownloadService(TarGzCompressionStrategy())


@pytest.fixture(scope="module")
def jsonl_gz_download_service(config_store) -> DownloadService:
    return DownloadService(JsonlGzCompressionStrategy())


@pytest.fixture(scope="module")
def party_id_map(config_store, corpus_loader: CorpusLoader) -> dict[str, int]:
    return corpus_loader.person_codecs.get_mapping("party_abbrev", "party_id")


# ---------------------------------------------------------------------------
# get_anforanden benchmarks
# ---------------------------------------------------------------------------


class TestGetAnforanden:
    """Correctness and performance tests for SearchService.get_anforanden."""

    def test_no_filter_returns_all(self, search_service: SearchService, benchmark):
        df = benchmark(search_service.get_speeches, selections={})
        assert len(df) > 0
        assert "speech_id" in df.columns
        assert "name" in df.columns

    def test_year_range_filter(self, search_service: SearchService, benchmark):
        df = benchmark(search_service.get_speeches, selections={"year": (1970, 1975)})
        assert len(df) > 0
        assert df["year"].between(1970, 1975).all()

    def test_party_filter(self, search_service: SearchService, party_id_map: dict[str, int], benchmark):
        party_ids = [p for p in [party_id_map.get("S"), party_id_map.get("M")] if p is not None]
        df = benchmark(search_service.get_speeches, selections={"party_id": party_ids, "year": (1970, 1990)})
        assert len(df) > 0
        assert set(df["party_abbrev"].unique()).issubset({"S", "M", "?"})

    def test_gender_filter(self, search_service: SearchService, benchmark):
        df = benchmark(search_service.get_speeches, selections={"gender_id": [2], "year": (1970, 1990)})
        assert len(df) > 0

    def test_combined_filter(self, search_service: SearchService, party_id_map: dict[str, int], benchmark):
        party_ids = [p for p in [party_id_map.get("S")] if p is not None]
        selections = {"party_id": party_ids, "gender_id": [1, 2], "year": (1960, 1970)}
        df = benchmark(search_service.get_speeches, selections=selections)
        assert len(df) > 0

    def test_result_has_required_columns(self, search_service: SearchService):
        df = search_service.get_speeches(selections={"year": (1970, 1971)})
        required = {"speech_id", "document_name", "name", "year", "party_abbrev", "gender", "speech_link", "link"}
        missing = required - set(df.columns)
        assert not missing, f"Missing columns: {missing}"

    def test_large_year_range(self, search_service: SearchService, benchmark):
        """Benchmark a broad query that returns a large result set."""
        df = benchmark(search_service.get_speeches, selections={"year": (1960, 2000)})
        assert len(df) > 0


# ---------------------------------------------------------------------------
# get_speeches_batch benchmarks
# ---------------------------------------------------------------------------


class TestGetSpeechesBatch:
    """Correctness and performance tests for SearchService.get_speeches_batch."""

    def _sample_speech_ids(self, search_service: SearchService, n: int, year_range: tuple) -> list[str]:
        df = search_service.get_speeches(selections={"year": year_range})
        available = df["speech_id"].dropna()
        return available.sample(min(n, len(available)), random_state=42).tolist()

    def test_small_batch(self, search_service: SearchService, benchmark):
        ids = self._sample_speech_ids(search_service, 10, (1970, 1975))
        results = benchmark(lambda: list(search_service.get_speeches_batch(ids)))
        assert len(results) == 10
        for speech_id, speech in results:
            assert speech_id.startswith("i-")
            assert speech is not None

    def test_medium_batch(self, search_service: SearchService, benchmark):
        ids = self._sample_speech_ids(search_service, 100, (1970, 1980))
        results = benchmark(lambda: list(search_service.get_speeches_batch(ids)))
        assert len(results) == 100

    def test_large_batch(self, search_service: SearchService, benchmark):
        ids = self._sample_speech_ids(search_service, 500, (1970, 1990))
        results = benchmark(lambda: list(search_service.get_speeches_batch(ids)))
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

    def test_batch_across_protocols(self, search_service: SearchService, benchmark):
        """IDs from many different protocols — tests feather file grouping path."""
        ids = self._sample_speech_ids(search_service, 200, (1960, 2000))
        results = benchmark(lambda: list(search_service.get_speeches_batch(ids)))
        assert len(results) == 200


# ---------------------------------------------------------------------------
# create_zip_stream benchmarks
# ---------------------------------------------------------------------------


class TestCreateZipStream:
    """Correctness and performance tests for DownloadService.create_zip_stream."""

    def _selections_to_commons(self, selections: dict) -> MagicMock:
        return _make_commons(selections)

    def test_small_zip(self, download_service: DownloadService, search_service: SearchService, benchmark):
        df = search_service.get_speeches(selections={"year": (1970, 1971)})
        speech_ids = df["speech_id"].dropna().sample(min(10, len(df)), random_state=1).tolist()
        commons = _make_commons({"year": (1970, 1971), "speech_id": speech_ids})
        zip_bytes = benchmark(lambda: _collect_zip(download_service.create_stream(search_service, commons)))
        names = _zip_entry_names(zip_bytes)
        assert len(names) > 0
        for name in names:
            assert name.endswith(".txt")
            assert "_i-" in name  # format: {speaker}_{speech_id}.txt

    def test_zip_year_filter(self, download_service: DownloadService, search_service: SearchService, benchmark):
        commons = _make_commons({"year": (1970, 1971)})
        zip_bytes = benchmark(lambda: _collect_zip(download_service.create_stream(search_service, commons)))
        assert len(_zip_entry_names(zip_bytes)) > 0

    def test_zip_party_and_gender_filter(
        self, download_service: DownloadService, search_service: SearchService, party_id_map: dict[str, int], benchmark
    ):
        party_ids = [p for p in [party_id_map.get("S")] if p is not None]
        commons = _make_commons({"party_id": party_ids, "gender_id": [2], "year": (1975, 1980)})
        benchmark(lambda: _collect_zip(download_service.create_stream(search_service, commons)))
        # no crash is sufficient for a narrow filter

    def test_zip_is_valid(self, download_service: DownloadService, search_service: SearchService):
        commons = _make_commons({"year": (1972, 1973)})
        zip_bytes = _collect_zip(download_service.create_stream(search_service, commons))
        assert zip_bytes[:4] == b"PK\x03\x04" or zip_bytes[:4] == b"PK\x05\x06", "Not a valid ZIP"
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            assert zf.testzip() is None, "ZIP contains corrupt entries"

    def test_zip_filenames_include_speaker(self, download_service: DownloadService, search_service: SearchService):
        commons = _make_commons({"year": (1970, 1971)})
        zip_bytes = _collect_zip(download_service.create_stream(search_service, commons))
        names = _zip_entry_names(zip_bytes)
        # All filenames follow '{speaker}_{speech_id}.txt' — speaker must not be blank
        for name in names:
            parts = name.rsplit("_i-", 1)
            assert len(parts) == 2, f"Unexpected filename format: {name!r}"
            speaker_part = parts[0]
            assert speaker_part, f"Empty speaker in filename: {name!r}"

    def test_zip_large_batch(self, download_service: DownloadService, search_service: SearchService, benchmark):
        """Benchmark a broad query to stress the streaming path."""
        commons = _make_commons({"year": (1970, 1980)})
        zip_bytes = benchmark(lambda: _collect_zip(download_service.create_stream(search_service, commons)))
        assert len(_zip_entry_names(zip_bytes)) > 0


# ---------------------------------------------------------------------------
# TarGzCompressionStrategy benchmarks
# ---------------------------------------------------------------------------


class TestTarGzCompressionStrategy:
    """Correctness and performance tests for TarGzCompressionStrategy."""

    def test_small_batch(self, tar_gz_download_service: DownloadService, search_service: SearchService, benchmark):
        df = search_service.get_speeches(selections={"year": (1970, 1971)})
        speech_ids = df["speech_id"].dropna().sample(min(10, len(df)), random_state=1).tolist()
        commons = _make_commons({"year": (1970, 1971), "speech_id": speech_ids})
        entries = benchmark(lambda: _collect_tar_gz(tar_gz_download_service.create_stream(search_service, commons)))
        assert len(entries) > 0
        for name in entries:
            assert name.endswith(".txt")
            assert "_i-" in name

    def test_year_filter(self, tar_gz_download_service: DownloadService, search_service: SearchService, benchmark):
        commons = _make_commons({"year": (1970, 1971)})
        entries = benchmark(lambda: _collect_tar_gz(tar_gz_download_service.create_stream(search_service, commons)))
        assert len(entries) > 0

    def test_is_valid_tar_gz(self, tar_gz_download_service: DownloadService, search_service: SearchService):
        commons = _make_commons({"year": (1972, 1973)})
        raw = _collect(tar_gz_download_service.create_stream(search_service, commons))
        # gzip magic bytes
        assert raw[:2] == b"\x1f\x8b", "Not a valid gzip stream"
        with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as tf:
            members = tf.getmembers()
        assert len(members) > 0

    def test_text_content_is_accessible(self, tar_gz_download_service: DownloadService, search_service: SearchService):
        commons = _make_commons({"year": (1972, 1972)})
        entries = _collect_tar_gz(tar_gz_download_service.create_stream(search_service, commons))
        # At least some entries should contain non-empty text
        non_empty = [v for v in entries.values() if v.strip()]
        assert len(non_empty) > 0, "No non-empty speech texts in tar.gz"

    def test_party_and_gender_filter(
        self,
        tar_gz_download_service: DownloadService,
        search_service: SearchService,
        party_id_map: dict[str, int],
        benchmark,
    ):
        party_ids = [p for p in [party_id_map.get("S")] if p is not None]
        commons = _make_commons({"party_id": party_ids, "gender_id": [2], "year": (1975, 1980)})
        benchmark(lambda: _collect_tar_gz(tar_gz_download_service.create_stream(search_service, commons)))

    def test_large_batch(self, tar_gz_download_service: DownloadService, search_service: SearchService, benchmark):
        """Benchmark a broad query to stress the tar.gz streaming path."""
        commons = _make_commons({"year": (1970, 1980)})
        entries = benchmark(lambda: _collect_tar_gz(tar_gz_download_service.create_stream(search_service, commons)))
        assert len(entries) > 0


# ---------------------------------------------------------------------------
# JsonlGzCompressionStrategy benchmarks
# ---------------------------------------------------------------------------


class TestJsonlGzCompressionStrategy:
    """Correctness and performance tests for JsonlGzCompressionStrategy."""

    def test_small_batch(self, jsonl_gz_download_service: DownloadService, search_service: SearchService, benchmark):
        df = search_service.get_speeches(selections={"year": (1970, 1971)})
        speech_ids = df["speech_id"].dropna().sample(min(10, len(df)), random_state=1).tolist()
        commons = _make_commons({"year": (1970, 1971), "speech_id": speech_ids})
        records = benchmark(lambda: _collect_jsonl_gz(jsonl_gz_download_service.create_stream(search_service, commons)))
        assert len(records) > 0
        for rec in records:
            assert "speech_id" in rec
            assert "speaker" in rec
            assert "text" in rec

    def test_year_filter(self, jsonl_gz_download_service: DownloadService, search_service: SearchService, benchmark):
        commons = _make_commons({"year": (1970, 1971)})
        records = benchmark(lambda: _collect_jsonl_gz(jsonl_gz_download_service.create_stream(search_service, commons)))
        assert len(records) > 0

    def test_is_valid_gzip(self, jsonl_gz_download_service: DownloadService, search_service: SearchService):
        commons = _make_commons({"year": (1972, 1973)})
        raw = _collect(jsonl_gz_download_service.create_stream(search_service, commons))
        assert raw[:2] == b"\x1f\x8b", "Not a valid gzip stream"
        with gzip.open(io.BytesIO(raw), "rt", encoding="utf-8") as fh:
            lines = [x for x in fh if x.strip()]
        assert len(lines) > 0

    def test_records_are_valid_json(self, jsonl_gz_download_service: DownloadService, search_service: SearchService):
        commons = _make_commons({"year": (1972, 1972)})
        records = _collect_jsonl_gz(jsonl_gz_download_service.create_stream(search_service, commons))
        required_keys = {"speech_id", "speaker", "text"}
        for rec in records:
            assert required_keys <= rec.keys(), f"Record missing keys: {rec.keys()}"
            assert isinstance(rec["speech_id"], str)
            assert isinstance(rec["speaker"], str)
            assert isinstance(rec["text"], str)

    def test_speech_ids_match_query(self, jsonl_gz_download_service: DownloadService, search_service: SearchService):
        """speech_id values in JSONL records match what get_anforanden returns."""
        commons = _make_commons({"year": (1970, 1971)})
        df = search_service.get_speeches(selections={"year": (1970, 1971)})
        expected_ids = set(df["speech_id"].dropna().tolist())
        records = _collect_jsonl_gz(jsonl_gz_download_service.create_stream(search_service, commons))
        returned_ids = {r["speech_id"] for r in records}
        assert returned_ids == expected_ids

    def test_party_and_gender_filter(
        self,
        jsonl_gz_download_service: DownloadService,
        search_service: SearchService,
        party_id_map: dict[str, int],
        benchmark,
    ):
        party_ids = [p for p in [party_id_map.get("S")] if p is not None]
        commons = _make_commons({"party_id": party_ids, "gender_id": [2], "year": (1975, 1980)})
        benchmark(lambda: _collect_jsonl_gz(jsonl_gz_download_service.create_stream(search_service, commons)))

    def test_large_batch(self, jsonl_gz_download_service: DownloadService, search_service: SearchService, benchmark):
        """Benchmark a broad query to stress the jsonl.gz streaming path."""
        commons = _make_commons({"year": (1970, 1980)})
        records = benchmark(lambda: _collect_jsonl_gz(jsonl_gz_download_service.create_stream(search_service, commons)))
        assert len(records) > 0


# ---------------------------------------------------------------------------
# Cross-strategy comparison benchmarks
# ---------------------------------------------------------------------------


class TestStrategyComparison:
    """Head-to-head benchmarks of all three compression strategies on the same data."""

    def test_zip_strategy(self, search_service: SearchService, benchmark):
        """Baseline ZIP performance."""
        svc = DownloadService(ZipCompressionStrategy())
        commons = _make_commons({"year": (1970, 1975)})
        result = benchmark(lambda: _collect(svc.create_stream(search_service, commons)))
        assert len(result) > 0

    def test_tar_gz_strategy(self, search_service: SearchService, benchmark):
        """Comparison: tar.gz performance on the same query."""
        svc = DownloadService(TarGzCompressionStrategy())
        commons = _make_commons({"year": (1970, 1975)})
        result = benchmark(lambda: _collect(svc.create_stream(search_service, commons)))
        assert len(result) > 0

    def test_jsonl_gz_strategy(self, search_service: SearchService, benchmark):
        """Comparison: jsonl.gz performance on the same query."""
        svc = DownloadService(JsonlGzCompressionStrategy())
        commons = _make_commons({"year": (1970, 1975)})
        result = benchmark(lambda: _collect(svc.create_stream(search_service, commons)))
        assert len(result) > 0

    def test_output_sizes(self, search_service: SearchService):
        """Compare compressed output sizes across strategies for the same dataset."""
        commons = _make_commons({"year": (1970, 1971)})

        zip_bytes = _collect(DownloadService(ZipCompressionStrategy()).create_stream(search_service, commons))
        tgz_bytes = _collect(DownloadService(TarGzCompressionStrategy()).create_stream(search_service, commons))
        jgz_bytes = _collect(DownloadService(JsonlGzCompressionStrategy()).create_stream(search_service, commons))

        # All formats must produce non-empty output
        assert len(zip_bytes) > 0
        assert len(tgz_bytes) > 0
        assert len(jgz_bytes) > 0

        # Log sizes for manual inspection (visible with pytest -s)
        print("\nOutput sizes for year=(1970,1971):")
        print(f"  ZIP:     {len(zip_bytes):>10,} bytes")
        print(f"  tar.gz:  {len(tgz_bytes):>10,} bytes")
        print(f"  jsonl.gz:{len(jgz_bytes):>10,} bytes")
