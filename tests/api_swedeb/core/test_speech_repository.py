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
    assert len(speech_store._sorted_sids) > 0


def test_speech_store_location_by_speech_id(speech_store):
    """Every speech_id in the lookup must return a valid location."""
    sid = speech_store._sorted_sids[0]
    loc = speech_store.location_for_speech_id(sid)
    assert loc is not None


def test_speech_store_get_row(speech_store):
    """get_row must return a dict with expected keys."""
    sid = speech_store._sorted_sids[0]
    feather_file, feather_row = speech_store.location_for_speech_id(sid)
    row = speech_store.get_row(feather_file, feather_row)
    assert "text" in row
    assert "speech_id" in row
    assert "document_name" in row


def test_speech_store_missing_key(speech_store):
    """Missing speech_id must return None, not raise."""
    assert speech_store.location_for_speech_id("i-NONEXISTENT") is None


# ---------------------------------------------------------------------------
# Scalar lookup regression tests  (searchsorted boundary correctness)
# ---------------------------------------------------------------------------
# These tests guard against the class of bug where np.searchsorted returns an
# in-bounds index whose stored value does NOT match the query — which must be
# treated as "not found", not silently returned as a wrong location.
#
# Boundary cases that can trip a dict → searchsorted migration:
#   - first element (index 0)
#   - last element  (index -1)
#   - a value that sorts before everything  ("\x00…")
#   - a value that sorts after everything   ("\xff…")
#   - a value that falls between two valid entries
# ---------------------------------------------------------------------------


def test_scalar_sid_first_and_last_element(speech_store):
    """location_for_speech_id must find the first and last sorted entries."""
    first_sid = speech_store._sorted_sids[0]
    last_sid = speech_store._sorted_sids[-1]

    loc_first = speech_store.location_for_speech_id(first_sid)
    loc_last = speech_store.location_for_speech_id(last_sid)

    assert loc_first is not None, f"first sid {first_sid!r} not found"
    assert loc_last is not None, f"last sid {last_sid!r} not found"
    assert loc_first[0].endswith(".feather")
    assert loc_last[0].endswith(".feather")
    assert loc_first[1] >= 0
    assert loc_last[1] >= 0


def test_scalar_sid_before_first_returns_none(speech_store):
    """A value lexicographically before the first entry must return None, not a wrong hit."""
    first_sid = speech_store._sorted_sids[0]
    before_first = "\x00" + first_sid  # guaranteed to sort before every real id
    assert speech_store.location_for_speech_id(before_first) is None


def test_scalar_sid_after_last_returns_none(speech_store):
    """A value lexicographically after the last entry must return None, not a wrong hit."""
    last_sid = speech_store._sorted_sids[-1]
    after_last = last_sid + "\xff"  # guaranteed to sort after every real id
    assert speech_store.location_for_speech_id(after_last) is None


def test_scalar_sid_between_entries_returns_none(speech_store):
    """A value that falls between two adjacent entries must return None."""
    if len(speech_store._sorted_sids) < 2:
        pytest.skip("corpus too small for between-entry test")
    a = speech_store._sorted_sids[0]
    b = speech_store._sorted_sids[1]
    # Build something strictly between a and b: extend a with \xff so it sorts
    # after a but — if b doesn't start with the same prefix + higher char — before b.
    candidate = a + "\xff"
    if candidate >= b:
        pytest.skip("adjacent entries too close for synthetic between-value")
    assert speech_store.location_for_speech_id(candidate) is None


def test_scalar_sid_all_entries_found(speech_store):
    """Every speech_id in the index must resolve to a non-None location."""
    for sid in speech_store._sorted_sids:
        loc = speech_store.location_for_speech_id(sid)
        assert loc is not None, f"speech_id {sid!r} unexpectedly not found"


def test_scalar_location_row_is_valid_index(speech_store):
    """Returned feather_row must be a non-negative integer for every entry."""
    for sid in speech_store._sorted_sids:
        loc = speech_store.location_for_speech_id(sid)
        assert loc is not None
        feather_file, feather_row = loc
        assert isinstance(feather_row, int), f"feather_row for {sid!r} is {type(feather_row)}, not int"
        assert feather_row >= 0, f"negative feather_row {feather_row} for {sid!r}"


# ---------------------------------------------------------------------------
# SpeechRepository interface tests
# ---------------------------------------------------------------------------


def test_fast_repo_speech_by_speech_id_from_store(speech_repository, speech_store):
    """speech() must return a valid Speech for a known speech_id."""
    sid = speech_store._sorted_sids[0]
    speech = speech_repository.speech(sid)
    assert isinstance(speech, Speech)
    assert speech.error is None, f"Unexpected error: {speech.error}"
    assert isinstance(speech.text, str)


def test_fast_repo_speech_by_speech_id(speech_repository, speech_store):
    """speech() must resolve an i-* speech_id correctly."""
    sid = speech_store._sorted_sids[0]
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
    valid_speech_id = speech_store._sorted_sids[0]
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
# Vectorized lookup regression tests
# ---------------------------------------------------------------------------
# These tests verify that the vectorized batch methods (locations_for_speech_ids
# and locations_for_document_names) return exactly the same (feather_file, row)
# pairs as the scalar methods, for every combination of found / not-found inputs.
# ---------------------------------------------------------------------------

_VECTOR_SAMPLE = 20  # speeches sampled for cross-validation


def _make_mixed_sid_list(speech_store: SpeechStore, n_valid: int = 10) -> list[str]:
    """Return a list with n_valid real speech_ids interleaved with 3 fake ones."""
    valid = speech_store._sorted_sids[:n_valid].tolist()
    fake = ["i-FAKE-0001", "i-FAKE-0002", "i-FAKE-0003"]
    # interleave so ordering edge-cases are exercised
    result = []
    for i, sid in enumerate(valid):
        result.append(sid)
        if i < len(fake):
            result.append(fake[i])
    return result


def test_vectorized_sids_matches_scalar(speech_store):
    """locations_for_speech_ids must agree with location_for_speech_id for each entry."""
    sample_ids = speech_store._sorted_sids[:_VECTOR_SAMPLE].tolist()
    feather_files, feather_rows, found = speech_store.locations_for_speech_ids(sample_ids)

    assert len(feather_files) == len(sample_ids)
    assert len(feather_rows) == len(sample_ids)
    assert len(found) == len(sample_ids)

    for i, sid in enumerate(sample_ids):
        scalar_loc = speech_store.location_for_speech_id(sid)
        assert found[i], f"speech_id {sid!r} unexpectedly not found in vectorized result"
        assert scalar_loc is not None, f"scalar lookup missed {sid!r}"
        assert str(feather_files[i]) == scalar_loc[0], f"feather_file mismatch for {sid!r}"
        assert int(feather_rows[i]) == scalar_loc[1], f"feather_row mismatch for {sid!r}"


def test_vectorized_sids_not_found(speech_store):
    """locations_for_speech_ids must mark fake speech_ids as not-found."""
    fake_ids = ["i-FAKE-A", "i-FAKE-B", "i-FAKE-C"]
    _, _, found = speech_store.locations_for_speech_ids(fake_ids)
    assert not found.any(), "Expected all fake ids to be not-found"


def test_vectorized_sids_empty_input(speech_store):
    """locations_for_speech_ids with an empty list must return three empty arrays."""
    feather_files, feather_rows, found = speech_store.locations_for_speech_ids([])
    assert len(feather_files) == 0
    assert len(feather_rows) == 0
    assert len(found) == 0


def test_vectorized_sids_mixed_found_and_not_found(speech_store):
    """locations_for_speech_ids must correctly partition found vs not-found in a mixed list."""
    mixed = _make_mixed_sid_list(speech_store, n_valid=10)
    feather_files, feather_rows, found = speech_store.locations_for_speech_ids(mixed)

    assert len(found) == len(mixed)

    for i, sid in enumerate(mixed):
        scalar_loc = speech_store.location_for_speech_id(sid)
        if scalar_loc is None:
            assert not found[i], f"Expected {sid!r} to be not-found in vectorized result"
        else:
            assert found[i], f"Expected {sid!r} to be found in vectorized result"
            assert str(feather_files[i]) == scalar_loc[0]
            assert int(feather_rows[i]) == scalar_loc[1]


# ---------------------------------------------------------------------------
# speeches_text_batch tests
# ---------------------------------------------------------------------------


def test_text_batch_returns_nonempty_strings(speech_repository, speech_store):
    """speeches_text_batch must return non-empty text for every known speech_id."""
    sample_ids = speech_store._sorted_sids[:_VECTOR_SAMPLE].tolist()
    results = dict(speech_repository.speeches_text_batch(sample_ids))

    assert set(results.keys()) == set(sample_ids)
    for sid, text in results.items():
        assert isinstance(text, str), f"text for {sid!r} is not a str"
        assert len(text) > 0, f"text for {sid!r} is unexpectedly empty"


def test_text_batch_unknown_id_yields_empty_string(speech_repository):
    """speeches_text_batch must yield an empty string for an unknown speech_id."""
    results = list(speech_repository.speeches_text_batch(["i-NONEXISTENT-0001"]))
    assert len(results) == 1
    speech_id, text = results[0]
    assert speech_id == "i-NONEXISTENT-0001"
    assert text == ""


def test_text_batch_empty_input(speech_repository):
    """speeches_text_batch with empty input must produce no output."""
    results = list(speech_repository.speeches_text_batch([]))
    assert results == []


def test_text_batch_matches_speech_text(speech_repository, speech_store):
    """speeches_text_batch text must equal Speech.text from speeches_batch for same ids."""
    sample_ids = speech_store._sorted_sids[:_VECTOR_SAMPLE].tolist()

    text_results = dict(speech_repository.speeches_text_batch(sample_ids))
    speech_results = dict(speech_repository.speeches_batch(sample_ids))

    for sid in sample_ids:
        assert sid in text_results
        assert sid in speech_results
        batch_text = text_results[sid]
        speech_text = speech_results[sid].text or ""
        assert batch_text == speech_text, f"Text mismatch for {sid!r}"


# ---------------------------------------------------------------------------
# Performance benchmarks (fast backend only)
# ---------------------------------------------------------------------------

_WARMUP_N = 10
_SAMPLE_N = 50  # scaled to small test corpus


def _sample_speech_ids(speech_store: SpeechStore, n: int) -> list[str]:
    """Return n speech_ids, cycling through the corpus if smaller than n."""
    ids = speech_store._sorted_sids.tolist()
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
    batch_ids = speech_store._sorted_sids.tolist()

    t0 = time.perf_counter()
    results = list(speech_repository.speeches_batch(batch_ids))
    elapsed = time.perf_counter() - t0

    n = len(batch_ids)
    rate = n / elapsed if elapsed > 0 else 0
    print(f"\n--- Batch Retrieval Benchmark ({n} speeches) ---" f"\n  {elapsed*1000:.1f}ms  ({rate:.0f} speeches/sec)")
    assert len(results) == n


def test_benchmark_worker_memory(speech_repository, speech_store):
    """Capture peak process RSS after loading all test speeches."""
    batch_ids = speech_store._sorted_sids.tolist()
    list(speech_repository.speeches_batch(batch_ids))

    rss_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    print(f"\n--- Worker Memory (peak RSS) ---\n  {rss_kb / 1024:.1f} MB")
