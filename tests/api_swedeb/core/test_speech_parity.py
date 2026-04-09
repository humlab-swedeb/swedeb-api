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
import os
import random
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
from api_swedeb.legacy.speech_lookup import SpeechTextRepository
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
]

_PARITY_REPORT = Path("tests/output/parity_report.json")
_FULL_CORPUS_PARITY_REPORT = Path("tests/output/parity_report_full_corpus_random_protocol_sample.json")

_FULL_CORPUS_TAGGED_FRAMES = Path(
    os.environ.get(
        "SWEDEB_FULL_CORPUS_TAGGED_FRAMES",
        "/home/roger/source/swedeb/sample-data/data/1867-2020/v1.4.1/tagged_frames",
    )
)
_FULL_CORPUS_BOOTSTRAP_ROOT = Path(
    os.environ.get(
        "SWEDEB_FULL_CORPUS_BOOTSTRAP_ROOT",
        "/home/roger/source/swedeb/sample-data/data/1867-2020/v1.4.1/speeches/bootstrap_corpus",
    )
)
_FULL_CORPUS_DTM_FOLDER = os.environ.get(
    "SWEDEB_FULL_CORPUS_DTM_FOLDER",
    "/home/roger/source/swedeb/sample-data/data/1867-2020/v1.4.1/dtm/text",
)
_FULL_CORPUS_DTM_TAG = os.environ.get("SWEDEB_FULL_CORPUS_DTM_TAG", "text")
_FULL_CORPUS_METADATA_DB = Path(
    os.environ.get(
        "SWEDEB_FULL_CORPUS_METADATA_DB",
        "/home/roger/source/swedeb/sample-data/data/1867-2020/metadata/riksprot_metadata.v1.1.3.db",
    )
)
_FULL_CORPUS_PROTOCOL_SAMPLE_SIZE = int(os.environ.get("SWEDEB_PARITY_PROTOCOL_SAMPLE_SIZE", "400"))
_FULL_CORPUS_SAMPLE_SEED = int(os.environ.get("SWEDEB_PARITY_SAMPLE_SEED", "20260409"))

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
    feather_rel: str = index_row["feather_file"]  # type: ignore[assignment]
    feather_row: int = int(index_row["feather_row"])  # type: ignore[assignment]
    table = protocol_cache.get(feather_rel)
    if table is None:
        return None
    return table.iloc[feather_row].to_dict()  # type: ignore[assignment]


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


def _diff_paragraph_lists(left_paras: list[str], right_paras: list[str]) -> list[str]:
    """Return mismatch descriptions for paragraph lists already materialised as lists."""
    left_stripped = [p.strip() for p in left_paras]
    right_stripped = [p.strip() for p in right_paras]

    diffs = []
    if len(left_stripped) != len(right_stripped):
        diffs.append(
            f"paragraph count: left={len(left_stripped)} right={len(right_stripped)}"
        )
        return diffs

    for i, (left, right) in enumerate(zip(left_stripped, right_stripped)):
        if left != right:
            diffs.append(f"para[{i}] mismatch: left={left[:60]!r} right={right[:60]!r}")

    return diffs


def _sample_protocol_zip_paths(tagged_frames_root: Path, sample_size: int, seed: int) -> list[Path]:
    """Return a deterministic random sample of tagged-frame ZIP files."""
    zip_paths = sorted(tagged_frames_root.rglob("prot-*.zip"))
    if not zip_paths:
        raise FileNotFoundError(f"No prot-*.zip files found under {tagged_frames_root}")
    effective_size = min(sample_size, len(zip_paths))
    return sorted(random.Random(seed).sample(zip_paths, effective_size))


def _write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False, default=str)


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
    sid_to_doc: dict[str, str] = legacy_index.set_index("speech_id")["document_name"].to_dict()   # type: ignore[assignment]

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


@pytest.fixture(scope="module")
def full_corpus_paths() -> dict[str, Path | str]:
    paths: dict[str, Path | str] = {
        "tagged_frames": _FULL_CORPUS_TAGGED_FRAMES,
        "bootstrap_root": _FULL_CORPUS_BOOTSTRAP_ROOT,
        "dtm_folder": _FULL_CORPUS_DTM_FOLDER,
        "metadata_db": _FULL_CORPUS_METADATA_DB,
    }
    missing = [str(path) for path in paths.values() if isinstance(path, Path) and not path.exists()]
    if missing:
        pytest.skip("Full-corpus parity paths are unavailable: " + ", ".join(missing))
    if not Path(_FULL_CORPUS_DTM_FOLDER).exists():
        pytest.skip(f"Full-corpus DTM folder is unavailable: {_FULL_CORPUS_DTM_FOLDER}")
    return paths


@pytest.fixture(scope="module")
def full_corpus_document_index(full_corpus_paths) -> pd.DataFrame:
    return load_speech_index(folder=str(full_corpus_paths["dtm_folder"]), tag=_FULL_CORPUS_DTM_TAG)


@pytest.fixture(scope="module")
def full_corpus_legacy_repository(full_corpus_paths, full_corpus_document_index) -> SpeechTextRepository:
    person_codecs = md.PersonCodecs().load(source=str(full_corpus_paths["metadata_db"]))
    return SpeechTextRepository(
        source=str(full_corpus_paths["tagged_frames"]),
        person_codecs=person_codecs,
        document_index=full_corpus_document_index,
    )


@pytest.fixture(scope="module")
def full_corpus_fast_repository(full_corpus_paths, full_corpus_document_index) -> Any:
    from api_swedeb.core.speech_repository_fast import SpeechRepositoryFast
    from api_swedeb.core.speech_store import SpeechStore

    store = SpeechStore(str(full_corpus_paths["bootstrap_root"]))
    return SpeechRepositoryFast(
        store=store,
        document_index=full_corpus_document_index,
        metadata_db_path=str(full_corpus_paths["metadata_db"]),
    )


@pytest.fixture(scope="module")
def full_corpus_protocol_sample(full_corpus_paths, full_corpus_document_index) -> dict[str, Any]:
    sampled_zip_paths = _sample_protocol_zip_paths(
        Path(full_corpus_paths["tagged_frames"]),
        _FULL_CORPUS_PROTOCOL_SAMPLE_SIZE,
        _FULL_CORPUS_SAMPLE_SEED,
    )
    sampled_protocols = sorted({path.stem for path in sampled_zip_paths})

    protocol_names = full_corpus_document_index["document_name"].astype("string[python]").str.split("_", n=1).str[0]
    sample_index = full_corpus_document_index.loc[protocol_names.isin(sampled_protocols)].copy()
    document_ids = [int(doc_id) for doc_id in sample_index.index.tolist()]

    if not document_ids:
        pytest.fail("Deterministic 400-protocol sample produced no matching speeches in the full-corpus speech index")

    return {
        "zip_paths": [str(path) for path in sampled_zip_paths],
        "protocol_names": sampled_protocols,
        "document_ids": document_ids,
        "document_names": sample_index["document_name"].astype(str).tolist(),
    }


@pytest.fixture(scope="module")
def full_corpus_parity_report(
    full_corpus_legacy_repository: SpeechTextRepository,
    full_corpus_fast_repository,
    full_corpus_protocol_sample: dict[str, Any],
    full_corpus_document_index: pd.DataFrame,

) -> dict[str, Any]:
    """Compute parity report for a deterministic random sample of full-corpus protocols.

    The sample is defined as a set of tagged-frame ZIP files and defaults to
    400 protocols from the full corpus paths under ``sample-data``. All speeches
    in the sampled protocols are compared field-by-field.
    """
    document_ids = full_corpus_protocol_sample["document_ids"]
    sampled_protocols = full_corpus_protocol_sample["protocol_names"]

    logger.info(
        "Full-corpus parity sample: "
        f"protocols={len(sampled_protocols)} speeches={len(document_ids)} "
        f"seed={_FULL_CORPUS_SAMPLE_SEED}"
    )

    fast_results = dict(full_corpus_fast_repository.speeches_batch(document_ids))
    legacy_results = dict(full_corpus_legacy_repository.speeches_batch(document_ids))

    errors: list[dict[str, Any]] = []
    paragraph_mismatches: list[dict[str, Any]] = []
    field_mismatches: list[dict[str, Any]] = []
    enrichment_mismatches: list[dict[str, Any]] = []

    core_fields_to_compare = [
        "speech_id",
        "u_id",
        "who",
        "speaker_note_id",
        "num_tokens",
        "num_words",
        "protocol_name",
        "date",
        "speaker_note",
    ]

    enrichment_fields_to_compare = [
        "name",
        "gender_id",
        "gender",
        "gender_abbrev",
        "party_id",
        "party_abbrev",
        "office_type_id",
        "office_type",
    ]

    for document_id in document_ids:
        row = full_corpus_document_index.loc[int(document_id)]
        document_name = str(row["document_name"])

        fast_speech = fast_results.get(document_id)
        legacy_speech = legacy_results.get(document_id)

        if fast_speech is None or legacy_speech is None:
            errors.append(
                {
                    "document_id": document_id,
                    "document_name": document_name,
                    "error": "missing result from one backend",
                    "fast_present": fast_speech is not None,
                    "legacy_present": legacy_speech is not None,
                }
            )
            continue

        if fast_speech.error or legacy_speech.error:
            errors.append(
                {
                    "document_id": document_id,
                    "document_name": document_name,
                    "fast_error": fast_speech.error,
                    "legacy_error": legacy_speech.error,
                }
            )
            continue

        paragraph_diffs = _diff_paragraph_lists(legacy_speech.paragraphs, fast_speech.paragraphs)
        if paragraph_diffs:
            paragraph_mismatches.append(
                {
                    "document_id": document_id,
                    "document_name": document_name,
                    "diffs": paragraph_diffs,
                }
            )

        diffs: dict[str, dict[str, Any]] = {}
        if _normalise_page(legacy_speech.page_number) != _normalise_page(fast_speech.page_number):
            diffs["page_number"] = {
                "legacy": legacy_speech.page_number,
                "fast": fast_speech.page_number,
            }

        if _normalise_page(legacy_speech.get("page_number2")) != _normalise_page(fast_speech.get("page_number2")):
            diffs["page_number2"] = {
                "legacy": legacy_speech.get("page_number2"),
                "fast": fast_speech.get("page_number2"),
            }

        for field in core_fields_to_compare:
            legacy_value = legacy_speech.get(field)
            fast_value = fast_speech.get(field)
            if legacy_value != fast_value:
                diffs[field] = {"legacy": legacy_value, "fast": fast_value}

        if diffs:
            field_mismatches.append(
                {
                    "document_id": document_id,
                    "document_name": document_name,
                    "diffs": diffs,
                }
            )

        enrichment_diffs: dict[str, dict[str, Any]] = {}
        for field in enrichment_fields_to_compare:
            legacy_value = legacy_speech.get(field)
            fast_value = fast_speech.get(field)
            if legacy_value != fast_value:
                enrichment_diffs[field] = {"legacy": legacy_value, "fast": fast_value}

        if enrichment_diffs:
            enrichment_mismatches.append(
                {
                    "document_id": document_id,
                    "document_name": document_name,
                    "diffs": enrichment_diffs,
                }
            )

    report = {
        "seed": _FULL_CORPUS_SAMPLE_SEED,
        "requested_protocol_sample_size": _FULL_CORPUS_PROTOCOL_SAMPLE_SIZE,
        "actual_protocol_sample_size": len(sampled_protocols),
        "speech_count": len(document_ids),
        "paths": {
            "tagged_frames": str(_FULL_CORPUS_TAGGED_FRAMES),
            "bootstrap_root": str(_FULL_CORPUS_BOOTSTRAP_ROOT),
            "dtm_folder": _FULL_CORPUS_DTM_FOLDER,
            "metadata_db": str(_FULL_CORPUS_METADATA_DB),
        },
        "errors": len(errors),
        "paragraph_mismatches": len(paragraph_mismatches),
        "field_mismatches": len(field_mismatches),
        "enrichment_mismatches": len(enrichment_mismatches),
        "sampled_protocols": sampled_protocols,
        "sampled_zip_paths": full_corpus_protocol_sample["zip_paths"],
        "details": {
            "errors": errors,
            "paragraphs": paragraph_mismatches,
            "fields": field_mismatches,
            "enrichment": enrichment_mismatches,
        },
    }
    _write_report(_FULL_CORPUS_PARITY_REPORT, report)

    return report


@pytest.mark.manual
@pytest.mark.integration
def test_full_corpus_parity_random_protocol_sample(full_corpus_parity_report: dict[str, Any]) -> None:
    """Assert core speech parity for the deterministic random full-corpus sample."""
    errors = full_corpus_parity_report["details"]["errors"]
    paragraph_mismatches = full_corpus_parity_report["details"]["paragraphs"]
    field_mismatches = full_corpus_parity_report["details"]["fields"]
    enrichment_mismatches = full_corpus_parity_report["details"]["enrichment"]

    assert errors == [], (
        f"{len(errors)} sampled speech(es) failed to load:\n"
        + textwrap.indent(json.dumps(errors[:5], indent=2, default=str), "  ")
    )
    assert paragraph_mismatches == [], (
        f"{len(paragraph_mismatches)} sampled speech(es) have paragraph differences:\n"
        + textwrap.indent(json.dumps(paragraph_mismatches[:5], indent=2, default=str), "  ")
    )
    assert field_mismatches == [], (
        f"{len(field_mismatches)} sampled speech(es) have field differences:\n"
        + textwrap.indent(json.dumps(field_mismatches[:5], indent=2, default=str), "  ")
    )

    if enrichment_mismatches:
        logger.warning(
            f"{len(enrichment_mismatches)} sampled speech(es) have enrichment differences "
            f"(reported in {_FULL_CORPUS_PARITY_REPORT}, not a test failure)"
        )


@pytest.mark.manual
@pytest.mark.integration
def test_full_corpus_parity_random_protocol_sample_strict_enrichment(
    full_corpus_parity_report: dict[str, Any],
) -> None:
    """Assert enrichment parity for the deterministic random full-corpus sample."""
    enrichment_mismatches = full_corpus_parity_report["details"]["enrichment"]

    assert enrichment_mismatches == [], (
        f"{len(enrichment_mismatches)} sampled speech(es) have enrichment differences:\n"
        + textwrap.indent(json.dumps(enrichment_mismatches[:5], indent=2, default=str), "  ")
    )
