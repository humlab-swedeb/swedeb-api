"""Integration tests for SpeechStore and SpeechRepository.

Tests
-----
- SpeechStore loads speech_lookup.feather and locates speeches correctly.
- SpeechRepository.speech() returns Speech with paragraphs / metadata.
- SpeechRepository.speeches_batch() returns correct Speech objects.
- CorpusLoader instantiates SpeechRepository from bootstrap_corpus folder.
"""

from __future__ import annotations

import resource
import statistics
import time
from pathlib import Path

import pytest

from api_swedeb.api.services.corpus_loader import CorpusLoader
from api_swedeb.core.configuration import ConfigValue
from api_swedeb.core.speech import Speech
from api_swedeb.core.speech_repository import SpeechRepository
from api_swedeb.core.speech_store import SpeechStore
from api_swedeb.workflows.prebuilt_speech_index.build import SpeechCorpusBuilder

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# get_config_store().configure_context(source=args.config)

# pylint: disable=redefined-outer-name, protected-access
# ---------------------------------------------------------------------------
# Module-scoped fixtures (build the corpus once)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def tagged_frames_folder() -> str:
    return ConfigValue("vrt.folder").resolve()


@pytest.fixture(scope="module")
def metadata_db_path() -> str:
    return ConfigValue("metadata.filename").resolve()


@pytest.fixture(scope="module")
def dtm_folder() -> str:
    return ConfigValue("dtm.folder").resolve()


@pytest.fixture(scope="module")
def dtm_tag() -> str:
    return ConfigValue("dtm.tag").resolve()


@pytest.fixture(scope="module")
def bootstrap_root(tmp_path_factory, tagged_frames_folder, metadata_db_path) -> Path:
    """Build bootstrap_corpus from test tagged-frames ZIPs into a temp directory."""
    output_root = tmp_path_factory.mktemp("bootstrap_corpus_fast")
    builder = SpeechCorpusBuilder(
        tagged_frames_folder=tagged_frames_folder,
        output_root=str(output_root),
        corpus_version="v1.4.1",
        metadata_version="v1.1.3",
        metadata_db_path=metadata_db_path,
        num_processes=0,
    )
    report = builder.build()
    assert report["failures"] == 0, f"Build failures: {report['failures_detail']}"
    return output_root


@pytest.fixture(scope="module")
def speech_store(bootstrap_root) -> SpeechStore:
    return SpeechStore(str(bootstrap_root))


@pytest.fixture(scope="module")
def speech_repository(speech_store, metadata_db_path) -> SpeechRepository:
    return SpeechRepository(
        store=speech_store,
        metadata_db_path=metadata_db_path,
    )


# ---------------------------------------------------------------------------
# SpeechStore unit tests
# ---------------------------------------------------------------------------


def test_speech_store_loads(speech_store):
    """SpeechStore must index at least one speech."""
    assert len(speech_store._name_to_loc) > 0
    assert len(speech_store._sid_to_loc) > 0


def test_speech_store_location_by_document_name(speech_store):
    """Every document_name in the lookup must return a valid location."""
    name = next(iter(speech_store._name_to_loc))
    loc = speech_store.location_for_document_name(name)
    assert loc is not None
    feather_file, feather_row = loc
    assert feather_file.endswith(".feather")
    assert feather_row >= 0


def test_speech_store_location_by_speech_id(speech_store):
    """Every speech_id in the lookup must return a valid location."""
    sid = next(iter(speech_store._sid_to_loc))
    loc = speech_store.location_for_speech_id(sid)
    assert loc is not None


def test_speech_store_get_row(speech_store):
    """get_row must return a dict with expected keys."""
    name = next(iter(speech_store._name_to_loc))
    feather_file, feather_row = speech_store.location_for_document_name(name)
    row = speech_store.get_row(feather_file, feather_row)
    assert "text" in row
    assert "speech_id" in row
    assert "document_name" in row


def test_speech_store_missing_key(speech_store):
    """Missing document_name must return None, not raise."""
    assert speech_store.location_for_document_name("prot-9999--xx--0001_1") is None
    assert speech_store.location_for_speech_id("i-NONEXISTENT") is None


# ---------------------------------------------------------------------------
# SpeechRepository interface tests
# ---------------------------------------------------------------------------


def test_fast_repo_speech_by_speech_id_from_store(speech_repository, speech_store):
    """speech() must return a valid Speech for a known speech_id."""
    sid = next(iter(speech_store._sid_to_loc))
    speech = speech_repository.speech(sid)
    assert isinstance(speech, Speech)
    assert speech.error is None, f"Unexpected error: {speech.error}"
    assert isinstance(speech.text, str)


def test_fast_repo_speech_by_speech_id(speech_repository, speech_store):
    """speech() must resolve an i-* speech_id correctly."""
    sid = next(iter(speech_store._sid_to_loc))
    speech = speech_repository.speech(sid)
    assert isinstance(speech, Speech)
    assert speech.error is None, f"Unexpected error for {sid}: {speech.error}"


def test_fast_repo_speech_missing_key(speech_repository):
    """speech() must return error Speech for unknown speech_id, not raise."""
    speech = speech_repository.speech("i-nonexistent-9999")
    assert speech.error is not None


# ---------------------------------------------------------------------------
# CorpusLoader integration
# ---------------------------------------------------------------------------


def test_corpus_loader_selects_fast_backend(bootstrap_root, metadata_db_path):
    """CorpusLoader must return SpeechRepository for bootstrap_corpus folder."""

    loader = CorpusLoader(
        dtm_tag=ConfigValue("dtm.tag").resolve(),
        dtm_folder=ConfigValue("dtm.folder").resolve(),
        metadata_filename=metadata_db_path,
        tagged_corpus_folder=ConfigValue("vrt.folder").resolve(),
        speech_bootstrap_corpus_folder=str(bootstrap_root),
    )
    repo = loader.repository
    assert isinstance(repo, SpeechRepository)


# ---------------------------------------------------------------------------
# Reliability and error-condition tests
# ---------------------------------------------------------------------------


def test_store_raises_on_missing_root(tmp_path):
    """SpeechStore must raise FileNotFoundError for a non-existent bootstrap root."""
    with pytest.raises(FileNotFoundError, match="bootstrap_corpus root not found"):
        SpeechStore(str(tmp_path / "nonexistent"))


def test_store_raises_on_missing_lookup(tmp_path):
    """SpeechStore must raise FileNotFoundError when speech_lookup.feather is absent."""
    empty_dir = tmp_path / "empty_bootstrap"
    empty_dir.mkdir()
    with pytest.raises(FileNotFoundError, match="speech_lookup.feather"):
        SpeechStore(str(empty_dir))


def test_fast_repo_speech_unknown_speech_id_nonexistent(speech_repository):
    """speech() with an unknown i-* speech_id must return an error Speech, not raise."""
    result = speech_repository.speech("i-nonexistent-9999-xx")
    assert result.error is not None


def test_fast_repo_speech_unknown_speech_id(speech_repository):
    """speech() with an unknown i-* speech_id must return an error Speech, not raise."""
    result = speech_repository.speech("i-UnknownPersonThatDoesNotExistXYZ")
    assert result.error is not None


def test_fast_repo_batch_unknown_speech_id(speech_repository):
    """speeches_batch() with an unknown speech_id must yield an error Speech, not raise."""
    results = list(speech_repository.speeches_batch(["i-missing-speech-id"]))
    assert len(results) == 1
    speech_id, speech = results[0]
    assert speech_id == "i-missing-speech-id"
    assert speech.error is not None


def test_fast_repo_batch_mixed_valid_and_invalid(speech_repository, speech_store):
    """speeches_batch() must handle a mix of valid and invalid speech_ids gracefully."""
    valid_speech_id = next(iter(speech_store._sid_to_loc))
    results = dict(speech_repository.speeches_batch([valid_speech_id, "i-missing-1", "i-missing-2"]))
    assert valid_speech_id in results
    assert results[valid_speech_id].error is None
    assert results["i-missing-1"].error is not None
    assert results["i-missing-2"].error is not None


def test_store_get_row_missing_feather_file(speech_store):
    """SpeechStore.get_row must raise FileNotFoundError for a missing .feather path."""
    with pytest.raises(FileNotFoundError):
        speech_store.get_row("nonexistent/protocol.feather", 0)


# ---------------------------------------------------------------------------
# Performance benchmarks (fast backend only)
# ---------------------------------------------------------------------------

_WARMUP_N = 10
_SAMPLE_N = 50  # scaled to small test corpus


def _sample_speech_ids(speech_store: SpeechStore, n: int) -> list[str]:
    """Return n speech_ids, cycling through the corpus if smaller than n."""
    ids = list(speech_store._sid_to_loc.keys())
    if len(ids) >= n:
        return ids[:n]
    return (ids * ((n // len(ids)) + 1))[:n]


def test_benchmark_single_lookup(speech_repository, speech_store):
    """Single-speech retrieval latency benchmark (prebuilt backend).

    Reports p50/p95. Passes unconditionally — numbers are printed for review.
    """
    all_ids = _sample_speech_ids(speech_store, _WARMUP_N + _SAMPLE_N)

    for sid in all_ids[:_WARMUP_N]:
        speech_repository.speech(sid)

    sample_ids = all_ids[_WARMUP_N : _WARMUP_N + _SAMPLE_N]
    times = []
    for sid in sample_ids:
        t0 = time.perf_counter()
        speech_repository.speech(sid)
        times.append(time.perf_counter() - t0)

    sorted_times = sorted(times)
    p50 = statistics.median(times) * 1000
    p95 = sorted_times[int(len(sorted_times) * 0.95)] * 1000
    print(
        f"\n--- Single-speech Benchmark ({_SAMPLE_N} samples, warm cache) ---" f"\n  p50={p50:.2f}ms  p95={p95:.2f}ms"
    )


def test_benchmark_batch_retrieval(speech_repository, speech_store):
    """Batch retrieval throughput benchmark (prebuilt backend).

    Reports speeches/sec. Passes unconditionally.
    """
    batch_ids = list(speech_store._sid_to_loc.keys())

    t0 = time.perf_counter()
    results = list(speech_repository.speeches_batch(batch_ids))
    elapsed = time.perf_counter() - t0

    n = len(batch_ids)
    rate = n / elapsed if elapsed > 0 else 0
    print(f"\n--- Batch Retrieval Benchmark ({n} speeches) ---" f"\n  {elapsed*1000:.1f}ms  ({rate:.0f} speeches/sec)")
    assert len(results) == n


def test_benchmark_worker_memory(speech_repository, speech_store):
    """Capture peak process RSS after loading all test speeches."""
    batch_ids = list(speech_store._sid_to_loc.keys())
    list(speech_repository.speeches_batch(batch_ids))

    rss_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    print(f"\n--- Worker Memory (peak RSS) ---\n  {rss_kb / 1024:.1f} MB")
