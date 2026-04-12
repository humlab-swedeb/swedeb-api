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

import pyarrow as pa
from loguru import logger
from pyarrow import feather

from api_swedeb.core.utility import fix_whitespace

from .enrichment import SpeakerLookups, enrich_speech_rows
from .merge import merge_protocol_utterances

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCHEMA_VERSION = "1.0.0"


_PYARROW_SCHEMA: pa.Schema = pa.schema(
    [
        ("speech_id", pa.string()),
        ("document_name", pa.string()),
        ("protocol_name", pa.string()),
        ("date", pa.string()),
        ("year", pa.int16()),
        ("speaker_id", pa.string()),
        ("speaker_note_id", pa.string()),
        ("speech_index", pa.int16()),
        ("page_number_start", pa.int16()),
        ("page_number_end", pa.int16()),
        ("num_tokens", pa.int16()),
        ("num_words", pa.int16()),
        ("name", pa.string()),
        ("gender_id", pa.int8()),
        ("gender", pa.string()),
        ("gender_abbrev", pa.string()),
        ("party_id", pa.int16()),
        ("party_abbrev", pa.string()),
        ("office_type_id", pa.int8()),
        ("office_type", pa.string()),
        ("sub_office_type_id", pa.int8()),
        ("sub_office_type", pa.string()),
        ("wiki_id", pa.string()),
        ("feather_file", pa.string()),
        ("feather_row", pa.int64()),
    ]
)

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _iter_zip_paths(tagged_frames_folder: str) -> list[Path]:
    """Return all *.zip files under *tagged_frames_folder*, sorted."""
    root = Path(tagged_frames_folder)
    return sorted(root.rglob("*.zip"))


def _year_from_protocol_name(protocol_name: str) -> int:
    """Extract the start year from a protocol name.

    Protocol names follow the pattern ``prot-YYYY--...`` or
    ``prot-YYYYZZ--...`` (session-year spanning two calendar years, e.g.
    ``prot-197576--087``).  The legacy speech index always uses the first four
    digits (the start year) for office-type lookups, so we do the same.

    Examples::

        _year_from_protocol_name("prot-1970--ak--029")  → 1970
        _year_from_protocol_name("prot-197576--087")    → 1975
    """
    try:
        return int(protocol_name[5:9])
    except (ValueError, IndexError):
        return 0


def _subfolder_from_protocol_name(protocol_name: str) -> str:
    """Derive the subfolder name from the protocol name."""
    return protocol_name.split("-")[1]


def _load_zip(zip_path: Path) -> tuple[dict, list[dict]]:
    """Load metadata and utterances from a tagged-frames ZIP.

    The protocol name is derived from the ZIP stem (authoritative) rather than
    from the metadata.json name field, which may differ.
    """
    protocol_name: str = zip_path.stem
    with zipfile.ZipFile(zip_path, "r") as zf:

        filenames: list[str] = zf.namelist()

        if len(filenames) != 2:
            raise ValueError(
                f"Invalid ZIP structure:: {zip_path}. expected exactly 2 files (metadata.json + utterances.json), found: {filenames}"
            )

        if "metadata.json" not in filenames:
            raise ValueError(f"Missing metadata.json in ZIP: {zip_path}")

        # Ignore actual filename, The utterances JSON filename can differ from protocol name
        utterances_filename: str = filenames[0] if filenames[0] != "metadata.json" else filenames[1]

        metadata: dict = json.loads(zf.read("metadata.json"))
        utterances: list[dict] = json.loads(zf.read(utterances_filename))

        # Prefer the actual ZIP stem as the canonical name.
        metadata["name"] = protocol_name

    return metadata, utterances


def _speech_rows_to_arrow(full_rows: list[dict[str, Any]], feather_file_rel: str) -> pa.Table:
    """Convert enriched full_rows dicts to an Arrow index table with location columns."""
    if not full_rows:
        return pa.Table.from_pylist([], schema=_PYARROW_SCHEMA)

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
                "wiki_id": s.get("wiki_id", "unknown"),
                "feather_file": feather_file_rel,
                "feather_row": row_idx,
            }
        )
    return pa.Table.from_pylist(rows, schema=_PYARROW_SCHEMA)


def _feather_checksum(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _write_feather(table: pa.Table, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    feather.write_feather(table, str(path), compression="lz4")


#####################################################################################################
# Per-protocol worker (runs in subprocess when using multiprocessing)
#####################################################################################################


def _process_zip(args: tuple) -> dict[str, Any]:
    """Process one ZIP file and write a Feather.

    Args:
        args: (zip_path, output_root, output_root_str, lookups_or_none)
            where ``lookups_or_none`` is a :class:`SpeakerLookups` instance or
            ``None`` when enrichment is disabled.

    Returns a result dict with keys: zip_path, ok, skipped, feather_path,
    row_count, warnings, quality, error.
    """
    zip_path, output_root, _, lookups = args
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

        protocol_stem: str = zip_path.stem
        subfolder: str = _subfolder_from_protocol_name(protocol_stem)
        year_int: int = _year_from_protocol_name(protocol_stem)  # The year is derived from the protocol name
        feather_rel: str = os.path.join(subfolder, f"{protocol_stem}.feather")
        feather_abs: Path = output_root / feather_rel

        # Build per-speech full payload table
        full_rows = []
        for _, s in enumerate(speeches):
            full_rows.append(
                {
                    "speech_id": s.get("speech_id") or "",
                    "document_name": f"{s.get('protocol_name')}_{s.get('speech_index')}",
                    "protocol_name": s.get("protocol_name") or "",
                    "date": s.get("date") or "",
                    "year": year_int,
                    "speaker_id": s.get("speaker_id") or "",
                    "speaker_note_id": s.get("speaker_note_id") or "",
                    "speech_index": int(s.get("speech_index") or 0),
                    "page_number_start": int(s.get("page_number_start") or 0),
                    "page_number_end": int(s.get("page_number_end") or 0),
                    "num_tokens": int(s.get("num_tokens") or 0),
                    "num_words": int(s.get("num_words") or 0),
                    "text": fix_whitespace("\n".join(s.get("paragraphs") or [])),
                }
            )

        quality: dict[str, int] = {}
        if lookups is not None and full_rows:
            full_rows, quality = enrich_speech_rows(full_rows, lookups)
        result["quality"] = quality

        table: pa.Table = pa.Table.from_pylist(full_rows) if full_rows else pa.table({})
        _write_feather(table, feather_abs)

        result["ok"] = True
        result["feather_path"] = str(feather_abs)
        result["feather_rel"] = feather_rel
        result["row_count"] = len(full_rows)
        result["index_table"] = _speech_rows_to_arrow(full_rows, feather_rel)

    except Exception:  # pylint: disable=broad-except
        result["error"] = traceback.format_exc()

    return result


#####################################################################################################
# ResultCompiler
#####################################################################################################


class ResultCompiler:
    """Helper for compiling per-protocol results into aggregate metrics and manifest.

    This is a separate class to keep the main builder logic focused on the
    orchestration of the build process, while encapsulating the details of how
    results are aggregated and reported.
    """

    def __init__(self, results: list[dict[str, Any]], total: int, corpus_version: str, metadata_version: str):
        self.results: list[dict[str, Any]] = results
        self.total: int = total
        self.corpus_version: str = corpus_version
        self.metadata_version: str = metadata_version

        self.skipped: list[dict[str, Any]] = [r for r in results if r.get("skipped")]
        self.successes: list[dict[str, Any]] = [r for r in results if r["ok"] and not r.get("skipped")]
        self.failures: list[dict[str, Any]] = [r for r in results if not r["ok"]]
        self.all_warnings: list[str] = [w for r in self.successes for w in r.get("warnings", [])]

    def compile(self) -> dict[str, Any]:
        """Compile the results into a summary dict and manifest."""
        quality_totals: dict[str, int] = self._compute_quality_metrics()
        # checksums: dict[str, str | None] =self._create_checksums(self.successes[0]["feather_path"].parent) if self.successes else {}
        checksums: dict[str, str | None] = {}
        manifest: dict = self._create_manifest(quality_totals, checksums)

        return {
            "total": self.total,
            "successes": len(self.successes),
            "skipped": len(self.skipped),
            "failures": len(self.failures),
            "warnings": len(self.all_warnings),
            "quality": quality_totals,
            "failures_detail": [{"zip": r["zip_path"], "error": r["error"]} for r in self.failures],
            "manifest": manifest,
        }

    def _compute_quality_metrics(self) -> dict[str, int]:
        """Compute aggregate quality metrics from per-protocol results."""
        quality_totals: dict[str, int] = {}
        for r in self.successes:
            for k, v in r.get("quality", {}).items():
                quality_totals[k] = quality_totals.get(k, 0) + v

        logger.info(
            f"Processed {len(self.successes)}/{self.total} protocols "
            f"({len(self.skipped)} empty/skipped, {len(self.failures)} failures, {len(self.all_warnings)} warnings)"
        )
        if quality_totals:
            logger.info(f"Enrichment quality: {quality_totals}")
        return quality_totals

    def _create_checksums(self, output_root: Path) -> dict[str, str | None]:
        """Compute checksums for the main index files."""
        speech_index_path: Path = output_root / "speech_index.feather"
        speech_lookup_path: Path = output_root / "speech_lookup.feather"
        return {
            "speech_index.feather": _feather_checksum(speech_index_path) if speech_index_path.exists() else None,
            "speech_lookup.feather": _feather_checksum(speech_lookup_path) if speech_lookup_path.exists() else None,
        }

    def _create_manifest(self, quality_metrics: dict[str, int], checksums: dict[str, str | None]) -> dict:
        manifest = {
            "schema_version": SCHEMA_VERSION,
            "corpus_version": self.corpus_version,
            "metadata_version": self.metadata_version,
            "build_timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "total_zips": self.total,
            "total_protocols_ok": len(self.successes),
            "total_protocols_skipped": len(self.skipped),
            "total_protocols_failed": len(self.failures),
            "total_speeches": sum(r["row_count"] for r in self.successes),
            "total_warnings": len(self.all_warnings),
            "enrichment_quality": quality_metrics or {},
            "checksums": checksums or {},
            "zip_to_feather": {r["zip_path"]: r.get("feather_rel") for r in self.successes},
            "failures": [{"zip": r["zip_path"], "error": r["error"]} for r in self.failures],
        }

        return manifest


#####################################################################################################
# Builder
#####################################################################################################


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
        self.corpus_version: str = corpus_version
        self.metadata_version: str = metadata_version
        self.metadata_db_path: str | None = metadata_db_path
        self.num_processes: int = num_processes

    #####################################################################################################
    # Public API
    #####################################################################################################

    def build(self) -> dict[str, Any]:
        """Run the full build and return a summary report dict."""

        self.output_root.mkdir(parents=True, exist_ok=True)

        lookups: SpeakerLookups | None = None

        if self.metadata_db_path:
            logger.info(f"Loading speaker lookups from {self.metadata_db_path}")
            lookups = SpeakerLookups(self.metadata_db_path)
            logger.info(f"  {len(lookups.person_to_name)} persons loaded")

        zip_paths: list[Path] = _iter_zip_paths(str(self.tagged_frames_folder))
        logger.info(f"Found {len(zip_paths)} tagged protocols (zipped) under {self.tagged_frames_folder}")

        args: list[tuple[Path, Path, str, SpeakerLookups | None]] = [
            (p, self.output_root, str(self.output_root), lookups) for p in zip_paths
        ]

        results: list[dict[str, Any]] = self._run(args, len(zip_paths))

        result_compiler: ResultCompiler = ResultCompiler(
            results, len(zip_paths), self.corpus_version, self.metadata_version
        )

        compiled_results: dict[str, Any] = result_compiler.compile()

        self._write_indexes(result_compiler.successes)
        self._write_manifest(compiled_results["manifest"])

        return compiled_results

    #####################################################################################################
    # Internals
    #####################################################################################################

    def _run(self, args: list[tuple[Path, Path, str, SpeakerLookups | None]], total: int) -> list[dict[str, Any]]:

        if self.num_processes > 0:
            with multiprocessing.Pool(processes=self.num_processes) as pool:
                results: list[dict[str, Any]] = []
                for i, result in enumerate(pool.imap_unordered(_process_zip, args)):
                    results.append(result)
                    if (i + 1) % 500 == 0 or (i + 1) == total:
                        logger.info(f"  {i+1}/{total} processed")
            return results

        results = []
        for i, arg in enumerate(args):
            result: dict[str, Any] = _process_zip(arg)
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
        speech_index_path: Path = self.output_root / "speech_index.feather"
        _write_feather(speech_index, speech_index_path)
        logger.info(f"Wrote speech_index.feather ({speech_index.num_rows} rows) → {speech_index_path}")

        # speech_lookup.feather – minimal key-to-location mapping
        lookup_columns = ["speech_id", "document_name", "feather_file", "feather_row"]
        speech_lookup = speech_index.select(lookup_columns)

        # Validate that every row has both key columns populated — a missing value
        # would silently corrupt the SpeechStore lookup dicts at runtime.
        for col in ("speech_id", "document_name"):
            null_count = speech_lookup.column(col).null_count
            empty_count = speech_lookup.column(col).to_pylist().count("")
            if null_count or empty_count:
                raise ValueError(
                    f"speech_lookup has {null_count} null + {empty_count} empty values in '{col}' — "
                    "all speeches must have both speech_id and document_name"
                )

        speech_lookup_path: Path = self.output_root / "speech_lookup.feather"
        _write_feather(speech_lookup, speech_lookup_path)

        logger.info(f"Wrote speech_lookup.feather ({speech_lookup.num_rows} rows) → {speech_lookup_path}")

    def _write_manifest(self, manifest: dict[str, Any]) -> None:
        """Write the manifest.json file with build metadata and checksums."""
        manifest_path: Path = self.output_root / "manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as fh:
            json.dump(manifest, fh, indent=2, ensure_ascii=False)
        logger.info(f"Wrote manifest → {manifest_path}")
