"""Integration tests for SpeechStore and SpeechRepositoryFast.

Phase 4 acceptance tests: verify that the fast prebuilt backend produces
identical outputs to the legacy SpeechTextRepository for all speeches in
the test corpus.

Tests
-----
- SpeechStore loads speech_lookup.feather and locates speeches correctly.
- SpeechRepositoryFast.speech() returns Speech with paragraphs / metadata.
- SpeechRepositoryFast.speeches_batch() matches legacy batch output.
- SpeechRepositoryFast.get_key_index() resolves all three key types.
- SpeechRepositoryFast.get_speech_info() returns expected fields.
- CorpusLoader selects the fast backend when configured.
"""

from __future__ import annotations

import resource
import statistics
import time
from pathlib import Path

import pytest

from api_swedeb.core import codecs as md
from api_swedeb.core.configuration import ConfigStore, ConfigValue
from api_swedeb.core.load import load_speech_index
from api_swedeb.core.speech import Speech
from api_swedeb.core.speech_repository_fast import SpeechRepositoryFast
from api_swedeb.core.speech_store import SpeechStore
from api_swedeb.core.speech_text import SpeechTextRepository
from api_swedeb.workflows.build_speech_corpus import SpeechCorpusBuilder

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
def fast_repo(speech_store, document_index, metadata_db_path) -> SpeechRepositoryFast:
    return SpeechRepositoryFast(
        store=speech_store,
        document_index=document_index,
        metadata_db_path=metadata_db_path,
    )


@pytest.fixture(scope="module")
def legacy_repo(tagged_frames_folder, metadata_db_path, document_index) -> SpeechTextRepository:
    person_codecs = md.PersonCodecs().load(source=metadata_db_path)
    return SpeechTextRepository(
        source=tagged_frames_folder,
        person_codecs=person_codecs,
        document_index=document_index,
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
# Parity tests: fast backend vs legacy backend
# ---------------------------------------------------------------------------


def test_fast_repo_speech_text_parity(fast_repo, legacy_repo, document_index):
    """Paragraph text must match between fast and legacy backends for all speeches."""
    mismatches: list[dict] = []

    for doc_id in document_index.index:
        doc_name = str(document_index.loc[doc_id, "document_name"])

        fast_speech = fast_repo.speech(doc_name)
        legacy_speech = legacy_repo.speech(doc_name)

        if fast_speech.error or legacy_speech.error:
            if legacy_speech.error:
                continue  # legacy failure — not a fast backend issue
            mismatches.append(
                {
                    "doc_name": doc_name,
                    "fast_error": fast_speech.error,
                    "legacy_error": legacy_speech.error,
                }
            )
            continue

        fast_paras = [p.strip() for p in (fast_speech.paragraphs or [])]
        legacy_paras = [p.strip() for p in (legacy_speech.paragraphs or [])]

        if fast_paras != legacy_paras:
            mismatches.append(
                {
                    "doc_name": doc_name,
                    "fast_paragraphs": fast_paras[:3],
                    "legacy_paragraphs": legacy_paras[:3],
                }
            )

    assert mismatches == [], f"{len(mismatches)} paragraph mismatches:\n" + "\n".join(
        str(m) for m in mismatches[:5]
    )


def test_fast_repo_speeches_batch_parity(fast_repo, legacy_repo, document_index):
    """speeches_batch() must yield the same paragraphs as the legacy backend."""
    doc_ids = list(document_index.index[:50])

    fast_by_id = {doc_id: speech for doc_id, speech in fast_repo.speeches_batch(doc_ids)}
    legacy_by_id = {doc_id: speech for doc_id, speech in legacy_repo.speeches_batch(doc_ids)}

    mismatches: list[str] = []
    for doc_id in doc_ids:
        fast_speech = fast_by_id.get(doc_id)
        legacy_speech = legacy_by_id.get(doc_id)

        if fast_speech is None or legacy_speech is None:
            mismatches.append(f"doc_id={doc_id}: missing in one backend")
            continue

        if fast_speech.error or legacy_speech.error:
            if legacy_speech.error:
                continue
            mismatches.append(f"doc_id={doc_id}: fast error={fast_speech.error}")
            continue

        fast_paras = [p.strip() for p in (fast_speech.paragraphs or [])]
        legacy_paras = [p.strip() for p in (legacy_speech.paragraphs or [])]

        if fast_paras != legacy_paras:
            mismatches.append(f"doc_id={doc_id}: paragraph mismatch")

    assert mismatches == [], f"{len(mismatches)} batch mismatches:\n" + "\n".join(mismatches[:5])


# ---------------------------------------------------------------------------
# CorpusLoader integration: prebuilt backend selection
# ---------------------------------------------------------------------------


def test_corpus_loader_selects_fast_backend(bootstrap_root, document_index, metadata_db_path):
    """CorpusLoader must return SpeechRepositoryFast when storage_backend=prebuilt."""
    from api_swedeb.api.services.corpus_loader import CorpusLoader

    loader = CorpusLoader(
        dtm_tag=ConfigValue("dtm.tag").resolve(),
        dtm_folder=ConfigValue("dtm.folder").resolve(),
        metadata_filename=metadata_db_path,
        tagged_corpus_folder=ConfigValue("vrt.folder").resolve(),
        speech_storage_backend="prebuilt",
        speech_bootstrap_corpus_folder=str(bootstrap_root),
    )
    repo = loader.repository
    assert isinstance(repo, SpeechRepositoryFast)


def test_corpus_loader_selects_legacy_backend():
    """CorpusLoader must return SpeechTextRepository when storage_backend=legacy."""
    from api_swedeb.api.services.corpus_loader import CorpusLoader
    from api_swedeb.core.speech_text import SpeechTextRepository

    loader = CorpusLoader(
        dtm_tag=ConfigValue("dtm.tag").resolve(),
        dtm_folder=ConfigValue("dtm.folder").resolve(),
        metadata_filename=ConfigValue("metadata.filename").resolve(),
        tagged_corpus_folder=ConfigValue("vrt.folder").resolve(),
        speech_storage_backend="legacy",
    )
    repo = loader.repository
    assert isinstance(repo, SpeechTextRepository)


# ===========================================================================
# Phase 5: Extended field-by-field parity tests
# ===========================================================================


def _iter_valid_speech_pairs(fast_repo, legacy_repo, document_index):
    """Yield (doc_name, fast_speech, legacy_speech) for speeches without errors."""
    for doc_id in document_index.index:
        doc_name = str(document_index.loc[doc_id, "document_name"])
        fast = fast_repo.speech(doc_name)
        legacy = legacy_repo.speech(doc_name)
        if fast.error or legacy.error:
            continue
        yield doc_name, fast, legacy


def test_parity_page_numbers(fast_repo, legacy_repo, document_index):
    """page_number (start) and page_number2 (end) must match between backends."""
    mismatches: list[dict] = []
    for doc_name, fast, legacy in _iter_valid_speech_pairs(fast_repo, legacy_repo, document_index):
        if fast.page_number != legacy.page_number:
            mismatches.append(
                {"doc_name": doc_name, "field": "page_number", "fast": fast.page_number, "legacy": legacy.page_number}
            )
        fast_p2 = fast.get("page_number2")
        legacy_p2 = legacy.get("page_number2")
        if fast_p2 != legacy_p2:
            mismatches.append(
                {"doc_name": doc_name, "field": "page_number2", "fast": fast_p2, "legacy": legacy_p2}
            )
    assert mismatches == [], f"{len(mismatches)} page_number mismatches:\n" + "\n".join(str(m) for m in mismatches[:5])


def test_parity_speaker_fields(fast_repo, legacy_repo, document_index):
    """Speaker metadata fields must match between backends for all speeches."""
    fields = ["name", "gender", "gender_abbrev", "party_abbrev", "office_type", "sub_office_type"]
    mismatches_by_field: dict[str, list] = {f: [] for f in fields}

    for doc_name, fast, legacy in _iter_valid_speech_pairs(fast_repo, legacy_repo, document_index):
        for field in fields:
            fast_val = fast.get(field)
            legacy_val = legacy.get(field)
            if fast_val != legacy_val:
                mismatches_by_field[field].append({"doc_name": doc_name, "fast": fast_val, "legacy": legacy_val})

    total = sum(len(v) for v in mismatches_by_field.values())
    if total > 0:
        summary = {f: len(v) for f, v in mismatches_by_field.items() if v}
        examples = {f: v[:2] for f, v in mismatches_by_field.items() if v}
        print(f"\nSpeaker field mismatches: {summary}")
        print(f"Examples: {examples}")
    assert total == 0, f"Speaker field mismatches: {total} total, breakdown: {summary}"


def test_parity_speaker_note(fast_repo, legacy_repo, document_index):
    """speaker_note must match between backends for all speeches."""
    mismatches: list[dict] = []
    for doc_name, fast, legacy in _iter_valid_speech_pairs(fast_repo, legacy_repo, document_index):
        if fast.speaker_note != legacy.speaker_note:
            mismatches.append(
                {
                    "doc_name": doc_name,
                    "fast": (fast.speaker_note or "")[:80],
                    "legacy": (legacy.speaker_note or "")[:80],
                }
            )
    assert mismatches == [], f"{len(mismatches)} speaker_note mismatches:\n" + "\n".join(str(m) for m in mismatches[:3])


def test_parity_protocol_name_and_date(fast_repo, legacy_repo, document_index):
    """protocol_name and date must match between backends."""
    mismatches: list[dict] = []
    for doc_name, fast, legacy in _iter_valid_speech_pairs(fast_repo, legacy_repo, document_index):
        if fast.protocol_name != legacy.protocol_name:
            mismatches.append(
                {"doc_name": doc_name, "field": "protocol_name", "fast": fast.protocol_name, "legacy": legacy.protocol_name}
            )
        if str(fast.get("date")) != str(legacy.get("date")):
            mismatches.append(
                {"doc_name": doc_name, "field": "date", "fast": fast.get("date"), "legacy": legacy.get("date")}
            )
    assert mismatches == [], f"{len(mismatches)} protocol_name/date mismatches:\n" + "\n".join(str(m) for m in mismatches[:5])


def test_parity_full_field_report(fast_repo, legacy_repo, document_index):
    """Generate a comprehensive field-by-field diff summary across all speeches.

    This test always passes — it exists to print the parity report
    (the per-field tests enforce correctness).
    """
    compare_fields = [
        "paragraphs",
        "page_number",
        "page_number2",
        "protocol_name",
        "name",
        "gender",
        "gender_abbrev",
        "party_abbrev",
        "office_type",
        "sub_office_type",
        "speaker_note",
    ]
    counts: dict[str, int] = {f: 0 for f in compare_fields}
    total_compared = 0

    for doc_name, fast, legacy in _iter_valid_speech_pairs(fast_repo, legacy_repo, document_index):
        total_compared += 1
        for field in compare_fields:
            fast_val = fast.get(field) if field != "paragraphs" else fast.paragraphs
            legacy_val = legacy.get(field) if field != "paragraphs" else legacy.paragraphs
            if fast_val != legacy_val:
                counts[field] += 1

    print(f"\n--- Phase 5 Parity Report ({total_compared} speeches) ---")
    for field, mismatch_count in counts.items():
        status = "OK" if mismatch_count == 0 else f"DIFF ({mismatch_count})"
        print(f"  {field:<22} {status}")


# ===========================================================================
# Phase 5: Reliability and error-condition tests
# ===========================================================================


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


def test_fast_repo_batch_unknown_doc_id(fast_repo):
    """speeches_batch() with an out-of-range doc_id must yield an error Speech, not raise."""
    results = list(fast_repo.speeches_batch([999999]))
    assert len(results) == 1
    doc_id, speech = results[0]
    assert doc_id == 999999
    assert speech.error is not None


def test_fast_repo_batch_mixed_valid_and_invalid(fast_repo, document_index):
    """speeches_batch() must handle a mix of valid and invalid doc_ids gracefully."""
    valid_id = int(document_index.index[0])
    results = dict(fast_repo.speeches_batch([valid_id, 999998, 999999]))
    assert valid_id in results
    assert results[valid_id].error is None
    assert results[999998].error is not None
    assert results[999999].error is not None


def test_store_get_row_missing_feather_file(speech_store):
    """SpeechStore.get_row must raise FileNotFoundError for a missing .feather path."""
    with pytest.raises(FileNotFoundError):
        speech_store.get_row("nonexistent/protocol.feather", 0)


# ===========================================================================
# Phase 5: Performance benchmarks
# ===========================================================================

_WARMUP_N = 10
_SAMPLE_N = 50  # scaled to small test corpus


def _sample_doc_names(document_index, n: int) -> list[str]:
    """Return n document_names, cycling through the corpus if smaller than n."""
    names = list(document_index["document_name"].astype(str))
    if len(names) >= n:
        return names[:n]
    return (names * ((n // len(names)) + 1))[:n]


def test_benchmark_single_lookup_comparison(fast_repo, legacy_repo, document_index):
    """Compare single-speech retrieval latency: fast vs legacy.

    Reports p50/p95 for both backends.  Passes unconditionally — the numbers
    are printed so they appear in the captured output for review.
    """
    all_names = _sample_doc_names(document_index, _WARMUP_N + _SAMPLE_N)

    for name in all_names[:_WARMUP_N]:
        fast_repo.speech(name)
        legacy_repo.speech(name)

    sample_names = all_names[_WARMUP_N : _WARMUP_N + _SAMPLE_N]

    fast_times = []
    for name in sample_names:
        t0 = time.perf_counter()
        fast_repo.speech(name)
        fast_times.append(time.perf_counter() - t0)

    legacy_times = []
    for name in sample_names:
        t0 = time.perf_counter()
        legacy_repo.speech(name)
        legacy_times.append(time.perf_counter() - t0)

    fast_sorted = sorted(fast_times)
    legacy_sorted = sorted(legacy_times)
    fast_p50 = statistics.median(fast_times) * 1000
    fast_p95 = fast_sorted[int(len(fast_sorted) * 0.95)] * 1000
    legacy_p50 = statistics.median(legacy_times) * 1000
    legacy_p95 = legacy_sorted[int(len(legacy_sorted) * 0.95)] * 1000

    speedup = legacy_p50 / fast_p50 if fast_p50 > 0 else float("inf")
    print(
        f"\n--- Single-speech Benchmark ({_SAMPLE_N} samples, warm cache) ---"
        f"\n  Fast:   p50={fast_p50:.2f}ms  p95={fast_p95:.2f}ms"
        f"\n  Legacy: p50={legacy_p50:.2f}ms  p95={legacy_p95:.2f}ms"
        f"\n  Speedup (p50): {speedup:.1f}x"
    )


def test_benchmark_batch_retrieval_comparison(fast_repo, legacy_repo, document_index):
    """Compare batch retrieval throughput for the full test corpus.

    Reports speeches/sec for both backends.
    """
    batch_ids = list(document_index.index)

    t0 = time.perf_counter()
    fast_results = list(fast_repo.speeches_batch(batch_ids))
    fast_elapsed = time.perf_counter() - t0

    t0 = time.perf_counter()
    legacy_results = list(legacy_repo.speeches_batch(batch_ids))
    legacy_elapsed = time.perf_counter() - t0

    n = len(batch_ids)
    fast_rate = n / fast_elapsed if fast_elapsed > 0 else 0
    legacy_rate = n / legacy_elapsed if legacy_elapsed > 0 else 0
    speedup = legacy_elapsed / fast_elapsed if fast_elapsed > 0 else float("inf")

    print(
        f"\n--- Batch Retrieval Benchmark ({n} speeches) ---"
        f"\n  Fast:   {fast_elapsed*1000:.1f}ms  ({fast_rate:.0f} speeches/sec)"
        f"\n  Legacy: {legacy_elapsed*1000:.1f}ms  ({legacy_rate:.0f} speeches/sec)"
        f"\n  Speedup: {speedup:.1f}x"
    )
    assert len(fast_results) == len(legacy_results), "Batch result count mismatch between backends"


def test_benchmark_startup_time(tagged_frames_folder, metadata_db_path, dtm_folder, dtm_tag, bootstrap_root):
    """Measure and compare instantiation time for both repository backends."""
    from api_swedeb.core import codecs as md

    di = load_speech_index(folder=dtm_folder, tag=dtm_tag)

    t0 = time.perf_counter()
    store = SpeechStore(str(bootstrap_root))
    fast = SpeechRepositoryFast(store=store, document_index=di, metadata_db_path=metadata_db_path)
    fast_init = time.perf_counter() - t0
    _ = fast.speaker_note_id2note
    fast_with_lazy = time.perf_counter() - t0

    t0 = time.perf_counter()
    person_codecs = md.PersonCodecs().load(source=metadata_db_path)
    legacy = SpeechTextRepository(source=tagged_frames_folder, person_codecs=person_codecs, document_index=di)
    legacy_init = time.perf_counter() - t0
    _ = legacy.speaker_note_id2note
    legacy_with_lazy = time.perf_counter() - t0

    print(
        f"\n--- Startup Time ---"
        f"\n  Fast:   init={fast_init*1000:.1f}ms  with_lazy={fast_with_lazy*1000:.1f}ms"
        f"\n  Legacy: init={legacy_init*1000:.1f}ms  with_lazy={legacy_with_lazy*1000:.1f}ms"
    )


def test_benchmark_worker_memory(fast_repo, legacy_repo, document_index):
    """Capture peak process RSS after loading both backends across all test speeches."""
    batch_ids = list(document_index.index)
    list(fast_repo.speeches_batch(batch_ids))
    list(legacy_repo.speeches_batch(batch_ids))

    rss_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    print(f"\n--- Worker Memory (peak RSS after both backends loaded) ---\n  {rss_kb / 1024:.1f} MB")
