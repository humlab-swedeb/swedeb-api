from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel


class BulkArchiveFormat(StrEnum):
    jsonl_gz = "jsonl_gz"
    zip = "zip"
    csv_gz = "csv_gz"
    xlsx = "xlsx"

    @classmethod
    def _missing_(cls, value: object) -> "BulkArchiveFormat | None":
        if isinstance(value, str):
            normalized = value.lower().replace("-", "_").replace(".", "_")
            for member in cls:
                if member.value == normalized:
                    return member
        return None


ARCHIVE_SUFFIXES: dict[BulkArchiveFormat, str] = {
    BulkArchiveFormat.jsonl_gz: ".jsonl.gz",
    BulkArchiveFormat.zip: ".zip",
    BulkArchiveFormat.csv_gz: ".csv.gz",
    BulkArchiveFormat.xlsx: ".xlsx",
}

ARCHIVE_MEDIA_TYPES: dict[BulkArchiveFormat, str] = {
    BulkArchiveFormat.jsonl_gz: "application/gzip",
    BulkArchiveFormat.zip: "application/zip",
    BulkArchiveFormat.csv_gz: "application/gzip",
    BulkArchiveFormat.xlsx: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


class ArchivePrepareResponse(BaseModel):
    archive_ticket_id: str
    status: Literal["pending"]
    source_ticket_id: str
    archive_format: str
    retry_after: int
    retrieval_url: str | None = None
    expires_at: datetime | None = None


class ArchiveTicketStatus(BaseModel):
    archive_ticket_id: str
    status: Literal["pending", "partial", "ready", "error"]
    source_ticket_id: str | None = None
    archive_format: str | None = None
    speech_count: int | None = None
    expires_at: datetime
    error: str | None = None
