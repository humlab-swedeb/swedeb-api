"""Archive ticket service — prepare, track, and execute bulk archive generation."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from functools import lru_cache
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
from api_swedeb.api.services.search_service import SearchService
from api_swedeb.api.services.ticketed_download_service import TicketedDownloadService
from api_swedeb.core.configuration import ConfigValue
from api_swedeb.schemas.bulk_archive_schema import (
    ArchivePrepareResponse,
    ArchiveTicketStatus,
    BulkArchiveFormat,
)

# ---------------------------------------------------------------------------
# Per-worker singleton helpers (Celery workers only)
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _get_worker_search_service() -> SearchService:
    from api_swedeb.api.services.corpus_loader import CorpusLoader  # pylint: disable=import-outside-toplevel

    return SearchService(CorpusLoader())


@lru_cache(maxsize=1)
def _get_worker_result_store() -> ResultStore:
    store = ResultStore.from_config()
    store.startup_sync()
    return store


# ---------------------------------------------------------------------------
# Celery task (module-level so Celery can discover it)
# ---------------------------------------------------------------------------


def execute_archive_task(archive_ticket_id: str) -> dict:
    """Execute an archive generation task in a Celery worker process.

    Registered as a Celery task by the celery_tasks module at import time.
    """
    search_service: SearchService = _get_worker_search_service()
    result_store: ResultStore = _get_worker_result_store()
    result_store.adopt_ticket(archive_ticket_id)

    _service = ArchiveTicketService()
    _service.execute_archive_task(
        archive_ticket_id=archive_ticket_id,
        result_store=result_store,
        search_service=search_service,
    )
    ticket: TicketMeta = result_store.require_ticket(archive_ticket_id)
    if ticket.status == TicketStatus.ERROR:
        raise RuntimeError(ticket.error or f"Archive ticket {archive_ticket_id} failed")
    if ticket.status != TicketStatus.READY:
        raise RuntimeError(f"Archive ticket {archive_ticket_id} did not reach ready state")

    return {"archive_ticket_id": archive_ticket_id, "artifact_bytes": ticket.artifact_bytes}


class ArchiveTicketService:
    def prepare(
        self,
        *,
        source_ticket_id: str,
        archive_format: BulkArchiveFormat,
        result_store: ResultStore,
    ) -> ArchivePrepareResponse:
        """Validate the source ticket and create an archive ticket.

        Raises ResultStoreNotFound if the source ticket is missing.
        Raises ValueError if the source ticket is not ready.
        """
        source_ticket: TicketMeta = result_store.require_ticket(source_ticket_id)
        if source_ticket.status == TicketStatus.PENDING:
            raise ValueError("Source ticket is not ready yet")
        if source_ticket.status == TicketStatus.ERROR:
            raise ValueError("Source ticket is in an error state")
        if source_ticket.speech_ids is None:
            raise ValueError("Source ticket has no speech IDs")

        query_meta: dict[str, Any] = {
            "source_ticket_id": source_ticket_id,
            "archive_format": archive_format.value,
            "speech_count": len(source_ticket.speech_ids),
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
        )

    def execute_archive_task(
        self,
        *,
        archive_ticket_id: str,
        result_store: ResultStore,
        search_service: SearchService,
    ) -> None:
        """Generate the archive artifact and mark the ticket ready or failed."""
        logger.info(f"Starting execute_archive_task for archive ticket {archive_ticket_id}")
        try:
            archive_ticket: TicketMeta = result_store.require_ticket(archive_ticket_id)
            source_ticket_id: str | None = archive_ticket.source_ticket_id
            archive_format_str: str | None = archive_ticket.archive_format

            if source_ticket_id is None:
                raise ValueError("Archive ticket has no source_ticket_id")
            if archive_format_str is None:
                raise ValueError("Archive ticket has no archive_format")

            archive_format = BulkArchiveFormat(archive_format_str)
            source_ticket: TicketMeta = result_store.require_ticket(source_ticket_id)
            if source_ticket.speech_ids is None:
                raise ValueError("Source ticket has no speech IDs")

            speech_ids: list[str] = source_ticket.speech_ids
            dest_path: Path = result_store.archive_artifact_path(archive_ticket_id, archive_format_str)
            manifest_meta: dict = self._build_manifest(archive_ticket, source_ticket)

            TicketedDownloadService.for_format(archive_format).write(
                speech_ids=speech_ids,
                search_service=search_service,
                dest_path=dest_path,
                manifest_meta=manifest_meta,
            )

            result_store.store_archive_ready(
                archive_ticket_id,
                artifact_path=dest_path,
                manifest_meta=manifest_meta,
                total_hits=len(speech_ids),
            )
            logger.info(f"Archive ticket {archive_ticket_id} ready ({len(speech_ids)} speeches)")
        except ResultStoreCapacityError:
            logger.warning(f"Result store capacity error for archive ticket {archive_ticket_id}")
            return
        except ResultStoreNotFound:
            logger.warning(f"Result store not found for archive ticket {archive_ticket_id}")
            return
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception(f"Error executing archive ticket {archive_ticket_id}: {exc}")
            result_store.store_error(archive_ticket_id, message="Failed to generate archive")

    def get_status(self, archive_ticket_id: str, result_store: ResultStore) -> ArchiveTicketStatus:
        ticket: TicketMeta = result_store.require_ticket(archive_ticket_id)
        return self._status_model(ticket)

    def _status_model(self, ticket: TicketMeta) -> ArchiveTicketStatus:
        return ArchiveTicketStatus(
            archive_ticket_id=ticket.ticket_id,
            status=ticket.status.value,
            source_ticket_id=ticket.source_ticket_id,
            archive_format=ticket.archive_format,
            speech_count=ticket.total_hits,
            expires_at=ticket.expires_at,
            error=ticket.error,
        )

    def _build_manifest(self, archive_ticket: TicketMeta, source_ticket: TicketMeta) -> dict:
        return {
            "archive_ticket_id": archive_ticket.ticket_id,
            "source_ticket_id": archive_ticket.source_ticket_id,
            "archive_format": archive_ticket.archive_format,
            "speech_count": len(source_ticket.speech_ids or []),
            "generated_at": datetime.now(UTC).isoformat(),
            "corpus_version": os.environ.get("CORPUS_VERSION", "unknown"),
            "source_query": source_ticket.query_meta,
        }
