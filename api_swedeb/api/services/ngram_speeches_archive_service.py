"""N-gram speech archive service.

Creates normal speech archive tickets from a ready n-gram result ticket by
deriving the speech-id set from the stored n-gram artifact.
"""

from __future__ import annotations

import hashlib
import math
from typing import Any

import pandas as pd

from api_swedeb.api.services.result_store import ResultStore, TicketMeta, TicketStatus
from api_swedeb.core.configuration import ConfigValue
from api_swedeb.schemas.bulk_archive_schema import ArchivePrepareResponse, BulkArchiveFormat

_SPEECH_ARCHIVE_FORMATS: set[BulkArchiveFormat] = {
    BulkArchiveFormat.csv_gz,
    BulkArchiveFormat.jsonl_gz,
    BulkArchiveFormat.zip,
}


class EmptyNGramSpeechArchiveError(ValueError):
    """Raised when an n-gram ticket has no referenced speeches to archive."""


def extract_ordered_speech_ids(data: pd.DataFrame) -> list[str]:
    """Return ordered unique speech IDs from an n-gram artifact's documents column."""
    if "documents" not in data.columns:
        return []

    seen: set[str] = set()
    speech_ids: list[str] = []

    for value in data["documents"]:
        if value is None:
            continue
        if isinstance(value, float) and math.isnan(value):
            continue

        tokens: list[Any]
        if isinstance(value, str):
            tokens = value.split(",")
        elif isinstance(value, (list, tuple, set)):
            tokens = list(value)
        else:
            tokens = str(value).split(",")

        for token in tokens:
            speech_id = str(token).strip()
            if not speech_id or speech_id in seen:
                continue
            seen.add(speech_id)
            speech_ids.append(speech_id)

    return speech_ids


class NGramSpeechesArchiveService:
    """Prepare speech archive tickets from ready n-gram tickets."""

    def prepare(
        self,
        *,
        source_ticket_id: str,
        archive_format: BulkArchiveFormat,
        result_store: ResultStore,
    ) -> ArchivePrepareResponse:
        source_ticket: TicketMeta = result_store.require_ticket(source_ticket_id)
        if source_ticket.status == TicketStatus.PENDING:
            raise ValueError("Source ticket is not ready yet")
        if source_ticket.status == TicketStatus.PARTIAL:
            raise ValueError("Source ticket is not ready yet")
        if source_ticket.status == TicketStatus.ERROR:
            raise ValueError("Source ticket is in an error state")
        if archive_format not in _SPEECH_ARCHIVE_FORMATS:
            raise ValueError(f"Unsupported speech archive format: {archive_format.value}")

        data: pd.DataFrame = result_store.load_artifact(source_ticket_id)
        speech_ids: list[str] = extract_ordered_speech_ids(data)
        if not speech_ids:
            raise EmptyNGramSpeechArchiveError("Source ticket has no speeches to archive")

        manifest_meta: dict[str, Any] = self._build_manifest_meta(
            source_ticket=source_ticket,
            archive_format=archive_format,
            speech_ids=speech_ids,
        )
        archive_ticket: TicketMeta = result_store.create_ticket(
            query_meta=manifest_meta,
            source_ticket_id=source_ticket_id,
            archive_format=archive_format.value,
            speech_ids=speech_ids,
            manifest_meta=manifest_meta,
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

    def _build_manifest_meta(
        self,
        *,
        source_ticket: TicketMeta,
        archive_format: BulkArchiveFormat,
        speech_ids: list[str],
    ) -> dict[str, Any]:
        return {
            "source_ticket_id": source_ticket.ticket_id,
            "archive_format": archive_format.value,
            "speech_count": len(speech_ids),
            "checksum": self._checksum(speech_ids),
            "source_query": source_ticket.query_meta,
        }

    def _checksum(self, speech_ids: list[str]) -> str:
        digest = hashlib.sha256()
        for speech_id in speech_ids:
            digest.update(speech_id.encode("utf-8"))
            digest.update(b"\n")
        return digest.hexdigest()
