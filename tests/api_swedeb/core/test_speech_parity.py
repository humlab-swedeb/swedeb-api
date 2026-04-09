"""Parity tests: compare enriched bootstrap_corpus output against the legacy
SpeechTextRepository for all speeches in the test tagged-frames corpus.

This test fulfils Phase 3 acceptance criterion:
  "Compare enriched output against current SpeechTextRepository for parity sample"

Field mapping between backends
-------------------------------
Legacy (SpeechTextRepository / _create_speech)  →  Prebuilt (per-protocol feather)
  paragraphs                                     →  paragraphs (JSON-serialised)
  num_tokens                                     →  num_tokens
  num_words                                      →  num_words
  page_number  (start)                           →  page_number_start
  page_number2 (end)                             →  page_number_end
  who                                            →  speaker_id
  u_id  (first utterance)                        →  speech_id
  speaker_note_id                                →  speaker_note_id
  name                                           →  name
  gender / gender_abbrev / gender_id             →  gender / gender_abbrev / gender_id
  party_abbrev / party_id                        →  party_abbrev / party_id
  office_type / office_type_id                   →  office_type / office_type_id
  sub_office_type / sub_office_type_id           →  sub_office_type / sub_office_type_id
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.feather as feather
import pytest
from loguru import logger

from api_swedeb.core import codecs as md
from api_swedeb.core.configuration import ConfigStore, ConfigValue
from api_swedeb.core.load import load_speech_index
from api_swedeb.core.speech_text import SpeechTextRepository
from api_swedeb.workflows.prebuilt_speech_index.build import SpeechCorpusBuilder

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Fields that must match exactly between backends.
_EXACT_FIELDS: list[tuple[str, str]] = [
    ("who", "speaker_id"),
    ("u_id", "speech_id"),
    ("speaker_note_id", "speaker_note_id"),
    ("num_tokens", "num_tokens"),
    ("num_words", "num_words"),
    ("page_number", "page_number_start"),
    ("page_number2", "page_number_end"),
]

# Text content – compared paragraph-by-paragraph (stripped).
_PARAGRAPHS_FIELD = "paragraphs"

# Enrichment fields – compared as equal strings / ints; mismatches are
# reported but do NOT fail the suite (enrichment lookup differences are
# expected between the year-matched prebuilt and the static codec mapping).
_ENRICHMENT_FIELDS: list[tuple[str, str]] = [
    ("name", "name"),
    ("gender_id", "gender_id"),
    ("gender", "gender"),
    ("gender_abbrev", "gender_abbrev"),
    ("party_id", "party_id"),
    ("party_abbrev", "party_abbrev"),
    ("office_type_id", "office_type_id"),
    ("office_type", "office_type"),
    ("sub_office_type_id", "sub_office_type_id"),
    ("sub_office_type", "sub_office_type"),
]

_PARITY_REPORT = Path("tests/output/parity_report.json")

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

ConfigStore.configure_context(source="tests/config.yml")


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
def bootstrap_corpus_root(tmp_path_factory, tagged_frames_folder, metadata_db_path) -> Path:
    """Build bootstrap_corpus from test tagged-frames ZIPs into a temp directory."""
    output_root = tmp_path_factory.mktemp("bootstrap_corpus")
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
def legacy_repository(tagged_frames_folder, metadata_db_path, dtm_folder, dtm_tag) -> SpeechTextRepository:
    """Instantiate the legacy SpeechTextRepository from test data."""
    person_codecs = md.PersonCodecs().load(source=metadata_db_path)
    document_index = load_speech_index(folder=dtm_folder, tag=dtm_tag)
    return SpeechTextRepository(
        source=tagged_frames_folder,
        person_codecs=person_codecs,
        document_index=document_index,
    )


@pytest.fixture(scope="module")
def speech_index_prebuilt(bootstrap_corpus_root: Path) -> pd.DataFrame:
    """Load the global speech_index.feather produced by the builder.

    Indexed by speech_id for fast join with the legacy speech index.
    """
    index_path = bootstrap_corpus_root / "speech_index.feather"
    df = feather.read_feather(str(index_path))
    return df.set_index("speech_id")


@pytest.fixture(scope="module")
def prebuilt_protocol_cache(bootstrap_corpus_root: Path, speech_index_prebuilt: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Pre-load all per-protocol feather files to avoid repeated disk reads."""
    cache: dict[str, pd.DataFrame] = {}
    for feather_rel in speech_index_prebuilt["feather_file"].unique():
        feather_path = bootstrap_corpus_root / feather_rel
        if feather_path.exists():
            cache[feather_rel] = feather.read_feather(str(feather_path))
    return cache


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_prebuilt_row(
    speech_id: str,
    speech_index_prebuilt: pd.DataFrame,
    protocol_cache: dict[str, pd.DataFrame],
) -> dict[str, Any] | None:
    """Return the prebuilt per-speech row for *speech_id*, or None if not found.

    Joins via the speech_index (indexed by speech_id) to locate the feather
    file and row offset, then fetches the full row (including paragraphs) from
    the per-protocol feather.
    """
    if speech_id not in speech_index_prebuilt.index:
        return None
    index_row = speech_index_prebuilt.loc[speech_id]
    feather_rel: str = index_row["feather_file"]
    feather_row: int = int(index_row["feather_row"])
    table = protocol_cache.get(feather_rel)
    if table is None:
        return None
    return table.iloc[feather_row].to_dict()


def _normalise_page(val: Any) -> int:
    """Normalise page-number to int (legacy may return '?' strings)."""
    try:
        return int(val)
    except (ValueError, TypeError):
        return 0


def _diff_paragraphs(legacy_paras: list[str], prebuilt_json: str) -> list[str]:
    """Return a list of mismatch descriptions for paragraph content."""
    try:
        prebuilt_paras: list[str] = json.loads(prebuilt_json) if isinstance(prebuilt_json, str) else prebuilt_json
    except (json.JSONDecodeError, TypeError):
        return ["could not decode prebuilt paragraphs"]

    legacy_stripped = [p.strip() for p in legacy_paras]
    prebuilt_stripped = [p.strip() for p in prebuilt_paras]

    diffs = []
    if len(legacy_stripped) != len(prebuilt_stripped):
        diffs.append(
            f"paragraph count: legacy={len(legacy_stripped)} prebuilt={len(prebuilt_stripped)}"
        )
    else:
        for i, (lp, pp) in enumerate(zip(legacy_stripped, prebuilt_stripped)):
            if lp != pp:
                diffs.append(
                    f"para[{i}] mismatch: legacy={lp[:60]!r} prebuilt={pp[:60]!r}"
                )
    return diffs


# ---------------------------------------------------------------------------
# Main parity test
# ---------------------------------------------------------------------------


def test_speech_parity(
    legacy_repository: SpeechTextRepository,
    speech_index_prebuilt: pd.DataFrame,
    prebuilt_protocol_cache: dict[str, pd.DataFrame],
) -> None:
    """Compare every speech in the prebuilt index against the legacy backend.

    The join key is ``speech_id`` (the u_id of the first utterance in a
    speech chain), which is stable across both systems.  The legacy speech
    index's ``document_name`` column (zero-padded, e.g. ``prot-…_001``) is
    used to drive the legacy retrieval so there is no format-mismatch issue.
    """
    # Load the legacy speech index to get all document_names + speech_ids
    from api_swedeb.core.load import load_speech_index

    legacy_index = load_speech_index(
        folder=ConfigValue("dtm.folder").resolve(),
        tag=ConfigValue("dtm.tag").resolve(),
    )
    # Map speech_id → legacy document_name (zero-padded format used by legacy)
    sid_to_doc: dict[str, str] = legacy_index.set_index("speech_id")["document_name"].to_dict()

    total = len(speech_index_prebuilt)
    logger.info(f"Parity check: {total} prebuilt speeches vs legacy (joined on speech_id)")

    exact_mismatches: list[dict] = []
    enrichment_mismatches: list[dict] = []
    paragraph_mismatches: list[dict] = []
    errors: list[dict] = []

    for speech_id in speech_index_prebuilt.index:
        # --- prebuilt retrieval ---
        prebuilt = _get_prebuilt_row(speech_id, speech_index_prebuilt, prebuilt_protocol_cache)
        if prebuilt is None:
            errors.append({"speech_id": speech_id, "source": "prebuilt", "error": "not found"})
            continue

        # --- resolve legacy document_name ---
        doc_name = sid_to_doc.get(speech_id)
        if doc_name is None:
            errors.append({"speech_id": speech_id, "source": "legacy", "error": "speech_id not in legacy index"})
            continue

        # --- legacy retrieval ---
        try:
            legacy_speech = legacy_repository.speech(doc_name)
        except Exception as exc:  # pylint: disable=broad-except
            errors.append({"speech_id": speech_id, "document_name": doc_name, "source": "legacy", "error": str(exc)})
            continue

        if legacy_speech.error:
            errors.append({"speech_id": speech_id, "document_name": doc_name, "source": "legacy", "error": legacy_speech.error})
            continue

        legacy: dict = legacy_speech._data  # type: ignore[attr-defined]

        # --- exact field comparison ---
        exact_diffs: dict[str, dict] = {}
        for legacy_key, prebuilt_key in _EXACT_FIELDS:
            lval = legacy.get(legacy_key)
            pval = prebuilt.get(prebuilt_key)

            # Normalise page numbers
            if legacy_key in ("page_number", "page_number2"):
                lval = _normalise_page(lval)
                pval = _normalise_page(pval)

            if lval != pval:
                exact_diffs[legacy_key] = {"legacy": lval, "prebuilt": pval}

        if exact_diffs:
            exact_mismatches.append({"speech_id": speech_id, "document_name": doc_name, "diffs": exact_diffs})

        # --- paragraph comparison ---
        para_diffs = _diff_paragraphs(
            legacy.get("paragraphs", []),
            prebuilt.get("paragraphs", "[]"),
        )
        if para_diffs:
            paragraph_mismatches.append({"speech_id": speech_id, "document_name": doc_name, "diffs": para_diffs})

        # --- enrichment comparison (informational) ---
        enr_diffs: dict[str, dict] = {}
        for legacy_key, prebuilt_key in _ENRICHMENT_FIELDS:
            lval = legacy.get(legacy_key)
            pval = prebuilt.get(prebuilt_key)
            if lval != pval:
                enr_diffs[legacy_key] = {"legacy": lval, "prebuilt": pval}

        if enr_diffs:
            enrichment_mismatches.append({"speech_id": speech_id, "document_name": doc_name, "diffs": enr_diffs})

    # --- write parity report ---
    _PARITY_REPORT.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "total": total,
        "errors": len(errors),
        "exact_mismatches": len(exact_mismatches),
        "paragraph_mismatches": len(paragraph_mismatches),
        "enrichment_mismatches": len(enrichment_mismatches),
        "details": {
            "errors": errors,
            "exact": exact_mismatches,
            "paragraphs": paragraph_mismatches,
            "enrichment": enrichment_mismatches,
        },
    }
    with open(_PARITY_REPORT, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False, default=str)
    logger.info(
        f"Parity report written to {_PARITY_REPORT} — "
        f"total={total}, errors={len(errors)}, "
        f"exact_mismatches={len(exact_mismatches)}, "
        f"para_mismatches={len(paragraph_mismatches)}, "
        f"enrichment_mismatches={len(enrichment_mismatches)}"
    )

    # --- assertions ---
    # Errors: no speech should fail to load on either backend
    assert errors == [], (
        f"{len(errors)} speech(es) could not be loaded:\n"
        + textwrap.indent(json.dumps(errors[:5], indent=2, default=str), "  ")
    )

    # Structure/content: paragraphs and core counters must match exactly
    assert paragraph_mismatches == [], (
        f"{len(paragraph_mismatches)} speech(es) have paragraph content differences:\n"
        + textwrap.indent(json.dumps(paragraph_mismatches[:5], indent=2, default=str), "  ")
    )
    assert exact_mismatches == [], (
        f"{len(exact_mismatches)} speech(es) have exact-field mismatches:\n"
        + textwrap.indent(json.dumps(exact_mismatches[:5], indent=2, default=str), "  ")
    )

    # Enrichment mismatches are reported but not hard-failed (the two lookups
    # differ in how they resolve office_type for a given year, so some
    # divergence is expected).
    if enrichment_mismatches:
        logger.warning(
            f"{len(enrichment_mismatches)}/{total} speeches have enrichment differences "
            f"(not a test failure — see {_PARITY_REPORT})"
        )
