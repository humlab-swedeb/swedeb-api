"""KWIC archive service — prepare and execute async KWIC archive generation."""

from __future__ import annotations

import csv
import gzip
import io
import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from loguru import logger

from api_swedeb.api.services.result_store import (
    ResultStore,
    ResultStoreCapacityError,
    ResultStoreNotFound,
    TicketMeta,
    TicketStatus,
)
from api_swedeb.core.configuration import ConfigValue
from api_swedeb.schemas.bulk_archive_schema import (
    ARCHIVE_MEDIA_TYPES,
    ARCHIVE_SUFFIXES,
    ArchivePrepareResponse,
    BulkArchiveFormat,
)

# KWIC columns exposed in archive output (excludes internal identifiers)
_ARCHIVE_COLUMNS: list[str] = [
    "left_word",
    "node_word",
    "right_word",
    "year",
    "name",
    "party_abbrev",
    "gender",
    "speech_name",
    "speech_id",
    "document_name",
    "chamber_abbrev",
]

_TICKET_ROW_ID = "_ticket_row_id"


class KWICArchiveService:
    """Thin service that converts a ready KWIC Feather artifact into a bulk archive."""

    def prepare(
        self,
        *,
        source_ticket_id: str,
        archive_format: BulkArchiveFormat,
        result_store: ResultStore,
    ) -> ArchivePrepareResponse:
        """Validate the source KWIC ticket and create an archive ticket.

        Raises:
            ResultStoreNotFound: if the source ticket is missing or expired.
            ValueError: if the source ticket is not in a ready state.
        """
        source_ticket: TicketMeta = result_store.require_ticket(source_ticket_id)
        if source_ticket.status == TicketStatus.PENDING:
            raise ValueError("Source ticket is not ready yet")
        if source_ticket.status == TicketStatus.ERROR:
            raise ValueError("Source ticket is in an error state")

        query_meta: dict[str, Any] = {
            "source_ticket_id": source_ticket_id,
            "archive_format": archive_format.value,
            "total_hits": source_ticket.total_hits,
            "source_query": source_ticket.query_meta,
        }
        archive_ticket: TicketMeta = result_store.create_ticket(
            query_meta=query_meta,
            source_ticket_id=source_ticket_id,
            archive_format=archive_format.value,
        )

        retry_after: int = ConfigValue("cache.ticket_poll_retry_after_seconds", default=2).resolve()
        return ArchivePrepareResponse(
            archive_ticket_id=archive_ticket.ticket_id,
            status="pending",
            source_ticket_id=source_ticket_id,
            archive_format=archive_format.value,
            retry_after=retry_after,
            expires_at=archive_ticket.expires_at,
        )

    def execute_archive_task(
        self,
        *,
        archive_ticket_id: str,
        result_store: ResultStore,
    ) -> None:
        """Serialize the KWIC Feather artifact and mark the archive ticket ready or failed."""
        logger.info(f"Starting KWIC execute_archive_task for archive ticket {archive_ticket_id}")

        try:
            archive_ticket: TicketMeta = result_store.require_ticket(archive_ticket_id)
        except ResultStoreNotFound:
            logger.warning(f"KWIC archive ticket {archive_ticket_id} not found; nothing to update")
            return
        except ResultStoreCapacityError:
            logger.warning(f"Result store capacity error loading KWIC archive ticket {archive_ticket_id}")
            return

        try:
            source_ticket_id: str | None = archive_ticket.source_ticket_id
            archive_format_str: str | None = archive_ticket.archive_format

            if source_ticket_id is None:
                raise ValueError("Archive ticket has no source_ticket_id")
            if archive_format_str is None:
                raise ValueError("Archive ticket has no archive_format")

            archive_format = BulkArchiveFormat(archive_format_str)

            import pandas as pd  # pylint: disable=import-outside-toplevel

            data: pd.DataFrame = result_store.load_artifact(source_ticket_id)
            data = data.drop(columns=[_TICKET_ROW_ID], errors="ignore")

            # Keep only the archive columns that are present in the artifact
            cols = [c for c in _ARCHIVE_COLUMNS if c in data.columns]
            data = data[cols]

            dest_path: Path = result_store.archive_artifact_path(archive_ticket_id, archive_format_str)
            dest_path.parent.mkdir(parents=True, exist_ok=True)

            self._write(data, archive_format, dest_path)

            result_store.store_archive_ready(
                archive_ticket_id,
                artifact_path=dest_path,
                total_hits=len(data),
            )
            logger.info(f"KWIC archive ticket {archive_ticket_id} ready ({len(data)} rows)")

        except ResultStoreCapacityError:
            logger.warning(f"Result store capacity error for KWIC archive ticket {archive_ticket_id}")
            return
        except ResultStoreNotFound as exc:
            logger.warning(f"Required resource not found for KWIC archive ticket {archive_ticket_id}: {exc}")
            result_store.store_error(archive_ticket_id, message=f"Required resource not found: {exc}")
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception(f"Error executing KWIC archive ticket {archive_ticket_id}: {exc}")
            result_store.store_error(archive_ticket_id, message="Failed to generate KWIC archive")

    # ------------------------------------------------------------------
    # Private serialization helpers
    # ------------------------------------------------------------------

    def _write(
        self,
        data: "pd.DataFrame",  # noqa: F821
        archive_format: BulkArchiveFormat,
        dest_path: Path,
    ) -> None:
        import pandas as pd  # pylint: disable=import-outside-toplevel

        partial = Path(str(dest_path) + ".partial")
        partial.parent.mkdir(parents=True, exist_ok=True)

        try:
            if archive_format == BulkArchiveFormat.jsonl_gz:
                self._write_jsonl_gz(data, partial)
            elif archive_format == BulkArchiveFormat.csv_gz:
                self._write_csv_gz(data, partial)
            elif archive_format == BulkArchiveFormat.xlsx:
                self._write_xlsx(data, partial)
            elif archive_format == BulkArchiveFormat.zip:
                self._write_zip_csv(data, partial)
            else:
                self._write_jsonl_gz(data, partial)

            partial.replace(dest_path)
        except Exception:
            partial.unlink(missing_ok=True)
            raise

    def _write_jsonl_gz(self, data: "pd.DataFrame", dest: Path) -> None:
        with gzip.open(str(dest), "wb", compresslevel=1) as gz:
            for record in data.to_dict(orient="records"):
                cleaned = {k: (None if isinstance(v, float) and v != v else v) for k, v in record.items()}
                line = (json.dumps(cleaned, ensure_ascii=False, default=str) + "\n").encode("utf-8")
                gz.write(line)

    def _write_csv_gz(self, data: "pd.DataFrame", dest: Path) -> None:
        buf = io.BytesIO()
        with gzip.GzipFile(fileobj=buf, mode="wb", compresslevel=1) as gz:
            csv_str = data.to_csv(index=False)
            gz.write(csv_str.encode("utf-8"))
        dest.write_bytes(buf.getvalue())

    def _write_xlsx(self, data: "pd.DataFrame", dest: Path) -> None:
        import openpyxl  # pylint: disable=import-outside-toplevel  # noqa: F401

        # pandas/openpyxl validates the file extension, so we must use .xlsx for the temp file
        tmp = dest.parent / (dest.name.replace(".partial", ".tmp.xlsx"))
        try:
            data.to_excel(str(tmp), index=False, engine="openpyxl")
            tmp.replace(dest)
        except Exception:
            tmp.unlink(missing_ok=True)
            raise

    def _write_zip_csv(self, data: "pd.DataFrame", dest: Path) -> None:
        csv_str = data.to_csv(index=False)
        with zipfile.ZipFile(str(dest), "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("kwic_data.csv", csv_str.encode("utf-8"))

    # ------------------------------------------------------------------
    # Reuse ArchiveTicketService helpers for status / file response
    # ------------------------------------------------------------------

    def _build_manifest(self, archive_ticket: TicketMeta) -> dict:
        return {
            "archive_ticket_id": archive_ticket.ticket_id,
            "source_ticket_id": archive_ticket.source_ticket_id,
            "archive_format": archive_ticket.archive_format,
            "generated_at": datetime.now(UTC).isoformat(),
        }
