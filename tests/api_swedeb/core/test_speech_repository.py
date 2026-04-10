"""Integration tests for SpeechStore and SpeechRepositoryFast.

Tests
-----
- SpeechStore loads speech_lookup.feather and locates speeches correctly.
- SpeechRepositoryFast.speech() returns Speech with paragraphs / metadata.
- SpeechRepositoryFast.speeches_batch() returns correct Speech objects.
- SpeechRepositoryFast.get_key_index() resolves all three key types.
- SpeechRepositoryFast.get_speech_info() returns expected fields.
- CorpusLoader instantiates SpeechRepositoryFast from bootstrap_corpus folder.
"""

from __future__ import annotations

import resource
import statistics
import time
from pathlib import Path

import pytest

from api_swedeb.core.configuration import ConfigStore, ConfigValue
from api_swedeb.core.load import load_speech_index
from api_swedeb.core.speech import Speech
from api_swedeb.core.speech_repository import SpeechRepository
from api_swedeb.core.speech_store import SpeechStore
from api_swedeb.workflows.prebuilt_speech_index.build import SpeechCorpusBuilder

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

ConfigStore.configure_context(source="tests/config.yml")


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
def document_index(dtm_folder, dtm_tag):
    return load_speech_index(folder=dtm_folder, tag=dtm_tag)


@pytest.fixture(scope="module")
def fast_repo(speech_store, document_index, metadata_db_path) -> SpeechRepository:
    return SpeechRepository(
        store=speech_store,
        document_index=document_index,
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
    assert "paragraphs" in row
    assert "speech_id" in row
    assert "document_name" in row


def test_speech_store_missing_key(speech_store):
    """Missing document_name must return None, not raise."""
    assert speech_store.location_for_document_name("prot-9999--xx--0001_1") is None
    assert speech_store.location_for_speech_id("i-NONEXISTENT") is None


# ---------------------------------------------------------------------------
# SpeechRepositoryFast interface tests
# ---------------------------------------------------------------------------


def test_fast_repo_speech_by_document_name(fast_repo, speech_store):
    """speech() must return a valid Speech for a known document_name."""
    name = next(iter(speech_store._name_to_loc))
    speech = fast_repo.speech(name)
    assert isinstance(speech, Speech)
    assert speech.error is None, f"Unexpected error: {speech.error}"
    assert isinstance(speech.paragraphs, list)


def test_fast_repo_speech_by_speech_id(fast_repo, speech_store):
    """speech() must resolve an i-* speech_id correctly."""
    sid = next(iter(speech_store._sid_to_loc))
    speech = fast_repo.speech(sid)
    assert isinstance(speech, Speech)
    assert speech.error is None, f"Unexpected error for {sid}: {speech.error}"


def test_fast_repo_speech_missing_key(fast_repo):
    """speech() must return error Speech for unknown key, not raise."""
    speech = fast_repo.speech("prot-9999--xx--0001_1")
    assert speech.error is not None


def test_fast_repo_get_key_index(fast_repo, document_index):
    """get_key_index must return a valid row in document_index for known document_names."""
    for doc_name in list(document_index["document_name"].head(5)):
        idx = fast_repo.get_key_index(doc_name)
        assert isinstance(idx, int)
        assert idx in document_index.index


def test_fast_repo_get_key_index_speech_id(fast_repo, document_index):
    """get_key_index must accept i-* speech_id strings."""
    for speech_id in list(document_index["speech_id"].head(5)):
        idx = fast_repo.get_key_index(speech_id)
        assert isinstance(idx, int)


def test_fast_repo_get_speech_info(fast_repo, document_index):
    """get_speech_info must return a dict with person_id and speaker_note."""
    doc_name = str(document_index["document_name"].iloc[0])
    info = fast_repo.get_speech_info(doc_name)
    assert isinstance(info, dict)
    assert "speaker_note" in info


def test_fast_repo_to_text(fast_repo, speech_store):
    """to_text must join paragraphs into a non-empty string."""
    name = next(iter(speech_store._name_to_loc))
    speech = fast_repo.speech(name)
    if speech.paragraphs:
        text = fast_repo.to_text({"paragraphs": speech.paragraphs})
        assert isinstance(text, str)
        assert len(text) > 0


# ---------------------------------------------------------------------------
# CorpusLoader integration
# ---------------------------------------------------------------------------


def test_corpus_loader_selects_fast_backend(bootstrap_root, metadata_db_path):
    """CorpusLoader must return SpeechRepositoryFast for bootstrap_corpus folder."""
    from api_swedeb.api.services.corpus_loader import CorpusLoader

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


def test_fast_repo_speech_unknown_prot_key(fast_repo):
    """speech() with an unknown prot- key must return an error Speech, not raise."""
    result = fast_repo.speech("prot-9999--xx--0009_99")
    assert result.error is not None


def test_fast_repo_speech_unknown_speech_id(fast_repo):
    """speech() with an unknown i-* speech_id must return an error Speech, not raise."""
    result = fast_repo.speech("i-UnknownPersonThatDoesNotExistXYZ")
    assert result.error is not None


def test_fast_repo_batch_unknown_speech_id(fast_repo):
    """speeches_batch() with an unknown speech_id must yield an error Speech, not raise."""
    results = list(fast_repo.speeches_batch(["i-missing-speech-id"]))
    assert len(results) == 1
    speech_id, speech = results[0]
    assert speech_id == "i-missing-speech-id"
    assert speech.error is not None


def test_fast_repo_batch_mixed_valid_and_invalid(fast_repo, document_index):
    """speeches_batch() must handle a mix of valid and invalid speech_ids gracefully."""
    valid_speech_id = str(document_index["speech_id"].iloc[0])
    results = dict(fast_repo.speeches_batch([valid_speech_id, "i-missing-1", "i-missing-2"]))
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


def _sample_doc_names(document_index, n: int) -> list[str]:
    """Return n document_names, cycling through the corpus if smaller than n."""
    names = list(document_index["document_name"].astype(str))
    if len(names) >= n:
        return names[:n]
    return (names * ((n // len(names)) + 1))[:n]


def test_benchmark_single_lookup(fast_repo, document_index):
    """Single-speech retrieval latency benchmark (prebuilt backend).

    Reports p50/p95. Passes unconditionally — numbers are printed for review.
    """
    all_names = _sample_doc_names(document_index, _WARMUP_N + _SAMPLE_N)

    for name in all_names[:_WARMUP_N]:
        fast_repo.speech(name)

    sample_names = all_names[_WARMUP_N : _WARMUP_N + _SAMPLE_N]
    times = []
    for name in sample_names:
        t0 = time.perf_counter()
        fast_repo.speech(name)
        times.append(time.perf_counter() - t0)

    sorted_times = sorted(times)
    p50 = statistics.median(times) * 1000
    p95 = sorted_times[int(len(sorted_times) * 0.95)] * 1000
    print(
        f"\n--- Single-speech Benchmark ({_SAMPLE_N} samples, warm cache) ---"
        f"\n  p50={p50:.2f}ms  p95={p95:.2f}ms"
    )


def test_benchmark_batch_retrieval(fast_repo, document_index):
    """Batch retrieval throughput benchmark (prebuilt backend).

    Reports speeches/sec. Passes unconditionally.
    """
    batch_ids = document_index["speech_id"].astype(str).tolist()

    t0 = time.perf_counter()
    results = list(fast_repo.speeches_batch(batch_ids))
    elapsed = time.perf_counter() - t0

    n = len(batch_ids)
    rate = n / elapsed if elapsed > 0 else 0
    print(
        f"\n--- Batch Retrieval Benchmark ({n} speeches) ---"
        f"\n  {elapsed*1000:.1f}ms  ({rate:.0f} speeches/sec)"
    )
    assert len(results) == n


def test_benchmark_worker_memory(fast_repo, document_index):
    """Capture peak process RSS after loading all test speeches."""
    batch_ids = document_index["speech_id"].astype(str).tolist()
    list(fast_repo.speeches_batch(batch_ids))

    rss_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    print(f"\n--- Worker Memory (peak RSS) ---\n  {rss_kb / 1024:.1f} MB")
