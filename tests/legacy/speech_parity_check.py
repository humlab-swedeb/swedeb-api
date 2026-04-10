"""Standalone CLI: parity check of the full corpus.

Compares the prebuilt bootstrap_corpus speech backend against the legacy
SpeechTextRepository for a deterministic random sample of protocols.

Field mapping between backends
-------------------------------
Legacy (SpeechTextRepository / _create_speech)  →  Prebuilt (SpeechRepositoryFast)
  paragraphs                                     →  paragraphs
  num_tokens                                     →  num_tokens
  num_words                                      →  num_words
  page_number  (start)                           →  page_number
  page_number2 (end)                             →  page_number2
  who                                            →  who
  u_id  (first utterance)                        →  u_id / speech_id
  speaker_note_id                                →  speaker_note_id
  name                                           →  name
  gender / gender_abbrev / gender_id             →  gender / gender_abbrev / gender_id
  party_abbrev / party_id                        →  party_abbrev / party_id
  office_type / office_type_id                   →  office_type / office_type_id
  sub_office_type / sub_office_type_id           →  sub_office_type / sub_office_type_id

Usage
-----
    python tests/legacy/speech_parity_check.py

Environment variables (with defaults matching the sample-data checkout):
    SWEDEB_FULL_CORPUS_TAGGED_FRAMES       path to tagged_frames folder
    SWEDEB_FULL_CORPUS_BOOTSTRAP_ROOT      path to bootstrap_corpus folder
    SWEDEB_FULL_CORPUS_DTM_FOLDER          path to dtm/text folder
    SWEDEB_FULL_CORPUS_DTM_TAG             dtm tag (default: text)
    SWEDEB_FULL_CORPUS_METADATA_DB         path to riksprot_metadata .db file
    SWEDEB_PARITY_PROTOCOL_SAMPLE_SIZE     number of protocols to sample (0 = all)
    SWEDEB_PARITY_SAMPLE_SEED              random seed for sampling

The report is written to tests/output/parity_report_full_corpus_random_protocol_sample.json
"""

from __future__ import annotations

import json
import os
import random
import sys
import textwrap
from pathlib import Path
from typing import Any

from loguru import logger

from api_swedeb.core import codecs as md
from api_swedeb.core.load import load_speech_index
from api_swedeb.core.speech_repository_fast import SpeechRepositoryFast
from api_swedeb.core.speech_store import SpeechStore
from api_swedeb.legacy.speech_lookup import SpeechTextRepository

from tqdm import tqdm

# ---------------------------------------------------------------------------
# Configuration — all overridable via environment variables
# ---------------------------------------------------------------------------

_FULL_CORPUS_TAGGED_FRAMES = Path("/home/roger/source/swedeb/sample-data/data/1867-2020/v1.4.1/tagged_frames")
_FULL_CORPUS_BOOTSTRAP_ROOT = Path("/home/roger/source/swedeb/sample-data/data/1867-2020/v1.4.1/speeches/bootstrap_corpus")
_FULL_CORPUS_DTM_FOLDER = "/home/roger/source/swedeb/sample-data/data/1867-2020/v1.4.1/dtm/text"
_FULL_CORPUS_DTM_TAG = "text" # os.environ.get("SWEDEB_FULL_CORPUS_DTM_TAG", "text")
_FULL_CORPUS_METADATA_DB = Path("/home/roger/source/swedeb/sample-data/data/1867-2020/metadata/riksprot_metadata.v1.1.3.db")
_FULL_CORPUS_PROTOCOL_SAMPLE_SIZE = 0
_FULL_CORPUS_SAMPLE_SEED = int(os.environ.get("SWEDEB_PARITY_SAMPLE_SEED", "20260409"))
_REPORT_PATH = Path("tests/output/parity_report_full_corpus_random_protocol_sample.json")

# ---------------------------------------------------------------------------
# Fields
# ---------------------------------------------------------------------------

_CORE_FIELDS_TO_COMPARE = [
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

_ENRICHMENT_FIELDS_TO_COMPARE = [
    "name",
    "gender_id",
    "gender",
    "gender_abbrev",
    "party_id",
    "party_abbrev",
    "office_type_id",
    "office_type",
]

# ---------------------------------------------------------------------------
# Helpers (used by the full-corpus comparison path only)
# ---------------------------------------------------------------------------


def _normalise_page(val: Any) -> int:
    try:
        return int(val)
    except (ValueError, TypeError):
        return 0


def _diff_paragraph_lists(left_paras: list[str], right_paras: list[str]) -> list[str]:
    left_stripped = [p.strip() for p in left_paras]
    right_stripped = [p.strip() for p in right_paras]

    diffs = []
    if len(left_stripped) != len(right_stripped):
        diffs.append(f"paragraph count: left={len(left_stripped)} right={len(right_stripped)}")
        return diffs

    for i, (left, right) in enumerate(zip(left_stripped, right_stripped)):
        if left != right:
            diffs.append(f"para[{i}] mismatch: left={left[:60]!r} right={right[:60]!r}")

    return diffs


def _sample_protocol_zip_paths(tagged_frames_root: Path, sample_size: int, seed: int) -> list[Path]:
    """Return a deterministic random sample of tagged-frame ZIP files."""
    zip_paths = sorted(tagged_frames_root.rglob("prot-*.zip"))

    if sample_size == 0:
        logger.info("Sample size is 0, using all {} protocol ZIP files.", len(zip_paths))
        return zip_paths

    if not zip_paths:
        raise FileNotFoundError(f"No prot-*.zip files found under {tagged_frames_root}")

    effective_size = min(sample_size, len(zip_paths))
    logger.info("Sampling {} protocol ZIP files out of {} available.", effective_size, len(zip_paths))
    return sorted(random.Random(seed).sample(zip_paths, effective_size))


def _write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False, default=str)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
from api_swedeb.core.configuration import ConfigStore
ConfigStore.configure_context(source='tests/config.yml')

def main() -> int:
    """Run full-corpus parity check. Returns exit code (0 = success)."""

    # --- validate paths ---
    missing = [
        str(p)
        for p in [_FULL_CORPUS_TAGGED_FRAMES, _FULL_CORPUS_BOOTSTRAP_ROOT, _FULL_CORPUS_METADATA_DB]
        if not p.exists()
    ]
    if not Path(_FULL_CORPUS_DTM_FOLDER).exists():
        missing.append(_FULL_CORPUS_DTM_FOLDER)
    if missing:
        logger.error("Required paths are missing:\n" + "\n".join(f"  {p}" for p in missing))
        return 1

    logger.info("Loading document index from {}", _FULL_CORPUS_DTM_FOLDER)
    document_index = load_speech_index(folder=_FULL_CORPUS_DTM_FOLDER, tag=_FULL_CORPUS_DTM_TAG)

    logger.info("Loading PersonCodecs from {}", _FULL_CORPUS_METADATA_DB)
    person_codecs = md.PersonCodecs().load(source=str(_FULL_CORPUS_METADATA_DB))

    logger.info("Instantiating legacy SpeechTextRepository")
    legacy_repo = SpeechTextRepository(
        source=str(_FULL_CORPUS_TAGGED_FRAMES),
        person_codecs=person_codecs,
        document_index=document_index,
    )

    logger.info("Instantiating SpeechRepositoryFast (prebuilt backend) from {}", _FULL_CORPUS_BOOTSTRAP_ROOT)
    store = SpeechStore(str(_FULL_CORPUS_BOOTSTRAP_ROOT))
    fast_repo = SpeechRepositoryFast(
        store=store,
        document_index=document_index,
        metadata_db_path=str(_FULL_CORPUS_METADATA_DB),
    )

    # --- sample protocols ---
    if _FULL_CORPUS_PROTOCOL_SAMPLE_SIZE == 0:
        logger.info("Protocol sample size is 0, using all protocols in the document index.")
        # sampled_protocols = sorted(
        #     set(document_index["document_name"].astype("string[python]").str.split("_", n=1).str[0])
        # )
        sampled_zip_paths = sorted(_FULL_CORPUS_TAGGED_FRAMES.rglob("prot-*.zip"))
        sampled_protocols = sorted({path.stem for path in sampled_zip_paths})
        speech_ids: list[str] = document_index["speech_id"].astype(str).tolist()

    else:
        logger.info(
            "Sampling protocols: size={} seed={}", _FULL_CORPUS_PROTOCOL_SAMPLE_SIZE, _FULL_CORPUS_SAMPLE_SEED
        )
        sampled_zip_paths = _sample_protocol_zip_paths(
            _FULL_CORPUS_TAGGED_FRAMES,
            _FULL_CORPUS_PROTOCOL_SAMPLE_SIZE,
            _FULL_CORPUS_SAMPLE_SEED,
        )
        sampled_protocols = sorted({path.stem for path in sampled_zip_paths})
        protocol_names = document_index["document_name"].astype("string[python]").str.split("_", n=1).str[0]
        sample_index = document_index.loc[protocol_names.isin(sampled_protocols)].copy()
        speech_ids: list[str] = sample_index["speech_id"].astype(str).tolist()

    if not speech_ids:
        logger.error("Sample produced no matching speeches in the document index.")
        return 1

    logger.info(
        "Parity check: protocols={} speeches={}", len(sampled_protocols), len(speech_ids)
    )

    # --- batch retrieval ---
    fast_results: dict[str, Any] = dict(fast_repo.speeches_batch(speech_ids))
    legacy_results: dict[str, Any] = dict(legacy_repo.speeches_batch(speech_ids))

    # --- compare ---
    errors: list[dict[str, Any]] = []
    paragraph_mismatches: list[dict[str, Any]] = []
    field_mismatches: list[dict[str, Any]] = []
    enrichment_mismatches: list[dict[str, Any]] = []

    for speech_id in tqdm(speech_ids, total=len(speech_ids), desc="Comparing speeches"):
        row = document_index.loc[document_index["speech_id"] == speech_id].iloc[0]
        document_name = str(row["document_name"])

        fast_speech = fast_results.get(speech_id)
        legacy_speech = legacy_results.get(speech_id)

        if fast_speech is None or legacy_speech is None:
            errors.append(
                {
                    "speech_id": speech_id,
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
                    "speech_id": speech_id,
                    "document_name": document_name,
                    "fast_error": fast_speech.error,
                    "legacy_error": legacy_speech.error,
                }
            )
            continue

        paragraph_diffs = _diff_paragraph_lists(legacy_speech.paragraphs, fast_speech.paragraphs)
        if paragraph_diffs:
            paragraph_mismatches.append(
                {"speech_id": speech_id, "document_name": document_name, "diffs": paragraph_diffs}
            )

        diffs: dict[str, dict[str, Any]] = {}
        if _normalise_page(legacy_speech.page_number) != _normalise_page(fast_speech.page_number):
            diffs["page_number"] = {"legacy": legacy_speech.page_number, "fast": fast_speech.page_number}
        if _normalise_page(legacy_speech.get("page_number2")) != _normalise_page(fast_speech.get("page_number2")):
            diffs["page_number2"] = {
                "legacy": legacy_speech.get("page_number2"),
                "fast": fast_speech.get("page_number2"),
            }
        for field in _CORE_FIELDS_TO_COMPARE:
            lval = legacy_speech.get(field)
            fval = fast_speech.get(field)
            if lval != fval:
                diffs[field] = {"legacy": lval, "fast": fval}
        if diffs:
            field_mismatches.append({"speech_id": speech_id, "document_name": document_name, "diffs": diffs})

        enrichment_diffs: dict[str, dict[str, Any]] = {}
        for field in _ENRICHMENT_FIELDS_TO_COMPARE:
            lval = legacy_speech.get(field)
            fval = fast_speech.get(field)
            if lval != fval:
                enrichment_diffs[field] = {"legacy": lval, "fast": fval}
        if enrichment_diffs:
            enrichment_mismatches.append(
                {"speech_id": speech_id, "document_name": document_name, "diffs": enrichment_diffs}
            )

    # --- report ---
    report: dict[str, Any] = {
        "seed": _FULL_CORPUS_SAMPLE_SEED,
        "requested_protocol_sample_size": _FULL_CORPUS_PROTOCOL_SAMPLE_SIZE,
        "actual_protocol_sample_size": len(sampled_protocols),
        "speech_count": len(speech_ids),
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
        "sampled_zip_paths": [str(p) for p in sampled_zip_paths],
        "details": {
            "errors": errors,
            "paragraphs": paragraph_mismatches,
            "fields": field_mismatches,
            "enrichment": enrichment_mismatches,
        },
    }
    _write_report(_REPORT_PATH, report)

    logger.info(
        "Report written to {} — speeches={} errors={} field_mismatches={} "
        "para_mismatches={} enrichment_mismatches={}",
        _REPORT_PATH,
        len(speech_ids),
        len(errors),
        len(field_mismatches),
        len(paragraph_mismatches),
        len(enrichment_mismatches),
    )

    failed = errors or paragraph_mismatches or field_mismatches
    if failed:
        logger.error("Parity check FAILED. See {} for details.", _REPORT_PATH)
        if errors:
            logger.error(
                "{} speech(es) could not be loaded:\n{}",
                len(errors),
                textwrap.indent(json.dumps(errors[:5], indent=2, default=str), "  "),
            )
        if paragraph_mismatches:
            logger.error(
                "{} speech(es) have paragraph differences:\n{}",
                len(paragraph_mismatches),
                textwrap.indent(json.dumps(paragraph_mismatches[:5], indent=2, default=str), "  "),
            )
        if field_mismatches:
            logger.error(
                "{} speech(es) have field differences:\n{}",
                len(field_mismatches),
                textwrap.indent(json.dumps(field_mismatches[:5], indent=2, default=str), "  "),
            )
        return 1

    if enrichment_mismatches:
        logger.warning(
            "{}/{} speeches have enrichment differences (not a failure — see {})",
            len(enrichment_mismatches),
            len(speech_ids),
            _REPORT_PATH,
        )

    logger.info("Parity check PASSED.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
