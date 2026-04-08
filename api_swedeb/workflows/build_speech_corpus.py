"""Offline builder for the pre-merged speech corpus (bootstrap_corpus).

Iterates every tagged-frames ZIP under a source folder, merges utterances into
speech rows via :func:`merge_protocol_utterances`, and writes one Feather file
per protocol to::

    {output_root}/{year}/{protocol_stem}.feather

It also writes two index files and a manifest at the root::

    {output_root}/speech_index.feather   – one row per speech, all fields
    {output_root}/speech_lookup.feather  – speech_id / document_name → (file, row offset)
    {output_root}/manifest.json          – build metadata and checksums

The Feather filename is always derived from the **actual ZIP basename** (not from
any filename that may appear inside metadata.json, which may differ).

See :mod:`api_swedeb.workflows.scripts.build_speech_corpus_cli` for the CLI
entry point, or run ``make build-speech-corpus``.
"""

from __future__ import annotations

import hashlib
import json
import multiprocessing
import os
import traceback
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow as pa
import pyarrow.feather as feather
from loguru import logger

from api_swedeb.core.speech_enrichment import SpeakerLookups, enrich_speech_rows
from api_swedeb.core.speech_merge import merge_protocol_utterances

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCHEMA_VERSION = "1.0.0"
_SPEECH_INDEX_COLUMNS = [
    "speech_id",
    "document_name",
    "protocol_name",
    "date",
    "year",
    "speaker_id",
    "speaker_note_id",
    "speech_index",
    "page_number_start",
    "page_number_end",
    "num_tokens",
    "num_words",
    "name",
    "gender_id",
    "gender",
    "gender_abbrev",
    "party_id",
    "party_abbrev",
    "office_type_id",
    "office_type",
    "sub_office_type_id",
    "sub_office_type",
    "feather_file",
    "feather_row",
]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _iter_zip_paths(tagged_frames_folder: str) -> list[Path]:
    """Return all *.zip files under *tagged_frames_folder*, sorted."""
    root = Path(tagged_frames_folder)
    return sorted(root.rglob("*.zip"))


def _load_zip(zip_path: Path) -> tuple[dict, list[dict]]:
    """Load metadata and utterances from a tagged-frames ZIP.

    The protocol name is derived from the ZIP stem (authoritative) rather than
    from the metadata.json name field, which may differ.
    """
    protocol_name = zip_path.stem
    with zipfile.ZipFile(zip_path, "r") as zf:
        metadata: dict = json.loads(zf.read("metadata.json"))
        # Prefer the actual ZIP stem as the canonical name.
        metadata["name"] = protocol_name
        utterances: list[dict] = json.loads(zf.read(f"{protocol_name}.json"))
    return metadata, utterances


def _speech_rows_to_arrow(full_rows: list[dict[str, Any]], feather_file_rel: str) -> pa.Table:
    """Convert enriched full_rows dicts to an Arrow index table with location columns."""
    if not full_rows:
        return pa.table({col: pa.array([], type=pa.string()) for col in _SPEECH_INDEX_COLUMNS})

    rows = []
    for row_idx, s in enumerate(full_rows):
        rows.append(
            {
                "speech_id": s.get("speech_id"),
                "document_name": s.get("document_name"),
                "protocol_name": s.get("protocol_name"),
                "date": s.get("date"),
                "year": s.get("year"),
                "speaker_id": s.get("speaker_id"),
                "speaker_note_id": s.get("speaker_note_id"),
                "speech_index": s.get("speech_index"),
                "page_number_start": s.get("page_number_start"),
                "page_number_end": s.get("page_number_end"),
                "num_tokens": s.get("num_tokens"),
                "num_words": s.get("num_words"),
                "name": s.get("name"),
                "gender_id": s.get("gender_id"),
                "gender": s.get("gender"),
                "gender_abbrev": s.get("gender_abbrev"),
                "party_id": s.get("party_id"),
                "party_abbrev": s.get("party_abbrev"),
                "office_type_id": s.get("office_type_id"),
                "office_type": s.get("office_type"),
                "sub_office_type_id": s.get("sub_office_type_id"),
                "sub_office_type": s.get("sub_office_type"),
                "feather_file": feather_file_rel,
                "feather_row": row_idx,
            }
        )
    return pa.Table.from_pylist(rows)


def _feather_checksum(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _write_feather(table: pa.Table, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    feather.write_feather(table, str(path), compression="lz4")


# ---------------------------------------------------------------------------
# Per-protocol worker (runs in subprocess when using multiprocessing)
# ---------------------------------------------------------------------------


def _process_zip(args: tuple) -> dict[str, Any]:
    """Process one ZIP file and write a Feather.

    Args:
        args: (zip_path, output_root, output_root_str, lookups_or_none)
            where ``lookups_or_none`` is a :class:`SpeakerLookups` instance or
            ``None`` when enrichment is disabled.

    Returns a result dict with keys: zip_path, ok, skipped, feather_path,
    row_count, warnings, quality, error.
    """
    zip_path, output_root, output_root_str, lookups = args
    result: dict[str, Any] = {
        "zip_path": str(zip_path),
        "ok": False,
        "skipped": False,
        "feather_path": None,
        "row_count": 0,
        "warnings": [],
        "quality": {},
        "error": None,
    }

    if zip_path.stat().st_size == 0:
        logger.debug(f"Skipping empty ZIP: {zip_path}")
        result["skipped"] = True
        result["ok"] = True
        return result

    try:
        metadata, utterances = _load_zip(zip_path)
        speeches, warnings = merge_protocol_utterances(metadata=metadata, utterances=utterances, strict=False)
        result["warnings"] = warnings

        year = zip_path.parent.name
        protocol_stem = zip_path.stem
        feather_rel = os.path.join(year, f"{protocol_stem}.feather")
        feather_abs = output_root / feather_rel

        # Build per-speech full payload table (paragraphs + annotation stored as strings)
        full_rows = []
        for row_idx, s in enumerate(speeches):
            full_rows.append(
                {
                    "speech_id": s.get("speech_id") or "",
                    "document_name": f"{s.get('protocol_name')}_{s.get('speech_index')}",
                    "protocol_name": s.get("protocol_name") or "",
                    "date": s.get("date") or "",
                    "year": int(s["date"][:4]) if s.get("date") else 0,
                    "speaker_id": s.get("speaker_id") or "",
                    "speaker_note_id": s.get("speaker_note_id") or "",
                    "speech_index": int(s.get("speech_index") or 0),
                    "page_number_start": int(s.get("page_number_start") or 0),
                    "page_number_end": int(s.get("page_number_end") or 0),
                    "num_tokens": int(s.get("num_tokens") or 0),
                    "num_words": int(s.get("num_words") or 0),
                    "paragraphs": json.dumps(s.get("paragraphs") or [], ensure_ascii=False),
                    "annotation": s.get("annotation") or "",
                }
            )

        quality: dict[str, int] = {}
        if lookups is not None and full_rows:
            full_rows, quality = enrich_speech_rows(full_rows, lookups)
        result["quality"] = quality

        table = pa.Table.from_pylist(full_rows) if full_rows else pa.table({})
        _write_feather(table, feather_abs)

        result["ok"] = True
        result["feather_path"] = str(feather_abs)
        result["feather_rel"] = feather_rel
        result["row_count"] = len(full_rows)
        result["index_table"] = _speech_rows_to_arrow(full_rows, feather_rel)

    except Exception:  # pylint: disable=broad-except
        result["error"] = traceback.format_exc()

    return result


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------


class SpeechCorpusBuilder:
    """Builds the bootstrap_corpus from tagged-frames ZIPs.

    Args:
        tagged_frames_folder: Root folder containing per-year ZIP subdirectories.
        output_root: Root folder for bootstrap_corpus output.
        corpus_version: Version string for the corpus (e.g. "v1.1.0").
        metadata_version: Version string for the metadata (e.g. "v1.1.0").
        metadata_db_path: Optional path to riksprot SQLite metadata DB.  When
            provided speaker metadata (name, gender, party, office type) is
            joined into every speech row and the speech_index.
        num_processes: Number of parallel workers (0 = sequential).
    """

    def __init__(
        self,
        tagged_frames_folder: str,
        output_root: str,
        corpus_version: str,
        metadata_version: str,
        metadata_db_path: str | None = None,
        num_processes: int = 0,
    ):
        self.tagged_frames_folder = Path(tagged_frames_folder)
        self.output_root = Path(output_root)
        self.corpus_version = corpus_version
        self.metadata_version = metadata_version
        self.metadata_db_path = metadata_db_path
        self.num_processes = num_processes

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build(self) -> dict[str, Any]:
        """Run the full build and return a summary report dict."""
        self.output_root.mkdir(parents=True, exist_ok=True)

        lookups: SpeakerLookups | None = None
        if self.metadata_db_path:
            logger.info(f"Loading speaker lookups from {self.metadata_db_path}")
            lookups = SpeakerLookups(self.metadata_db_path)
            logger.info(f"  {len(lookups.person_to_name)} persons loaded")

        zip_paths = _iter_zip_paths(str(self.tagged_frames_folder))
        total = len(zip_paths)
        logger.info(f"Found {total} ZIPs under {self.tagged_frames_folder}")

        args = [(p, self.output_root, str(self.output_root), lookups) for p in zip_paths]
        results = self._run(args, total)

        skipped = [r for r in results if r.get("skipped")]
        successes = [r for r in results if r["ok"] and not r.get("skipped")]
        failures = [r for r in results if not r["ok"]]
        all_warnings = [w for r in successes for w in r.get("warnings", [])]

        quality_totals: dict[str, int] = {}
        for r in successes:
            for k, v in r.get("quality", {}).items():
                quality_totals[k] = quality_totals.get(k, 0) + v

        logger.info(
            f"Processed {len(successes)}/{total} protocols "
            f"({len(skipped)} empty/skipped, {len(failures)} failures, {len(all_warnings)} warnings)"
        )
        if quality_totals:
            logger.info(f"Enrichment quality: {quality_totals}")

        self._write_indexes(successes)
        manifest = self._write_manifest(total, successes, skipped, failures, all_warnings, quality_totals)

        return {
            "total": total,
            "successes": len(successes),
            "skipped": len(skipped),
            "failures": len(failures),
            "warnings": len(all_warnings),
            "quality": quality_totals,
            "failures_detail": [{"zip": r["zip_path"], "error": r["error"]} for r in failures],
            "manifest": manifest,
        }

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _run(self, args: list, total: int) -> list[dict]:
        if self.num_processes > 0:
            with multiprocessing.Pool(processes=self.num_processes) as pool:
                results = []
                for i, result in enumerate(pool.imap_unordered(_process_zip, args)):
                    results.append(result)
                    if (i + 1) % 500 == 0 or (i + 1) == total:
                        logger.info(f"  {i+1}/{total} processed")
            return results
        else:
            results = []
            for i, arg in enumerate(args):
                result = _process_zip(arg)
                results.append(result)
                if (i + 1) % 500 == 0 or (i + 1) == total:
                    logger.info(f"  {i+1}/{total} processed")
            return results

    def _write_indexes(self, successes: list[dict]) -> None:
        """Concatenate per-protocol index tables and write speech_index + speech_lookup feathers."""
        tables = [r["index_table"] for r in successes if r.get("index_table") is not None]
        if not tables:
            logger.warning("No index tables to write.")
            return

        speech_index = pa.concat_tables(tables)

        # speech_index.feather – full index
        speech_index_path = self.output_root / "speech_index.feather"
        _write_feather(speech_index, speech_index_path)
        logger.info(f"Wrote speech_index.feather ({speech_index.num_rows} rows) → {speech_index_path}")

        # speech_lookup.feather – minimal key-to-location mapping
        lookup_columns = ["speech_id", "document_name", "feather_file", "feather_row"]
        speech_lookup = speech_index.select(lookup_columns)
        speech_lookup_path = self.output_root / "speech_lookup.feather"
        _write_feather(speech_lookup, speech_lookup_path)
        logger.info(f"Wrote speech_lookup.feather ({speech_lookup.num_rows} rows) → {speech_lookup_path}")

    def _write_manifest(
        self,
        total: int,
        successes: list[dict],
        skipped: list[dict],
        failures: list[dict],
        all_warnings: list[str],
        quality_totals: dict[str, int] | None = None,
    ) -> dict:
        speech_index_path = self.output_root / "speech_index.feather"
        speech_lookup_path = self.output_root / "speech_lookup.feather"

        manifest = {
            "schema_version": SCHEMA_VERSION,
            "corpus_version": self.corpus_version,
            "metadata_version": self.metadata_version,
            "build_timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "source_folder": str(self.tagged_frames_folder),
            "output_root": str(self.output_root),
            "total_zips": total,
            "total_protocols_ok": len(successes),
            "total_protocols_skipped": len(skipped),
            "total_protocols_failed": len(failures),
            "total_speeches": sum(r["row_count"] for r in successes),
            "total_warnings": len(all_warnings),
            "enrichment_quality": quality_totals or {},
            "checksums": {
                "speech_index.feather": _feather_checksum(speech_index_path) if speech_index_path.exists() else None,
                "speech_lookup.feather": _feather_checksum(speech_lookup_path) if speech_lookup_path.exists() else None,
            },
            "zip_to_feather": {r["zip_path"]: r.get("feather_rel") for r in successes},
            "failures": [{"zip": r["zip_path"], "error": r["error"]} for r in failures],
        }

        manifest_path = self.output_root / "manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as fh:
            json.dump(manifest, fh, indent=2, ensure_ascii=False)
        logger.info(f"Wrote manifest → {manifest_path}")
        return manifest
