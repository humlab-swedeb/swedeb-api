"""Ticketed download service — strategy-based bulk archive writing.

Each :class:`ArchiveWriter` implementation handles a single output format.
Add a new format by:

1. Subclassing :class:`ArchiveWriter` and implementing :meth:`~ArchiveWriter.write`.
2. Registering the class in :data:`_WRITER_REGISTRY`.
"""

from __future__ import annotations

import csv
import gzip
import json
import re
import zipfile
from abc import ABC, abstractmethod
from pathlib import Path

from api_swedeb.api.services.search_service import SearchService
from api_swedeb.core.configuration.inject import ConfigValue
from api_swedeb.schemas.bulk_archive_schema import BulkArchiveFormat

_UNSAFE_CHARS = re.compile(r"[^\w\-.]")


def _safe_filename_part(value: str) -> str:
    return _UNSAFE_CHARS.sub("_", value).strip("_") or "unknown"


# ---------------------------------------------------------------------------
# Strategy interface
# ---------------------------------------------------------------------------


class ArchiveWriter(ABC):
    """Strategy interface for writing a bulk speech archive to a file atomically.

    Implementations must write output to ``dest_path`` + ``.partial`` and
    rename it to *dest_path* on success, or remove the partial file on failure.
    """

    @abstractmethod
    def write(
        self,
        speech_ids: list[str],
        search_service: SearchService,
        dest_path: Path,
        manifest_meta: dict | None = None,
        compresslevel: int = 1,
    ) -> int:
        """Write archive atomically to *dest_path*.

        Returns the number of bytes written.
        """
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Concrete strategies
# ---------------------------------------------------------------------------


class JsonlGzArchiveWriter(ArchiveWriter):
    """Write speeches as a gzip-compressed JSONL file.

    Each line is a JSON object with ``speech_id`` and ``text`` keys.
    """

    def write(
        self,
        speech_ids: list[str],
        search_service: SearchService,
        dest_path: Path,
        manifest_meta: dict | None = None,  # noqa: ARG002 (not included in JSONL format)
        compresslevel: int = 1,
    ) -> int:
        partial = Path(str(dest_path) + ".partial")
        partial.parent.mkdir(parents=True, exist_ok=True)
        try:
            with gzip.open(str(partial), "wb", compresslevel=compresslevel) as gz:
                for speech_id, text in search_service.get_speeches_text_batch(speech_ids):
                    record: dict = {"speech_id": speech_id, "text": text}
                    line = (json.dumps(record, ensure_ascii=False) + "\n").encode("utf-8")
                    gz.write(line)
            partial.replace(dest_path)
            return dest_path.stat().st_size
        except Exception:
            partial.unlink(missing_ok=True)
            raise


class ZipArchiveWriter(ArchiveWriter):
    """Write speeches as a ZIP file, one ``.txt`` entry per speech.

    A ``manifest.json`` entry is prepended when *manifest_meta* is provided.
    """

    def write(
        self,
        speech_ids: list[str],
        search_service: SearchService,
        dest_path: Path,
        manifest_meta: dict | None = None,
        compresslevel: int = 1,
    ) -> int:
        unknown: str = ConfigValue("display.labels.speaker.unknown", default="unknown").resolve()
        speaker_names: dict[str, str] = search_service.get_speaker_names(speech_ids)
        partial = Path(str(dest_path) + ".partial")
        partial.parent.mkdir(parents=True, exist_ok=True)
        try:
            with zipfile.ZipFile(
                str(partial),
                mode="w",
                compression=zipfile.ZIP_DEFLATED,
                compresslevel=compresslevel,
                allowZip64=True,
            ) as zf:
                if manifest_meta is not None:
                    zf.writestr("manifest.json", json.dumps(manifest_meta, indent=2, ensure_ascii=False))
                for speech_id, text in search_service.get_speeches_text_batch(speech_ids):
                    speaker = speaker_names.get(speech_id, unknown)
                    filename = f"{_safe_filename_part(speaker)}_{speech_id}.txt"
                    zf.writestr(filename, text.encode("utf-8"))
            partial.replace(dest_path)
            return dest_path.stat().st_size
        except Exception:
            partial.unlink(missing_ok=True)
            raise


class CsvArchiveWriter(ArchiveWriter):
    """Write speeches as a gzip-compressed CSV file.

    Columns: ``speech_id``, ``speaker_name``, ``text``.  Fields are quoted
    only when necessary (commas, newlines, or embedded quotes).
    """

    def write(
        self,
        speech_ids: list[str],
        search_service: SearchService,
        dest_path: Path,
        manifest_meta: dict | None = None,  # noqa: ARG002 (not included in CSV format)
        compresslevel: int = 1,
    ) -> int:
        unknown: str = ConfigValue("display.labels.speaker.unknown", default="unknown").resolve()
        speaker_names: dict[str, str] = search_service.get_speaker_names(speech_ids)
        partial = Path(str(dest_path) + ".partial")
        partial.parent.mkdir(parents=True, exist_ok=True)
        try:
            with gzip.open(partial, "wt", encoding="utf-8", newline="", compresslevel=compresslevel) as gz:
                writer = csv.writer(gz, quoting=csv.QUOTE_MINIMAL)
                writer.writerow(["speech_id", "speaker_name", "text"])
                for speech_id, text in search_service.get_speeches_text_batch(speech_ids):
                    speaker_name = speaker_names.get(speech_id, unknown)
                    writer.writerow([speech_id, speaker_name, text])
            partial.replace(dest_path)
            return dest_path.stat().st_size
        except Exception:
            partial.unlink(missing_ok=True)
            raise


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

#: Maps each :class:`~api_swedeb.schemas.bulk_archive_schema.BulkArchiveFormat`
#: to the :class:`ArchiveWriter` class that handles it.  Add an entry here to
#: register a new output format.
_WRITER_REGISTRY: dict[BulkArchiveFormat, type[ArchiveWriter]] = {
    BulkArchiveFormat.jsonl_gz: JsonlGzArchiveWriter,
    BulkArchiveFormat.zip: ZipArchiveWriter,
    BulkArchiveFormat.csv_gz: CsvArchiveWriter,
}


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class TicketedDownloadService:
    """Orchestrates bulk archive writing using an injected :class:`ArchiveWriter` strategy.

    Prefer constructing via :meth:`for_format` rather than directly.

    Example — adding a new format::

        # 1. Implement the strategy
        class ParquetArchiveWriter(ArchiveWriter):
            def write(self, speech_ids, search_service, dest_path, manifest_meta=None, compresslevel=1) -> int:
                ...

        # 2. Register it
        _WRITER_REGISTRY[BulkArchiveFormat.parquet] = ParquetArchiveWriter

        # 3. Use it
        svc = TicketedDownloadService.for_format(BulkArchiveFormat.parquet)
        search_service = SearchService(...)
        svc.write(speech_ids=ids, search_service=search_service, dest_path=path)
    """

    def __init__(self, writer: ArchiveWriter, compresslevel: int = 1) -> None:
        self._writer = writer
        self.compresslevel = compresslevel

    @classmethod
    def for_format(cls, archive_format: BulkArchiveFormat, compresslevel: int = 1) -> "TicketedDownloadService":
        """Return a :class:`TicketedDownloadService` configured for *archive_format*.

        Raises :exc:`ValueError` for unregistered formats.
        """
        writer_cls = _WRITER_REGISTRY.get(archive_format)
        if writer_cls is None:
            registered = [f.value for f in _WRITER_REGISTRY]
            raise ValueError(f"Unsupported archive format: {archive_format!r}. Registered formats: {registered}")
        return cls(writer=writer_cls(), compresslevel=compresslevel)

    def write(
        self,
        *,
        speech_ids: list[str],
        search_service: SearchService,
        dest_path: Path,
        manifest_meta: dict | None = None,
    ) -> int:
        """Write the archive to *dest_path* atomically.

        Returns the number of bytes written.
        """
        return self._writer.write(
            speech_ids=speech_ids,
            search_service=search_service,
            dest_path=dest_path,
            manifest_meta=manifest_meta,
            compresslevel=self.compresslevel,
        )
