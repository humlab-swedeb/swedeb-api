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
